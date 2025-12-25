"""
Integration Tests for Document Portal API.
Tests the endpoints: /extract/id, /verify/contract, /analyze/compliance.
Mocks the 'Ingestion' module to avoid dependency on Tesseract/OCR during testing.
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
def mock_ingestion():
    with patch("api.main.ingestion") as mock:
        yield mock

def test_health_check():
    """Verify API is running."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_extract_id_endpoint(mock_ingestion):
    """Test ID extraction endpoint."""
    mock_ingestion.ingest.return_value = MOCK_ID_TEXT
    
    # Create a dummy image file
    files = {"file": ("id.jpg", b"fake_image_bytes", "image/jpeg")}
    
    response = client.post("/extract/id", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["extracted"]["data"]["license_number"] == "87654321"
    assert data["extracted"]["data"]["dob"] == "05/15/1990"

def test_verify_contract_endpoint(mock_ingestion):
    """Test Contract Verification endpoint."""
    mock_ingestion.ingest.return_value = MOCK_LEASE_TEXT
    
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

def test_analyze_compliance_endpoint(mock_ingestion):
    """Test Compliance Analysis endpoint."""
    mock_ingestion.ingest.return_value = MOCK_LEASE_TEXT
    
    files = {"file": ("lease.pdf", b"fake_pdf_bytes", "application/pdf")}
    
    response = client.post("/analyze/compliance", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert data["jurisdiction"] == "Texas, USA"
