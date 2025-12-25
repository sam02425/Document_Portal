
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from api.main import app
from pathlib import Path

client = TestClient(app)

@pytest.fixture
def mock_gemini():
    with patch("api.main.gemini_extractor") as mock:
        yield mock

def test_extract_invoice_batch(mock_gemini):
    # Mock Gemini Response
    mock_gemini.extract_data.return_value = {
        "data": {
            "invoice_details": {"number": "123"},
            "financials": {"total_amount": 50.0}
        },
        "confidence": 95
    }
    
    # Create dummy files
    files = [
        ("files", ("page1.jpg", b"fakeimgbytes", "image/jpeg")),
        ("files", ("page2.jpg", b"fakeimgbytes", "image/jpeg"))
    ]
    
    # Mock Ingestion (to avoid file processing errors on fake bytes)
    with patch("api.main.Ingestion") as mock_ingest:
        mock_ingest_instance = mock_ingest.return_value
        mock_ingest_instance.ingest.return_value = "OCR Text"
        
        response = client.post("/extract/invoice?use_gemini=true", files=files)
        
    assert response.status_code == 200
    data = response.json()
    assert data["batch_count"] == 2
    # Verify Gemini called twice
    assert mock_gemini.extract_data.call_count == 2
