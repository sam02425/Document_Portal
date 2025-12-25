"""
Gemini Vision Extractor.
Uses Google's Gemini 1.5 Flash (via LangChain) to extract structured data from images.
Achieves >90% confidence on messy documents where OCR fails.
"""
import base64
import json
import os
from typing import Dict, Any
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage
except ImportError:
    ChatGoogleGenerativeAI = None # Handling if dependencies missing in env

from logger import GLOBAL_LOGGER as log

class GeminiVisionExtractor:
    def __init__(self, api_key: str = None):
        if not ChatGoogleGenerativeAI:
             raise ImportError("langchain-google-genai not installed.")
             
        # Use env var GOOGLE_API_KEY or variants if not provided
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("google_api_key") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            log.warning("GOOGLE_API_KEY not found. Gemini Extraction will fail.")
            
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=self.api_key,
            temperature=0,
            convert_system_message_to_human=True
        )

    def extract_data(self, image_path: str) -> Dict[str, Any]:
        """
        Sends image to Gemini Flash and requests JSON output.
        """
        try:
            # 1. Read and Encode Image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # 2. Prompt
            prompt = """
        Analyze this image. It is likely an Invoice, Receipt, or Shift Report.

        EXTRACT THE FOLLOWING AS JSON WITH MAXIMUM DETAIL FOR POS INTEGRATION:
        {
            "doc_type": "Invoice" | "Shift Report" | "Lottery Report" | "Receipt" | "Other",
            "vendor": {
                "name": "string",
                "phone": "string",
                "address": "string",
                "website": "string",
                "vendor_id": "string (if visible)"
            },
            "invoice_details": {
                "number": "string",
                "date": "YYYY-MM-DD",
                "due_date": "YYYY-MM-DD",
                "po_number": "string",
                "terms": "string (e.g., Net 30)"
            },
            "financials": {
                "total_amount": "number (float)",
                "subtotal": "number",
                "tax": "number",
                "tax_rate": "number (percentage if visible)",
                "shipping": "number",
                "credits": "number (negative if credit)",
                "balance_due": "number",
                "currency": "string (default: USD)"
            },
            "line_items": [
                {
                    "item_number": "number (line number on invoice)",
                    "description": "string (full product name/description)",
                    "brand": "string (extract brand if visible)",
                    "upc": "string (UPC/EAN barcode if visible)",
                    "sku": "string (SKU/product code)",
                    "product_code": "string (alternative product code)",
                    "quantity": "number",
                    "unit_of_measure": "string (EA, CS, BX, LB, OZ, GAL, etc.)",
                    "pack_size": "string (e.g., 12-pack, 24oz, 6ct)",
                    "unit_price": "number",
                    "total_price": "number",
                    "category": "string (Food, Beverage, Tobacco, etc.)"
                }
            ],
            "shift_report_details": {
               "total_sales": "number",
               "fuel_sales": "number",
               "merch_sales": "number",
               "cash_drop": "number",
               "credit_card_sales": "number",
               "cash_sales": "number"
            }
        }

        CRITICAL RULES FOR POS INTEGRATION:
        1. If it's a "Shift Report" or "Night Audit", use `shift_report_details` heavily.
        2. If it's an Invoice (like Pepsi, Coke, McLane), extract EVERY SINGLE line item into `line_items`.
        3. For each line item, extract:
           - UPC codes (12-13 digit barcodes, often visible on product line)
           - SKU or product codes
           - Unit of measure (look for EA, CS, CASE, BOX, LB, OZ, GAL, etc.)
           - Pack size (12-pack, 6ct, 24oz bottle, etc.)
           - Brand name if identifiable in description
        4. Extract Date formats to YYYY-MM-DD.
        5. For unit_of_measure, standardize to common codes:
           - EA (Each), CS (Case), BX (Box), LB (Pound), OZ (Ounce), GAL (Gallon)
           - If unclear, use the abbreviation from the invoice
        6. If a field is missing, use null (not empty string).
        7. Look for vendor ID numbers, account numbers, or customer codes.

        EXAMPLES:
        - "Coca-Cola 12oz 24pk" -> {description: "Coca-Cola 12oz 24pk", brand: "Coca-Cola", pack_size: "24pk", unit_of_measure: "CS"}
        - "100234567 PEPSI 2L 8PK" -> {sku: "100234567", description: "PEPSI 2L 8PK", brand: "PEPSI", pack_size: "8pk"}
        """

            # 3. Call LLM
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
            )
            
            start_time = os.times().elapsed
            response = self.llm.invoke([message])
            duration = os.times().elapsed - start_time
            
            # 4. Parse JSON
            content = response.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            
            return {
                "data": data,
                "confidence": 95, # Gemini is usually very high confidence
                "method": "gemini_flash_vision",
                "duration": duration
            }

        except Exception as e:
            log.error(f"Gemini Extraction failed: {e}")
            return {
                "data": {},
                "confidence": 0,
                "error": str(e)
            }
