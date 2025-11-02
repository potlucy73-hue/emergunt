"""
Data processing and enrichment module.
Handles cleaning, enrichment, safety score calculation, and risk level assignment.
"""

import logging
from typing import Dict, Optional, Any, List
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class DataProcessor:
    """Processes and enriches FMCSA carrier data."""
    
    @staticmethod
    def clean_mc_number(mc_number: str) -> Optional[str]:
        """
        Clean and validate MC number.
        
        Args:
            mc_number: Raw MC number input
            
        Returns:
            Cleaned MC number or None if invalid
        """
        if not mc_number:
            return None
        
        # Remove whitespace and common separators
        cleaned = re.sub(r'[\s\-_\.]', '', str(mc_number).strip())
        
        # Remove "MC" prefix if present
        cleaned = re.sub(r'^MC', '', cleaned, flags=re.IGNORECASE)
        
        # Validate it's numeric and reasonable length
        if cleaned.isdigit() and len(cleaned) <= 10:
            return cleaned
        
        logger.warning(f"Invalid MC number format: {mc_number}")
        return None
    
    @staticmethod
    def extract_mc_numbers_from_input(input_data: str) -> List[str]:
        """
        Extract MC numbers from various input formats (CSV, comma-separated, etc.).
        
        Args:
            input_data: Raw input string or file content
            
        Returns:
            List of cleaned MC numbers
        """
        mc_numbers = []
        
        # Try parsing as CSV first
        lines = input_data.strip().split('\n')
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
            
            # Try CSV parsing (comma-separated)
            parts = [p.strip() for p in line.split(',')]
            
            for part in parts:
                # Try to identify MC number column
                # MC numbers are typically numeric
                cleaned = DataProcessor.clean_mc_number(part)
                if cleaned:
                    mc_numbers.append(cleaned)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_mc_numbers = []
        for mc in mc_numbers:
            if mc not in seen:
                seen.add(mc)
                unique_mc_numbers.append(mc)
        
        logger.info(f"Extracted {len(unique_mc_numbers)} unique MC numbers from input")
        return unique_mc_numbers
    
    @staticmethod
    def determine_authority_status(carrier_data: Dict[str, Any]) -> str:
        """
        Auto-detect carrier authority status.
        
        Args:
            carrier_data: Raw carrier data dictionary
            
        Returns:
            Status: Active, Inactive, or Suspended
        """
        auth_status = carrier_data.get("authority_status", "").lower()
        
        if not auth_status:
            return "Unknown"
        
        # Check for active indicators
        if any(term in auth_status for term in ["active", "authorized", "current", "valid"]):
            return "Active"
        
        # Check for inactive indicators
        if any(term in auth_status for term in ["inactive", "revoked", "cancelled", "canceled", "out of service"]):
            return "Inactive"
        
        # Check for suspended
        if "suspended" in auth_status:
            return "Suspended"
        
        return "Unknown"
    
    @staticmethod
    def calculate_safety_score(carrier_data: Dict[str, Any]) -> float:
        """
        Calculate safety score (1-10 scale) based on violations and accidents.
        Lower score = worse safety record.
        
        Args:
            carrier_data: Carrier data dictionary
            
        Returns:
            Safety score from 1.0 (worst) to 10.0 (best)
        """
        violations = carrier_data.get("violations_12mo", 0) or 0
        accidents = carrier_data.get("accidents_12mo", 0) or 0
        
        # Start with perfect score
        score = 10.0
        
        # Deduct points for violations (0.5 points per violation, max -4)
        violation_deduction = min(violations * 0.5, 4.0)
        score -= violation_deduction
        
        # Deduct points for accidents (1.5 points per accident, max -4.5)
        accident_deduction = min(accidents * 1.5, 4.5)
        score -= accident_deduction
        
        # Ensure minimum score of 1.0
        score = max(score, 1.0)
        
        return round(score, 1)
    
    @staticmethod
    def determine_risk_level(carrier_data: Dict[str, Any]) -> str:
        """
        Determine risk level based on violations and accidents.
        
        Args:
            carrier_data: Carrier data dictionary
            
        Returns:
            Risk level: Low, Medium, or High
        """
        violations = carrier_data.get("violations_12mo", 0) or 0
        accidents = carrier_data.get("accidents_12mo", 0) or 0
        
        # High risk: >3 violations OR >1 accident OR both conditions
        if violations > 3 or accidents > 1:
            return "High"
        
        # Medium risk: 1-3 violations OR 1 accident
        if violations > 0 or accidents > 0:
            return "Medium"
        
        # Low risk: no violations or accidents
        return "Low"
    
    @staticmethod
    def enrich_carrier_data(carrier_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich carrier data with computed fields.
        
        Args:
            carrier_data: Raw carrier data from scraper
            
        Returns:
            Enriched carrier data dictionary
        """
        enriched = carrier_data.copy()
        
        # Determine authority status if not already set
        if not enriched.get("authority_status") or enriched["authority_status"] == "Unknown":
            enriched["authority_status"] = DataProcessor.determine_authority_status(carrier_data)
        
        # Calculate safety score
        enriched["safety_score"] = DataProcessor.calculate_safety_score(carrier_data)
        
        # Determine risk level
        enriched["risk_level"] = DataProcessor.determine_risk_level(carrier_data)
        
        # Add extraction timestamp
        enriched["extracted_date"] = datetime.now().isoformat()
        
        # Ensure numeric fields are properly set
        enriched["violations_12mo"] = int(enriched.get("violations_12mo", 0) or 0)
        enriched["accidents_12mo"] = int(enriched.get("accidents_12mo", 0) or 0)
        
        logger.debug(f"Enriched data for MC {enriched.get('mc_number')}")
        
        return enriched
    
    @staticmethod
    def format_for_output(carrier_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format carrier data for CSV/JSON output with correct column order.
        
        Args:
            carrier_data: Enriched carrier data
            
        Returns:
            Formatted dictionary with columns in required order
        """
        return {
            "MC#": carrier_data.get("mc_number", ""),
            "DOT#": carrier_data.get("dot_number", ""),
            "Company Name": carrier_data.get("company_name", ""),
            "Authority Status": carrier_data.get("authority_status", ""),
            "Insurance Status": carrier_data.get("insurance_status", ""),
            "Insurance Expiry": carrier_data.get("insurance_expiry", ""),
            "Safety Score": carrier_data.get("safety_score", ""),
            "Violations (12mo)": carrier_data.get("violations_12mo", 0),
            "Accidents (12mo)": carrier_data.get("accidents_12mo", 0),
            "Phone": carrier_data.get("phone", ""),
            "Email": carrier_data.get("email", ""),
            "State": carrier_data.get("state", ""),
            "Risk Level": carrier_data.get("risk_level", ""),
            "Extracted Date": carrier_data.get("extracted_date", "")
        }
    
    @staticmethod
    def validate_carrier_data(carrier_data: Dict[str, Any]) -> bool:
        """
        Validate that carrier data has minimum required fields.
        
        Args:
            carrier_data: Carrier data dictionary
            
        Returns:
            True if valid, False otherwise
        """
        # At minimum, we need MC number
        if not carrier_data.get("mc_number"):
            return False
        
        # Prefer to have company name as well
        if not carrier_data.get("company_name"):
            logger.warning(f"MC {carrier_data.get('mc_number')} missing company name")
        
        return True

