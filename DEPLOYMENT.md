# Complete Deployment Guide

## 🚀 Production Deployment

### Prerequisites
- Python 3.11+
- PostgreSQL or MySQL (for production database)
- Redis (for session management)
- Domain name with SSL
- Stripe account
- Cloudflare account

### Step 1: Environment Setup

1. **Create production `.env` file:**
```env
# GitHub
GITHUB_TOKEN=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
GITHUB_REPO=potlucy73-hue/csa
GITHUB_MC_LIST_FILE=mc_list.txt
GITHUB_BRANCH=main

# JWT (Generate strong secret: openssl rand -hex 32)
JWT_SECRET_KEY=your-super-secret-production-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Cloudflare Turnstile
CLOUDFLARE_TURNSTILE_SITE_KEY=your_site_key
CLOUDFLARE_TURNSTILE_SECRET_KEY=your_secret_key

# Stripe
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# App
APP_URL=https://yourdomain.com
API_HOST=0.0.0.0
API_PORT=8000

# Database (for production, use PostgreSQL)
DATABASE_URL=postgresql://user:pass@localhost/fmcsa

# Founder
FOUNDER_EMAIL=founder@fmcsa.com
```

### Step 2: Deploy to Cloud (VPS/Server)

#### Option A: Using Docker (Recommended)

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./output:/app/output
      - ./extractions.db:/app/extractions.db
    restart: unless-stopped
  
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped
```

#### Option B: Direct Deployment

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run with gunicorn (production WSGI server)
pip install gunicorn
gunicorn api:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Step 3: Nginx Configuration

**nginx.conf:**
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Step 4: Cloudflare Setup

1. **Add Turnstile site:**
   - Go to Cloudflare Dashboard → Turnstile
   - Create new site
   - Copy Site Key and Secret Key to `.env`

2. **Add to frontend:** (already in static/index.html)

### Step 5: Stripe Setup

1. **Create Stripe account**
2. **Get API keys** from Dashboard
3. **Set up webhook:**
   - Webhook URL: `https://yourdomain.com/api/payments/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
4. **Copy webhook secret** to `.env`

### Step 6: Testing

**Run test script:**
```bash
python test_github.py
```

**Test endpoints:**
```bash
# Health check
curl http://localhost:8000/health

# Check GitHub repo
curl "http://localhost:8000/github/check-repo?repo=potlucy73-hue/csa"
```

## 📊 Monitoring

### Setup Monitoring (Optional)

**Using Sentry (Error Tracking):**
```bash
pip install sentry-sdk[fastapi]
```

Add to `api.py`:
```python
import sentry_sdk
sentry_sdk.init(
    dsn="your-sentry-dsn",
    traces_sample_rate=1.0,
)
```

## 🔒 Security Checklist

- [ ] Change JWT_SECRET_KEY to strong random value
- [ ] Use HTTPS (SSL certificate)
- [ ] Enable Cloudflare Turnstile
- [ ] Set up rate limiting
- [ ] Use environment variables (never commit .env)
- [ ] Regular security updates
- [ ] Database backups
- [ ] Monitor logs

## 📈 Scaling

For high traffic:
1. Use PostgreSQL instead of SQLite
2. Add Redis for caching
3. Use load balancer
4. Deploy multiple instances
5. Use CDN for static files

