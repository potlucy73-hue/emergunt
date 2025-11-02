# GitHub Actions Setup Guide

## ✅ Complete Setup Instructions

### Step 1: Copy Files to GitHub Repo

Apne GitHub repo (`potlucy73-hue/csa`) me ye files add karein:

**Required Python Files:**
1. `github_integration.py` - GitHub API integration
2. `github_runner.py` - GitHub Actions runner script
3. `main.py` - Core extraction logic
4. `database.py` - Database operations
5. `fmcsa_scraper.py` - FMCSA scraper
6. `data_processor.py` - Data processing
7. `requirements.txt` - Python dependencies

**Workflow File:**
1. `.github/workflows/fmcsa-extraction.yml` - GitHub Actions workflow

### Step 2: Setup GitHub Secrets

1. GitHub repo me jao: **Settings → Secrets and variables → Actions**
2. Ye secrets add karein (agar nahi hain to):

**GITHUB_TOKEN:**
- Name: `GITHUB_TOKEN`
- Value: `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`

**Ya use default GITHUB_TOKEN** (automatically available in Actions)

### Step 3: Test Workflow

**Option 1: Manual Trigger**
1. GitHub repo me jao
2. **Actions** tab click karo
3. **FMCSA Data Extraction** workflow select karo
4. **Run workflow** button click karo
5. **Run workflow** confirm karo

**Option 2: Auto Trigger**
1. `mc_list.txt` file update karo
2. Commit aur push karo
3. Workflow automatically run hogi

### Step 4: Check Results

1. **Actions** tab me workflow status dekho
2. Job complete hone ke baad:
   - **Artifacts** section me results download karein
   - Ya `output/` folder me check karein (agar commit hua ho)

## 📁 Required File Structure in Repo

```
potlucy73-hue/csa/
├── mc_list.txt                    # MC numbers list (already exists)
├── github_integration.py          # GitHub API integration
├── github_runner.py                # Runner script
├── main.py                         # Core extraction
├── database.py                     # Database
├── fmcsa_scraper.py                # Scraper
├── data_processor.py               # Data processor
├── requirements.txt                 # Dependencies
├── .github/
│   └── workflows/
│       └── fmcsa-extraction.yml    # GitHub Actions workflow
└── output/                         # Results folder (created automatically)
```

## 🔧 How It Works

1. **Trigger**: `mc_list.txt` update ya manual trigger
2. **Workflow Starts**: GitHub Actions runner start hota hai
3. **Reads MC List**: GitHub API se `mc_list.txt` read karta hai
4. **Extraction**: Har MC number ke liye FMCSA se data extract karta hai
5. **Saves Results**: `output/` folder me CSV aur JSON save karta hai
6. **Commits Results**: Results ko automatically commit kar deta hai (optional)

## 🎯 Testing

### Local Test:
```bash
# Test GitHub integration
python github_runner.py
```

### GitHub Actions Test:
1. `mc_list.txt` me kuch MC numbers dalo
2. Commit aur push karo
3. Actions tab me workflow status dekho

## 📊 Viewing Results

### Option 1: Download Artifacts
1. Actions tab → Completed workflow
2. Artifacts section
3. Download ZIP file

### Option 2: Check Repository
1. `output/` folder check karo
2. CSV aur JSON files dekho

### Option 3: Dashboard (If deployed)
1. Web UI open karo
2. History tab me jobs dekho
3. Results download karo

## ⚠️ Important Notes

1. **GitHub Token**: Actions me automatically available hota hai (`secrets.GITHUB_TOKEN`)
2. **Timeout**: Workflow 60 minutes me complete honi chahiye
3. **Rate Limiting**: FMCSA se 10 requests per minute
4. **Logs**: `extraction_logs.txt` me detailed logs

## 🚨 Troubleshooting

### Workflow Fails:
- Check Actions logs for errors
- Verify all Python files are in repo
- Check GitHub token permissions

### No MC Numbers Found:
- Verify `mc_list.txt` exists
- Check file format (one MC per line)
- Verify branch name (default: `main`)

### Extraction Timeout:
- Reduce MC numbers in batch
- Increase timeout in workflow
- Check FMCSA website status

## 📝 Example mc_list.txt Format

```
720604
720605
720606
720607
720608
```

One MC number per line, no commas, no headers.

## 🎉 Success Indicators

- ✅ Workflow completes without errors
- ✅ Artifacts available for download
- ✅ Results in `output/` folder
- ✅ CSV files with extracted data
- ✅ `extraction_logs.txt` shows success messages

---

**Ready to run!** Bas files GitHub repo me add karo aur workflow trigger karo! 🚀

