# Document Portal API Documentation

## Interactive API Documentation

Document Portal provides comprehensive interactive API documentation through OpenAPI/Swagger UI.

### Accessing the Documentation

Once the server is running, visit:

```
http://localhost:8000/docs
```

This opens the **Swagger UI** with:
- ✅ Interactive API testing
- ✅ Request/response examples
- ✅ Schema validation
- ✅ Try-it-out functionality

### Alternative Documentation

For a simpler view, visit:

```
http://localhost:8000/redoc
```

This opens **ReDoc** with:
- ✅ Clean, three-panel layout
- ✅ Code samples in multiple languages
- ✅ Easier navigation

### Downloading the OpenAPI Schema

Get the raw OpenAPI JSON schema:

```bash
curl http://localhost:8000/openapi.json > openapi.json
```

---

## Quick Start Guide

### 1. Start the Server

```bash
# Development mode
uvicorn api.main:app --reload --port 8000

# Production mode
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 2. Explore the API

Navigate to `http://localhost:8000/docs` and you'll see:

- **📋 health** - Service status
- **🆔 id-extraction** - ID processing
- **✅ verification** - ID-to-contract matching
- **📦 invoice** - Invoice/receipt extraction
- **📄 document** - Document scanning
- **📜 compliance** - Compliance checking

### 3. Try an Endpoint

Example: Extract ID information

1. Click on **`POST /extract/id`** under `id-extraction`
2. Click **"Try it out"**
3. Upload an ID image
4. Set parameters:
   - `use_vision`: `true` (enable AI extraction)
   - `user_id`: `test_user_123` (optional, for caching)
5. Click **"Execute"**
6. View the response below

---

## API Endpoints Reference

### Health Check

#### `GET /`

Check service status.

**Response:**
```json
{
  "status": "ok",
  "service": "Document Portal",
  "version": "2.0.0"
}
```

---

### ID Extraction

#### `POST /extract/id`

