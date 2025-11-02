"""
GitHub Actions runner script for FMCSA extraction.
Reads MC list from repository and runs extraction.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Configure logging
log_file = os.getenv("LOG_FILE", "extraction_logs.txt")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

try:
    from github_integration import GitHubIntegration
    from main import process_mc_numbers
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure all Python files are in the repository")
    sys.exit(1)


async def main():
    """Main runner function for GitHub Actions."""
    logger.info("="*60)
    logger.info("Starting FMCSA extraction from GitHub repository...")
    logger.info("="*60)
    
    # Initialize GitHub integration
    github = GitHubIntegration()
    
    # Get repository info from environment (set by GitHub Actions)
    repo = os.getenv("GITHUB_REPO")
    file_path = os.getenv("GITHUB_MC_LIST_FILE", "mc_list.txt")
    branch = os.getenv("GITHUB_BRANCH") or os.getenv("GITHUB_REF_NAME") or "main"
    
    # If repo not set, try to get from GITHUB_REPOSITORY
    if not repo:
        github_repo = os.getenv("GITHUB_REPOSITORY")
        if github_repo:
            repo = github_repo
            logger.info(f"Using GITHUB_REPOSITORY: {repo}")
        else:
            logger.error("GitHub repository not specified in environment variables")
            logger.error("Set GITHUB_REPO or ensure GITHUB_REPOSITORY is available")
            sys.exit(1)
    
    logger.info(f"Repository: {repo}")
    logger.info(f"File: {file_path}")
    logger.info(f"Branch: {branch}")
    logger.info(f"Token configured: {'Yes' if github.github_token else 'No'}")
    
    try:
        # Read MC list from GitHub
        logger.info(f"Reading MC list from {repo}/{file_path} (branch: {branch})")
        mc_numbers = await github.read_mc_list_from_repo(
            repo=repo,
            file_path=file_path,
            branch=branch
        )
        
        if not mc_numbers:
            logger.warning("No MC numbers found in repository file")
            logger.warning("Please check that mc_list.txt exists and contains MC numbers")
            sys.exit(0)
        
        logger.info(f"Found {len(mc_numbers)} MC numbers to process")
        logger.info(f"First 5 MC numbers: {mc_numbers[:5]}")
        
        # Run extraction
        logger.info("Starting extraction process...")
        job_id = await process_mc_numbers(mc_numbers)
        
        logger.info("="*60)
        logger.info(f"Extraction completed successfully!")
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Results saved in output/ directory")
        logger.info("="*60)
        
    except Exception as e:
        logger.error("="*60)
        logger.error(f"Error in GitHub runner: {e}")
        logger.error("="*60)
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Extraction interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

