"""Test GitHub integration"""
import asyncio
import os
from dotenv import load_dotenv
from github_integration import GitHubIntegration

load_dotenv()

async def test():
    gh = GitHubIntegration()
    print(f"GitHub Repo: {gh.github_repo}")
    print(f"MC List File: {gh.mc_list_file}")
    print(f"Branch: {gh.branch}")
    print(f"Token configured: {'Yes' if gh.github_token else 'No'}")
    
    try:
        mc_numbers = await gh.read_mc_list_from_repo()
        print(f"\n✅ Success! Found {len(mc_numbers)} MC numbers")
        print(f"First 10 MC numbers: {mc_numbers[:10]}")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test())

