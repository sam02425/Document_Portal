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


    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parses MM/DD/YYYY or MM-DD-YYYY"""
        try:
            date_str = date_str.replace('-', '/')
            return datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            return None

    def validate_id_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates extracted ID data: checks expiration, calculates age, etc.
        """
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "age": None,
            "is_expired": False
        }
        
        dob_str = data.get("dob")
        exp_str = data.get("expiration_date")
        
        # 1. Age Calculation
        if dob_str:
            dob = self._parse_date(dob_str)
            if dob:
                today = datetime.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                validation_results["age"] = age
                if age < 0:
                     validation_results["valid"] = False
                     validation_results["errors"].append("Date of Birth is in the future.")
                elif age < 18:
                     validation_results["warnings"].append("Under 18 years old.")
                elif age < 21:
                     validation_results["warnings"].append("Under 21 years old.")
            else:
                 validation_results["warnings"].append("Unparseable DOB format.")
        
        # 2. Expiration Check
        if exp_str:
            exp = self._parse_date(exp_str)
            if exp:
                if exp < datetime.today():
                    validation_results["valid"] = False
                    validation_results["is_expired"] = True
                    validation_results["errors"].append("ID is Expired.")
            else:
                validation_results["warnings"].append("Unparseable Expiration Date.")
        
        # 3. Logical Consistency
        if dob_str and exp_str:
            dob = self._parse_date(dob_str)
            exp = self._parse_date(exp_str)
            if dob and exp and exp < dob:
                 validation_results["valid"] = False
                 validation_results["errors"].append("Expiration Date is before Date of Birth.")

        return validation_results

    def extract_id_data(self, text: str, fallback_llm_func=None) -> Dict[str, Any]:
        """
        Main entry point. Tries Regex first, then falls back to LLM if confidence is low.
        Performs validation on the final result.
        """
        result = self.extract_from_text(text)
        
        if result["confidence"] < 80 and fallback_llm_func:
            log.info("Low confidence in regex extraction. Falling back to LLM.")
            # This is where we would call the cheap LLM (e.g. Gemini Flash)
            try:
                llm_result = fallback_llm_func(text)
                if llm_result:
                    result = {
                        "data": llm_result,
                        "confidence": 95, 
                        "method": "llm_fallback"
                    }
            except Exception as e:
                log.error(f"LLM Fallback failed: {e}")
        
        # Run Validation
        validation = self.validate_id_data(result["data"])
        result["validation"] = validation
        
        return result

