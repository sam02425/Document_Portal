"""
Unit tests for enhanced IDExtractor functionality.
Tests name/address extraction, Gemini Vision integration, and validation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from document_portal_core.extractor import IDExtractor


@pytest.fixture
def extractor():
    """Fixture for IDExtractor instance (without Gemini)."""
    with patch('document_portal_core.extractor.GEMINI_AVAILABLE', False):
        return IDExtractor()


@pytest.fixture
def extractor_with_gemini():
    """Fixture for IDExtractor with mocked Gemini."""
    with patch('document_portal_core.extractor.GEMINI_AVAILABLE', True):
        with patch('document_portal_core.extractor.ChatGoogleGenerativeAI') as mock_gemini:
            extractor = IDExtractor(api_key="test-key")
            return extractor


@pytest.fixture
def sample_id_text():
    """Sample OCR text from a driver's license."""
    return """
    TEXAS DRIVER LICENSE
    DL NO: D12345678
    DOB: 01/15/1990
    EXP: 01/15/2028
    SEX: M
    HGT: 5'10"
    JOHN MICHAEL SMITH
    123 MAIN ST
    AUSTIN TX 78701
    """


@pytest.fixture
def sample_gemini_response():
    """Sample response from Gemini Vision."""
    return {
        "id_type": "Driver License",
        "full_name": "John Michael Smith",
        "first_name": "John",
        "middle_name": "Michael",
        "last_name": "Smith",
        "address": {
            "street": "123 Main St",
            "city": "Austin",
            "state": "TX",
            "zip": "78701"
        },
        "dob": "01/15/1990",
        "expiration_date": "01/15/2028",
        "license_number": "D12345678",
        "sex": "M",
        "height": "5'10\"",
        "issuing_state": "TX"
    }


class TestRegexExtraction:
    """Tests for regex-based ID extraction."""

    def test_extract_license_number(self, extractor, sample_id_text):
        """Test extraction of license number."""
        result = extractor.extract_from_text(sample_id_text)
        assert result["data"]["license_number"] == "D12345678"

    def test_extract_dob(self, extractor, sample_id_text):
        """Test extraction of date of birth."""
        result = extractor.extract_from_text(sample_id_text)
        assert result["data"]["dob"] == "01/15/1990"

    def test_extract_expiration(self, extractor, sample_id_text):
        """Test extraction of expiration date."""
        result = extractor.extract_from_text(sample_id_text)
        assert result["data"]["expiration_date"] == "01/15/2028"

    def test_extract_sex(self, extractor, sample_id_text):
        """Test extraction of sex."""
        result = extractor.extract_from_text(sample_id_text)
        assert result["data"]["sex"] == "M"

    def test_extract_height(self, extractor, sample_id_text):
        """Test extraction of height."""
        result = extractor.extract_from_text(sample_id_text)
        assert result["data"]["height"] == "5'10\""

    def test_confidence_calculation(self, extractor, sample_id_text):
        """Test confidence scoring based on fields found."""
        result = extractor.extract_from_text(sample_id_text)
        # Should have found 5 fields (license, dob, exp, sex, height)
        assert result["confidence"] == 100  # 5 * 20 = 100

    def test_extract_minimal_data(self, extractor):
        """Test extraction with minimal data."""
        minimal_text = "DOB: 01/15/1990"
        result = extractor.extract_from_text(minimal_text)
        assert result["confidence"] == 20  # Only 1 field
        assert "dob" in result["data"]

    def test_extract_empty_text(self, extractor):
        """Test extraction from empty text."""
        result = extractor.extract_from_text("")
        assert result["confidence"] == 0
        assert result["data"] == {}


class TestGeminiVisionExtraction:
    """Tests for Gemini Vision-based extraction."""

    def test_vision_extraction_success(self, extractor_with_gemini, sample_gemini_response):
        """Test successful Gemini Vision extraction."""
        # Mock the LLM response
        mock_response = Mock()
        mock_response.content = f'```json\n{{"data": {sample_gemini_response}}}\n```'

        with patch.object(extractor_with_gemini.llm, 'invoke', return_value=mock_response):
            result = extractor_with_gemini.extract_from_image_vision("test.jpg")

            # Note: The actual response is wrapped, so we extract nested data
            assert result["confidence"] == 95
            assert result["method"] == "gemini_vision"

    def test_vision_extraction_no_llm(self, extractor):
        """Test vision extraction when LLM not available."""
        result = extractor.extract_from_image_vision("test.jpg")
        assert result["confidence"] == 0
        assert "error" in result

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_vision_extraction_file_not_found(self, mock_open, extractor_with_gemini):
        """Test vision extraction with missing file."""
        result = extractor_with_gemini.extract_from_image_vision("missing.jpg")
        assert result["confidence"] == 0
        assert "error" in result


