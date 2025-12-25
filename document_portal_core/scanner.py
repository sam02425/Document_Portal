"""
Document Scanner Module.
Implements 'CamScanner'-like logic:
1. Detect edges.
2. Find largest quadrilateral contour (the document).
3. Apply 4-point perspective transform to obtain a top-down 'scanned' view.
4. Apply adaptive thresholding for high-contrast legibility.
"""
import cv2
import numpy as np
from logger import GLOBAL_LOGGER as log
from pathlib import Path

class DocumentScanner:
    def scan_document(self, image_path: str, output_path: str = None) -> str:
        """
        Processes an image to extract the document page.
        Returns the path to the saved 'scanned' image.
        """
        try:
            # 1. Read Image
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Could not read image")

            ratio = 1
            # Resize for faster processing (detection phase) usually done on smaller image
            # specific size height 500
            h, w = img.shape[:2]
            if h > 1500: # optimization
                ratio = 1500 / h
                # We process on small image, but warp original
                # For simplicity in this v1, we just resize the actual image to avoid coord mapping complexity
                # If quality is paramount, we'd map coords back. 
                # For "Contract App", 1500px height is plenty sufficient for OCR.
                img = cv2.resize(img, (int(w*ratio), 1500))

            # 2. Preprocessing (Gray -> Blur -> Canny)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blur, 75, 200)

            # 3. Find Contours
            cnts, _ = cv2.findContours(edges.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            # Sort by area, largest first
            cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]

            doc_cnt = None
            for c in cnts:
                # Approximate the contour
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)

                # If has 4 points, we assume it's our document
                if len(approx) == 4:
                    doc_cnt = approx
                    break

            # 4. Perspective Transform
            if doc_cnt is not None:
                log.info("Document contour found, warping perspective.")
                warped = self._four_point_transform(img, doc_cnt.reshape(4, 2))
            else:
                log.warning("No document contour found. Returning original image.")
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
