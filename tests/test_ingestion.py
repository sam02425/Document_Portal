"""
Unit tests for the Ingestion module in document_portal_core.
"""
import os
from pathlib import Path
from document_portal_core.ingestion import Ingestion

def test_ingest_txt(tmp_path):
    # Create a dummy text file (simulate OCR result)
    file_path = tmp_path / "test.txt"
    file_path.write_text("This is a test document.")
    ingestion = Ingestion()
    # Should raise ValueError for unsupported file type
    try:
        ingestion.ingest(file_path)
    except ValueError as e:
        assert "Unsupported file type" in str(e)

def test_ingest_image(tmp_path):
    # Create a dummy image file (blank white PNG)
    import numpy as np
    import cv2
    img = 255 * np.ones((100, 200, 3), dtype=np.uint8)
    img_path = tmp_path / "test.png"
    cv2.imwrite(str(img_path), img)
    ingestion = Ingestion()
    text = ingestion.ingest(img_path)
    assert isinstance(text, str)

def test_ingest_docx(tmp_path):
    # Create a dummy docx file
    from docx import Document
    docx_path = tmp_path / "test.docx"
    doc = Document()
    doc.add_paragraph("Hello world!")
    doc.save(str(docx_path))
    ingestion = Ingestion()
    text = ingestion.ingest(docx_path)
    assert "Hello world!" in text
