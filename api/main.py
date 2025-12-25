from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import shutil
import os
import uuid
import json
from pathlib import Path

# Core Modules
from document_portal_core.ingestion import Ingestion
from document_portal_core.verifier import Verifier
from document_portal_core.extractor import IDExtractor
from document_portal_core.compliance import ComplianceChecker
from logger import GLOBAL_LOGGER as log

app = FastAPI(title="Document Portal API", version="1.0.0")

# Initialize modules
ingestion = Ingestion()
verifier = Verifier()
id_extractor = IDExtractor()
compliance_checker = ComplianceChecker()

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
async def extract_id(file: UploadFile = File(...)):
    """
    Extracts structured data from an ID image (Driver's License, Passport).
    """
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{file.filename}"
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 1. Ingest (OCR)
        text = ingestion.ingest(temp_path)
        
        # 2. Extract
        result = id_extractor.extract_id_data(text)
        
        return {"filename": file.filename, "extracted": result, "raw_text_preview": text[:200]}
        
    except Exception as e:
        log.error(f"ID Extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path.exists():
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