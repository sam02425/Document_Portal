"""
Invoice Extraction Module.
Extracts key invoice fields: Total Amount, Invoice Date, Invoice Number, Vendor Name.
Optimized for high-speed regex extraction with confidence scoring.
"""
import re
from typing import Dict, Any, Optional
from datetime import datetime
from logger import GLOBAL_LOGGER as log

class InvoiceExtractor:
    """
    Extracts structured information from Invoices/Bills.
    """
    
    PATTERNS = {
        # Money: Looks for $XX.XX or XX,XX
        # Added: TOTAL SALES, INVOICE TOTAL
        "total_amount": [
            r"TOTAL\s*SALES\s*[:.]?\s*[\$]?\s*([0-9,]+[.,][0-9]{2})",
            r"INVOICE\s*TOTAL\s*[:.]?\s*[\$]?\s*([0-9,]+[.,][0-9]{2})",
            r"AMOUNT\s*DUE\s*[:.]?\s*[\$]?\s*([0-9,]+[.,][0-9]{2})",
            r"TOTAL\s*(AMOUNT|DUE)?\s*[:.]?\s*[\$]?\s*([0-9,]+[.,][0-9]{2})",
            r"BALANCE\s*DUE\s*[:.]?\s*[\$]?\s*([0-9,]+[.,][0-9]{2})",
            r"GRAND\s*TOTAL\s*[:.]?\s*[\$]?\s*([0-9,]+[.,][0-9]{2})",
            # Fallback for just huge numbers at bottom? No, risky.
        ],
        # Date: MM/DD/YYYY or YYYY-MM-DD
        "date": [
            r"(INVOICE|BILL|DUE)\s*DATE\s*[:.]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"DATE\s*[:.]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{4}[-]\d{2}[-]\d{2})" # YYYY-MM-DD standalone
        ],
        # Invoice Number: #12345 or Inv: 12345
        "invoice_number": [
            r"(INVOICE|BILL)\s*(NO|NUMBER|#)?\s*[:.]?\s*([A-Za-z0-9\-]+)",
            r"INV\s*[:.]?\s*([A-Za-z0-9\-]+)"
        ],
        # Classification Keywords
        "type_shift_report": [r"TILL", r"SHIFT", r"PUMP", r"REGISTER", r"SAFE LOANS"],
        "type_lottery": [r"MEGA", r"LOTO", r"SCRATCH", r"JACKPOT"]
    }

    def extract_invoice_data(self, text: str) -> Dict[str, Any]:
        """
        Extracts invoice data from raw text.
        """
        # Debug: Print first 500 chars to log to see what Tesseract is seeing
        log.info(f"Raw Text Preview: {text[:500]}")
        
        text_upper = text.upper()
        extracted = {}
        
        # 0. Classify Document Type
        doc_type = "invoice"
        for keyword in self.PATTERNS["type_shift_report"]:
            if re.search(keyword, text_upper):
                doc_type = "shift_report"
                break
        if doc_type == "invoice": # check lottery if not shift
             for keyword in self.PATTERNS["type_lottery"]:
                if re.search(keyword, text_upper):
                    doc_type = "lottery_report"
                    break
        extracted["detected_type"] = doc_type

        # 1. Total Amount (Highest Priority)
        for pattern in self.PATTERNS["total_amount"]:
            match = re.search(pattern, text_upper)
            if match:
                # Get the last group matches which should be the amount
                amount_str = match.groups()[-1]
                # Normalize comma to dot
                amount_str = amount_str.replace(",", ".") 
                # Fix double dots if any (e.g. 792.04. -> 792.04)
                if amount_str.count(".") > 1:
                     amount_str = amount_str.replace(".", "", amount_str.count(".") - 1)
                     
                extracted["total_amount"] = amount_str
                break
        
        # 2. Date
        for pattern in self.PATTERNS["date"]:
            match = re.search(pattern, text_upper)
            if match:
                extracted["invoice_date"] = match.groups()[-1]
                break
                
        # 3. Invoice Number
        for pattern in self.PATTERNS["invoice_number"]:
            match = re.search(pattern, text_upper)
            if match:
                val = match.groups()[-1]
                if any(char.isdigit() for char in val):
                    extracted["invoice_number"] = val
                    break

        # 4. Vendor Name (Hardest with Regex)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            extracted["vendor_name_guess"] = lines[0]

        # Calculate Confidence
        fields_found = len([k for k in extracted.keys() if k not in ["vendor_name_guess", "detected_type"]])
        confidence = min(fields_found * 33, 100)
        
        # Boost confidence if we found Total Amount (most important)
        if "total_amount" in extracted:
            confidence = max(confidence, 60)

        return {
            "data": extracted,
            "confidence": confidence,
            "doc_type": doc_type
        }
