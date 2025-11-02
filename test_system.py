"""
Complete system test - GitHub integration, API endpoints, and frontend.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from github_integration import GitHubIntegration

load_dotenv()

async def test_github():
    """Test GitHub integration."""
    print("\n" + "="*60)
    print("TEST 1: GitHub Integration")
    print("="*60)
    
    gh = GitHubIntegration()
    print(f"Repo: {gh.github_repo}")
    print(f"File: {gh.mc_list_file}")
    print(f"Token: {'Configured' if gh.github_token else 'Missing'}")
    
    try:
        mc_numbers = await gh.read_mc_list_from_repo()
        print(f"\nSUCCESS: Found {len(mc_numbers)} MC numbers")
        if mc_numbers:
            print(f"Sample: {mc_numbers[:5]}")
        return True
    except Exception as e:
        print(f"\nFAILED: {e}")
        return False

async def test_api_endpoints():
    """Test API endpoints."""
    print("\n" + "="*60)
    print("TEST 2: API Endpoints")
    print("="*60)
    
    import httpx
    
    base_url = "http://localhost:8000"
    
    # Test health check
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("[OK] Health endpoint working")
            else:
                print("[FAIL] Health endpoint failed")
                return False
    except Exception as e:
        print(f"[SKIP] API server not running: {e}")
        print("  Start server with: python api.py")
        return False
    
    # Test GitHub check endpoint
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{base_url}/github/check-repo",
                params={"repo": "potlucy73-hue/csa", "file_path": "mc_list.txt"}
            )
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] GitHub check endpoint working")
                print(f"  Repo exists: {data.get('file_exists', False)}")
            else:
                print("[FAIL] GitHub check endpoint failed")
    except Exception as e:
        print(f"[WARN] GitHub check failed: {e}")
    
    return True

def test_imports():
    """Test all imports."""
    print("\n" + "="*60)
    print("TEST 3: Module Imports")
    print("="*60)
    
    modules = [
        ("api", "api"),
        ("auth", "auth"),
        ("payments", "payments"),
        ("admin", "admin"),
        ("github_integration", "github_integration"),
        ("database", "database"),
        ("fmcsa_scraper", "fmcsa_scraper"),
        ("data_processor", "data_processor"),
    ]
    
    all_ok = True
    for name, module in modules:
        try:
            __import__(module)
            print(f"[OK] {name}")
        except ImportError as e:
            print(f"[FAIL] {name}: {e}")
            all_ok = False
    
    return all_ok

def test_env():
    """Test environment configuration."""
    print("\n" + "="*60)
    print("TEST 4: Environment Configuration")
    print("="*60)
    
    required = ["GITHUB_TOKEN", "GITHUB_REPO"]
    optional = ["CLOUDFLARE_TURNSTILE_SITE_KEY", "STRIPE_SECRET_KEY", "JWT_SECRET_KEY"]
    
    all_ok = True
    for key in required:
        value = os.getenv(key)
        if value:
            masked = '*' * min(len(value), 20)
            print(f"[OK] {key}: {masked}")
        else:
            print(f"[FAIL] {key}: Missing (Required)")
            all_ok = False
    
    for key in optional:
        value = os.getenv(key)
        if value:
            print(f"[OK] {key}: Configured")
        else:
            print(f"[OPTIONAL] {key}: Not configured")
    
    return all_ok

async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("COMPLETE SYSTEM TEST")
    print("="*60)
    
    results = []
    
    # Test 1: Environment
    results.append(test_env())
    
    # Test 2: Imports
    results.append(test_imports())
    
    # Test 3: GitHub
    results.append(await test_github())
    
    # Test 4: API (optional - requires server running)
    results.append(await test_api_endpoints())
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Environment: {'PASS' if results[0] else 'FAIL'}")
    print(f"Imports: {'PASS' if results[1] else 'FAIL'}")
    print(f"GitHub: {'PASS' if results[2] else 'FAIL'}")
    print(f"API: {'PASS' if results[3] else 'SKIP'}")
    print(f"\nTotal: {sum(results)}/{len(results)} tests passed")
    
    if all(results[:3]):  # First 3 are critical
        print("\n[SUCCESS] System is ready!")
        print("\nNext steps:")
        print("1. Start server: python api.py")
        print("2. Open browser: http://localhost:8000")
        print("3. Test GitHub extraction from UI")
        return True
    else:
        print("\n[ERROR] Some critical tests failed. Please fix issues above.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

