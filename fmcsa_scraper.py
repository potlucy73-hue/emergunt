"""
FMCSA data scraper using Playwright web scraping.
Falls back to Apify API if configured, otherwise uses web scraping.
"""

import os
import asyncio
import logging
import re
from typing import Dict, Optional, Any
from datetime import datetime
from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class FMCSAScraper:
    """FMCSA data extraction using web scraping or Apify API."""
    
    def __init__(self, use_api: bool = False, timeout: int = 30):
        """
        Initialize FMCSA scraper.
        
        Args:
            use_api: If True, use Apify API instead of scraping
            timeout: Request timeout in seconds
        """
        self.use_api = use_api and bool(os.getenv("APIFY_API_KEY"))
        self.timeout = timeout
        self.apify_api_key = os.getenv("APIFY_API_KEY")
        self.apify_actor_id = os.getenv("APIFY_FMCSA_ACTOR_ID", "fmcsa-scraper")
        self.base_url = "https://ai.fmcsa.dot.gov/SMS/Tools/CarrierSearch.aspx"
        self.playwright_instance = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        if not self.use_api:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if not self.use_api and hasattr(self, 'browser'):
            await self.browser.close()
            await self.playwright.stop()
    
    async def extract_carrier_data(self, mc_number: str) -> Optional[Dict[str, Any]]:
        """
        Extract carrier data for a given MC number.
        
        Args:
            mc_number: MC number to look up
            
        Returns:
            Dictionary with carrier data or None if extraction failed
        """
        if self.use_api:
            return await self._extract_via_api(mc_number)
        else:
            return await self._extract_via_scraping(mc_number)
    
    async def _extract_via_api(self, mc_number: str) -> Optional[Dict[str, Any]]:
        """
        Extract data using Apify API.
        
        Args:
            mc_number: MC number to look up
            
        Returns:
            Carrier data dictionary or None
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Apify API call (adjust endpoint based on actual Apify actor)
                response = await client.post(
                    f"https://api.apify.com/v2/acts/{self.apify_actor_id}/run-sync-get-dataset-items",
                    headers={
                        "Authorization": f"Bearer {self.apify_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={"mcNumber": mc_number}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        return self._parse_apify_response(data[0], mc_number)
                
                logger.warning(f"API extraction failed for MC {mc_number}")
                return None
        except Exception as e:
            logger.error(f"Error in API extraction for MC {mc_number}: {e}")
            return None
    
    async def _extract_via_scraping(self, mc_number: str) -> Optional[Dict[str, Any]]:
        """
        Extract data using Playwright web scraping.
        
        Args:
            mc_number: MC number to look up
            
        Returns:
            Carrier data dictionary or None
        """
        page = None
        try:
            page = await self.context.new_page()
            
            # Navigate to FMCSA carrier search page
            await page.goto(self.base_url, wait_until="networkidle", timeout=self.timeout * 1000)
            
            # Fill in MC number and search
            await page.fill("#txtMCNumber", mc_number)
            await page.click("#btnSearch")
            
            # Wait for results to load
            await page.wait_for_selector(".result-section, .error-message", timeout=self.timeout * 1000)
            
            # Check if results found
            error_element = await page.query_selector(".error-message")
            if error_element:
                error_text = await error_element.inner_text()
                if "not found" in error_text.lower() or "no results" in error_text.lower():
                    logger.warning(f"MC {mc_number} not found")
                    return None
            
            # Extract data from result page
            carrier_data = await self._parse_scraped_page(page, mc_number)
            
            await page.close()
            return carrier_data
            
        except PlaywrightTimeout:
            logger.error(f"Timeout extracting MC {mc_number}")
            if page:
                await page.close()
            return None
        except Exception as e:
            logger.error(f"Error scraping MC {mc_number}: {e}")
            if page:
                await page.close()
            return None
    
    async def _parse_scraped_page(self, page: Page, mc_number: str) -> Dict[str, Any]:
        """
        Parse carrier data from scraped FMCSA page.
        
        Args:
            page: Playwright page object
            mc_number: MC number being extracted
            
        Returns:
            Dictionary with parsed carrier data
        """
        data = {
            "mc_number": mc_number,
            "dot_number": None,
            "company_name": None,
            "authority_status": None,
            "authority_type": None,
            "insurance_status": None,
            "insurance_expiry": None,
            "safety_rating": None,
            "violations_12mo": 0,
            "accidents_12mo": 0,
            "authority_date": None,
            "email": None,
            "phone": None,
            "state": None
        }
        
        try:
            # Extract company name
            company_elem = await page.query_selector(".company-name, h2, .carrier-name")
            if company_elem:
                data["company_name"] = (await company_elem.inner_text()).strip()
            
            # Extract DOT number
            dot_elem = await page.query_selector("#lblDOTNumber, .dot-number")
            if dot_elem:
                data["dot_number"] = (await dot_elem.inner_text()).strip()
            
            # Extract authority status
            auth_status_elem = await page.query_selector(".authority-status, #lblAuthorityStatus")
            if auth_status_elem:
                status_text = (await auth_status_elem.inner_text()).strip()
                data["authority_status"] = status_text
            
            # Extract authority type
            auth_type_elem = await page.query_selector(".authority-type, #lblAuthorityType")
            if auth_type_elem:
                data["authority_type"] = (await auth_type_elem.inner_text()).strip()
            
            # Extract insurance status
            ins_status_elem = await page.query_selector(".insurance-status, #lblInsuranceStatus")
            if ins_status_elem:
                ins_text = (await ins_status_elem.inner_text()).strip()
                data["insurance_status"] = "Active" if "active" in ins_text.lower() else "Expired"
            
            # Extract insurance expiry date
            ins_expiry_elem = await page.query_selector(".insurance-expiry, #lblInsuranceExpiry")
            if ins_expiry_elem:
                data["insurance_expiry"] = (await ins_expiry_elem.inner_text()).strip()
            
            # Extract safety rating (1-10 scale)
            rating_elem = await page.query_selector(".safety-rating, #lblSafetyRating, .rating")
            if rating_elem:
                rating_text = (await rating_elem.inner_text()).strip()
                # Try to extract numeric rating
                rating_match = re.search(r'(\d+)', rating_text)
                if rating_match:
                    data["safety_rating"] = rating_match.group(1)
            
            # Extract violations (last 12 months)
            violations_elem = await page.query_selector(".violations-count, #lblViolations12mo")
            if violations_elem:
                violations_text = (await violations_elem.inner_text()).strip()
                try:
                    data["violations_12mo"] = int(re.search(r'(\d+)', violations_text).group(1))
                except:
                    pass
            
            # Extract accidents (last 12 months)
            accidents_elem = await page.query_selector(".accidents-count, #lblAccidents12mo")
            if accidents_elem:
                accidents_text = (await accidents_elem.inner_text()).strip()
                try:
                    data["accidents_12mo"] = int(re.search(r'(\d+)', accidents_text).group(1))
                except:
                    pass
            
            # Extract authority establishment date
            auth_date_elem = await page.query_selector(".authority-date, #lblAuthorityDate")
            if auth_date_elem:
                data["authority_date"] = (await auth_date_elem.inner_text()).strip()
            
            # Extract contact information
            phone_elem = await page.query_selector(".phone, .contact-phone")
            if phone_elem:
                data["phone"] = (await phone_elem.inner_text()).strip()
            
            email_elem = await page.query_selector(".email, .contact-email")
            if email_elem:
                data["email"] = (await email_elem.inner_text()).strip()
            
            # Extract state/address
            state_elem = await page.query_selector(".state, .carrier-state, .address-state")
            if state_elem:
                data["state"] = (await state_elem.inner_text()).strip()
            
            # If state not found, try extracting from address
            if not data["state"]:
                address_elem = await page.query_selector(".address, .carrier-address")
                if address_elem:
                    address_text = (await address_elem.inner_text()).strip()
                    # Try to extract state abbreviation (2-letter code)
                    state_match = re.search(r'\b([A-Z]{2})\b', address_text)
                    if state_match:
                        data["state"] = state_match.group(1)
            
            logger.debug(f"Successfully parsed data for MC {mc_number}")
            
        except Exception as e:
            logger.warning(f"Error parsing page for MC {mc_number}: {e}")
            # Return partial data if available
            if not data.get("company_name"):
                return None
        
        return data
    
    def _parse_apify_response(self, api_data: Dict[str, Any], mc_number: str) -> Dict[str, Any]:
        """
        Parse Apify API response into standard format.
        
        Args:
            api_data: Raw API response data
            mc_number: MC number being extracted
            
        Returns:
            Dictionary with parsed carrier data
        """
        # Map Apify fields to our standard format
        # Adjust field names based on actual Apify actor response structure
        return {
            "mc_number": mc_number,
            "dot_number": api_data.get("dotNumber") or api_data.get("DOT"),
            "company_name": api_data.get("companyName") or api_data.get("name"),
            "authority_status": api_data.get("authorityStatus") or api_data.get("status"),
            "authority_type": api_data.get("authorityType"),
            "insurance_status": api_data.get("insuranceStatus"),
            "insurance_expiry": api_data.get("insuranceExpiry") or api_data.get("insuranceExpiration"),
            "safety_rating": str(api_data.get("safetyRating", "")),
            "violations_12mo": int(api_data.get("violations12mo", 0) or 0),
            "accidents_12mo": int(api_data.get("accidents12mo", 0) or 0),
            "authority_date": api_data.get("authorityDate") or api_data.get("establishedDate"),
            "email": api_data.get("email"),
            "phone": api_data.get("phone") or api_data.get("phoneNumber"),
            "state": api_data.get("state") or api_data.get("address", {}).get("state") if isinstance(api_data.get("address"), dict) else None
        }

