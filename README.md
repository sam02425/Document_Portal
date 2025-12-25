# Document Portal 🚀

**The Intelligent Document Processing Engine for Modern Applications.**

Document Portal is a high-performance, container-ready microservice designed to handle your toughest document extraction, verification, and compliance challenges. Whether you're building a FinTech app, a Property Management system, or a Legal Tech platform, Document Portal provides the heavy lifting.

---

## 🌟 Key Features

### 1. High-Confidence Invoice Extraction 🧾
*   **Hybrid AI Pipeline**: Combines **Google Gemini 2.0 Flash** (Multimodal LLM) with traditional OCR to achieve **95%+ accuracy**.
*   **Smart Classification**: Automatically distinctions between *Invoices*, *Shift Reports*, and *Lottery Tickets*.
*   **Structured Data**: Returns clean JSON with Vendor, Date, Total Amount, and Invoice Number.

### 2. Instant ID Verification 🪪
*   **Fast Regex Engine**: deterministic extraction for speed and privacy.
*   **Built-in Validation**:
    *   **Age Verification**: Automatically flages "Under 18" and "Under 21".
    *   **Expiration Check**: Rejects expired IDs instantly.
    *   **Logical Consistency**: Ensures DOB is not in the future.

### 3. Document Scanning & Enhancement 📷
*   **CamScanner-Style Processing**: Auto-detection of document corners and perspective cropping.
*   **Image Optimization**: Enhances contrast/brightness for poor-quality scans before processing.

### 4. Contract Logic & Compliance ⚖️
*   **Claim Verification**: Upload a contract and a list of expected values (e.g., Rent Amount, Lease Dates) to verify they match.
*   **Regulatory Analysis**: Built-in rules engine (currently optimized for Texas Residential Leases) to flag missing clauses.

---

## 🛠️ Integration Guide

Document Portal is built as a **REST API** with **CORS support**, making it ready for integration with:
*   **Web Apps**: React, Vue, Angular
*   **Mobile Apps**: iOS (Swift), Android (Kotlin), Flutter, React Native
*   **Backend Services**: Python, Node.js, Go

👉 **[Read the Full API Documentation](API_DOC.md)**  
👉 **[View Technical Algorithms](ALGORITHMS.md)**

---

## 🚀 Quick Start

### Prerequisites
*   Python 3.10+
*   `tesseract-ocr` installed on your system.
*   Valid API Keys for Gemini (optional, for High Confidence mode).

### Installation
1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/your-org/document-portal.git
    cd Document_Portal
    ```

2.  **Environment Setup**:
    Create a `.env` file:
    ```bash
    GOOGLE_API_KEY=your_gemini_key_here
    ```

3.  **Install Dependencies**:
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

4.  **Run the Server**:
    ```bash
    uvicorn api.main:app --reload
    ```
    The API will be live at `http://localhost:8000`.

### Testing
Run the provided benchmark script to see it in action:
```bash
python test_invoices.py
```

---

## 🔒 Security & Privacy
*   **Input Sanitization**: All temporary files are UUID-named and auto-deleted after processing.
*   **Result Persistence**: Logs (excluding sensitive images) are stored locally in `results/` for audit trails.
*   **Local-First Option**: Use `use_gemini=False` to process everything using local OCR (Tesseract) for maximum data privacy.

---

## 📞 Support
For enterprise support or custom rule configuration, contact [Curry Creations Support](mailto:support@currycreations.com).
