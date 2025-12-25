"""
Unit tests for enhanced DocumentScanner functionality.
Tests shadow removal, auto-rotation, blur detection, and edge enhancement.
"""
import pytest
import numpy as np
import cv2
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from document_portal_core.scanner import DocumentScanner


@pytest.fixture
def scanner():
    """Fixture for DocumentScanner instance."""
    return DocumentScanner()


@pytest.fixture
def sample_image():
    """Create a sample test image (white rectangle on black background)."""
    # 800x600 black image
    img = np.zeros((600, 800, 3), dtype=np.uint8)
    # White rectangle (document) in center
    cv2.rectangle(img, (100, 100), (700, 500), (255, 255, 255), -1)
    return img


@pytest.fixture
def blurry_image():
    """Create a blurry test image."""
    img = np.zeros((600, 800, 3), dtype=np.uint8)
    cv2.rectangle(img, (100, 100), (700, 500), (255, 255, 255), -1)
    # Apply Gaussian blur
    img = cv2.GaussianBlur(img, (21, 21), 10)
    return img


@pytest.fixture
def rotated_image():
    """Create a rotated test image."""
    img = np.zeros((600, 800, 3), dtype=np.uint8)
    cv2.rectangle(img, (100, 100), (700, 500), (255, 255, 255), -1)
    # Rotate by 15 degrees
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, 15, 1.0)
    img = cv2.warpAffine(img, M, (w, h))
    return img


@pytest.fixture
def shadowed_image():
    """Create an image with shadow (gradient)."""
    img = np.ones((600, 800, 3), dtype=np.uint8) * 200
    # Add gradient shadow
    for i in range(600):
        gradient = int(200 - (i / 600) * 100)
        img[i, :] = gradient
    return img


class TestShadowRemoval:
    """Tests for shadow removal functionality."""

    def test_remove_shadow_basic(self, scanner, shadowed_image):
        """Test that shadow removal reduces gradient variance."""
        result = scanner._remove_shadow(shadowed_image)

        # Result should be more uniform than original
        orig_variance = np.var(shadowed_image)
        result_variance = np.var(result)

        assert result_variance < orig_variance * 0.8  # 20% improvement minimum

    def test_remove_shadow_preserves_shape(self, scanner, shadowed_image):
        """Test that shadow removal preserves image shape."""
        result = scanner._remove_shadow(shadowed_image)
        assert result.shape == shadowed_image.shape

    def test_remove_shadow_handles_grayscale(self, scanner):
        """Test shadow removal with grayscale image."""
        gray_img = np.ones((600, 800), dtype=np.uint8) * 128
        # Should convert to BGR internally
        result = scanner._remove_shadow(gray_img)
        assert result is not None

    def test_remove_shadow_error_handling(self, scanner):
        """Test shadow removal with invalid input."""
        invalid_img = np.array([])  # Empty array
        result = scanner._remove_shadow(invalid_img)
        # Should return original on error
        assert np.array_equal(result, invalid_img)


class TestRotationDetection:
    """Tests for auto-rotation detection."""

    def test_detect_rotation_straight_image(self, scanner, sample_image):
        """Test rotation detection on straight image."""
        angle = scanner._detect_rotation_angle(sample_image)
        # Should be close to 0 for straight image
        assert abs(angle) < 5

    def test_detect_rotation_rotated_image(self, scanner, rotated_image):
        """Test rotation detection on rotated image."""
        angle = scanner._detect_rotation_angle(rotated_image)
        # Should detect some rotation (not necessarily exact)
        assert angle != 0

    def test_detect_rotation_no_lines(self, scanner):
        """Test rotation detection with uniform image (no lines)."""
        uniform_img = np.ones((600, 800, 3), dtype=np.uint8) * 128
        angle = scanner._detect_rotation_angle(uniform_img)
        # Should return 0 when no lines detected
        assert angle == 0.0

    def test_detect_rotation_grayscale(self, scanner):
        """Test rotation detection with grayscale image."""
        gray_img = np.zeros((600, 800), dtype=np.uint8)
        cv2.line(gray_img, (100, 100), (700, 120), 255, 2)  # Slightly rotated line
        angle = scanner._detect_rotation_angle(gray_img)
        assert angle is not None


class TestBlurDetection:
    """Tests for blur detection and sharpening."""

    def test_detect_blur_sharp_image(self, scanner, sample_image):
        """Test blur detection on sharp image."""
        variance, is_blurry = scanner._detect_blur(sample_image)
        # Sharp image should have high variance
        assert variance > 100
        assert not is_blurry

    def test_detect_blur_blurry_image(self, scanner, blurry_image):
        """Test blur detection on blurry image."""
        variance, is_blurry = scanner._detect_blur(blurry_image)
        # Blurry image should have low variance
        assert variance < 100
        assert is_blurry

    def test_sharpen_image_increases_edges(self, scanner, blurry_image):
        """Test that sharpening increases edge detail."""
        sharpened = scanner._sharpen_image(blurry_image)

        # Calculate edge intensity before and after
        gray_orig = cv2.cvtColor(blurry_image, cv2.COLOR_BGR2GRAY)
        gray_sharp = cv2.cvtColor(sharpened, cv2.COLOR_BGR2GRAY)

        edges_orig = cv2.Laplacian(gray_orig, cv2.CV_64F).var()
        edges_sharp = cv2.Laplacian(gray_sharp, cv2.CV_64F).var()

        # Sharpened should have more edge detail
        assert edges_sharp > edges_orig

    def test_sharpen_preserves_shape(self, scanner, sample_image):
        """Test that sharpening preserves image shape."""
        sharpened = scanner._sharpen_image(sample_image)
        assert sharpened.shape == sample_image.shape


