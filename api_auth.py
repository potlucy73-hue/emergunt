"""
Enhanced API with authentication, payments, and admin dashboard endpoints.
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request, Header, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from typing import Optional
from datetime import datetime
import os
from dotenv import load_dotenv

from api import app, db
from auth import AuthService, UserCreate, UserLogin, Token
from payments import PaymentService
from admin import AdminService

load_dotenv()

# Initialize services
auth_service = AuthService()
payment_service = PaymentService()
admin_service = AdminService()

# Security
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user."""
    token = credentials.credentials
    payload = auth_service.verify_token(token)
    user_id = int(payload["sub"])
    return user_id


async def get_current_user_async(request: Request):
    """Get current user from token in header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    token = auth_header.split(" ")[1]
    payload = auth_service.verify_token(token)
    user_id = int(payload["sub"])
    
    # Get full user data
    user = await auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user


def require_admin(user: dict = Depends(get_current_user_async)):
    """Require admin/founder role."""
    if user.get("role") not in ["admin", "founder"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


def require_founder(user: dict = Depends(get_current_user_async)):
    """Require founder role."""
    if user.get("role") != "founder":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Founder access required"
        )
    return user


# Authentication Endpoints
@app.post("/api/auth/register", response_model=Token)
async def register(
    user_data: UserCreate,
    request: Request
):
    """Register new user."""
    # Create user
    user = await auth_service.create_user(user_data)
    
    # Create token
    token = auth_service.create_access_token(user)
    
    # Log activity
    client_ip = request.client.host if request.client else ""
    await auth_service.log_activity(
        user["id"],
        "user_registered",
        f"User registered: {user_data.email}",
        client_ip
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@app.post("/api/auth/login", response_model=Token)
async def login(
    login_data: UserLogin,
    request: Request
):
    """Login user."""
    user = await auth_service.authenticate_user(
        login_data.email,
        login_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check subscription status
    if not payment_service.can_access_feature(user):
        user["subscription_status"] = "expired"
    
    # Create token
    token = auth_service.create_access_token(user)
    
    # Log activity
    client_ip = request.client.host if request.client else ""
    await auth_service.log_activity(
        user["id"],
        "user_login",
        "User logged in",
        client_ip
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@app.get("/api/auth/me")
async def get_current_user_info(
    user: dict = Depends(get_current_user_async)
):
    """Get current user information."""
    # Check subscription status
    if not payment_service.can_access_feature(user):
        user["subscription_status"] = "expired"
    return user


# Payment Endpoints
@app.post("/api/payments/create-checkout")
async def create_checkout(
    user: dict = Depends(get_current_user_async)
):
    """Create Stripe checkout session."""
    session = await payment_service.create_checkout_session(
        user["id"],
        user.get("stripe_customer_id")
    )
    return session


@app.post("/api/payments/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature")
):
    """Handle Stripe webhooks."""
    body = await request.body()
    result = await payment_service.handle_webhook(body, stripe_signature)
    return result


@app.get("/api/payments/subscription-status")
async def subscription_status(
    user: dict = Depends(get_current_user_async)
):
    """Get user subscription status."""
    can_access = payment_service.can_access_feature(user)
    is_trial = payment_service.is_trial_active(user)
    
    return {
        "subscription_status": user.get("subscription_status", "trial"),
        "can_access": can_access,
        "is_trial": is_trial,
        "trial_days_left": (
            (datetime.fromisoformat(user["subscription_end_date"]) - datetime.now()).days
            if user.get("subscription_end_date") and is_trial else 0
        )
    }


# Admin/Founder Endpoints
@app.get("/api/admin/dashboard")
async def admin_dashboard(
    admin: dict = Depends(require_admin)
):
    """Get admin dashboard statistics."""
    stats = await admin_service.get_dashboard_stats()
    return stats


@app.get("/api/admin/users")
async def admin_get_users(
    page: int = 1,
    per_page: int = 50,
    search: Optional[str] = None,
    admin: dict = Depends(require_admin)
):
    """Get all users (admin only)."""
    users = await admin_service.get_all_users(page, per_page, search)
    return users


@app.get("/api/admin/user/{user_id}")
async def admin_get_user(
    user_id: int,
    admin: dict = Depends(require_admin)
):
    """Get user details (admin only)."""
    user_details = await admin_service.get_user_details(user_id)
    return user_details


@app.get("/api/admin/extractions")
async def admin_get_extractions(
    page: int = 1,
    per_page: int = 50,
    admin: dict = Depends(require_admin)
):
    """Get all extraction jobs (admin only)."""
    jobs = await admin_service.get_extraction_history(page, per_page)
    return jobs


# Protected extraction endpoints
@app.post("/api/extract-from-github")
async def extract_from_github_protected(
    repo: Optional[str] = None,
    file_path: Optional[str] = None,
    branch: Optional[str] = None,
    user: dict = Depends(get_current_user_async)
):
    """Extract from GitHub (requires authentication)."""
    # Check if user can access
    if not payment_service.can_access_feature(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subscription required. Please upgrade your plan."
        )
    
    # Use existing endpoint logic from api.py
    from api import extract_from_github
    return await extract_from_github(repo, file_path, branch)


@app.post("/api/extract-bulk")
async def extract_bulk_protected(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user_async)
):
    """Upload and extract (requires authentication)."""
    # Check subscription
    if not payment_service.can_access_feature(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Subscription required. Please upgrade your plan."
        )
    
    # Use existing endpoint
    from api import extract_bulk
    return await extract_bulk(file)


# Update root to serve frontend
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve frontend."""
    from pathlib import Path
    static_path = Path(__file__).parent / "static" / "index.html"
    if static_path.exists():
        with open(static_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>FMCSA API</h1><p>Frontend not found</p>"

