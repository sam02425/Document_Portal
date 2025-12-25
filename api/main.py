
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import shutil
import os
import uuid
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Core Modules
from document_portal_core.ingestion import Ingestion
from document_portal_core.verifier import Verifier
from document_portal_core.extractor import IDExtractor
from document_portal_core.compliance import ComplianceChecker
from document_portal_core.scanner import DocumentScanner
from document_portal_core.invoice_extractor import InvoiceExtractor
from document_portal_core.gemini_extractor import GeminiVisionExtractor
from document_portal_core.id_matcher import IDMatcher
from document_portal_core.user_store import USER_STORE
from document_portal_core.result_manager import RESULT_MANAGER
from logger import GLOBAL_LOGGER as log

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Document Portal API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (for development)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize modules
ingestion = Ingestion()
verifier = Verifier()
id_extractor = IDExtractor()
invoice_extractor = InvoiceExtractor()
compliance_checker = ComplianceChecker()
document_scanner = DocumentScanner()
gemini_extractor = GeminiVisionExtractor() # Needs GOOGLE_API_KEY in env
id_matcher = IDMatcher()

# Temp storage for uploads
UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

class VerificationRequest(BaseModel):
    claims: Dict[str, Any]
    document_text: str

class AnalysisRequest(BaseModel):
    document_text: str
    doc_type: str = "general"

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Document Portal"}

