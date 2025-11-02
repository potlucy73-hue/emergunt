# FMCSA Truck Carrier Data Extraction Tool

A production-ready Python tool for bulk extraction of FMCSA truck carrier data including company information, authority status, insurance details, safety ratings, and violation history.

## Features

- **Bulk MC Number Processing**: Upload CSV files or paste MC numbers for batch processing
- **Dual Extraction Methods**: Supports both Apify API and Playwright web scraping
- **Data Enrichment**: Auto-detects carrier status, calculates safety scores, flags high-risk carriers
- **Multiple Output Formats**: CSV and JSON exports with timestamps
- **REST API**: FastAPI endpoints for programmatic access
- **Progress Tracking**: Real-time job status monitoring
- **Error Handling**: Comprehensive retry mechanism and failed extraction tracking
- **Database Storage**: SQLite database for extraction history

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Installation

1. **Clone or download this repository**

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On Mac/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers** (required for web scraping):
   ```bash
   playwright install chromium
   ```

5. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` file and add your configuration:
   ```env
   # GitHub Integration (Required for GitHub features)
   GITHUB_TOKEN=your_github_personal_access_token
   GITHUB_REPO=your-username/your-repo-name
   GITHUB_MC_LIST_FILE=mc_list.txt
   GITHUB_BRANCH=main
   
   # Apify API (Optional, if using API method)
   APIFY_API_KEY=your_actual_api_key
   ```
   
   **How to get GitHub Token:**
   1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   2. Generate new token with `repo` scope
   3. Copy token and paste in `.env` file

### Usage

#### Command Line Interface

Run the main extraction script:
```bash
python main.py
```

The script will:
- Prompt for MC numbers (comma-separated or file path)
- Extract data from FMCSA
- Save results to `output/extracted_carriers_[timestamp].csv` and `.json`
- Save failed extractions to `output/failed_extractions.csv`

#### Web Frontend & REST API Server

Start the FastAPI server with web UI:
```bash
python api.py
```

Or using uvicorn directly:
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Then open your browser:
- **Web UI**: `http://localhost:8000` (Beautiful frontend interface)
- **API Docs**: `http://localhost:8000/docs` (Swagger documentation)
- **API Info**: `http://localhost:8000/api-info` (API information)

#### GitHub Repository Integration

**Option 1: Using Web UI**
1. Open `http://localhost:8000` in browser
2. Click "GitHub Repository" tab
3. Enter your repository name (e.g., `username/repo-name`)
4. Click "Check Repository" to verify
5. Click "Start Extraction" to begin

**Option 2: Using GitHub Actions**
1. Create a file `mc_list.txt` in your GitHub repository root
2. Paste your MC numbers (one per line or comma-separated)
3. Push to repository - GitHub Actions will automatically trigger
4. Or manually trigger from Actions tab → "FMCSA Data Extraction" → "Run workflow"

**Option 3: Using API**
```bash
curl -X POST "http://localhost:8000/extract-from-github?repo=username/repo-name&file_path=mc_list.txt&branch=main"
```

#### API Endpoints

- **POST /extract-bulk**: Upload CSV file with MC numbers
  ```bash
  curl -X POST "http://localhost:8000/extract-bulk" \
    -F "file=@mc_numbers.csv"
  ```

- **POST /extract-from-github**: Extract from GitHub repository
  ```bash
  curl -X POST "http://localhost:8000/extract-from-github?repo=username/repo-name&file_path=mc_list.txt&branch=main"
  ```

- **GET /github/check-repo**: Check if GitHub repository and file exist
  ```bash
  curl "http://localhost:8000/github/check-repo?repo=username/repo-name&file_path=mc_list.txt"
  ```

- **GET /extract-status/{job_id}**: Check extraction progress
  ```bash
  curl "http://localhost:8000/extract-status/job_20241202_123456"
  ```

- **GET /extract-results/{job_id}**: Download results (CSV or JSON)
  ```bash
  curl "http://localhost:8000/extract-results/job_20241202_123456?format=csv" -o results.csv
  curl "http://localhost:8000/extract-results/job_20241202_123456?format=json" -o results.json
  ```

- **GET /extract-failed/{job_id}**: Download failed extractions
  ```bash
  curl "http://localhost:8000/extract-failed/job_20241202_123456" -o failed.csv
  ```

- **GET /history**: View all past extractions
  ```bash
  curl "http://localhost:8000/history"
  ```

## Project Structure

```
FMCSA/
├── main.py                 # Core extraction logic and CLI
├── fmcsa_scraper.py        # FMCSA web scraping implementation
├── data_processor.py       # Data cleaning and enrichment
├── github_integration.py   # GitHub API integration
├── github_runner.py        # GitHub Actions runner script
├── api.py                  # FastAPI REST endpoints with web UI
├── database.py             # SQLite database operations
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── README.md               # This file
├── .github/
│   └── workflows/
│       └── fmcsa-extraction.yml  # GitHub Actions workflow
├── static/                 # Web frontend files
│   ├── index.html         # Frontend HTML
│   ├── style.css          # Frontend styles
│   └── app.js             # Frontend JavaScript
├── output/                # Generated output files
├── extraction_logs.txt    # Application logs
└── extractions.db         # SQLite database
```

## Input Format

### CSV File Format

Your input CSV should have at least one column containing MC numbers:

```csv
MC Number
123456
789012
345678
```

Or multiple columns (MC number will be auto-detected):

```csv
Company,MC,DOT
ABC Trucking,123456,12345
XYZ Logistics,789012,67890
```

## Output Format

### CSV Output Columns

1. MC#
2. DOT#
3. Company Name
4. Authority Status
5. Insurance Status
6. Insurance Expiry
7. Safety Score
8. Violations (12mo)
9. Accidents (12mo)
10. Phone
11. Email
12. State
13. Risk Level
14. Extracted Date

### Risk Levels

- **Low**: No violations or accidents
- **Medium**: 1-3 violations OR 1 accident
- **High**: >3 violations OR >1 accident OR both

## Configuration

All settings can be configured via `.env` file:

- `REQUESTS_PER_MINUTE`: Rate limiting (default: 10)
- `MAX_RETRIES`: Retry attempts for failed requests (default: 3)
- `REQUEST_TIMEOUT`: Timeout per request in seconds (default: 30)
- `LOG_LEVEL`: Logging verbosity (INFO, DEBUG, WARNING, ERROR)

## Error Handling

- Failed extractions are logged to `failed_extractions.csv` with reasons
- Automatic retry mechanism (up to 3 attempts)
- Rate limiting prevents FMCSA blocking
- Request timeout handling (30 seconds max per lookup)

## Logging

All operations are logged to `extraction_logs.txt` with timestamps:
- Extraction start/completion
- Errors and warnings
- API calls and responses
- Database operations

## Database

SQLite database (`extractions.db`) stores:
- Extraction job history
- Individual carrier records
- Extraction timestamps
- Job status and metadata

## Troubleshooting

### Playwright Installation Issues

If Playwright browsers fail to install:
```bash
playwright install --with-deps chromium
```

### Rate Limiting Issues

If you're getting blocked by FMCSA:
- Increase `REQUESTS_PER_MINUTE` delay in `.env`
- Add random delays between requests

### Memory Issues

For very large batches (>1000 MC numbers):
- Process in smaller chunks
- Use API method instead of scraping

## License

This tool is provided as-is for data extraction purposes. Ensure compliance with FMCSA website terms of service when using.

## Support

For issues or questions:
1. Check `extraction_logs.txt` for error details
2. Review `.env` configuration
3. Verify Python version (3.11+)
4. Ensure all dependencies are installed

