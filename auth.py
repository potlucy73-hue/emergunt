"""
Authentication system with JWT tokens, user management, and Cloudflare verification.
"""

import os
import jwt  # PyJWT package
import bcrypt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr
from fastapi import HTTPException, status
import aiosqlite
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "change-this-secret-key-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

# Cloudflare Turnstile
CLOUDFLARE_SECRET = os.getenv("CLOUDFLARE_TURNSTILE_SECRET_KEY")
CLOUDFLARE_SITE_KEY = os.getenv("CLOUDFLARE_TURNSTILE_SITE_KEY")

# Founder/Admin emails
FOUNDER_EMAIL = os.getenv("FOUNDER_EMAIL", "founder@fmcsa.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@fmcsa.com")


class UserCreate(BaseModel):
    """User registration model."""
    email: EmailStr
    password: str
    full_name: str
    turnstile_token: Optional[str] = None


class UserLogin(BaseModel):
    """User login model."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class AuthService:
    """Authentication and user management service."""
    
    def __init__(self, db_path: str = "extractions.db"):
        """Initialize auth service."""
        self.db_path = db_path
        self.init_auth_db()
    
    def init_auth_db(self):
        """Initialize authentication database tables."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                subscription_status TEXT DEFAULT 'trial',
                subscription_start_date TEXT,
                subscription_end_date TEXT,
                stripe_customer_id TEXT,
                created_at TEXT NOT NULL,
                last_login TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Activity logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Authentication database initialized")
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash."""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    async def verify_cloudflare_turnstile(self, token: str) -> bool:
        """Verify Cloudflare Turnstile token."""
        if not CLOUDFLARE_SECRET:
            logger.warning("Cloudflare secret not configured, skipping verification")
            return True  # Allow if not configured
        
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    data={
                        "secret": CLOUDFLARE_SECRET,
                        "response": token
                    }
                )
                result = response.json()
                return result.get("success", False)
        except Exception as e:
            logger.error(f"Cloudflare verification error: {e}")
            return False
    
    async def create_user(self, user_data: UserCreate) -> Dict[str, Any]:
        """
        Create new user account.
        
        Args:
            user_data: User creation data
            
        Returns:
            Created user dictionary
        """
        # Verify Cloudflare Turnstile
        if not await self.verify_cloudflare_turnstile(user_data.turnstile_token or ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cloudflare verification failed"
            )
        
        # Check if user exists
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT id FROM users WHERE email = ?",
                (user_data.email,)
            ) as cursor:
                if await cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already registered"
                    )
            
            # Determine role
            role = "founder" if user_data.email == FOUNDER_EMAIL else "user"
            
            # Calculate trial end date
            trial_end = datetime.now() + timedelta(days=int(os.getenv("TRIAL_DAYS", "7")))
            
            # Hash password
            password_hash = self.hash_password(user_data.password)
            
            # Insert user
            created_at = datetime.now().isoformat()
            async with conn.execute("""
                INSERT INTO users (
                    email, password_hash, full_name, role, subscription_status,
                    subscription_start_date, subscription_end_date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_data.email,
                password_hash,
                user_data.full_name,
                role,
                "trial",
                created_at,
                trial_end.isoformat(),
                created_at
            )) as cursor:
                user_id = cursor.lastrowid
            
            await conn.commit()
            
            # Get created user
            async with conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                user_dict = dict(row) if row else {}
                user_dict.pop("password_hash", None)
                
                logger.info(f"User created: {user_data.email} (ID: {user_id})")
                return user_dict
    
    async def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user and return user data.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            User dictionary if authenticated, None otherwise
        """
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM users WHERE email = ? AND is_active = 1",
                (email,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                
                user = dict(row)
                
                # Verify password
                if not self.verify_password(password, user["password_hash"]):
                    return None
                
                # Update last login
                await conn.execute(
                    "UPDATE users SET last_login = ? WHERE id = ?",
                    (datetime.now().isoformat(), user["id"])
                )
                await conn.commit()
                
                # Remove password hash from response
                user.pop("password_hash", None)
                
                logger.info(f"User authenticated: {email}")
                return user
    
    def create_access_token(self, user: Dict[str, Any]) -> str:
        """
        Create JWT access token.
        
        Args:
            user: User dictionary
            
        Returns:
            JWT token string
        """
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE)
        payload = {
            "sub": str(user["id"]),
            "email": user["email"],
            "role": user.get("role", "user"),
            "exp": expire
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return token
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
        """
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    user = dict(row)
                    user.pop("password_hash", None)
                    return user
                return None
    
    async def log_activity(self, user_id: Optional[int], action: str, details: str = "", ip_address: str = ""):
        """Log user activity."""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    INSERT INTO activity_logs (user_id, action, details, ip_address, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, action, details, ip_address, datetime.now().isoformat()))
                await conn.commit()
        except Exception as e:
            logger.error(f"Error logging activity: {e}")
    
    async def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics (for admin dashboard)."""
        async with aiosqlite.connect(self.db_path) as conn:
            # Total users
            async with conn.execute("SELECT COUNT(*) as count FROM users") as cursor:
                total_users = (await cursor.fetchone())["count"]
            
            # Active subscriptions
            async with conn.execute(
                "SELECT COUNT(*) as count FROM users WHERE subscription_status = 'active'"
            ) as cursor:
                active_subscribers = (await cursor.fetchone())["count"]
            
            # Trial users
            async with conn.execute(
                "SELECT COUNT(*) as count FROM users WHERE subscription_status = 'trial'"
            ) as cursor:
                trial_users = (await cursor.fetchone())["count"]
            
            # New users today
            today = datetime.now().date().isoformat()
            async with conn.execute(
                "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = ?",
                (today,)
            ) as cursor:
                new_today = (await cursor.fetchone())["count"]
            
            return {
                "total_users": total_users,
                "active_subscribers": active_subscribers,
                "trial_users": trial_users,
                "new_users_today": new_today,
                "total_revenue": 0  # Will be calculated from Stripe
            }

