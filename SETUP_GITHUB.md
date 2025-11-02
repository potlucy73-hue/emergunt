# GitHub Integration Setup Guide

## Quick Start - GitHub Integration

### Step 1: GitHub Repository Setup

1. **Create a GitHub repository** (or use existing one)
2. **Create `mc_list.txt` file** in repository root
3. **Add MC numbers** (one per line or comma-separated):
   ```
   123456
   789012
   345678
   ```
4. **Commit and push** to repository

### Step 2: Get GitHub Personal Access Token

1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token (classic)"**
3. Give it a name (e.g., "FMCSA Extraction")
4. Select scopes:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `read:repo` (Read repository contents)
5. Click **"Generate token"**
6. **Copy the token** (you'll only see it once!)

### Step 3: Configure Environment

1. **Copy `.env.example` to `.env`**:
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file**:
   ```env
   # GitHub Integration
   GITHUB_TOKEN=your_copied_token_here
   GITHUB_REPO=your-username/your-repo-name
   GITHUB_MC_LIST_FILE=mc_list.txt
   GITHUB_BRANCH=main
   ```

### Step 4: Setup GitHub Actions (Optional but Recommended)

1. **Copy workflow file to your repository**:
   - The workflow file is already created: `.github/workflows/fmcsa-extraction.yml`
   - If you're using this in your own repo, copy this file there

2. **Add GitHub Secret** (for GitHub Actions):
   - Go to: Repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `GITHUB_TOKEN`
   - Value: Your GitHub personal access token
   - Click "Add secret"

3. **Enable GitHub Actions**:
   - Go to: Repository → Actions tab
   - Workflow will trigger automatically when `mc_list.txt` is updated

## Usage Methods

### Method 1: Web UI (Easiest)
```bash
# Start server
python api.py

# Open browser
http://localhost:8000
```

1. Click "GitHub Repository" tab
2. Enter repo name: `username/repo-name`
3. Click "Check Repository"
4. Click "Start Extraction"

### Method 2: GitHub Actions (Automated)
1. Edit `mc_list.txt` in your GitHub repo
2. Commit and push
3. GitHub Actions automatically runs extraction
4. Results saved in `output/` directory
5. Download from Actions artifacts

### Method 3: API Call
```bash
curl -X POST "http://localhost:8000/extract-from-github?repo=username/repo-name&file_path=mc_list.txt&branch=main"
```

### Method 4: Command Line (Local)
```bash
# Set environment variables
export GITHUB_TOKEN=your_token
export GITHUB_REPO=username/repo-name

# Run extraction
python main.py
# Select option 2: Load from GitHub
```

## Troubleshooting

### "GitHub authentication failed"
- Check your `GITHUB_TOKEN` in `.env` file
- Make sure token has `repo` scope
- Token might be expired - generate a new one

### "File not found in repository"
- Check repository name format: `owner/repo` (no `https://github.com/`)
- Verify `mc_list.txt` exists in repo root
- Check branch name (default is `main`)
- Make sure file is committed and pushed

### "Rate limit exceeded"
- GitHub API has rate limits
- Wait 1 hour or use authenticated requests
- Check rate limit: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit`

### GitHub Actions not running
- Check Actions tab for errors
- Verify workflow file exists: `.github/workflows/fmcsa-extraction.yml`
- Check if Actions are enabled for your repository
- Verify `GITHUB_TOKEN` secret is set

## Example Repository Structure

```
your-repo/
├── mc_list.txt          # MC numbers here
├── .github/
│   └── workflows/
│       └── fmcsa-extraction.yml
├── output/              # Results appear here (after Actions run)
│   ├── extracted_carriers_*.csv
│   └── extracted_carriers_*.json
└── README.md
```

## Security Notes

⚠️ **Important:**
- Never commit `.env` file to GitHub (it contains your token)
- Add `.env` to `.gitignore`
- Use GitHub Secrets for Actions (not hardcoded tokens)
- Rotate tokens periodically

## Next Steps

1. ✅ Repository setup complete
2. ✅ GitHub token configured
3. ✅ Environment variables set
4. 🚀 Ready to extract!

Run `python api.py` and open `http://localhost:8000` to start!

