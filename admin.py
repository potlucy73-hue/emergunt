"""
Admin/Founder dashboard with analytics, user management, and system overview.
"""

import aiosqlite
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class AdminService:
    """Admin dashboard service with analytics."""
    
    def __init__(self, db_path: str = "extractions.db"):
        """Initialize admin service."""
        self.db_path = db_path
    
    async def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get complete dashboard statistics."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            # User Statistics
            async with conn.execute("SELECT COUNT(*) as count FROM users") as cursor:
                total_users = (await cursor.fetchone())["count"]
            
            async with conn.execute(
                "SELECT COUNT(*) as count FROM users WHERE subscription_status = 'active'"
            ) as cursor:
                active_subscribers = (await cursor.fetchone())["count"]
            
            async with conn.execute(
                "SELECT COUNT(*) as count FROM users WHERE subscription_status = 'trial'"
            ) as cursor:
                trial_users = (await cursor.fetchone())["count"]
            
            async with conn.execute(
                "SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = DATE('now')"
            ) as cursor:
                new_users_today = (await cursor.fetchone())["count"]
            
            # Extraction Statistics
            async with conn.execute("SELECT COUNT(*) as count FROM jobs") as cursor:
                total_jobs = (await cursor.fetchone())["count"]
            
            async with conn.execute(
                "SELECT COUNT(*) as count FROM jobs WHERE status = 'completed'"
            ) as cursor:
                completed_jobs = (await cursor.fetchone())["count"]
            
            async with conn.execute("SELECT COUNT(*) as count FROM carriers") as cursor:
                total_extractions = (await cursor.fetchone())["count"]
            
            # Revenue Statistics
            async with conn.execute(
                "SELECT SUM(amount) as total FROM subscriptions WHERE status = 'active'"
            ) as cursor:
                row = await cursor.fetchone()
                monthly_revenue = row["total"] if row["total"] else 0
            
            # Recent Activity
            async with conn.execute("""
                SELECT action, COUNT(*) as count 
                FROM activity_logs 
                WHERE DATE(created_at) >= DATE('now', '-7 days')
                GROUP BY action
            """) as cursor:
                recent_activity = {row["action"]: row["count"] for row in await cursor.fetchall()}
            
            # User Growth (last 30 days)
            async with conn.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM users
                WHERE DATE(created_at) >= DATE('now', '-30 days')
                GROUP BY DATE(created_at)
                ORDER BY date
            """) as cursor:
                user_growth = [dict(row) for row in await cursor.fetchall()]
            
            return {
                "users": {
                    "total": total_users,
                    "active_subscribers": active_subscribers,
                    "trial_users": trial_users,
                    "new_today": new_users_today
                },
                "extractions": {
                    "total_jobs": total_jobs,
                    "completed_jobs": completed_jobs,
                    "total_extractions": total_extractions
                },
                "revenue": {
                    "monthly_recurring": monthly_revenue,
                    "estimated_annual": monthly_revenue * 12
                },
                "activity": recent_activity,
                "growth": user_growth
            }
    
    async def get_all_users(
        self,
        page: int = 1,
        per_page: int = 50,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated list of all users."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            offset = (page - 1) * per_page
            
            # Build query
            query = "SELECT id, email, full_name, role, subscription_status, created_at, last_login FROM users WHERE 1=1"
            params = []
            
            if search:
                query += " AND (email LIKE ? OR full_name LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([per_page, offset])
            
            async with conn.execute(query, params) as cursor:
                users = [dict(row) for row in await cursor.fetchall()]
            
            # Get total count
            count_query = "SELECT COUNT(*) as count FROM users WHERE 1=1"
            if search:
                count_query += " AND (email LIKE ? OR full_name LIKE ?)"
            
            async with conn.execute(count_query, params[:-2] if search else []) as cursor:
                total = (await cursor.fetchone())["count"]
            
            return {
                "users": users,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                }
            }
    
    async def get_user_details(self, user_id: int) -> Dict[str, Any]:
        """Get detailed user information."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            # Get user
            async with conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,)
            ) as cursor:
                user = dict(await cursor.fetchone())
                user.pop("password_hash", None)
            
            # Get user's jobs
            async with conn.execute(
                "SELECT COUNT(*) as count FROM jobs WHERE job_id IN (SELECT job_id FROM carriers WHERE job_id IN (SELECT job_id FROM jobs))"
            ) as cursor:
                # Simplified: get user's extraction count
                async with conn.execute(
                    "SELECT COUNT(*) as count FROM carriers",
                    (user_id,)
                ) as cursor2:
                    extraction_count = (await cursor2.fetchone())["count"]
            
            # Get recent activity
            async with conn.execute(
                "SELECT * FROM activity_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
                (user_id,)
            ) as cursor:
                recent_activity = [dict(row) for row in await cursor.fetchall()]
            
            return {
                "user": user,
                "statistics": {
                    "extractions": extraction_count
                },
                "recent_activity": recent_activity
            }
    
    async def get_extraction_history(
        self,
        page: int = 1,
        per_page: int = 50
    ) -> Dict[str, Any]:
        """Get all extraction jobs."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            
            offset = (page - 1) * per_page
            
            async with conn.execute("""
                SELECT j.*, 
                       (SELECT COUNT(*) FROM carriers WHERE job_id = j.job_id) as carrier_count
                FROM jobs j
                ORDER BY j.created_at DESC
                LIMIT ? OFFSET ?
            """, (per_page, offset)) as cursor:
                jobs = [dict(row) for row in await cursor.fetchall()]
            
            async with conn.execute("SELECT COUNT(*) as count FROM jobs") as cursor:
                total = (await cursor.fetchone())["count"]
            
            return {
                "jobs": jobs,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page
                }
            }

