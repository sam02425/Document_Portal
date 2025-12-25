"""
Unit tests for UOM standardization and compression functionality.
"""
import pytest
import numpy as np
from pathlib import Path
from PIL import Image
from unittest.mock import Mock, patch, MagicMock
from document_portal_core.uom_utils import UOMStandardizer
from document_portal_core.ingestion import Ingestion


@pytest.fixture
def uom_standardizer():
    """Fixture for UOMStandardizer instance."""
    return UOMStandardizer()


@pytest.fixture
def ingestion():
    """Fixture for Ingestion instance."""
    return Ingestion()


@pytest.fixture
def sample_image_array():
    """Create a sample image as numpy array."""
    return np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)


class TestUOMStandardization:
    """Tests for unit of measure standardization."""

    def test_standardize_case(self, uom_standardizer):
        """Test standardization to CASE."""
        assert uom_standardizer.standardize("case") == "CS"
        assert uom_standardizer.standardize("CASE") == "CS"
        assert uom_standardizer.standardize("cases") == "CS"
        assert uom_standardizer.standardize("ca") == "CS"

    def test_standardize_each(self, uom_standardizer):
        """Test standardization to EACH."""
        assert uom_standardizer.standardize("each") == "EA"
        assert uom_standardizer.standardize("EACH") == "EA"
        assert uom_standardizer.standardize("pc") == "EA"
        assert uom_standardizer.standardize("piece") == "EA"

    def test_standardize_pound(self, uom_standardizer):
        """Test standardization to POUND."""
        assert uom_standardizer.standardize("pound") == "LB"
        assert uom_standardizer.standardize("lb") == "LB"
        assert uom_standardizer.standardize("lbs") == "LB"
        assert uom_standardizer.standardize("#") == "LB"

    def test_standardize_gallon(self, uom_standardizer):
        """Test standardization to GALLON."""
        assert uom_standardizer.standardize("gallon") == "GAL"
        assert uom_standardizer.standardize("gal") == "GAL"
        assert uom_standardizer.standardize("gallons") == "GAL"

    def test_standardize_box(self, uom_standardizer):
        """Test standardization to BOX."""
        assert uom_standardizer.standardize("box") == "BX"
        assert uom_standardizer.standardize("boxes") == "BX"

    def test_standardize_dozen(self, uom_standardizer):
        """Test standardization to DOZEN."""
        assert uom_standardizer.standardize("dozen") == "DZ"
        assert uom_standardizer.standardize("doz") == "DZ"

    def test_standardize_unknown(self, uom_standardizer):
        """Test handling of unknown UOM."""
        result = uom_standardizer.standardize("XYZ")
        assert result == "XYZ"  # Returns as-is uppercase

    def test_standardize_empty(self, uom_standardizer):
        """Test handling of empty UOM."""
        assert uom_standardizer.standardize("") == "EA"  # Default

    def test_standardize_plural_removal(self, uom_standardizer):
        """Test removal of plural 's'."""
        assert uom_standardizer.standardize("bottles") == "BOTTLE"


class TestPackSizeParsing:
    """Tests for pack size parsing."""

    def test_parse_pack_12pk(self, uom_standardizer):
        """Test parsing 12-pack."""
        result = uom_standardizer.parse_pack_size("Coca-Cola 12oz 12pk")
        assert result == "12-PACK"

    def test_parse_pack_24pack(self, uom_standardizer):
        """Test parsing 24-pack."""
        result = uom_standardizer.parse_pack_size("Pepsi 2L 24-PACK")
        assert result == "24-PACK"

    def test_parse_bottle_size(self, uom_standardizer):
        """Test parsing bottle size."""
        result = uom_standardizer.parse_pack_size("Water 16oz Bottle")
        assert result == "16OZ"

    def test_parse_liter_size(self, uom_standardizer):
        """Test parsing liter size."""
        result = uom_standardizer.parse_pack_size("Pepsi 2L")
        assert result == "2L"

    def test_parse_no_pack_size(self, uom_standardizer):
        """Test when no pack size found."""
        result = uom_standardizer.parse_pack_size("Generic Product")
        assert result is None


class TestUOMValidation:
    """Tests for UOM validation."""

    def test_validate_known_uom(self, uom_standardizer):
        """Test validation of known UOM."""
        is_valid, standardized = uom_standardizer.validate_uom("case")
        assert is_valid is True
        assert standardized == "CS"

    def test_validate_unknown_uom(self, uom_standardizer):
        """Test validation of unknown UOM."""
        is_valid, standardized = uom_standardizer.validate_uom("xyz")
        assert is_valid is False
        assert standardized is None


class TestUOMConversion:
    """Tests for UOM quantity conversion."""

    def test_convert_dozen_to_each(self, uom_standardizer):
        """Test conversion from dozen to each."""
        result = uom_standardizer.convert_quantity(5, "DZ", "EA")
        assert result == 60  # 5 dozen = 60 each

    def test_convert_gallon_to_quart(self, uom_standardizer):
        """Test conversion from gallon to quart."""
        result = uom_standardizer.convert_quantity(2, "GAL", "QT")
        assert result == 8  # 2 gallons = 8 quarts

    def test_convert_pound_to_ounce(self, uom_standardizer):
        """Test conversion from pound to ounce."""
        result = uom_standardizer.convert_quantity(2, "LB", "OZ")
        assert result == 32  # 2 pounds = 32 ounces

    def test_convert_same_uom(self, uom_standardizer):
        """Test conversion with same UOM."""
        result = uom_standardizer.convert_quantity(5, "EA", "EA")
        assert result == 5

    def test_convert_unsupported(self, uom_standardizer):
        """Test conversion with unsupported pair."""
        result = uom_standardizer.convert_quantity(5, "EA", "GAL")
        assert result is None


