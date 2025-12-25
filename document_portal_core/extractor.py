"""
ID Extraction module for Document Portal.
Optimized for speed and low cost by using Regex patterns before falling back to LLM.
Enhanced with Gemini Vision for name and address extraction.
"""
import re
import os
import base64
import json
from typing import Dict, Any, Optional
from datetime import datetime
from logger import GLOBAL_LOGGER as log

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    log.warning("langchain-google-genai not installed. Gemini Vision fallback unavailable.")

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

    def __init__(self, api_key: str = None):
        """
        Initialize ID Extractor with optional Gemini API key for vision-based extraction.

        Args:
            api_key: Google API key for Gemini Vision (optional, will use env var if not provided)
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.llm = None

        if GEMINI_AVAILABLE and self.api_key:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    google_api_key=self.api_key,
                    temperature=0,
                    convert_system_message_to_human=True
                )
                log.info("Gemini Vision initialized for ID extraction")
            except Exception as e:
                log.warning(f"Failed to initialize Gemini Vision: {e}")
        else:
            log.warning("Gemini Vision not available. Name/Address extraction will be limited.")

    def extract_from_image_vision(self, image_path: str) -> Dict[str, Any]:
        """
        Extracts ID information directly from image using Gemini Vision.
        Returns comprehensive extraction including name and address.
        """
        if not self.llm:
            return {"data": {}, "confidence": 0, "error": "Gemini Vision not initialized"}

        try:
            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Structured prompt for ID extraction
            prompt = """
Analyze this ID document (Driver's License, State ID, or Passport) and extract ALL information in JSON format.

EXTRACT THE FOLLOWING:
{
    "id_type": "Driver License" | "State ID" | "Passport" | "Other",
    "full_name": "First Middle Last",
    "first_name": "string",
    "middle_name": "string",
    "last_name": "string",
    "address": {
        "street": "string (e.g., 123 Main St)",
        "city": "string",
        "state": "string (2-letter code, e.g., TX)",
        "zip": "string (5-digit)"
    },
    "dob": "MM/DD/YYYY",
    "expiration_date": "MM/DD/YYYY",
    "license_number": "string",
    "sex": "M" | "F",
    "height": "string (e.g., 5'10\")",
    "weight": "string (e.g., 170 lbs)",
    "eye_color": "string",
    "hair_color": "string",
    "issuing_state": "string (2-letter code)",
    "issue_date": "MM/DD/YYYY"
}

CRITICAL RULES:
1. Extract the FULL NAME exactly as printed
2. Parse address into separate components (street, city, state, zip)
3. Dates must be in MM/DD/YYYY format
4. If a field is missing or unreadable, use null
5. Double-check DOB and expiration date accuracy
6. Return ONLY valid JSON, no markdown formatting
"""

            # Call Gemini Vision
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
            )

            response = self.llm.invoke([message])

            # Parse JSON response
            content = response.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)

            return {
                "data": data,
                "confidence": 95,  # Gemini Vision has high confidence
                "method": "gemini_vision"
            }

        except Exception as e:
            log.error(f"Gemini Vision ID extraction failed: {e}")
            return {"data": {}, "confidence": 0, "error": str(e)}

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

    def extract_id_data(self, text: str = None, image_path: str = None, fallback_llm_func=None,
                       use_vision_first: bool = False) -> Dict[str, Any]:
        """
        Main entry point for ID extraction.

        Args:
            text: OCR text from ID (optional if image_path provided)
            image_path: Path to ID image for vision-based extraction (optional)
            fallback_llm_func: Deprecated, use image_path instead
            use_vision_first: If True and image available, use Gemini Vision first (default: False)

        Returns:
            Dict with extracted data, confidence, validation, and method used

        Strategy:
            1. If use_vision_first=True and image available: Use Gemini Vision
            2. Otherwise: Try regex extraction from text
            3. If confidence < 80 or name/address missing: Fall back to Gemini Vision
            4. Validate extracted data
        """
        result = None

        # Strategy 1: Vision-first mode (when explicitly requested)
        if use_vision_first and image_path and self.llm:
            log.info("Using Gemini Vision for ID extraction (vision-first mode)")
            result = self.extract_from_image_vision(image_path)

        # Strategy 2: Regex extraction from text
        elif text:
            result = self.extract_from_text(text)

            # Check if critical fields are missing (name, address)
            data = result.get("data", {})
            missing_critical = not data.get("full_name") and not data.get("address")

            # Fall back to vision if:
            # - Confidence is low (<80%) OR
            # - Critical fields (name/address) are missing AND vision is available
            if (result["confidence"] < 80 or missing_critical) and image_path and self.llm:
                log.info(f"Regex confidence low ({result['confidence']}%) or missing name/address. "
                        "Falling back to Gemini Vision.")
                vision_result = self.extract_from_image_vision(image_path)

                # Merge results: prefer vision for name/address, keep regex for other fields if vision fails
                if vision_result.get("confidence", 0) > result["confidence"]:
                    result = vision_result
                elif vision_result.get("data"):
                    # Merge: vision for name/address, regex for dates/license
                    result["data"].update({
                        k: v for k, v in vision_result["data"].items()
                        if k in ["full_name", "first_name", "last_name", "middle_name", "address", "id_type"]
                        and v is not None
                    })
                    result["method"] = "hybrid_regex_vision"
                    result["confidence"] = max(result["confidence"], 85)

            # Legacy fallback function support
            elif result["confidence"] < 80 and fallback_llm_func:
                log.info("Using legacy fallback LLM function")
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

        # Strategy 3: Image-only mode (no text provided)
        elif image_path and self.llm:
            log.info("No text provided, using Gemini Vision for ID extraction")
            result = self.extract_from_image_vision(image_path)

        else:
            # No valid input
            result = {
                "data": {},
                "confidence": 0,
                "error": "No text or image provided for extraction"
            }

        # Run Validation
        validation = self.validate_id_data(result.get("data", {}))
        result["validation"] = validation

        return result

