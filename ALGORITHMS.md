# Document Portal: Algorithms & Processing Logic

This document details the technical implementation, algorithms, and models used for key extraction features.

## 1. ID Verification System

The ID extraction uses a **Deterministic Heuristic Approach** optimized for speed and strict validation.

### Extraction Logic (Regex)
We use highly specific Regular Expressions to locate key fields within the OCR text (Raw string from Tesseract or other sources).
*   **Driver's License**: Matches standard patterns (e.g., 7+ alphanumeric chars following "DL", "LIC", "NO").
*   **Dates (DOB/EXP)**: Matches `MM/DD/YYYY` or `MM-DD-YYYY` formats following key labels like "DOB", "BIRTH", "EXP", "EXPIRES".
*   **Demographics**: Regex capture for Sex (M/F) and Height (Feet/Inches).

### Validation Logic (Algorithmic)
Once raw data is extracted, it passes through a validation layer (`validate_id_data`) to ensure logical consistency and compliance.

1.  **Date Standardization**: All dates are normalized to Python `datetime` objects.
2.  **Age Calculation**:
    *   Formula: `Age = Today.Year - DOB.Year - ((Today.Month, Today.Day) < (DOB.Month, DOB.Day))`
    *   **Check**: If `Age < 0`, the ID is flagged as Invalid (Future DOB).
    *   **Warning**: If `Age < 18` or `Age < 21`, a warning flag is raised for Frontend UI alerts.
3.  **Expiration Enforcement**:
    *   **Check**: If `Expiration_Date < Today`, the ID is flagged as **Invalid**.
    *   **Consistency**: If `Expiration_Date < DOB`, the ID is flagged as malformed.

### Confidence Scoring
Confidence is calculated heuristically based on information density:
*   `Score = min(Field_Count * 20, 100)`
*   Example: Finding DOB, Exp, and License Number = 60% base confidence (configurable).

---

## 2. Invoice Extraction System (Hybrid AI)

The Invoice Extractor implements a **Hybrid Pipeline** that chooses the best tool for the job based on confidence requirements.

### Mode A: High-Fidelity API (Default)
**Model**: **Google Gemini 2.0 Flash** (Multimodal LLM)

*   **Architecture**: The system sends the raw image (JPG/PNG/PDF) directly to the Gemini Vision API.
*   **Prompt Engineering**: A structured prompt instructs the model to extract specific fields (`vendor_name`, `total_amount`, `date`, `invoice_number`) and classify the document (`Invoice`, `Shift Report`, `Lottery`).
*   **Output**: Structured JSON.
*   **Performance**: Benchmarks show **95%+ Confidence** on variable layouts where standard OCR fails.

### Mode B: Low-Cost / Offline Fallback
**Engine**: **Tesseract OCR v5** + **Regex**

1.  **Advanced Preprocessing (`_preprocess_for_ocr`)**:
    *   **Resizing**: Images are upscaled/downscaled to ~3000px height for optimal OCR character recognition.
    *   **Grayscale & Thresholding**: Converts to B&W to remove color noise.
    *   **CLAHE**: *Contrast Limited Adaptive Histogram Equalization* is applied to enhance local contrast, making text readable even in shadowed or poorly lit scans.
2.  **Regex Parsing**:
    *   Iterates through OCR text lines looking for price patterns (`$\d+\.\d{2}`) and keywords ("TOTAL", "AMOUNT DUE").
    *   Uses keyword density to guess Vendor names.
3.  **Limitations**: Lower accuracy on receipts with complex layouts or handwriting.

## 3. Result Persistence
All extraction events are logged by the `ResultManager` to the `results/{model_name}/` directory.
*   **Log Format**: JSON
*   **Metrics**: `timestamp`, `duration_seconds`, `confidence_score`.
*   **Purpose**: Enables continuous accuracy monitoring and auditing.