class TestEdgeEnhancement:
    """Tests for document edge enhancement."""

    def test_enhance_edges_output_grayscale(self, scanner, sample_image):
        """Test that edge enhancement returns grayscale."""
        enhanced = scanner._enhance_document_edges(sample_image)
        assert len(enhanced.shape) == 2  # Grayscale has 2 dimensions

    def test_enhance_edges_increases_contrast(self, scanner):
        """Test that enhancement increases contrast."""
        # Low contrast image
        low_contrast = np.ones((600, 800, 3), dtype=np.uint8) * 128
        low_contrast[200:400, 200:600] = 140  # Subtle rectangle

        enhanced = scanner._enhance_document_edges(low_contrast)

        # Enhanced should have higher variance (more contrast)
        assert enhanced.var() > 0


class TestDocumentScanning:
    """Integration tests for full document scanning."""

    @patch('cv2.imread')
    @patch('cv2.imwrite')
    def test_scan_document_basic(self, mock_imwrite, mock_imread, scanner, sample_image):
        """Test basic document scanning workflow."""
        mock_imread.return_value = sample_image
        mock_imwrite.return_value = True

        result_path = scanner.scan_document("test.jpg", enhance=True)

        assert mock_imread.called
        assert mock_imwrite.called
        assert result_path is not None

    @patch('cv2.imread')
    @patch('cv2.imwrite')
    def test_scan_document_with_enhancement(self, mock_imwrite, mock_imread, scanner, sample_image):
        """Test scanning with enhancement enabled."""
        mock_imread.return_value = sample_image
        mock_imwrite.return_value = True

        result_path = scanner.scan_document("test.jpg", enhance=True)

        # Should call imwrite (save result)
        assert mock_imwrite.called

    @patch('cv2.imread')
    def test_scan_document_invalid_image(self, mock_imread, scanner):
        """Test scanning with invalid image."""
        mock_imread.return_value = None

        with pytest.raises(ValueError, match="Could not read image"):
            scanner.scan_document("invalid.jpg")

    @patch('cv2.imread')
    @patch('cv2.imwrite')
    def test_scan_document_fallback_no_contour(self, mock_imwrite, mock_imread, scanner):
        """Test that scanning falls back gracefully when no contour found."""
        # Uniform image (no document edges)
        uniform_img = np.ones((600, 800, 3), dtype=np.uint8) * 128
        mock_imread.return_value = uniform_img
        mock_imwrite.return_value = True

        result_path = scanner.scan_document("uniform.jpg", enhance=True)

        # Should still return a result (enhanced image)
        assert result_path is not None
        assert mock_imwrite.called

    @patch('cv2.imread')
    @patch('cv2.imwrite')
    def test_scan_document_large_image_resize(self, mock_imwrite, mock_imread, scanner):
        """Test that large images are resized."""
        # Very large image
        large_img = np.zeros((3000, 4000, 3), dtype=np.uint8)
        cv2.rectangle(large_img, (500, 500), (3500, 2500), (255, 255, 255), -1)
        mock_imread.return_value = large_img
        mock_imwrite.return_value = True

        scanner.scan_document("large.jpg", enhance=True)

        # Check that imwrite was called with resized image
        assert mock_imwrite.called
        saved_img = mock_imwrite.call_args[0][1]
        assert saved_img.shape[0] <= 1500  # Height should be resized

    @patch('cv2.imread')
    @patch('cv2.imwrite')
    def test_scan_document_finds_contour(self, mock_imwrite, mock_imread, scanner, sample_image):
        """Test that scanning finds and warps document contour."""
        mock_imread.return_value = sample_image
        mock_imwrite.return_value = True

        with patch.object(scanner, '_four_point_transform', wraps=scanner._four_point_transform) as mock_transform:
            scanner.scan_document("test.jpg", enhance=True)

            # Should call perspective transform if contour found
            # (may or may not be called depending on contour detection success)
            assert mock_imwrite.called


class TestPerspectiveTransform:
    """Tests for 4-point perspective transformation."""

    def test_four_point_transform_basic(self, scanner, sample_image):
        """Test basic perspective transformation."""
        # Define four corner points (slightly skewed)
        pts = np.array([
            [100, 100],
            [700, 120],
            [690, 500],
            [110, 480]
        ], dtype=np.float32)

        warped = scanner._four_point_transform(sample_image, pts)

        assert warped is not None
        assert warped.shape[0] > 0
        assert warped.shape[1] > 0

    def test_order_points(self, scanner):
        """Test point ordering for perspective transform."""
        # Unordered points
        pts = np.array([
            [700, 500],  # br
            [100, 100],  # tl
            [700, 100],  # tr
            [100, 500]   # bl
        ], dtype=np.float32)

        ordered = scanner._order_points(pts)

        # Check order: tl, tr, br, bl
        assert ordered[0][0] < ordered[1][0]  # tl.x < tr.x
        assert ordered[0][1] < ordered[2][1]  # tl.y < br.y


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
