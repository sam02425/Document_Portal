import time
import sys
import os
import cv2
import numpy as np
import pytesseract

# Mock data generation
def create_dummy_id_image():
    # Create valid image for OCR to chew on - LARGE to trigger resize
    img = np.zeros((3000, 4000, 3), dtype=np.uint8)
    img.fill(255)
    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, 'TEXAS DRIVER LICENSE', (50, 50), font, 1, (0,0,0), 2)
    cv2.putText(img, 'DL: 12345678', (50, 100), font, 0.8, (0,0,0), 2)
    cv2.putText(img, 'DOB: 01/01/1980', (50, 150), font, 0.8, (0,0,0), 2)
    # Make it noisy to simulate real world
    noise = np.random.normal(0, 10, img.shape).astype(np.uint8)
    img = cv2.add(img, noise)
    return img

def benchmark():
    print("--- Starting Benchmark ---")
    
    # 1. Image Creation (Setup)
    img = create_dummy_id_image()
    
    # 2. OCR Benchmark
    start_ocr = time.time()
    text = pytesseract.image_to_string(img)
    end_ocr = time.time()
    ocr_time = end_ocr - start_ocr
    print(f"OCR Time (Tesseract): {ocr_time:.4f} seconds")
    
    # 3. Regex/Logic Benchmark
    # We'll use the extraction logic from our module
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from document_portal_core.extractor import IDExtractor
    
    extractor = IDExtractor()
    start_logic = time.time()
    # Run 1000 times to simulate load/get measurable time
    for _ in range(1000):
        _ = extractor.extract_from_text(text)
    end_logic = time.time()
    logic_time = (end_logic - start_logic) / 1000
    print(f"Logic Time (Regex) avg: {logic_time:.6f} seconds")
    
    # Conclusion
    ratio = ocr_time / logic_time
    print("-" * 30)
    print(f"OCR is {ratio:.1f}x slower than Logic.")
    
if __name__ == "__main__":
    benchmark()
