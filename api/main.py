
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
    user_id: str = Form(None) # Optional user_id for caching
):
    """
    Extracts ID data. Checks cache first if user_id is provided.
    """
    temp_path = None # Initialize temp_path for finally block
    try:
        # 1. Check Cache
        if user_id:
            cached_data = USER_STORE.get_user_data(user_id)
            if cached_data:
                log.info(f"Cache hit for user {user_id}")
                return {"extracted": cached_data, "source": "cache"}

        # 2. Process Image (OCR)
        # Save temp file
        temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
            
        # Extract text (using optimized ingestion)
        text = ingestion._process_image(Path(temp_path))
        
        # Extract Data
        # Fallback to LLM if needed (pass the Analyzer's cheap LLM func)
        # For now, simplest path:
        result = id_extractor.extract_id_data(text) # Add fallback later if needed
        
        # 3. Save to Cache
        if user_id and result.get("confidence", 0) > 50: # Use .get for safety
            USER_STORE.save_user_data(user_id, result)

        return {"extracted": result, "source": "ocr"}
        
    except Exception as e:
        log.error("ID Extraction failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and temp_path.exists():
            os.remove(temp_path)

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