Extract structured information from ID images (Driver's License, State ID, Passport).

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | File | Yes | ID image (JPG, PNG) |
| `user_id` | String | No | User ID for caching results |
| `use_vision` | Boolean | No | Enable Gemini Vision (default: true) |

**Request Example:**

```bash
curl -X POST "http://localhost:8000/extract/id" \
  -F "file=@drivers_license.jpg" \
  -F "use_vision=true" \
  -F "user_id=user123"
```

**Response Example:**

```json
{
  "extracted": {
    "data": {
      "full_name": "John Michael Smith",
      "first_name": "John",
      "middle_name": "Michael",
      "last_name": "Smith",
      "address": {
        "street": "123 Main St",
        "city": "Austin",
        "state": "TX",
        "zip": "78701"
      },
      "dob": "01/15/1990",
      "expiration_date": "01/15/2028",
      "license_number": "D12345678",
      "sex": "M",
      "height": "5'10\"",
      "issuing_state": "TX"
    },
    "confidence": 95,
    "method": "gemini_vision",
    "validation": {
      "valid": true,
      "age": 34,
      "is_expired": false,
      "errors": [],
      "warnings": []
    }
  },
  "source": "extraction",
  "method_used": "gemini_vision"
}
```

---

### ID-to-Contract Verification

#### `POST /verify/id_to_contract`

Verify that ID information matches contract party data.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `id_file` | File | Yes | ID image |
| `contract_file` | File | No* | Contract PDF/image |
| `contract_data_json` | String | No* | Contract party data as JSON |
| `verification_fields` | String | No | Fields to verify (default: "name,address,dob") |

*Either `contract_file` or `contract_data_json` must be provided.

**Request Example:**

```bash
curl -X POST "http://localhost:8000/verify/id_to_contract" \
  -F "id_file=@id.jpg" \
  -F 'contract_data_json={"party_name":"John Smith","party_address":"123 Main St, Austin, TX","party_dob":"01/15/1990"}' \
  -F "verification_fields=name,address,dob"
```

**Response Example:**

```json
{
  "id_extraction": {
    "data": {
      "full_name": "John Michael Smith",
      "address": {...},
      "dob": "01/15/1990"
    },
    "confidence": 95,
    "method": "gemini_vision"
  },
  "contract_data": {
    "party_name": "John Smith",
    "party_address": "123 Main St, Austin, TX",
    "party_dob": "01/15/1990"
  },
  "verification_result": {
    "overall_match": true,
    "overall_score": 92.5,
    "field_results": {
      "name": {
        "match": true,
        "score": 95,
        "method": "fuzzy_components",
        "details": {
          "first_name_score": 100,
          "last_name_score": 100,
          "middle_name_match": true
        }
      },
      "address": {
        "match": true,
        "score": 90,
        "method": "normalized_comparison",
        "component_matches": {
          "number": true,
          "street_name": true,
          "city": true,
          "state": true
        }
      },
      "dob": {
        "match": true,
        "score": 100,
        "method": "exact_date"
      }
    },
    "recommendation": "verified"
  },
  "status": "success"
}
```

**Recommendation Values:**
- `verified`: Overall score ≥ 85%, all fields match
- `review_required`: Score 60-85%, manual review suggested
- `rejected`: Score < 60%, verification failed

---

### Invoice Extraction

#### `POST /extract/invoice`

Extract structured data from invoices and receipts with POS-ready output.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `files[]` | File | Yes | Invoice images (supports multiple) |
| `use_gemini` | Boolean | No | Use AI extraction (default: true) |

**Request Example:**

```bash
curl -X POST "http://localhost:8000/extract/invoice" \
  -F "files=@invoice_page1.jpg" \
  -F "files=@invoice_page2.jpg" \
  -F "use_gemini=true"
```

**Response Example:**

```json
{
  "batch_count": 2,
  "merged_count": 1,
  "results": [
    {
      "filename": "invoice_page1.jpg",
      "extracted": {
        "data": {
          "doc_type": "Invoice",
          "vendor": {
            "name": "Coca-Cola Bottling Company",
            "phone": "555-1234",
            "vendor_id": "V12345"
          },
          "invoice_details": {
            "number": "INV-2024-001",
            "date": "2024-01-15",
            "terms": "Net 30"
          },
          "financials": {
            "total_amount": 1234.56,
            "subtotal": 1150.00,
            "tax": 84.56,
            "tax_rate": 7.35
          },
          "line_items": [
            {
              "item_number": 1,
              "description": "Coca-Cola 12oz 24-Pack",
              "brand": "Coca-Cola",
              "upc": "049000042566",
              "sku": "CC-12-24",
              "quantity": 10,
              "unit_of_measure": "CS",
              "pack_size": "24-pack",
              "unit_price": 12.99,
              "total_price": 129.90,
              "category": "Beverage"
            },
            {
              "item_number": 2,
              "description": "Sprite 20oz 12-Pack",
              "brand": "Sprite",
              "upc": "049000050103",
              "sku": "SP-20-12",
              "quantity": 5,
              "unit_of_measure": "CS",
              "pack_size": "12-pack",
              "unit_price": 9.99,
              "total_price": 49.95,
              "category": "Beverage"
            }
          ]
        },
        "confidence": 95
      },
      "is_merged": true,
      "merged_page_count": 2
    }
  ]
}
```

---

### Document Scanning

#### `POST /scan/document`

Preprocess document images with background removal and perspective correction.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | File | Yes | Document image |

**Request Example:**

```bash
curl -X POST "http://localhost:8000/scan/document" \
  -F "file=@receipt_photo.jpg" \
  --output scanned_receipt.jpg
```

**Response:**
Returns the scanned image as JPEG.

---

## Error Handling

All endpoints return standard HTTP status codes:

### Success Codes
- `200 OK`: Request succeeded
- `201 Created`: Resource created

### Client Error Codes
- `400 Bad Request`: Invalid input (e.g., malformed JSON)
- `422 Unprocessable Entity`: Validation error (e.g., missing required field)

### Server Error Codes
- `500 Internal Server Error`: Processing failed (check logs)

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

---

## Rate Limiting

Currently no rate limiting is enforced in development mode.

**Production Recommendations:**
- Implement rate limiting middleware
- Use API keys for authentication
- Set limits: 100 req/hour (free), unlimited (premium)

---

## Best Practices

### 1. Image Quality

For best results:
- ✅ Use well-lit, clear images
- ✅ Ensure document fills most of frame
- ✅ Avoid extreme angles (< 30° tilt)
- ✅ Minimum resolution: 800x600
- ✅ Formats: JPG, PNG (max 10MB)

### 2. Batch Processing

For multiple invoices:
- ✅ Group by vendor for better merging
- ✅ Upload in sequence (page 1, then page 2)
- ✅ Max 50 files per batch

### 3. Caching

Use `user_id` parameter to enable caching:
- ✅ Reduces API calls for same user
- ✅ Improves response time
- ✅ Cache TTL: 24 hours

### 4. Error Handling

Always check:
- ✅ `confidence` score (min 50% recommended)
- ✅ `validation.valid` field for IDs
- ✅ `recommendation` field for verification

---

## Testing with Swagger UI

### Test ID Extraction

1. Navigate to `/docs`
2. Expand `POST /extract/id`
3. Click **Try it out**
4. Upload a sample ID image
5. Enable `use_vision`
6. Execute and view results

### Test ID Verification

1. Expand `POST /verify/id_to_contract`
2. Upload ID image
3. Provide contract data:
   ```json
   {
     "party_name": "John Smith",
     "party_address": "123 Main St, Austin, TX 78701",
     "party_dob": "01/15/1990"
   }
   ```
4. Execute and check `recommendation`

---

## Code Generation

Swagger UI provides code snippets in multiple languages:

1. Click on any endpoint
2. Click **"Try it out"** and execute
3. Click **"Code"** button (appears after execution)
4. Copy generated code for:
   - cURL
   - Python (requests)
   - JavaScript (fetch)
   - Java
   - C#
   - PHP

---

## Support

For questions or issues:
- 📧 Email: support@documentportal.com
- 📖 Docs: `/docs` or `/redoc`
- 🐛 Issues: GitHub repository

---

**Document Portal API v2.0.0**
*Production-ready intelligent document processing*
