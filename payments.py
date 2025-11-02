"""
Payment system with Stripe integration, trial management, and subscription handling.
"""

import os
import stripe
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import aiosqlite
import logging
import httpx

logger = logging.getLogger(__name__)

# Stripe Configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "7"))
SUBSCRIPTION_PRICE = float(os.getenv("SUBSCRIPTION_PRICE_MONTHLY", "29.99"))


class PaymentService:
    """Payment and subscription management service."""
    
    def __init__(self, db_path: str = "extractions.db"):
        """Initialize payment service."""
        self.db_path = db_path
        self.init_payments_db()
    
    def init_payments_db(self):
        """Initialize payments database tables."""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Subscriptions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                stripe_subscription_id TEXT UNIQUE,
                stripe_customer_id TEXT,
                status TEXT NOT NULL,
                plan_type TEXT DEFAULT 'monthly',
                amount REAL,
                currency TEXT DEFAULT 'USD',
                current_period_start TEXT,
                current_period_end TEXT,
                trial_start TEXT,
                trial_end TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Payments/Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                stripe_payment_intent_id TEXT UNIQUE,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                status TEXT NOT NULL,
                payment_method TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Payments database initialized")
    
    def is_trial_active(self, user: Dict[str, Any]) -> bool:
        """Check if user's trial is still active."""
        if user.get("subscription_status") != "trial":
            return False
        
        trial_end = user.get("subscription_end_date")
        if not trial_end:
            return False
        
        try:
            end_date = datetime.fromisoformat(trial_end)
            return datetime.now() < end_date
        except:
            return False
    
    def can_access_feature(self, user: Dict[str, Any]) -> bool:
        """Check if user can access premium features."""
        status = user.get("subscription_status", "trial")
        return status in ["active", "trial"] and (
            status == "active" or self.is_trial_active(user)
        )
    
    async def create_stripe_customer(self, user_id: int, email: str, name: str) -> str:
        """
        Create Stripe customer.
        
        Args:
            user_id: User ID
            email: User email
            name: User name
            
        Returns:
            Stripe customer ID
        """
        if not stripe.api_key:
            logger.warning("Stripe not configured")
            return ""
        
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"user_id": str(user_id)}
            )
            
            # Update user in database
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute(
                    "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                    (customer.id, user_id)
                )
                await conn.commit()
            
            logger.info(f"Stripe customer created: {customer.id} for user {user_id}")
            return customer.id
        except Exception as e:
            logger.error(f"Error creating Stripe customer: {e}")
            return ""
    
    async def create_checkout_session(
        self,
        user_id: int,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create Stripe checkout session for subscription.
        
        Args:
            user_id: User ID
            customer_id: Existing Stripe customer ID
            
        Returns:
            Checkout session dictionary
        """
        if not stripe.api_key:
            raise ValueError("Stripe not configured")
        
        # Get user details
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            ) as cursor:
                user = dict(await cursor.fetchone())
        
        # Create or get customer
        if not customer_id:
            customer_id = await self.create_stripe_customer(
                user_id, user["email"], user["full_name"]
            )
        
        try:
            # Create price ID if needed (in production, create in Stripe dashboard)
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': 'FMCSA Data Extraction - Monthly',
                            'description': 'Monthly subscription for FMCSA carrier data extraction'
                        },
                        'unit_amount': int(SUBSCRIPTION_PRICE * 100),  # Convert to cents
                        'recurring': {
                            'interval': 'month'
                        }
                    },
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f"{os.getenv('APP_URL', 'http://localhost:8000')}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{os.getenv('APP_URL', 'http://localhost:8000')}/payment/cancel",
                metadata={"user_id": str(user_id)}
            )
            
            return {
                "session_id": session.id,
                "url": session.url
            }
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            raise
    
    async def handle_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Handle Stripe webhook events.
        
        Args:
            payload: Webhook payload
            signature: Webhook signature
            
        Returns:
            Event processing result
        """
        if not STRIPE_WEBHOOK_SECRET:
            raise ValueError("Stripe webhook secret not configured")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, STRIPE_WEBHOOK_SECRET
            )
            
            # Handle different event types
            if event['type'] == 'checkout.session.completed':
                session = event['data']['object']
                user_id = int(session['metadata']['user_id'])
                await self.activate_subscription(user_id, session)
            
            elif event['type'] == 'customer.subscription.updated':
                subscription = event['data']['object']
                await self.update_subscription(subscription)
            
            elif event['type'] == 'customer.subscription.deleted':
                subscription = event['data']['object']
                await self.cancel_subscription(subscription['id'])
            
            return {"status": "success", "event": event['type']}
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            raise
    
    async def activate_subscription(self, user_id: int, session: Dict[str, Any]):
        """Activate user subscription after successful payment."""
        async with aiosqlite.connect(self.db_path) as conn:
            subscription_id = session.get('subscription')
            
            # Get subscription from Stripe
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                
                # Update user
                await conn.execute("""
                    UPDATE users 
                    SET subscription_status = 'active',
                        subscription_end_date = ?
                    WHERE id = ?
                """, (
                    datetime.fromtimestamp(subscription.current_period_end).isoformat(),
                    user_id
                ))
                
                # Save subscription
                await conn.execute("""
                    INSERT INTO subscriptions (
                        user_id, stripe_subscription_id, stripe_customer_id,
                        status, amount, currency, current_period_start,
                        current_period_end, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    subscription.id,
                    subscription.customer,
                    subscription.status,
                    subscription.items.data[0].price.unit_amount / 100,
                    subscription.currency.upper(),
                    datetime.fromtimestamp(subscription.current_period_start).isoformat(),
                    datetime.fromtimestamp(subscription.current_period_end).isoformat(),
                    datetime.now().isoformat()
                ))
                
                await conn.commit()
                logger.info(f"Subscription activated for user {user_id}")
    
    async def update_subscription(self, subscription: Dict[str, Any]):
        """Update subscription status."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
                UPDATE subscriptions 
                SET status = ?,
                    current_period_start = ?,
                    current_period_end = ?,
                    updated_at = ?
                WHERE stripe_subscription_id = ?
            """, (
                subscription['status'],
                datetime.fromtimestamp(subscription['current_period_start']).isoformat(),
                datetime.fromtimestamp(subscription['current_period_end']).isoformat(),
                datetime.now().isoformat(),
                subscription['id']
            ))
            await conn.commit()
    
    async def cancel_subscription(self, subscription_id: str):
        """Cancel subscription."""
        async with aiosqlite.connect(self.db_path) as conn:
            # Get user_id
            async with conn.execute(
                "SELECT user_id FROM subscriptions WHERE stripe_subscription_id = ?",
                (subscription_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    user_id = row[0]
                    
                    # Update user
                    await conn.execute("""
                        UPDATE users 
                        SET subscription_status = 'cancelled',
                            subscription_end_date = ?
                        WHERE id = ?
                    """, (datetime.now().isoformat(), user_id))
                    
                    await conn.commit()
                    logger.info(f"Subscription cancelled for user {user_id}")