@app.post("/extract/id")
async def extract_id_endpoint(
    file: UploadFile = File(...),
    user_id: str = Form(None),  # Optional user_id for caching
    use_vision: bool = Form(True)  # Use Gemini Vision for name/address extraction (default: True)
):
    """
    Extracts ID data with enhanced name and address extraction.
    Automatically uses Gemini Vision when regex confidence is low or name/address is missing.

    Args:
        file: ID image file (Driver's License, State ID, Passport)
        user_id: Optional user ID for caching results
        use_vision: Enable Gemini Vision fallback for name/address (default: True)

    Returns:
        {
            "extracted": {
                "data": {
                    "full_name": "...",
                    "address": {"street": "...", "city": "...", "state": "...", "zip": "..."},
                    "dob": "...",
                    "expiration_date": "...",
                    "license_number": "...",
                    ...
                },
                "confidence": 95,
                "method": "gemini_vision" | "hybrid_regex_vision" | "regex_heuristic",
                "validation": {...}
            },
            "source": "cache" | "extraction"
        }
    """
    temp_path = None
    try:
        # 1. Check Cache
        if user_id:
            cached_data = USER_STORE.get_user_data(user_id)
            if cached_data:
                log.info(f"Cache hit for user {user_id}")
                return {"extracted": cached_data, "source": "cache"}

        # 2. Save temp file
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        # 3. Extract text via OCR (for regex extraction)
        text = ingestion._process_image(Path(temp_path))

        # 4. Extract ID data with vision fallback
        result = id_extractor.extract_id_data(
            text=text,
            image_path=str(temp_path) if use_vision else None,
            use_vision_first=False  # Try regex first, fall back to vision if needed
        )

        # 5. Save to Cache
        if user_id and result.get("confidence", 0) > 50:
            USER_STORE.save_user_data(user_id, result)

        return {
            "extracted": result,
            "source": "extraction",
            "method_used": result.get("method", "unknown")
        }

    except Exception as e:
        log.error("ID Extraction failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and temp_path.exists():
            os.remove(temp_path)

@app.post("/verify/id_to_contract")
async def verify_id_to_contract_endpoint(
    id_file: UploadFile = File(...),
    contract_file: UploadFile = File(None),
    contract_data_json: str = Form(None),
    verification_fields: str = Form("name,address,dob")
):
    """
    Verifies that ID information matches contract party information.

    This endpoint performs comprehensive matching between an ID (Driver's License, State ID, Passport)
    and contract party data. It handles name variations, address normalization, and DOB verification.

    Args:
        id_file: ID image file (required)
        contract_file: Contract PDF/image file (optional, provide either this or contract_data_json)
        contract_data_json: JSON string with contract party data (optional)
            Format: {"party_name": "...", "party_address": "...", "party_dob": "..."}
        verification_fields: Comma-separated fields to verify (default: "name,address,dob")

    Returns:
        {
            "id_extraction": {...},
            "contract_data": {...},
            "verification_result": {
                "overall_match": True/False,
                "overall_score": 85.5,
                "field_results": {
                    "name": {"match": True, "score": 95, "method": "fuzzy_components", ...},
                    "address": {"match": True, "score": 90, "method": "normalized_comparison", ...},
                    "dob": {"match": True, "score": 100, "method": "exact_date", ...}
                },
                "recommendation": "verified" | "review_required" | "rejected"
            }
        }

    Example Usage (with contract_data_json):
        POST /verify/id_to_contract
        Form data:
            id_file: <ID image>
            contract_data_json: '{"party_name": "John Smith", "party_address": "123 Main St, Austin, TX", "party_dob": "01/15/1990"}'
            verification_fields: "name,address,dob"
    """
    id_temp_path = None
    contract_temp_path = None

    try:
        # 1. Save ID file
        id_temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{id_file.filename}"
        with open(id_temp_path, "wb") as f:
            f.write(await id_file.read())

        # 2. Extract ID data
        log.info("Extracting ID data...")
        id_text = ingestion._process_image(Path(id_temp_path))
        id_result = id_extractor.extract_id_data(
            text=id_text,
            image_path=str(id_temp_path),
            use_vision_first=False
        )

        if id_result.get("confidence", 0) < 50:
            raise HTTPException(
                status_code=400,
                detail="ID extraction confidence too low. Please provide a clearer image."
            )

        # 3. Get contract data
        contract_data = {}

        if contract_data_json:
            # Use provided JSON data
            try:
                contract_data = json.loads(contract_data_json)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in contract_data_json")

        elif contract_file:
            # Extract from contract file
            contract_temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{contract_file.filename}"
            with open(contract_temp_path, "wb") as f:
                f.write(await contract_file.read())

            log.info("Extracting contract data...")
            contract_text = ingestion.ingest(contract_temp_path)

            # Try to extract party information from contract text
            # This is a simple extraction - you may want to enhance this
            # For now, we'll look for basic patterns
            contract_data = {
                "extracted_text": contract_text[:500],  # First 500 chars for context
                "note": "Provide structured contract_data_json for better matching"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Either contract_file or contract_data_json must be provided"
            )

        # 4. Parse verification fields
        fields_to_verify = [f.strip() for f in verification_fields.split(",")]

        # 5. Perform matching
        log.info(f"Performing ID-to-contract matching for fields: {fields_to_verify}")
        verification_result = id_matcher.match_id_to_contract(
            id_data=id_result.get("data", {}),
            contract_data=contract_data,
            verification_fields=fields_to_verify
        )

        return {
            "id_extraction": {
                "data": id_result.get("data", {}),
                "confidence": id_result.get("confidence", 0),
                "method": id_result.get("method", "unknown")
            },
            "contract_data": contract_data,
            "verification_result": verification_result,
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"ID-to-contract verification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if id_temp_path and id_temp_path.exists():
            os.remove(id_temp_path)
        if contract_temp_path and contract_temp_path.exists():
            os.remove(contract_temp_path)

@app.post("/verify/contract")
async def verify_contract(
    file: UploadFile = File(...), 
    claims_json: str = Form(...)
):
    """
    Verifies a contract PDF/Image against a set of claims (JSON).
    """
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    try:
        claims = json.loads(claims_json)
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 1. Ingest
        text = ingestion.ingest(temp_path)
        
        # 2. Verify Claims
        verification_result = verifier.quick_verify(claims, text)
        
        # 3. Compliance Check (Texas)
        compliance_result = compliance_checker.check_texas_lease_compliance(text)
        
        return {
            "filename": file.filename,
            "verification": verification_result,
            "compliance": compliance_result
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in claims_json")
    except Exception as e:
        log.error(f"Contract Verification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path.exists():
            os.remove(temp_path)

@app.post("/analyze/compliance")
async def analyze_compliance(file: UploadFile = File(...)):
    """
    Checks document for Texas Lease Compliance.
    """
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        text = ingestion.ingest(temp_path)
        result = compliance_checker.check_texas_lease_compliance(text)
        
        return result
    except Exception as e:
        log.error(f"Compliance check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path.exists():
            os.remove(temp_path)

# --- Phase 6: CamScanner Endpoint ---
@app.post("/scan/document")
async def scan_document_endpoint(
    file: UploadFile = File(...)
):
    """
    Auto-crops and flattens a document image (CamScanner style).
    """
    temp_path = None # Initialize temp_path for finally block
    output_path = None # Initialize output_path for finally block
    try:
        # Save temp file
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
            
        # Scan (Crop + Warp)
        output_path = document_scanner.scan_document(temp_path)
        
        return FileResponse(output_path, media_type="image/jpeg", filename=f"scanned_{file.filename}")
        
    except Exception as e:
        log.error("Scan failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and temp_path.exists():
            os.remove(temp_path)
        if output_path and output_path.exists():
            os.remove(output_path)

# --- Phase 7 & 9: Invoice Extraction Endpoint ---
@app.post("/extract/invoice")
async def extract_invoice_endpoint(
    files: List[UploadFile] = File(...),
    use_gemini: bool = True # Default to High Confidence
):
    """
    Extracts data from Invoices/Bills. Supports Batch Upload (up to 50).
    Auto-merges split pages (e.g. Page 1 & Page 2 of same invoice).
    """
    results = []
    
    # Process each file
    for file in files:
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        try:
            with open(temp_path, "wb") as f:
                f.write(await file.read())
                
            # Compression (Privacy/Speed optimization)
            ingestion.compress_image(temp_path) 
            
            start_time = time.time()
            if use_gemini:
                result = gemini_extractor.extract_data(str(temp_path))
                model_name = "gemini-2.0-flash"
            else:
                text = ingestion._process_image(Path(temp_path))
                result = invoice_extractor.extract_invoice_data(text)
                model_name = "tesseract_regex"
            duration = time.time() - start_time
            
            # Pack result with filename for merging
            full_result = {
                "filename": file.filename, 
                "extracted": result,
                "model_used": model_name
            }
            results.append(full_result)
            
            # Log
            RESULT_MANAGER.log_result(
                model_name=model_name, 
                filename=file.filename, 
                data=result.get("data", {}), 
                duration_seconds=duration,
                confidence=result.get("confidence", 0)
            )
            
        finally:
            if temp_path.exists():
                os.remove(temp_path)

    # Merge Results
    from document_portal_core.invoice_merger import InvoiceMerger
    merger = InvoiceMerger()
    merged_results = merger.merge_results(results)
    
    return {
        "batch_count": len(files),
        "merged_count": len(merged_results),
        "results": merged_results
    }

# --- Chat Endpoint (Existing) ---
# This endpoint was provided in the instruction but does not exist in the original code.
# Assuming it's a placeholder for a future or omitted endpoint, it's not added.
# If it was meant to be added, please provide the full context for ChatRequest and rag.
# @app.post("/chat")
# async def chat_endpoint(request: ChatRequest):
#     try:
#         response = rag.chat(request.message)
#         return {"response": response}
#     except Exception as e:
#         log.error("Chat failed", error=str(e))
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         if temp_path.exists():
#             os.remove(temp_path)