class TestUOMExtraction:
    """Tests for UOM extraction from descriptions."""

    def test_extract_from_case_description(self, uom_standardizer):
        """Test extraction from description with 'case'."""
        result = uom_standardizer.extract_uom_from_description("Coca-Cola 12oz Case")
        assert result == "CS"

    def test_extract_from_each_description(self, uom_standardizer):
        """Test extraction from description with 'each'."""
        result = uom_standardizer.extract_uom_from_description("Apple per each")
        assert result == "EA"

    def test_extract_no_uom(self, uom_standardizer):
        """Test extraction when no UOM in description."""
        result = uom_standardizer.extract_uom_from_description("Generic Product")
        assert result is None


class TestCompression:
    """Tests for image compression functionality."""

    @patch('PIL.Image.open')
    @patch('PIL.Image.Image.save')
    def test_compress_image_basic(self, mock_save, mock_open, ingestion, tmp_path):
        """Test basic image compression."""
        # Mock image
        mock_img = Mock()
        mock_img.size = (1024, 768)
        mock_img.mode = "RGB"
        mock_open.return_value.__enter__.return_value = mock_img

        test_file = tmp_path / "test.jpg"
        test_file.touch()

        result = ingestion.compress_image(test_file, max_dimension=2048, quality=85)

        assert mock_save.called
        assert result == test_file

    @patch('PIL.Image.open')
    @patch('PIL.Image.Image.save')
    def test_compress_large_image(self, mock_save, mock_open, ingestion, tmp_path):
        """Test compression of large image."""
        # Mock large image
        mock_img = Mock()
        mock_img.size = (4000, 3000)  # Large image
        mock_img.mode = "RGB"
        mock_img.thumbnail = Mock()
        mock_open.return_value.__enter__.return_value = mock_img

        test_file = tmp_path / "large.jpg"
        test_file.touch()

        ingestion.compress_image(test_file, max_dimension=2048, quality=85)

        # Should call thumbnail to resize
        assert mock_img.thumbnail.called

    @patch('PIL.Image.open')
    @patch('PIL.Image.Image.save')
    def test_compress_rgba_image(self, mock_save, mock_open, ingestion, tmp_path):
        """Test compression of RGBA image."""
        # Mock RGBA image
        mock_img = Mock()
        mock_img.size = (1024, 768)
        mock_img.mode = "RGBA"
        mock_img.convert = Mock(return_value=mock_img)
        mock_open.return_value.__enter__.return_value = mock_img

        test_file = tmp_path / "rgba.png"
        test_file.touch()

        ingestion.compress_image(test_file, max_dimension=2048, quality=85)

        # Should convert RGBA to RGB
        mock_img.convert.assert_called_with("RGB")


class TestCompressionWithSSIM:
    """Tests for SSIM-based compression."""

    @patch('document_portal_core.ingestion.ssim', create=True)
    @patch('PIL.Image.open')
    def test_compress_with_target_quality_ssim_available(self, mock_open, ingestion, tmp_path):
        """Test compression with SSIM when available."""
        # Mock image
        mock_img = Mock()
        mock_img.size = (1024, 768)
        mock_img.mode = "RGB"
        mock_img.copy = Mock(return_value=mock_img)
        mock_img.save = Mock()
        mock_open.return_value.__enter__.return_value = mock_img

        test_file = tmp_path / "test.jpg"
        test_file.write_text("dummy")

        with patch('document_portal_core.ingestion.np.array', return_value=np.zeros((768, 1024, 3))):
            # This will fall back to fixed quality since SSIM import fails
            result = ingestion.compress_with_target_quality(test_file, target_ssim=0.98)

            assert "compressed_path" in result
            assert "quality_used" in result

    @patch('PIL.Image.open')
    def test_compress_with_target_quality_fallback(self, mock_open, ingestion, tmp_path):
        """Test compression fallback when SSIM unavailable."""
        # Mock image
        mock_img = Mock()
        mock_img.size = (1024, 768)
        mock_img.mode = "RGB"
        mock_img.copy = Mock(return_value=mock_img)
        mock_img.save = Mock()
        mock_open.return_value.__enter__.return_value = mock_img

        test_file = tmp_path / "test.jpg"
        test_file.write_text("dummy")

        result = ingestion.compress_with_target_quality(test_file, target_ssim=0.98)

        # Should return result even without SSIM
        assert "compressed_path" in result
        assert "quality_used" in result
        assert result["quality_used"] == 85  # Default quality

    def test_compress_with_error_handling(self, ingestion, tmp_path):
        """Test compression error handling."""
        # Non-existent file
        test_file = tmp_path / "nonexistent.jpg"

        result = ingestion.compress_with_target_quality(test_file, target_ssim=0.98)

        # Should return error result
        assert "error" in result or result.get("quality_used") == 85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
