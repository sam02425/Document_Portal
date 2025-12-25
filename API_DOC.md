# Document Portal API Integration Guide

This guide details how to integrate your web, mobile, or desktop application with the Document Portal API.

## Base URL
```
http://localhost:8000
```
*(Replace with deployed URL for production)*

## Authentication
Currently, the API is open for internal use. For production, we recommend wrapping it behind an API Gateway with API Key validation.

## Cross-Platform Support
*   **CORS Enabled**: The API supports requests from any origin (`*`), making it compatible with React, Vue, Flutter Web, and other browser-based apps.
*   **Standard JSON**: All non-file responses are standard JSON.
*   **Multipart/Form-Data**: All file uploads use standard multipart forms, supported natively by iOS (URLSession), Android (Retrofit/OkHttp), and Web (FormData).

---

## Endpoints

### 1. Extract ID Data
Extracts information from Driver's Licenses and Passports. Includes age verification and expiration checks.

*   **URL**: `/extract/id`
*   **Method**: `POST`
*   **Content-Type**: `multipart/form-data`

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | File | Yes | Image (JPG, PNG) of the ID. |
| `user_id` | String | No | Unique User ID for caching results. |

**Response Example:**
```json
{
  "extracted": {
    "data": {
      "dob": "05/15/1990",
      "expiration_date": "06/20/2030",
      "license_number": "D1234567"
    },
    "confidence": 100,
    "validation": {
      "valid": true,
      "age": 35,
      "is_expired": false,
      "warnings": []
    }
  },
  "source": "ocr"
}
```

**Integration Example (JavaScript/React):**
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('user_id', 'user_123');

const response = await fetch('http://localhost:8000/extract/id', {
  method: 'POST',
  body: formData
});
const result = await response.json();
```

### 2. Extract Invoice Data (High Confidence)
Extracts total amount, vendor, date, and document type from invoices and receipts.

*   **URL**: `/extract/invoice`
*   **Method**: `POST`
*   **Content-Type**: `multipart/form-data`

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `file` | File | Yes | - | Image of the invoice/receipt. |
| `use_gemini` | Boolean | No | `true` | Set to `true` for High Confidence AI (slower), `false` for Regex (faster). |

**Response Example:**
```json
{
  "filename": "invoice_001.jpg",
  "extracted": {
    "data": {
      "vendor_name": "Walmart",
      "total_amount": "45.20",
      "date": "2023-10-25",
      "doc_type": "Receipt"
    },
    "confidence": 95
  },
  "model_used": "gemini-2.0-flash"
}
```

### 3. Document Scanning (CamScanner Style)
Auto-crops and enhances a document image (perspective correction).

*   **URL**: `/scan/document`
*   **Method**: `POST`
*   **Content-Type**: `multipart/form-data`

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | File | Yes | Raw camera image. |

**Response**: Returns the processed **Image File** (image/jpeg).

### 4. Verify Contract
Verifies extracted text against a set of JSON claims.

*   **URL**: `/verify/contract`
*   **Method**: `POST`
*   **Content-Type**: `multipart/form-data`

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | File | Yes | Contract PDF/Image. |
| `claims_json` | String | Yes | JSON string of claims to verify (e.g. `{"rent": "1000"}`). |

### 5. Compliance Check
Checks a document for state-specific compliance (currently Texas Lease laws).

*   **URL**: `/analyze/compliance`
*   **Method**: `POST`
*   **Content-Type**: `multipart/form-data`

| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `file` | File | Yes | Document to analyze. |
