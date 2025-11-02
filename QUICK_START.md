# 🚀 Quick Start Guide - FMCSA Extraction Tool

## ✅ Setup Complete - Ready to Use!

Aapka GitHub integration configure ho gaya hai:
- **GitHub Repo**: `potlucy73-hue/csa`
- **MC List File**: `mc_list.txt`
- **Token**: Configured ✅

## 📋 Installation Steps

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Environment

`.env` file me aapka GitHub token already add hai. Agar aur configuration chahiye to:

```env
GITHUB_TOKEN=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
GITHUB_REPO=potlucy73-hue/csa
GITHUB_MC_LIST_FILE=mc_list.txt
GITHUB_BRANCH=main
```

### 3. Test Connection

```bash
python test_complete.py
```

### 4. Run Application

**Option A: Web UI (Recommended)**
```bash
python api.py
```
Phir browser me kholo: `http://localhost:8000`

**Option B: Command Line**
```bash
python main.py
```

**Option C: API Only**
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

## 🎯 Usage

### Web UI Se:
1. Browser me `http://localhost:8000` kholo
2. "GitHub Repository" tab me jao
3. Repo name auto-filled hoga: `potlucy73-hue/csa`
4. "Check Repository" click karo
5. "Start Extraction" click karo
6. Progress dekho aur results download karo

### GitHub Actions Se (Automated):
1. GitHub repo me `mc_list.txt` file me MC numbers dalo
2. Commit aur push karo
3. GitHub Actions automatically extraction run karega
4. Results `output/` folder me save honge

### API Se:
```bash
curl -X POST "http://localhost:8000/extract-from-github?repo=potlucy73-hue/csa"
```

## 🔐 Authentication & Payments (Optional - For SaaS)

Agar aap SaaS platform banana chahte ho:

1. **Cloudflare Turnstile Setup:**
   - Cloudflare account banao
   - Turnstile site create karo
   - Site key aur secret key `.env` me dalo

2. **Stripe Setup:**
   - Stripe account banao
   - API keys `.env` me dalo
   - Webhook configure karo

3. **Authentication:**
   - Signup/Login page: `/static/auth.html`
   - Protected endpoints: `/api/auth/*`

4. **Admin Dashboard:**
   - Founder email: `.env` me `FOUNDER_EMAIL` set karo
   - Dashboard: `/api/admin/dashboard`

## 📊 Features Available

✅ GitHub repo se MC list read  
✅ Automated extraction  
✅ Web UI with progress tracking  
✅ CSV aur JSON output  
✅ Failed extractions tracking  
✅ Job history  
✅ **NEW**: Authentication system  
✅ **NEW**: Payment/Trial system  
✅ **NEW**: Admin dashboard  
✅ **NEW**: Cloudflare bot protection

## 🧪 Testing

Complete test suite run karo:
```bash
python test_complete.py
```

Individual tests:
```bash
python test_github.py  # GitHub integration test
```

## 📁 File Structure

```
FMCSA/
├── api.py              # Main API (with auth endpoints)
├── api_auth.py          # Authentication endpoints
├── auth.py              # Auth service
├── payments.py          # Payment service
├── admin.py             # Admin dashboard
├── github_integration.py # GitHub API
├── static/              # Web frontend
│   ├── index.html      # Main UI
│   ├── auth.html       # Login/Signup
│   ├── style.css       # Styles
│   └── app.js          # Frontend JS
├── test_complete.py     # Test suite
└── DEPLOYMENT.md        # Deployment guide
```

## ⚠️ Important Notes

1. **GitHub Token**: Private rakho, kisi ko share mat karo
2. **.env file**: Git me commit mat karo
3. **Production**: `DEPLOYMENT.md` dekho deployment ke liye
4. **Security**: JWT secret key change karo production me

## 🆘 Troubleshooting

**GitHub connection fail:**
- Token check karo
- Repo name verify karo
- `mc_list.txt` file exist karta hai ya nahi

**Import errors:**
```bash
pip install -r requirements.txt
```

**Playwright issues:**
```bash
playwright install chromium
playwright install-deps chromium
```

## 🎉 Ready to Use!

Sab kuch configure ho gaya hai. Ab bas run karo aur use karo!

```bash
python api.py
```

Happy Extracting! 🚛📊

