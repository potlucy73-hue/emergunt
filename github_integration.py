"""
GitHub integration module for reading MC numbers from GitHub repository.
Supports reading from GitHub repo files and triggering via GitHub Actions.
"""

import os
import base64
import logging
from typing import List, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GitHubIntegration:
    """GitHub API integration for reading MC numbers from repository."""
    
    def __init__(self):
        """Initialize GitHub integration with API credentials."""
        self.github_token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_API_KEY")
        self.github_repo = os.getenv("GITHUB_REPO")  # Format: owner/repo
        self.mc_list_file = os.getenv("GITHUB_MC_LIST_FILE", "mc_list.txt")
        self.branch = os.getenv("GITHUB_BRANCH", "main")
        
        if not self.github_token:
            logger.warning("GitHub token not found. GitHub integration will not work.")
        
        if not self.github_repo:
            logger.warning("GitHub repo not configured. Set GITHUB_REPO environment variable.")
    
    def _get_headers(self) -> dict:
        """Get GitHub API request headers."""
        if not self.github_token:
            return {"Accept": "application/vnd.github.v3+json"}
        
        return {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    async def read_mc_list_from_repo(
        self, 
        repo: Optional[str] = None,
        file_path: Optional[str] = None,
        branch: Optional[str] = None
    ) -> List[str]:
        """
        Read MC numbers from GitHub repository file.
        
        Args:
            repo: Repository in format 'owner/repo' (uses env var if not provided)
            file_path: Path to MC list file in repo (default: mc_list.txt)
            branch: Branch name (default: main)
            
        Returns:
            List of MC numbers
        """
        repo = repo or self.github_repo
        file_path = file_path or self.mc_list_file
        branch = branch or self.branch
        
        if not repo:
            raise ValueError("GitHub repository not specified. Set GITHUB_REPO or pass repo parameter.")
        
        try:
            # GitHub API endpoint for file content
            url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
            params = {"ref": branch} if branch else {}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    params=params
                )
                
                if response.status_code == 404:
                    raise FileNotFoundError(f"File {file_path} not found in repository {repo}")
                
                response.raise_for_status()
                data = response.json()
                
                # Decode base64 content
                if "content" in data:
                    content = base64.b64decode(data["content"]).decode('utf-8')
                else:
                    raise ValueError("Invalid response from GitHub API")
                
                # Parse MC numbers
                from data_processor import DataProcessor
                processor = DataProcessor()
                mc_numbers = processor.extract_mc_numbers_from_input(content)
                
                logger.info(f"Read {len(mc_numbers)} MC numbers from GitHub repo {repo}/{file_path}")
                return mc_numbers
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError("GitHub authentication failed. Check your GITHUB_TOKEN.")
            elif e.response.status_code == 403:
                raise ValueError("GitHub API rate limit exceeded or insufficient permissions.")
            else:
                raise ValueError(f"GitHub API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error reading MC list from GitHub: {e}")
            raise
    
    async def get_repo_info(self, repo: Optional[str] = None) -> dict:
        """
        Get repository information.
        
        Args:
            repo: Repository in format 'owner/repo'
            
        Returns:
            Repository information dictionary
        """
        repo = repo or self.github_repo
        
        if not repo:
            raise ValueError("GitHub repository not specified")
        
        try:
            url = f"https://api.github.com/repos/{repo}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting repo info: {e}")
            raise
    
    async def check_file_exists(
        self,
        repo: Optional[str] = None,
        file_path: Optional[str] = None,
        branch: Optional[str] = None
    ) -> bool:
        """
        Check if MC list file exists in repository.
        
        Args:
            repo: Repository in format 'owner/repo'
            file_path: Path to file
            branch: Branch name
            
        Returns:
            True if file exists, False otherwise
        """
        repo = repo or self.github_repo
        file_path = file_path or self.mc_list_file
        branch = branch or self.branch
        
        try:
            url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
            params = {"ref": branch} if branch else {}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    params=params
                )
                return response.status_code == 200
        except:
            return False

