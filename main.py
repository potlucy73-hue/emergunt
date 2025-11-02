"""
Main CLI application for FMCSA carrier data extraction.
Handles bulk processing, job management, and output generation.
"""

import asyncio
import os
import sys
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import time

from database import Database
from fmcsa_scraper import FMCSAScraper
from data_processor import DataProcessor

# Load environment variables
load_dotenv()

# Configure logging
log_file = os.getenv("LOG_FILE", "extraction_logs.txt")
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class ExtractionJob:
    """Manages a single extraction job."""
    
    def __init__(self, job_id: str, mc_numbers: List[str]):
        """
        Initialize extraction job.
        
        Args:
            job_id: Unique job identifier
            mc_numbers: List of MC numbers to process
        """
        self.job_id = job_id
        self.mc_numbers = mc_numbers
        self.db = Database(os.getenv("DATABASE_PATH", "extractions.db"))
        self.scraper = None
        self.processor = DataProcessor()
        self.output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
        self.output_dir.mkdir(exist_ok=True)
        
        # Rate limiting configuration
        self.requests_per_minute = int(os.getenv("REQUESTS_PER_MINUTE", "10"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.request_timeout = int(os.getenv("REQUEST_TIMEOUT", "30"))
        
        # Track progress
        self.processed_count = 0
        self.failed_count = 0
        self.carriers_data = []
        self.failed_extractions = []
    
    async def run(self):
        """Execute the extraction job."""
        logger.info(f"Starting extraction job {self.job_id} with {len(self.mc_numbers)} MC numbers")
        
        # Create job in database
        await self.db.create_job(self.job_id, len(self.mc_numbers))
        
        # Initialize scraper
        use_api = bool(os.getenv("APIFY_API_KEY"))
        async with FMCSAScraper(use_api=use_api, timeout=self.request_timeout) as scraper:
            self.scraper = scraper
            
            # Process each MC number
            for idx, mc_number in enumerate(self.mc_numbers):
                await self._process_mc_number(mc_number)
                
                # Update progress
                await self.db.update_job_status(
                    self.job_id,
                    "processing",
                    processed=self.processed_count,
                    failed=self.failed_count
                )
                
                # Rate limiting - wait between requests
                if idx < len(self.mc_numbers) - 1:  # Don't wait after last item
                    delay = 60 / self.requests_per_minute
                    await asyncio.sleep(delay)
            
            # Mark job as completed
            await self.db.update_job_status(
                self.job_id,
                "completed",
                processed=self.processed_count,
                failed=self.failed_count
            )
            
            # Save outputs
            await self._save_outputs()
            
            logger.info(f"Job {self.job_id} completed: {self.processed_count} succeeded, {self.failed_count} failed")
    
    async def _process_mc_number(self, mc_number: str):
        """
        Process a single MC number with retry logic.
        
        Args:
            mc_number: MC number to process
        """
        retry_count = 0
        last_error = None
        
        while retry_count <= self.max_retries:
            try:
                # Extract data
                raw_data = await self.scraper.extract_carrier_data(mc_number)
                
                if raw_data is None:
                    raise Exception("No data returned from scraper")
                
                # Validate data
                if not self.processor.validate_carrier_data(raw_data):
                    raise Exception("Invalid carrier data returned")
                
                # Enrich data
                enriched_data = self.processor.enrich_carrier_data(raw_data)
                
                # Save to database
                await self.db.save_carrier(self.job_id, enriched_data)
                
                # Track success
                self.carriers_data.append(enriched_data)
                self.processed_count += 1
                
                logger.info(f"Successfully extracted MC {mc_number}")
                return
                
            except Exception as e:
                last_error = str(e)
                retry_count += 1
                
                if retry_count <= self.max_retries:
                    wait_time = retry_count * 2  # Exponential backoff
                    logger.warning(f"Retry {retry_count}/{self.max_retries} for MC {mc_number} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    # Max retries reached, record failure
                    error_reason = f"{last_error} (after {self.max_retries} retries)"
                    self.failed_extractions.append({
                        "mc_number": mc_number,
                        "error_reason": error_reason,
                        "retry_count": self.max_retries
                    })
                    await self.db.save_failed_extraction(
                        self.job_id, mc_number, error_reason, self.max_retries
                    )
                    self.failed_count += 1
                    logger.error(f"Failed to extract MC {mc_number}: {error_reason}")
    
    async def _save_outputs(self):
        """Save extraction results to CSV and JSON files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Prepare formatted data
        formatted_data = [self.processor.format_for_output(carrier) for carrier in self.carriers_data]
        
        # Save CSV
        csv_filename = self.output_dir / f"extracted_carriers_{timestamp}.csv"
        if formatted_data:
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=formatted_data[0].keys())
                writer.writeheader()
                writer.writerows(formatted_data)
            logger.info(f"Saved CSV output: {csv_filename}")
        
        # Save JSON
        json_filename = self.output_dir / f"extracted_carriers_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved JSON output: {json_filename}")
        
        # Save failed extractions
        if self.failed_extractions:
            failed_filename = self.output_dir / f"failed_extractions_{timestamp}.csv"
            with open(failed_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["MC Number", "Error Reason", "Retry Count"])
                writer.writeheader()
                writer.writerows([
                    {
                        "MC Number": fe["mc_number"],
                        "Error Reason": fe["error_reason"],
                        "Retry Count": fe["retry_count"]
                    }
                    for fe in self.failed_extractions
                ])
            logger.info(f"Saved failed extractions: {failed_filename}")


def generate_job_id() -> str:
    """Generate a unique job ID."""
    return f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{int(time.time() * 1000) % 10000}"


async def process_mc_numbers(mc_numbers: List[str]) -> str:
    """
    Process a list of MC numbers.
    
    Args:
        mc_numbers: List of MC numbers to process
        
    Returns:
        Job ID
    """
    job_id = generate_job_id()
    job = ExtractionJob(job_id, mc_numbers)
    await job.run()
    return job_id


def read_input_file(file_path: str) -> str:
    """
    Read input file and return content.
    
    Args:
        file_path: Path to input file
        
    Returns:
        File content as string
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def main():
    """Main CLI entry point."""
    print("=" * 60)
    print("FMCSA Carrier Data Extraction Tool")
    print("=" * 60)
    print()
    
    # Get input method
    print("Select input method:")
    print("1. Enter MC numbers manually (comma-separated)")
    print("2. Load from CSV file")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    input_data = ""
    
    if choice == "1":
        print("\nEnter MC numbers (comma-separated or one per line):")
        print("Press Enter twice when done, or type 'done' on a new line")
        lines = []
        while True:
            line = input()
            if line.lower() == "done" or (not line and lines):
                break
            if line:
                lines.append(line)
        input_data = "\n".join(lines)
        
    elif choice == "2":
        file_path = input("\nEnter CSV file path: ").strip().strip('"')
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            sys.exit(1)
        input_data = read_input_file(file_path)
        
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)
    
    # Process MC numbers
    processor = DataProcessor()
    mc_numbers = processor.extract_mc_numbers_from_input(input_data)
    
    if not mc_numbers:
        print("Error: No valid MC numbers found in input.")
        sys.exit(1)
    
    print(f"\nFound {len(mc_numbers)} unique MC numbers to process.")
    confirm = input("Proceed with extraction? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("Extraction cancelled.")
        sys.exit(0)
    
    print(f"\nStarting extraction... This may take a while for {len(mc_numbers)} carriers.")
    print("Progress will be logged to extraction_logs.txt\n")
    
    # Run extraction
    try:
        job_id = asyncio.run(process_mc_numbers(mc_numbers))
        print(f"\n✓ Extraction completed!")
        print(f"Job ID: {job_id}")
        print(f"Results saved to 'output/' directory")
        print(f"Check extraction_logs.txt for detailed logs")
        
    except KeyboardInterrupt:
        print("\n\nExtraction interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        print(f"\nError: {e}")
        print("Check extraction_logs.txt for details")
        sys.exit(1)


if __name__ == "__main__":
    main()