class TestHybridExtraction:
    """Tests for hybrid extraction strategy."""

    def test_hybrid_uses_regex_first(self, extractor_with_gemini, sample_id_text):
        """Test that hybrid extraction tries regex first."""
        with patch.object(extractor_with_gemini, 'extract_from_text', wraps=extractor_with_gemini.extract_from_text) as mock_regex:
            result = extractor_with_gemini.extract_id_data(
                text=sample_id_text,
                image_path="test.jpg",
                use_vision_first=False
            )
            # Should call regex extraction
            assert mock_regex.called

    def test_hybrid_fallback_to_vision_low_confidence(self, extractor_with_gemini, sample_gemini_response):
        """Test fallback to vision when regex confidence low."""
        low_confidence_text = "Some random text"

        mock_response = Mock()
        mock_response.content = f'{sample_gemini_response}'

        with patch.object(extractor_with_gemini, 'extract_from_image_vision') as mock_vision:
            mock_vision.return_value = {
                "data": sample_gemini_response,
                "confidence": 95,
                "method": "gemini_vision"
            }

            result = extractor_with_gemini.extract_id_data(
                text=low_confidence_text,
                image_path="test.jpg"
            )

            # Should fall back to vision due to low regex confidence
            assert mock_vision.called

    def test_vision_first_mode(self, extractor_with_gemini, sample_gemini_response):
        """Test use_vision_first parameter."""
        mock_response = Mock()
        mock_response.content = f'{sample_gemini_response}'

        with patch.object(extractor_with_gemini, 'extract_from_image_vision') as mock_vision:
            mock_vision.return_value = {
                "data": sample_gemini_response,
                "confidence": 95,
                "method": "gemini_vision"
            }

            result = extractor_with_gemini.extract_id_data(
                text="some text",
                image_path="test.jpg",
                use_vision_first=True
            )

            # Should call vision first
            assert mock_vision.called
            assert result["method"] == "gemini_vision"


class TestValidation:
    """Tests for ID data validation."""

    def test_validate_age_calculation(self, extractor):
        """Test age calculation from DOB."""
        data = {"dob": "01/15/1990"}
        validation = extractor.validate_id_data(data)

        assert "age" in validation
        assert validation["age"] > 30  # Should be around 34-35 in 2024-2025

    def test_validate_expired_id(self, extractor):
        """Test detection of expired ID."""
        data = {
            "dob": "01/15/1990",
            "expiration_date": "01/15/2020"  # Expired
        }
        validation = extractor.validate_id_data(data)

        assert validation["is_expired"] is True
        assert not validation["valid"]
        assert "ID is Expired" in validation["errors"]

    def test_validate_valid_id(self, extractor):
        """Test validation of valid ID."""
        data = {
            "dob": "01/15/1990",
            "expiration_date": "01/15/2030"  # Future expiration
        }
        validation = extractor.validate_id_data(data)

        assert validation["is_expired"] is False
        assert validation["valid"] is True

    def test_validate_under_18(self, extractor):
        """Test warning for under 18."""
        # DOB that makes person under 18
        recent_year = datetime.now().year - 10
        data = {"dob": f"01/15/{recent_year}"}
        validation = extractor.validate_id_data(data)

        assert "Under 18 years old" in validation["warnings"]

    def test_validate_under_21(self, extractor):
        """Test warning for under 21."""
        # DOB that makes person under 21 but over 18
        recent_year = datetime.now().year - 19
        data = {"dob": f"01/15/{recent_year}"}
        validation = extractor.validate_id_data(data)

        assert "Under 21 years old" in validation["warnings"]

    def test_validate_future_dob(self, extractor):
        """Test error for future DOB."""
        future_year = datetime.now().year + 1
        data = {"dob": f"01/15/{future_year}"}
        validation = extractor.validate_id_data(data)

        assert not validation["valid"]
        assert "Date of Birth is in the future" in validation["errors"]

    def test_validate_illogical_expiration(self, extractor):
        """Test error when expiration before DOB."""
        data = {
            "dob": "01/15/2000",
            "expiration_date": "01/15/1999"  # Before DOB!
        }
        validation = extractor.validate_id_data(data)

        assert not validation["valid"]
        assert "Expiration Date is before Date of Birth" in validation["errors"]


class TestDateParsing:
    """Tests for date parsing."""

    def test_parse_slash_format(self, extractor):
        """Test parsing MM/DD/YYYY format."""
        date = extractor._parse_date("01/15/1990")
        assert date.year == 1990
        assert date.month == 1
        assert date.day == 15

    def test_parse_dash_format(self, extractor):
        """Test parsing MM-DD-YYYY format."""
        date = extractor._parse_date("01-15-1990")
        assert date.year == 1990
        assert date.month == 1
        assert date.day == 15

    def test_parse_invalid_date(self, extractor):
        """Test parsing invalid date."""
        date = extractor._parse_date("invalid")
        assert date is None

    def test_parse_empty_date(self, extractor):
        """Test parsing empty date."""
        date = extractor._parse_date("")
        assert date is None


class TestIntegration:
    """Integration tests for full extraction workflow."""

    def test_full_extraction_with_validation(self, extractor, sample_id_text):
        """Test complete extraction and validation workflow."""
        result = extractor.extract_id_data(text=sample_id_text)

        # Should have extracted data
        assert "data" in result
        assert "confidence" in result
        assert "validation" in result

        # Validation should be present
        assert "valid" in result["validation"]
        assert "age" in result["validation"]

    def test_extraction_without_text_or_image(self, extractor):
        """Test extraction with no inputs."""
        result = extractor.extract_id_data()

        assert result["confidence"] == 0
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
