"""
ID Extraction module for Document Portal.
Optimized for speed and low cost by using Regex patterns before falling back to LLM.
"""
import re
from typing import Dict, Any, Optional
from datetime import datetime
from logger import GLOBAL_LOGGER as log

class IDExtractor:
    """
    Extracts structured information from ID documents (Driver's Licenses, Passports).
    """

    # Common Regex Patterns for US IDs
    PATTERNS = {
        "date_match": r"(\d{2}[-/]\d{2}[-/]\d{4})",
        "dl_number": r"(DL|LIC|NO)\.?\s*[:#]?\s*([A-Z0-9]{7,})",
        "dob": r"(DOB|BIRTH)\s*[:.]?\s*(\d{2}[-/]\d{2}[-/]\d{4})",
        "exp": r"(EXP|EXPIRES)\s*[:.]?\s*(\d{2}[-/]\d{2}[-/]\d{4})",
        "sex": r"(SEX|GENDER)\s*[:.]?\s*([MF])",
        "height": r"(HGT|HEIGHT)\s*[:.]?\s*(\d+['\-]\d+\"?)",
    }

    def __init__(self):
        pass

    def extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extracts ID information from raw OCR text using Heuristics/Regex.
        """
        extracted = {}
        text_upper = text.upper()

        # 1. Dates (DOB, Expiration)
        dates = re.findall(self.PATTERNS["date_match"], text_upper)
        
        # Heuristic: Expiration usually > DOB. 
        # But explicitly looking for labels is safer.
        
        dob_match = re.search(self.PATTERNS["dob"], text_upper)
        if dob_match:
            extracted["dob"] = dob_match.group(2)
        
        exp_match = re.search(self.PATTERNS["exp"], text_upper)
        if exp_match:
            extracted["expiration_date"] = exp_match.group(2)

        # 2. License Number
        dl_match = re.search(self.PATTERNS["dl_number"], text_upper)
        if dl_match:
            extracted["license_number"] = dl_match.group(2)

        # 3. Sex
        sex_match = re.search(self.PATTERNS["sex"], text_upper)
        if sex_match:
            extracted["sex"] = sex_match.group(2)

        # 4. Height
        hgt_match = re.search(self.PATTERNS["height"], text_upper)
        if hgt_match:
            extracted["height"] = hgt_match.group(2)
            
        # 5. Name (Difficult with Regex alone, usually requires NER or LLM)
        # We will mark it as missing to trigger LLM fallback if needed.
        
        # Calculate confidence based on fields found
        found_fields = len(extracted)
        confidence = min(found_fields * 20, 100) # 5 fields = 100%
        
        return {
            "data": extracted,
            "confidence": confidence,
            "method": "regex_heuristic"
        }

    def extract_id_data(self, text: str, fallback_llm_func=None) -> Dict[str, Any]:
        """
        Main entry point. Tries Regex first, then falls back to LLM if confidence is low.
        """
        result = self.extract_from_text(text)
        
        if result["confidence"] < 80 and fallback_llm_func:
            log.info("Low confidence in regex extraction. Falling back to LLM.")
            # This is where we would call the cheap LLM (e.g. Gemini Flash)
            try:
                llm_result = fallback_llm_func(text)
                if llm_result:
                    return {
                        "data": llm_result,
                        "confidence": 95, 
                        "method": "llm_fallback"
                    }
            except Exception as e:
                log.error(f"LLM Fallback failed: {e}")
                
        return result
