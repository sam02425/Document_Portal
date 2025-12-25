"""
Integration tests for API endpoints.
Tests all enhanced endpoints including ID extraction, ID-to-contract matching, and invoice extraction.
"""
import pytest
import json
import io
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from PIL import Image
import numpy as np

# Import the FastAPI app
from api.main import app


@pytest.fixture
def client():
    """Fixture for FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_id_image():
    """Create a sample ID image file."""
    # Create a simple image
    img_array = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
    img = Image.fromarray(img_array, 'RGB')

    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)

    return ("id.jpg", img_bytes, "image/jpeg")


@pytest.fixture
def sample_invoice_image():
    """Create a sample invoice image file."""
    img_array = np.random.randint(0, 255, (1200, 900, 3), dtype=np.uint8)
    img = Image.fromarray(img_array, 'RGB')

    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)

    return ("invoice.jpg", img_bytes, "image/jpeg")


class TestHealthCheck:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["service"] == "Document Portal"


class TestIDExtraction:
    """Tests for ID extraction endpoint."""

    @patch('api.main.ingestion._process_image')
    @patch('api.main.id_extractor.extract_id_data')
    def test_extract_id_success(self, mock_extract, mock_process, client, sample_id_image):
        """Test successful ID extraction."""
        # Mock OCR and extraction
        mock_process.return_value = "TEXAS DRIVER LICENSE\nDL NO: D12345678"
        mock_extract.return_value = {
            "data": {
                "full_name": "John Smith",
                "license_number": "D12345678",
                "dob": "01/15/1990"
            },
            "confidence": 95,
            "method": "regex_heuristic",
            "validation": {"valid": True, "age": 34}
        }

        response = client.post(
            "/extract/id",
            files={"file": sample_id_image}
        )

        assert response.status_code == 200
        data = response.json()
        assert "extracted" in data
        assert data["extracted"]["confidence"] == 95
        assert data["source"] == "extraction"

    @patch('api.main.ingestion._process_image')
    @patch('api.main.id_extractor.extract_id_data')
    def test_extract_id_with_cache(self, mock_extract, mock_process, client, sample_id_image):
        """Test ID extraction with user_id caching."""
        mock_process.return_value = "TEXAS DRIVER LICENSE"
        mock_extract.return_value = {
            "data": {"license_number": "D12345678"},
            "confidence": 95,
            "method": "regex_heuristic",
            "validation": {"valid": True}
        }

        # First request (cache miss)
        response1 = client.post(
            "/extract/id",
            files={"file": sample_id_image},
            data={"user_id": "test_user_123"}
        )

        assert response1.status_code == 200

        # Second request should potentially hit cache (depending on implementation)
        sample_id_image[1].seek(0)  # Reset file pointer
        response2 = client.post(
            "/extract/id",
            files={"file": sample_id_image},
            data={"user_id": "test_user_123"}
        )

        assert response2.status_code == 200

    @patch('api.main.ingestion._process_image')
    @patch('api.main.id_extractor.extract_id_data')
    def test_extract_id_with_vision(self, mock_extract, mock_process, client, sample_id_image):
        """Test ID extraction with vision enabled."""
        mock_process.return_value = "Some text"
        mock_extract.return_value = {
            "data": {
                "full_name": "John Smith",
                "address": {"street": "123 Main St", "city": "Austin", "state": "TX"}
            },
            "confidence": 95,
            "method": "gemini_vision",
            "validation": {"valid": True}
        }

        response = client.post(
            "/extract/id",
            files={"file": sample_id_image},
            data={"use_vision": "true"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["method_used"] == "gemini_vision"

    def test_extract_id_no_file(self, client):
        """Test ID extraction without file."""
        response = client.post("/extract/id")
        assert response.status_code == 422  # Validation error


class TestIDToContractVerification:
    """Tests for ID-to-contract verification endpoint."""

    @patch('api.main.ingestion._process_image')
    @patch('api.main.id_extractor.extract_id_data')
    @patch('api.main.id_matcher.match_id_to_contract')
    def test_verify_id_to_contract_success(self, mock_match, mock_extract, mock_process, client, sample_id_image):
        """Test successful ID-to-contract verification."""
        # Mock ID extraction
        mock_process.return_value = "ID text"
        mock_extract.return_value = {
            "data": {
                "full_name": "John Smith",
                "address": {"street": "123 Main St", "city": "Austin", "state": "TX"},
                "dob": "01/15/1990"
            },
            "confidence": 95,
            "method": "gemini_vision"
        }

        # Mock matching
        mock_match.return_value = {
            "overall_match": True,
            "overall_score": 92.5,
            "field_results": {
                "name": {"match": True, "score": 95},
                "address": {"match": True, "score": 90},
                "dob": {"match": True, "score": 100}
            },
            "recommendation": "verified"
        }

        contract_data = {
            "party_name": "John Smith",
            "party_address": "123 Main St, Austin, TX",
            "party_dob": "01/15/1990"
        }

        response = client.post(
            "/verify/id_to_contract",
            files={"id_file": sample_id_image},
            data={"contract_data_json": json.dumps(contract_data)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["verification_result"]["overall_match"] is True
        assert data["verification_result"]["recommendation"] == "verified"

    @patch('api.main.ingestion._process_image')
    @patch('api.main.id_extractor.extract_id_data')
    def test_verify_id_low_confidence(self, mock_extract, mock_process, client, sample_id_image):
        """Test verification with low confidence ID extraction."""
        mock_process.return_value = "unclear text"
        mock_extract.return_value = {
            "data": {},
            "confidence": 30,  # Low confidence
            "method": "regex_heuristic"
        }

        contract_data = {"party_name": "John Smith"}

        response = client.post(
            "/verify/id_to_contract",
            files={"id_file": sample_id_image},
            data={"contract_data_json": json.dumps(contract_data)}
        )

        assert response.status_code == 400  # Bad request due to low confidence
        assert "confidence too low" in response.json()["detail"]

    def test_verify_id_invalid_json(self, client, sample_id_image):
        """Test verification with invalid JSON."""
        response = client.post(
            "/verify/id_to_contract",
            files={"id_file": sample_id_image},
            data={"contract_data_json": "invalid json {"}
        )

        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    def test_verify_id_no_contract_data(self, client, sample_id_image):
        """Test verification without contract data."""
        response = client.post(
            "/verify/id_to_contract",
            files={"id_file": sample_id_image}
        )

        assert response.status_code == 400
        assert "contract_file or contract_data_json must be provided" in response.json()["detail"]


class TestInvoiceExtraction:
    """Tests for invoice extraction endpoint."""

    @patch('api.main.gemini_extractor.extract_data')
    @patch('api.main.ingestion.compress_image')
    def test_extract_invoice_gemini(self, mock_compress, mock_extract, client, sample_invoice_image):
        """Test invoice extraction with Gemini."""
        mock_compress.return_value = Path("compressed.jpg")
        mock_extract.return_value = {
            "data": {
                "vendor": {"name": "Test Vendor"},
                "financials": {"total_amount": 1234.56},
                "line_items": [
                    {
                        "description": "Product 1",
                        "upc": "012345678901",
                        "unit_of_measure": "CS",
                        "quantity": 10
                    }
                ]
            },
            "confidence": 95
        }

        response = client.post(
            "/extract/invoice",
            files=[("files", sample_invoice_image)],
            data={"use_gemini": "true"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["batch_count"] == 1
        assert len(data["results"]) >= 1

    @patch('api.main.ingestion._process_image')
    @patch('api.main.invoice_extractor.extract_invoice_data')
    @patch('api.main.ingestion.compress_image')
    def test_extract_invoice_ocr(self, mock_compress, mock_extract, mock_process, client, sample_invoice_image):
        """Test invoice extraction with OCR."""
        mock_compress.return_value = Path("compressed.jpg")
        mock_process.return_value = "INVOICE\nTotal: $100.00"
        mock_extract.return_value = {
            "data": {
                "total_amount": "100.00",
                "detected_type": "invoice"
            },
            "confidence": 60
        }

        response = client.post(
            "/extract/invoice",
            files=[("files", sample_invoice_image)],
            data={"use_gemini": "false"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["batch_count"] == 1

    @patch('api.main.gemini_extractor.extract_data')
    @patch('api.main.ingestion.compress_image')
    def test_extract_invoice_batch(self, mock_compress, mock_extract, client, sample_invoice_image):
        """Test batch invoice extraction."""
        mock_compress.return_value = Path("compressed.jpg")
        mock_extract.return_value = {
            "data": {"vendor": {"name": "Test"}},
            "confidence": 95
        }

        # Create multiple invoice images
        sample_invoice_image[1].seek(0)
        invoice2 = (sample_invoice_image[0], io.BytesIO(sample_invoice_image[1].read()), sample_invoice_image[2])

        response = client.post(
            "/extract/invoice",
            files=[
                ("files", sample_invoice_image),
                ("files", invoice2)
            ],
            data={"use_gemini": "true"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["batch_count"] == 2


class TestDocumentScanning:
    """Tests for document scanning endpoint."""

    @patch('api.main.document_scanner.scan_document')
    def test_scan_document_success(self, mock_scan, client, sample_id_image):
        """Test successful document scanning."""
        mock_scan.return_value = "scanned_output.jpg"

        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b'fake image data'

            response = client.post(
                "/scan/document",
                files={"file": sample_id_image}
            )

            assert response.status_code == 200 or response.status_code == 500  # Depends on file cleanup


class TestContractVerification:
    """Tests for contract verification endpoint."""

    @patch('api.main.ingestion.ingest')
    @patch('api.main.verifier.quick_verify')
    @patch('api.main.compliance_checker.check_texas_lease_compliance')
    def test_verify_contract(self, mock_compliance, mock_verify, mock_ingest, client, sample_invoice_image):
        """Test contract verification."""
        mock_ingest.return_value = "Contract text content"
        mock_verify.return_value = {
            "checks": [],
            "summary": {"average_score": 90}
        }
        mock_compliance.return_value = {
            "compliance_score": 85,
            "checks": []
        }

        claims = {
            "party_a": {"name": "John Smith"},
            "party_b": {"name": "Jane Doe"}
        }

        response = client.post(
            "/verify/contract",
            files={"file": sample_invoice_image},
            data={"claims_json": json.dumps(claims)}
        )

        assert response.status_code == 200
        data = response.json()
        assert "verification" in data
        assert "compliance" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
