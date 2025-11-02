"""
SQLite database operations for storing extraction history and carrier data.
Handles job tracking, carrier records, and extraction metadata.
"""

import sqlite3
import aiosqlite
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class Database:
    """Database manager for FMCSA extraction data."""
    
    def __init__(self, db_path: str = "extractions.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Jobs table - tracks extraction jobs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                total_mc_numbers INTEGER DEFAULT 0,
                processed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                error_message TEXT
            )
        """)
        
        # Carriers table - stores extracted carrier data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS carriers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                mc_number TEXT,
                dot_number TEXT,
                company_name TEXT,
                authority_status TEXT,
                authority_type TEXT,
                insurance_status TEXT,
                insurance_expiry TEXT,
                safety_rating TEXT,
                violations_12mo INTEGER DEFAULT 0,
                accidents_12mo INTEGER DEFAULT 0,
                authority_date TEXT,
                email TEXT,
                phone TEXT,
                state TEXT,
                safety_score REAL,
                risk_level TEXT,
                extracted_date TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            )
        """)
        
        # Failed extractions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failed_extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                mc_number TEXT,
                error_reason TEXT,
                retry_count INTEGER DEFAULT 0,
                failed_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    async def create_job(self, job_id: str, total_mc_numbers: int) -> bool:
        """
        Create a new extraction job.
        
        Args:
            job_id: Unique job identifier
            total_mc_numbers: Total number of MC numbers to process
            
        Returns:
            True if successful
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    INSERT INTO jobs (job_id, status, total_mc_numbers, processed_count, 
                                    failed_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (job_id, "processing", total_mc_numbers, 0, 0, 
                      datetime.now().isoformat()))
                await conn.commit()
                logger.info(f"Created job {job_id} with {total_mc_numbers} MC numbers")
                return True
        except Exception as e:
            logger.error(f"Error creating job: {e}")
            return False
    
    async def update_job_status(self, job_id: str, status: str, 
                               processed: Optional[int] = None,
                               failed: Optional[int] = None,
                               error_message: Optional[str] = None):
        """
        Update job status and progress.
        
        Args:
            job_id: Job identifier
            status: New status (processing, completed, failed)
            processed: Number of successfully processed MC numbers
            failed: Number of failed extractions
            error_message: Error message if job failed
        """
        try:
            updates = ["status = ?"]
            params = [status]
            
            if processed is not None:
                updates.append("processed_count = ?")
                params.append(processed)
            
            if failed is not None:
                updates.append("failed_count = ?")
                params.append(failed)
            
            if error_message:
                updates.append("error_message = ?")
                params.append(error_message)
            
            if status in ["completed", "failed"]:
                updates.append("completed_at = ?")
                params.append(datetime.now().isoformat())
            
            params.append(job_id)
            
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute(
                    f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?",
                    params
                )
                await conn.commit()
                logger.debug(f"Updated job {job_id} status to {status}")
        except Exception as e:
            logger.error(f"Error updating job status: {e}")
    
    async def save_carrier(self, job_id: str, carrier_data: Dict[str, Any]) -> bool:
        """
        Save extracted carrier data to database.
        
        Args:
            job_id: Job identifier
            carrier_data: Dictionary containing carrier information
            
        Returns:
            True if successful
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    INSERT INTO carriers (
                        job_id, mc_number, dot_number, company_name, authority_status,
                        authority_type, insurance_status, insurance_expiry, safety_rating,
                        violations_12mo, accidents_12mo, authority_date, email, phone,
                        state, safety_score, risk_level, extracted_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    carrier_data.get("mc_number"),
                    carrier_data.get("dot_number"),
                    carrier_data.get("company_name"),
                    carrier_data.get("authority_status"),
                    carrier_data.get("authority_type"),
                    carrier_data.get("insurance_status"),
                    carrier_data.get("insurance_expiry"),
                    carrier_data.get("safety_rating"),
                    carrier_data.get("violations_12mo", 0),
                    carrier_data.get("accidents_12mo", 0),
                    carrier_data.get("authority_date"),
                    carrier_data.get("email"),
                    carrier_data.get("phone"),
                    carrier_data.get("state"),
                    carrier_data.get("safety_score"),
                    carrier_data.get("risk_level"),
                    carrier_data.get("extracted_date", datetime.now().isoformat())
                ))
                await conn.commit()
                logger.debug(f"Saved carrier {carrier_data.get('mc_number')} for job {job_id}")
                return True
        except Exception as e:
            logger.error(f"Error saving carrier: {e}")
            return False
    
    async def save_failed_extraction(self, job_id: str, mc_number: str, 
                                    error_reason: str, retry_count: int = 0):
        """
        Save failed extraction record.
        
        Args:
            job_id: Job identifier
            mc_number: MC number that failed
            error_reason: Reason for failure
            retry_count: Number of retry attempts
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    INSERT INTO failed_extractions (job_id, mc_number, error_reason, 
                                                   retry_count, failed_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (job_id, mc_number, error_reason, retry_count, 
                      datetime.now().isoformat()))
                await conn.commit()
                logger.debug(f"Saved failed extraction for MC {mc_number}: {error_reason}")
        except Exception as e:
            logger.error(f"Error saving failed extraction: {e}")
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status and progress.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dictionary with job status information or None if not found
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("""
                    SELECT * FROM jobs WHERE job_id = ?
                """, (job_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
                    return None
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return None
    
    async def get_job_carriers(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all carriers extracted for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            List of carrier dictionaries
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("""
                    SELECT * FROM carriers WHERE job_id = ?
                    ORDER BY id
                """, (job_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting job carriers: {e}")
            return []
    
    async def get_job_failed_extractions(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Get all failed extractions for a job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            List of failed extraction dictionaries
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("""
                    SELECT * FROM failed_extractions WHERE job_id = ?
                    ORDER BY id
                """, (job_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting failed extractions: {e}")
            return []
    
    async def get_all_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all extraction jobs (for history).
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List of job dictionaries
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("""
                    SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?
                """, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting all jobs: {e}")
            return []

