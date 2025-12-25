"""
Document Scanner Module.
Implements enhanced 'CamScanner'-like logic with advanced preprocessing:
1. Shadow removal and illumination normalization
2. Auto-rotation detection
3. Detect edges and find largest quadrilateral contour (the document)
4. Apply 4-point perspective transform to obtain a top-down 'scanned' view
5. Blur detection and sharpening
6. Fallback strategies for low-contrast backgrounds
"""
import cv2
import numpy as np
from logger import GLOBAL_LOGGER as log
from pathlib import Path
from typing import Optional, Tuple

class DocumentScanner:

    def _remove_shadow(self, img: np.ndarray) -> np.ndarray:
        """
        Removes shadows using illumination normalization.
        Uses morphological operations to estimate background illumination.
        """
        try:
            rgb_planes = cv2.split(img)
            result_planes = []

            for plane in rgb_planes:
                # Dilate to get background estimation
                dilated = cv2.dilate(plane, np.ones((7, 7), np.uint8))
                # Median blur to smooth the background
                bg = cv2.medianBlur(dilated, 21)
                # Subtract background and normalize
                diff = 255 - cv2.absdiff(plane, bg)
                # Normalize to full range
                norm = cv2.normalize(diff, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
                result_planes.append(norm)

            result = cv2.merge(result_planes)
            return result
        except Exception as e:
            log.warning(f"Shadow removal failed: {e}, returning original")
            return img

    def _detect_rotation_angle(self, img: np.ndarray) -> float:
        """
        Detects text orientation angle for auto-rotation.
        Returns angle in degrees.
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            # Use Canny edge detection
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)
            # Detect lines using HoughLines
            lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

            if lines is None:
                return 0.0

            # Calculate median angle
            angles = []
            for rho, theta in lines[:, 0]:
                angle = np.degrees(theta) - 90
                angles.append(angle)

            if angles:
                median_angle = np.median(angles)
                # Snap to nearest 90-degree rotation if close
                if abs(median_angle) < 5:
                    return 0
                elif abs(median_angle - 90) < 5 or abs(median_angle + 90) < 5:
                    return 90 if median_angle > 0 else -90
                else:
                    return median_angle
            return 0.0
        except Exception as e:
            log.warning(f"Rotation detection failed: {e}")
            return 0.0

    def _detect_blur(self, img: np.ndarray) -> Tuple[float, bool]:
        """
        Detects if image is blurry using Laplacian variance.
        Returns (variance, is_blurry) tuple.
        Threshold: variance < 100 indicates blur.
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            is_blurry = laplacian_var < 100
            return laplacian_var, is_blurry
        except Exception as e:
            log.warning(f"Blur detection failed: {e}")
            return 0.0, False

    def _sharpen_image(self, img: np.ndarray) -> np.ndarray:
        """
        Applies unsharp masking to sharpen blurry images.
        """
        try:
            kernel = np.array([[-1,-1,-1],
                             [-1, 9,-1],
                             [-1,-1,-1]])
            sharpened = cv2.filter2D(img, -1, kernel)
            return sharpened
        except Exception as e:
            log.warning(f"Sharpening failed: {e}")
            return img

    def _enhance_document_edges(self, img: np.ndarray) -> np.ndarray:
        """
        Enhances document edges for better contour detection.
        Useful for low-contrast backgrounds.
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Apply bilateral filter to reduce noise while keeping edges sharp
            bilateral = cv2.bilateralFilter(gray, 9, 75, 75)

            # Adaptive histogram equalization for better contrast
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(bilateral)

            return enhanced
        except Exception as e:
            log.warning(f"Edge enhancement failed: {e}")
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    def scan_document(self, image_path: str, output_path: str = None, enhance: bool = True) -> str:
        """
        Processes an image to extract the document page with advanced preprocessing.

        Args:
            image_path: Path to input image
            output_path: Optional path for output (auto-generated if None)
            enhance: Apply shadow removal and sharpening (default: True)

        Returns:
            Path to the saved 'scanned' image
        """
        try:
            # 1. Read Image
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Could not read image")

            original_img = img.copy()

            # 2. Auto-rotation detection
            rotation_angle = self._detect_rotation_angle(img)
            if abs(rotation_angle) > 2:  # Only rotate if angle is significant
                log.info(f"Auto-rotating image by {rotation_angle:.2f} degrees")
                h, w = img.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, rotation_angle, 1.0)
                img = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

            # 3. Shadow removal (if enhancement enabled)
            if enhance:
                img = self._remove_shadow(img)
                log.info("Applied shadow removal")

            # 4. Blur detection and sharpening
            blur_var, is_blurry = self._detect_blur(img)
            if is_blurry and enhance:
                log.info(f"Blur detected (variance: {blur_var:.2f}), applying sharpening")
                img = self._sharpen_image(img)

            # 5. Resize for faster processing
            h, w = img.shape[:2]
            ratio = 1
            if h > 1500:
                ratio = 1500 / h
                img = cv2.resize(img, (int(w*ratio), 1500))

            # 6. Enhanced edge detection with fallback
            enhanced_gray = self._enhance_document_edges(img)
            blur = cv2.GaussianBlur(enhanced_gray, (5, 5), 0)
            edges = cv2.Canny(blur, 50, 150)  # Slightly lower thresholds for better detection

            # 7. Find Contours
            cnts, _ = cv2.findContours(edges.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            # Sort by area, largest first
            cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:10]  # Check more contours

            doc_cnt = None
            # Try to find a 4-point contour (document shape)
            for c in cnts:
                # Approximate the contour
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)

                # If has 4 points, we assume it's our document
                if len(approx) == 4:
                    # Additional check: ensure contour is large enough (at least 10% of image area)
                    area = cv2.contourArea(approx)
                    img_area = img.shape[0] * img.shape[1]
                    if area > img_area * 0.1:
                        doc_cnt = approx
                        break

            # 8. Perspective Transform or fallback
            if doc_cnt is not None:
                log.info("Document contour found, warping perspective.")
                warped = self._four_point_transform(img, doc_cnt.reshape(4, 2))
            else:
                log.warning("No document contour found. Using enhanced image without perspective correction.")
                # Fallback: Use the enhanced image (shadow removed, sharpened)
                warped = img

            # 5. Post-process (Scan Effect) - Optional
            # Convert to grayscale and apply threshold to make it look like a photocopy
            # warped_gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
            # scanned = cv2.adaptiveThreshold(warped_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            
            # For now, return color scan as it's often preferred for IDs
            scanned = warped

            # Save
            if output_path is None:
                output_path = image_path.replace(".", "_scanned.")
            
            cv2.imwrite(output_path, scanned)
            return output_path

        except Exception as e:
            log.error(f"Scan failed: {e}")
            return image_path # Fallback

    def _four_point_transform(self, image, pts):
        # 1. Order points (tl, tr, br, bl)
        rect = self._order_points(pts)
        (tl, tr, br, bl) = rect

        # 2. Compute width/height of new image
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        # 3. Construct destination points
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")

        # 4. Get transform matrix and warp
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        return warped

    def _order_points(self, pts):
        # Initialzie a list of coordinates: top-left, top-right, bottom-right, bottom-left
        rect = np.zeros((4, 2), dtype="float32")

        # Top-left has smallest sum, Bottom-right has largest sum
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        # Top-right has smallest diff, Bottom-left has largest diff
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]

        return rect
