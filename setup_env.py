"""
Quick setup script to configure environment variables.
"""

import os

# GitHub Configuration
GITHUB_CONFIG = {
    "GITHUB_TOKEN": "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",
    "GITHUB_REPO": "potlucy73-hue/csa",
    "GITHUB_MC_LIST_FILE": "mc_list.txt",
    "GITHUB_BRANCH": "main"
}

# Default Configuration
DEFAULT_CONFIG = {
    "DATABASE_PATH": "extractions.db",
    "LOG_FILE": "extraction_logs.txt",
    "LOG_LEVEL": "INFO",
    "OUTPUT_DIR": "output",
    "API_HOST": "0.0.0.0",
    "API_PORT": "8000",
    "REQUESTS_PER_MINUTE": "10",
    "MAX_RETRIES": "3",
    "REQUEST_TIMEOUT": "30",
    "JWT_SECRET_KEY": "change-this-secret-key-in-production",
    "TRIAL_DAYS": "7",
    "SUBSCRIPTION_PRICE_MONTHLY": "29.99"
}

def setup_env_file():
    """Create or update .env file with configuration."""
    env_file = ".env"
    
    # Read existing .env if exists
    existing_config = {}
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    existing_config[key] = value
    
    # Merge configurations
    config = {**DEFAULT_CONFIG, **GITHUB_CONFIG, **existing_config}
    
    # Write .env file
    with open(env_file, 'w') as f:
        f.write("# FMCSA Extraction Tool Configuration\n\n")
        f.write("# GitHub Integration\n")
        for key, value in GITHUB_CONFIG.items():
            f.write(f"{key}={value}\n")
        
        f.write("\n# Application Settings\n")
        for key, value in DEFAULT_CONFIG.items():
            if key not in GITHUB_CONFIG:
                f.write(f"{key}={value}\n")
        
        f.write("\n# Optional - Add these for full SaaS features:\n")
        f.write("# CLOUDFLARE_TURNSTILE_SITE_KEY=your_site_key\n")
        f.write("# CLOUDFLARE_TURNSTILE_SECRET_KEY=your_secret_key\n")
        f.write("# STRIPE_PUBLISHABLE_KEY=pk_...\n")
        f.write("# STRIPE_SECRET_KEY=sk_...\n")
        f.write("# FOUNDER_EMAIL=founder@fmcsa.com\n")
    
    print("✅ .env file configured successfully!")
    print(f"✅ GitHub Repo: {GITHUB_CONFIG['GITHUB_REPO']}")
    print(f"✅ MC List File: {GITHUB_CONFIG['GITHUB_MC_LIST_FILE']}")
    print("\n📝 Next steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Test connection: python test_complete.py")
    print("3. Run application: python api.py")

if __name__ == "__main__":
    setup_env_file()

