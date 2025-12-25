# Verifier Module Changes

Date: 2025-12-25

Summary:
- Added `document_portal_core/verifier.py` implementing:
  - Deterministic checks (exact and normalized substring matches).
  - Fuzzy matching using `rapidfuzz` when available, with a `difflib` fallback.
  - Clause verification with evidence excerpts and scoring.
  - `quick_verify()` for synchronous quick-checks across common claim structures (party names, addresses, expected clause text).
  - A demo in-memory background job scaffold: `enqueue_llm_verification()` and `get_job_result()`.

Files added:
- `document_portal_core/verifier.py` — main implementation.
- `tests/test_verifier.py` — unit tests covering exact, fuzzy, clause, quick_verify, and job enqueue.
- `api/main.py` — new `/verify` endpoint integrated with ingestion and verifier.

Usage (API):
- POST `/verify` (multipart/form-data)
  - `file`: uploaded document (image/pdf/docx)
  - `claims`: JSON string with claimed metadata, e.g.:
    ```json
    {
      "party_a": {"name": "Alice Corp", "address": "123 Main St."},
      "party_b": {"name": "Bob LLC", "address": "456 Side Ave."},
      "expected_changes": [{"expected_text": "Term shall be two years."}]
    }
    ```
  - `enqueue_llm` (boolean form field): if true, enqueues a demo LLM verification job and returns `job_id`.

Notes & Next Steps:
- The background job scaffold is a demo in-memory implementation. For production, replace with Celery/RQ and persist JOB_STORE in a durable store.
- Consider persisting Faiss indexes for large-scale candidate lookup and integrating semantic search for clause/evidence extraction.
- For better entity extraction (addresses, names), integrate a lightweight NER pipeline (spaCy or HuggingFace models) to normalize and canonicalize entities before verification.
- Add CI test runner integration to execute `pytest` in the project environment; ensure system dependencies (OpenCV, Tesseract) are available where needed.
