"""
FastAPI REST API endpoints for FMCSA extraction tool.
Provides programmatic access to extraction functionality.
"""

import os
import sys
import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query, status
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import logging
import aiofiles

from database import Database
from fmcsa_scraper import FMCSAScraper
from data_processor import DataProcessor
from main import ExtractionJob
from github_integration import GitHubIntegration

# Import auth services (after logger is defined)
AUTH_ENABLED = False
auth_service = None
payment_service = None
admin_service = None

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv("LOG_FILE", "extraction_logs.txt"), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Import auth services (after logger is defined)
try:
    from fastapi import Depends, Request as FastAPIRequest
    from fastapi.security import HTTPBearer
    from auth import AuthService, UserCreate, UserLogin, Token
    from payments import PaymentService
    from admin import AdminService
    AUTH_ENABLED = True
    auth_service = AuthService()
    payment_service = PaymentService()
    admin_service = AdminService()
    security = HTTPBearer()
except Exception as e:
    logger.warning(f"Auth services not available: {e}")
    AUTH_ENABLED = False

# Initialize FastAPI app
app = FastAPI(
    title="FMCSA Carrier Data Extraction API",
    description="REST API for bulk FMCSA carrier data extraction",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Initialize database
db = Database(os.getenv("DATABASE_PATH", "extractions.db"))

# Store active jobs (in production, use Redis or similar)
active_jobs: Dict[str, asyncio.Task] = {}


class BulkExtractResponse(BaseModel):
    """Response model for bulk extraction request."""
    job_id: str
    total_mc_numbers: int
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    status: str
    total_mc_numbers: int
    processed_count: int
    failed_count: int
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class HistoryItem(BaseModel):
    """Model for extraction history item."""
    job_id: str
    status: str
    total_mc_numbers: int
    processed_count: int
    failed_count: int
    created_at: str
    completed_at: Optional[str] = None


def generate_job_id() -> str:
    """Generate a unique job ID."""
    return f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


async def run_extraction_job(job_id: str, mc_numbers: List[str]):
    """Background task to run extraction job."""
    try:
        job = ExtractionJob(job_id, mc_numbers)
        await job.run()
        # Remove from active jobs when completed
        if job_id in active_jobs:
            del active_jobs[job_id]
    except Exception as e:
        logger.error(f"Error in extraction job {job_id}: {e}")
        await db.update_job_status(job_id, "failed", error_message=str(e))
        if job_id in active_jobs:
            del active_jobs[job_id]


@app.post("/extract-bulk", response_model=BulkExtractResponse)
async def extract_bulk(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Upload CSV file with MC numbers and start bulk extraction.
    
    Returns job_id for tracking progress.
    """
    try:
        # Read uploaded file
        content = await file.read()
        input_data = content.decode('utf-8')
        
        # Extract MC numbers
        processor = DataProcessor()
        mc_numbers = processor.extract_mc_numbers_from_input(input_data)
        
        if not mc_numbers:
            raise HTTPException(
                status_code=400,
                detail="No valid MC numbers found in uploaded file"
            )
        
        # Generate job ID
        job_id = generate_job_id()
        
        # Start background job
        task = asyncio.create_task(run_extraction_job(job_id, mc_numbers))
        active_jobs[job_id] = task
        
        logger.info(f"Started extraction job {job_id} with {len(mc_numbers)} MC numbers")
        
        return BulkExtractResponse(
            job_id=job_id,
            total_mc_numbers=len(mc_numbers),
            status="processing",
            message=f"Extraction job started. Use /extract-status/{job_id} to check progress."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in extract_bulk: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/extract-from-github", response_model=BulkExtractResponse)
async def extract_from_github(
    background_tasks: BackgroundTasks,
    repo: Optional[str] = Query(None),
    file_path: Optional[str] = Query(None),
    branch: Optional[str] = Query(None)
):
    """
    Extract MC numbers from GitHub repository and start bulk extraction.
    
    Args:
        repo: GitHub repository in format 'owner/repo' (uses GITHUB_REPO env var if not provided)
        file_path: Path to MC list file in repo (default: mc_list.txt)
        branch: Branch name (default: main)
    
    Returns:
        Job ID for tracking progress
    """
    try:
        # Initialize GitHub integration
        github = GitHubIntegration()
        
        # Use provided parameters or environment defaults
        repo = repo or github.github_repo
        file_path = file_path or github.mc_list_file
        branch = branch or github.branch
        
        if not repo:
            raise HTTPException(
                status_code=400,
                detail="GitHub repository not specified. Provide 'repo' parameter or set GITHUB_REPO environment variable."
            )
        
        # Read MC list from GitHub
        logger.info(f"Reading MC list from GitHub repo: {repo}/{file_path}")
        mc_numbers = await github.read_mc_list_from_repo(
            repo=repo,
            file_path=file_path,
            branch=branch
        )
        
        if not mc_numbers:
            raise HTTPException(
                status_code=404,
                detail=f"No MC numbers found in {repo}/{file_path}"
            )
        
        # Generate job ID
        job_id = generate_job_id()
        
        # Start background job
        task = asyncio.create_task(run_extraction_job(job_id, mc_numbers))
        active_jobs[job_id] = task
        
        logger.info(f"Started GitHub extraction job {job_id} with {len(mc_numbers)} MC numbers")
        
        return BulkExtractResponse(
            job_id=job_id,
            total_mc_numbers=len(mc_numbers),
            status="processing",
            message=f"Extraction job started from GitHub repo {repo}. Use /extract-status/{job_id} to check progress."
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in extract_from_github: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/github/check-repo")
async def check_github_repo(
    repo: Optional[str] = Query(None),
    file_path: Optional[str] = Query(None),
    branch: Optional[str] = Query(None)
):
    """
    Check if GitHub repository and MC list file exist.
    
    Returns:
        Repository information and file existence status
    """
    try:
        github = GitHubIntegration()
        
        repo = repo or github.github_repo
        file_path = file_path or github.mc_list_file
        branch = branch or github.branch
        
        if not repo:
            raise HTTPException(
                status_code=400,
                detail="GitHub repository not specified"
            )
        
        # Check file existence
        file_exists = await github.check_file_exists(repo, file_path, branch)
        
        # Get repo info
        try:
            repo_info = await github.get_repo_info(repo)
            repo_name = repo_info.get("full_name", repo)
            repo_url = repo_info.get("html_url", f"https://github.com/{repo}")
        except:
            repo_name = repo
            repo_url = f"https://github.com/{repo}"
        
        return {
            "repo": repo_name,
            "repo_url": repo_url,
            "file_path": file_path,
            "branch": branch,
            "file_exists": file_exists,
            "status": "ok" if file_exists else "file_not_found"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking GitHub repo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/extract-status/{job_id}", response_model=JobStatusResponse)
async def get_extract_status(job_id: str):
    """
    Get extraction job status and progress.
    """
    job_status = await db.get_job_status(job_id)
    
    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return JobStatusResponse(
        job_id=job_status["job_id"],
        status=job_status["status"],
        total_mc_numbers=job_status["total_mc_numbers"],
        processed_count=job_status["processed_count"],
        failed_count=job_status["failed_count"],
        created_at=job_status["created_at"],
        completed_at=job_status.get("completed_at"),
        error_message=job_status.get("error_message")
    )


@app.get("/extract-results/{job_id}")
async def get_extract_results(job_id: str, format: str = "csv"):
    """
    Download extraction results as CSV or JSON.
    
    Args:
        job_id: Job identifier
        format: Output format ('csv' or 'json')
    """
    # Verify job exists
    job_status = await db.get_job_status(job_id)
    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    # Get carrier data
    carriers = await db.get_job_carriers(job_id)
    
    if not carriers:
        raise HTTPException(
            status_code=404,
            detail=f"No results found for job {job_id}"
        )
    
    # Process data for output
    processor = DataProcessor()
    formatted_data = [processor.format_for_output(carrier) for carrier in carriers]
    
    # Create output directory if needed
    output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
    output_dir.mkdir(exist_ok=True)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if format.lower() == "json":
        import json
        filename = output_dir / f"extracted_carriers_{job_id}_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)
        
        return FileResponse(
            str(filename),
            media_type="application/json",
            filename=f"extracted_carriers_{job_id}.json"
        )
    
    else:  # CSV
        import csv
        filename = output_dir / f"extracted_carriers_{job_id}_{timestamp}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            if formatted_data:
                writer = csv.DictWriter(f, fieldnames=formatted_data[0].keys())
                writer.writeheader()
                writer.writerows(formatted_data)
        
        return FileResponse(
            str(filename),
            media_type="text/csv",
            filename=f"extracted_carriers_{job_id}.csv"
        )


@app.get("/extract-failed/{job_id}")
async def get_failed_extractions(job_id: str):
    """
    Download failed extractions for a job as CSV.
    """
    # Verify job exists
    job_status = await db.get_job_status(job_id)
    if not job_status:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    # Get failed extractions
    failed = await db.get_job_failed_extractions(job_id)
    
    if not failed:
        raise HTTPException(
            status_code=404,
            detail=f"No failed extractions found for job {job_id}"
        )
    
    # Create CSV
    output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = output_dir / f"failed_extractions_{job_id}_{timestamp}.csv"
    
    import csv
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["MC Number", "Error Reason", "Retry Count"])
        writer.writeheader()
        writer.writerows([
            {
                "MC Number": fe["mc_number"],
                "Error Reason": fe["error_reason"],
                "Retry Count": fe["retry_count"]
            }
            for fe in failed
        ])
    
    return FileResponse(
        str(filename),
        media_type="text/csv",
        filename=f"failed_extractions_{job_id}.csv"
    )


@app.get("/history", response_model=List[HistoryItem])
async def get_history(limit: int = 100):
    """
    Get extraction job history.
    
    Args:
        limit: Maximum number of jobs to return (default: 100)
    """
    jobs = await db.get_all_jobs(limit=limit)
    
    return [
        HistoryItem(
            job_id=job["job_id"],
            status=job["status"],
            total_mc_numbers=job["total_mc_numbers"],
            processed_count=job["processed_count"],
            failed_count=job["failed_count"],
            created_at=job["created_at"],
            completed_at=job.get("completed_at")
        )
        for job in jobs
    ]


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve frontend HTML."""
    static_path = Path(__file__).parent / "static" / "main.html"
    if static_path.exists():
        with open(static_path, 'r', encoding='utf-8') as f:
            return f.read()
    # Fallback to index.html
    static_path = Path(__file__).parent / "static" / "index.html"
    if static_path.exists():
        with open(static_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>FMCSA API</h1><p>Frontend not found</p>"

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Serve login page."""
    static_path = Path(__file__).parent / "static" / "login.html"
    if static_path.exists():
        with open(static_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Login</h1><p>Login page not found</p>"


@app.get("/api-info")
async def api_info():
    """API information endpoint."""
    return {
        "name": "FMCSA Carrier Data Extraction API",
        "version": "1.0.0",
        "endpoints": {
            "POST /extract-bulk": "Upload CSV and start extraction",
            "POST /extract-from-github": "Extract from GitHub repository",
            "GET /extract-status/{job_id}": "Check extraction progress",
            "GET /extract-results/{job_id}": "Download results (CSV/JSON)",
            "GET /extract-failed/{job_id}": "Download failed extractions",
            "GET /github/check-repo": "Check GitHub repository",
            "GET /history": "View extraction history",
            "GET /docs": "API documentation (Swagger)"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ==================== AUTHENTICATION ENDPOINTS ====================
if AUTH_ENABLED:
    async def get_current_user_async(request: FastAPIRequest):
        """Get current user from token in header."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None  # Allow public access if not authenticated
        token = auth_header.split(" ")[1]
        try:
            payload = auth_service.verify_token(token)
            user_id = int(payload["sub"])
            user = await auth_service.get_user_by_id(user_id)
            return user
        except:
            return None
    
    def require_auth(user: dict = Depends(get_current_user_async)):
        """Require authentication."""
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        return user
    
    def require_admin(user: dict = Depends(require_auth)):
        """Require admin/founder role."""
        if user.get("role") not in ["admin", "founder"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return user
    
    @app.post("/api/auth/register")
    async def register(user_data: UserCreate, request: FastAPIRequest):
        """Register new user."""
        user = await auth_service.create_user(user_data)
        token = auth_service.create_access_token(user)
        client_ip = request.client.host if request.client else ""
        await auth_service.log_activity(user["id"], "user_registered", f"User registered: {user_data.email}", client_ip)
        return {"access_token": token, "token_type": "bearer", "user": user}
    
    @app.post("/api/auth/login")
    async def login(login_data: UserLogin, request: FastAPIRequest):
        """Login user."""
        user = await auth_service.authenticate_user(login_data.email, login_data.password)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
        if payment_service and not payment_service.can_access_feature(user):
            user["subscription_status"] = "expired"
        token = auth_service.create_access_token(user)
        client_ip = request.client.host if request.client else ""
        await auth_service.log_activity(user["id"], "user_login", "User logged in", client_ip)
        return {"access_token": token, "token_type": "bearer", "user": user}
    
    @app.get("/api/auth/me")
    async def get_current_user_info(user: dict = Depends(require_auth)):
        """Get current user information."""
        if payment_service and not payment_service.can_access_feature(user):
            user["subscription_status"] = "expired"
        return user
    
    @app.get("/api/admin/dashboard")
    async def admin_dashboard(admin: dict = Depends(require_admin)):
        """Get admin dashboard statistics."""
        return await admin_service.get_dashboard_stats()
    
    @app.get("/api/admin/users")
    async def admin_get_users(page: int = 1, per_page: int = 50, search: Optional[str] = None, admin: dict = Depends(require_admin)):
        """Get all users (admin only)."""
        return await admin_service.get_all_users(page, per_page, search)
    
    @app.get("/api/admin/user/{user_id}")
    async def admin_get_user(user_id: int, admin: dict = Depends(require_admin)):
        """Get user details (admin only)."""
        return await admin_service.get_user_details(user_id)


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    
    uvicorn.run(app, host=host, port=port)

