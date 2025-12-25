"""
Integration Tests for Document Portal API.
Tests the endpoints: /extract/id, /verify/contract, /analyze/compliance.
Mocks the 'Ingestion.ingest' method to avoid dependency on Tesseract/OCR during testing.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import json
import sys
import os

# Add parent dir to path to import api
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

client = TestClient(app)

# Mock Data
MOCK_ID_TEXT = """
TEXAS DRIVER LICENSE
DL: 87654321
DOB: 05/15/1990
EXP: 05/15/2030
LN: SMITH FN: JANE
"""

MOCK_LEASE_TEXT = """
TEXAS RESIDENTIAL LEASE AGREEMENT
1. Landlord shall repair or remedy conditions affecting physical health or safety.
2. Security deposit will be returned within 30 days.
"""

@pytest.fixture
def mock_ingest():
    # Patch both processing methods to cover ID (image) and Contracts (PDF)
    with patch("document_portal_core.ingestion.Ingestion._process_image") as mock_img, \
         patch("document_portal_core.ingestion.Ingestion._process_pdf") as mock_pdf:
        
        # We return a helper that sets return values for both
        mock = MagicMock()
        
        def set_return_value(text):
            mock_img.return_value = text
            mock_pdf.return_value = text
            
        mock.return_value = set_return_value # Not used directly but consistent
        mock.set_text = set_return_value
        
        # Default behavior:
        mock_img.return_value = ""
        mock_pdf.return_value = ""
        
        yield mock

def test_health_check():
    """Verify API is running."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_extract_id_endpoint(mock_ingest):
    """Test ID extraction endpoint."""
    mock_ingest.set_text(MOCK_ID_TEXT)
    
    # Create a dummy image file
    files = {"file": ("id.jpg", b"fake_image_bytes", "image/jpeg")}
    
    response = client.post("/extract/id", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["extracted"]["data"]["license_number"] == "87654321"
    assert data["extracted"]["data"]["dob"] == "05/15/1990"

def test_verify_contract_endpoint(mock_ingest):
    """Test Contract Verification endpoint."""
    mock_ingest.set_text(MOCK_LEASE_TEXT)
    
    claims = {
        "expected_changes": [{"expected_text": "Security deposit"}]
    }
    
    files = {"file": ("lease.pdf", b"fake_pdf_bytes", "application/pdf")}
    data = {"claims_json": json.dumps(claims)}
    
    response = client.post("/verify/contract", files=files, data=data)
    
    assert response.status_code == 200
    res_data = response.json()
    
    # Check Verification Result
    assert res_data["verification"]["checks"][0]["result"] == "pass" # "Security deposit" is in text
    
    # Check Compliance Result
    assert res_data["compliance"]["compliance_score"] > 0
    assert "Texas, USA" in res_data["compliance"]["jurisdiction"]

def test_analyze_compliance_endpoint(mock_ingest):
    """Test Compliance Analysis endpoint."""
    mock_ingest.set_text(MOCK_LEASE_TEXT)
    
    files = {"file": ("lease.pdf", b"fake_pdf_bytes", "application/pdf")}
    
    response = client.post("/analyze/compliance", files=files)
    
    assert response.status_code == 200
    data = response.json()
    # It might return Jurisdiction detected
    assert data.get("jurisdiction") == "Texas, USA"
