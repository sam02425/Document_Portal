"""
Document ingestion and preprocessing logic for Document Portal.
This module provides the Ingestion class for robustly handling PDFs, Word files, and images.
It automatically corrects image orientation, de-skews, and extracts text using OCR.
It is designed for speed and reliability, even with poorly taken photos.
"""
import sys
from typing import Union
from pathlib import Path
import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from docx import Document as DocxDocument
from PIL import Image, ImageOps
from logger import GLOBAL_LOGGER as log
from exception.custom_exception import DocumentPortalException

class Ingestion:
    """
    Unified document ingestion for images, PDFs, and Word files.
    Automatically corrects image orientation and extracts text.
    """
    def __init__(self):
        pass

    def ingest(self, file_path: Union[str, Path]) -> str:
        """
        Ingest a document (image, PDF, or Word) and return extracted text.
        Args:
            file_path (str | Path): Path to the file.
        Returns:
            str: Extracted text content.
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        # Validate supported file types first so callers get clear errors
        if suffix in {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}:
            try:
                return self._process_image(file_path)
            except Exception as e:
                log.error("Failed to ingest image", error=str(e))
                raise DocumentPortalException("Document ingestion failed", sys)
        elif suffix == '.pdf':
            try:
                return self._process_pdf(file_path)
            except Exception as e:
                log.error("Failed to ingest PDF", error=str(e))
                raise DocumentPortalException("Document ingestion failed", sys)
        elif suffix == '.docx':
            try:
                return self._process_docx(file_path)
            except Exception as e:
                log.error("Failed to ingest DOCX", error=str(e))
                raise DocumentPortalException("Document ingestion failed", sys)
        else:
            # Unsupported file types should raise a ValueError for callers to handle
            raise ValueError(f"Unsupported file type: {suffix}")

    def _process_image(self, image_path: Path) -> str:
        try:
            img = cv2.imread(str(image_path))
            img = self._auto_orient_image(img)
            pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            try:
                text = pytesseract.image_to_string(pil_img)
            except Exception as e:
                log.warning("Tesseract OCR failed or not available; returning empty text", error=str(e))
                text = ""
            return text
        except Exception as e:
            log.error("Image processing failed", error=str(e))
            raise

    def _auto_orient_image(self, img: np.ndarray) -> np.ndarray:
        # Use OpenCV and Tesseract to auto-rotate and de-skew
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            coords = np.column_stack(np.where(gray > 0))
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            return rotated
        except Exception as e:
            log.warning("Auto-orientation failed, returning original image", error=str(e))
            return img

    def _process_pdf(self, pdf_path: Path) -> str:
        try:
            images = convert_from_path(str(pdf_path))
            text = ""
            for img in images:
                img = ImageOps.exif_transpose(img)
                try:
                    text += pytesseract.image_to_string(img)
                except Exception as e:
                    log.warning("Tesseract OCR failed on PDF page; skipping page", error=str(e))
                    continue
            return text
        except Exception as e:
            log.error("PDF processing failed", error=str(e))
            raise

    def _process_docx(self, docx_path: Path) -> str:
        try:
            doc = DocxDocument(str(docx_path))
            text = "\n".join([p.text for p in doc.paragraphs])
            return text
        except Exception as e:
            log.error("DOCX processing failed", error=str(e))
            raise
