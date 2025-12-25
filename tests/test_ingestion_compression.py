
import pytest
from unittest.mock import MagicMock, patch
from document_portal_core.ingestion import Ingestion
from pathlib import Path

@pytest.fixture
def ingestion():
    return Ingestion()

@patch("document_portal_core.ingestion.Image")
def test_compress_image_resizes(mock_image, ingestion):
    # Setup Mock Image
    mock_img_instance = MagicMock()
    mock_img_instance.size = (4000, 3000) # Large image
    mock_img_instance.mode = 'RGB'
    
    # Context Manager for Image.open
    mock_image.open.return_value.__enter__.return_value = mock_img_instance
    
    # Path Mock
    dummy_path = Path("dummy.jpg")
    
    ingestion.compress_image(dummy_path)
    
    # Verify thumbnail called (Resize)
    mock_img_instance.thumbnail.assert_called()
    # Check max dimension
    args, _ = mock_img_instance.thumbnail.call_args
    assert args[0][0] == 2048

@patch("document_portal_core.ingestion.Image")
def test_compress_image_converts_rgba(mock_image, ingestion):
    # Setup Mock Image
    mock_img_instance = MagicMock()
    mock_img_instance.size = (1000, 1000) # Small enough
    mock_img_instance.mode = 'RGBA' # Needs conversion
    
    # Return a converted mock when convert is called
    converted_mock = MagicMock()
    mock_img_instance.convert.return_value = converted_mock
    
    mock_image.open.return_value.__enter__.return_value = mock_img_instance
    
    ingestion.compress_image(Path("dummy.png"))
    
    # Verify conversion to RGB
    mock_img_instance.convert.assert_called_with('RGB')
    # Verify save called on CONVERTED image
    converted_mock.save.assert_called()
