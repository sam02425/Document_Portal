# Document Portal — Requirements and SDLC Guidance

This document captures the functional requirements and the Software Development Life Cycle (SDLC) requirements for the Document Portal application (contract analysis, comparison, graph extraction, verification, RAG). It is intended to serve as a reference for developers, QA, DevOps, and product owners.

**Repository location:** `Document_Portal/`

---

**Table of Contents**
- **Functional Requirements**
  - Summary
  - User stories
  - API contract (endpoints, inputs, outputs)
  - Data models and expected payloads
  - Acceptance criteria and example requests
- **Non-Functional & SDLC Requirements**
  - Quality & testing (unit, integration, e2e)
  - CI/CD and release process
  - Deployment & environment management
  - Observability (logging, metrics, tracing)
  - Security & secrets management
  - Performance, scaling & capacity planning
  - Backup & data retention
  - Maintenance & operational runbook
- **Appendix**
  - Recommended tools and libraries
  - Next steps / roadmap

---

**FUNCTIONAL REQUIREMENTS**

Summary
- The Document Portal ingests contracts (images, PDFs, DOCX), extracts text robustly (auto-rotate, de-skew, OCR), and provides several capabilities:
  - `Analyze`: extract structured metadata and summaries.
  - `Compare`: compare two documents and produce a structured differences report.
  - `Graph`: extract relationships between parties/clauses and return nodes + edges for visualization.
  - `Verify`: verify user-provided claims (party names/addresses/updated clauses) against the document content with evidence-backed results; supports a fast synchronous quick-check and optional LLM background enrichment.
  - `Chat/RAG`: conversational retrieval over indexed documents using a Faiss-backed retriever.

User stories (examples)
- As a user, I can upload a contract image and receive a structured summary, party names, and key clauses.
- As a user, I can upload a reference contract and an actual contract and get a table of differences and suggested amendments.
- As a user, I can submit claimed metadata (party names/addresses/clauses) and receive a verification report that includes scores and evidence excerpts.
- As a developer, I can index a set of documents into a Faiss index and perform conversational Q&A using the `chat` endpoints.

API contract (high level)
- Base path: application root; implemented with FastAPI in `api/main.py`.

Endpoints (current):
- `GET /health` — health check (returns {status: ok}).
- `POST /analyze` — accepts `file: UploadFile` (image/pdf/docx)
  - Input: multi-part form with `file` (binary). Optional query/form options may be added later.
  - Output: JSONAnalysis (structured metadata, summary, key clauses, extraction confidence).
  - Errors: 400 for invalid file, 500 for server errors.
- `POST /compare` — accepts `reference: UploadFile`, `actual: UploadFile`
  - Input: two files.
  - Output: JSON with `rows` containing the comparison DataFrame records.
- `POST /graph` — accepts `reference: UploadFile`, `actual: UploadFile`
  - Output: {nodes: [...], edges: [...]} describing relationships.
- `POST /verify` — accepts `file: UploadFile`, `claims: JSON string`, `enqueue_llm: bool` (form fields)
  - Input claims: JSON string with keys like `party_a`, `party_b`, `expected_changes`.
  - Output: `quick_report` with checks and summary, optionally `job_id` and `job_status` when LLM enrichment is requested.
- `POST /chat/index` — file list indexing into Faiss (session-based indexing).
- `POST /chat/query` — conversational query to Faiss-backed RAG chain.

Detailed request/response examples (minimal)
- `POST /verify` (multipart/form-data)
  - `file`: binary file
  - `claims`: JSON string, e.g.
    {
      "party_a": {"name": "Alice Corp", "address": "123 Main St."},
      "party_b": {"name": "Bob LLC", "address": "456 Side Ave."},
      "expected_changes": [{"expected_text": "Term shall be two years."}]
    }
  - Response: {"quick_report": {...}, "job_id": "..." (optional)}

Data models & shape
- Analysis result (example keys):
  - `summary`: str
  - `parties`: [{name, role, address, confidence}]
  - `clauses`: [{clause_id, text, clause_type, confidence, excerpt_start, excerpt_end}]
- Verify report:
  - `checks`: [{id, type, value, result, score, method, excerpt?}]
  - `summary`: {average_score}
- Comparison result: DataFrame rows with columns like `section`, `reference_text`, `actual_text`, `difference_type`, `severity`, `recommendation`.

Acceptance criteria (examples)
- For `analyze`: given a clean PDF with parties and a term clause, the endpoint returns party names and a `term` clause with confidence >= 0.7.
- For `verify`: when the claimed party name appears exactly in text, `verify` returns `pass` with score 100 and `method` = `exact`.
- For `compare`: the result includes rows for any clause text that differs between the two documents; automated tests validate detection for synthetic input.

---

**NON-FUNCTIONAL & SDLC REQUIREMENTS**

Quality & testing
- Unit tests: all core modules must have unit tests (ingestion, analyzer, comparator, graph, rag, verifier). Tests live in `tests/`.
  - Target coverage: at least 70% for core modules; aim for 85% over time.
- Integration tests: test full ingestion -> analyze -> verify flows using representative files.
- End-to-end tests: scriptable e2e tests for the API endpoints using a test runner (e.g., pytest + httpx/requests). Use fixtures to swap external calls with mocks.
- Test data: keep small, synthetic test fixtures in `tests/fixtures/` and avoid sharing real PII.

CI/CD
- Pipeline (GitHub Actions recommended):
  - Steps: lint (flake8/ruff), type-check (mypy), unit tests (pytest), build package (optional), build Docker image, security scan (safety/Dependabot alerts), and publish artifacts (if applicable).
  - PR gating: require tests && lint to pass before merge to `main`.
- Branching: use feature branches; PRs must be reviewed and approved. Protect `main` branch.
- Releases: tag releases (semver) and update change log. Use a changelog file (e.g., `CHANGELOG.md`) or maintain release notes.

Deployment & environments
- Environments: `dev`, `staging`, `prod`.
- Containerization: provide `Dockerfile` (already present) and optionally `docker-compose` for local development (app + worker + redis for background jobs).
- Orchestration: deploy to Kubernetes or a managed container service (ECS, GKE, AKS) with an image registry (Docker Hub, ECR, GCR).
- Environment variables: all secrets and credentials (API keys, model credentials) must be stored in a secret store (Vault, AWS Secrets Manager, or k8s secrets).
- Config: keep non-secret configuration in files like `config/config.yaml` and document expected keys.

Observability
- Logging: structured logs (JSON) at appropriate levels. Use `logger/custom_logger.py` with `GLOBAL_LOGGER` wrapper.
- Metrics: export basic metrics via Prometheus (requests per endpoint, latencies, error counts, queue lengths for background jobs).
- Tracing: add distributed tracing (OpenTelemetry) for request traces across ingestion -> LLM -> Faiss calls.
- Alerts: configure alerting for high error rates, job failures, and resource exhaustion.

Security & privacy
- Authentication & Authorization:
  - Enforce API authentication (JWT or API keys) on endpoints that expose sensitive data (analyze/compare/verify/chat).
  - Provide role-based access control for admin operations (index rebuilds, index deletion).
- Data protection:
  - Use TLS for all transport.
  - Encrypt sensitive persisted data at rest (indexes with access controls, any stored documents).
  - Scrub or avoid storing PII in tests and logs. When logging, avoid printing full document contents.
- Secrets: never commit secrets. Use environment-managed secrets.
- Third-party dependencies:
  - Regularly scan dependencies for vulnerabilities. Pin versions in `requirements.txt` or `pyproject.toml`.

Performance & scaling
- Latency targets:
  - Quick-check verification should complete under 2s for small documents in normal conditions (depends on I/O and OCR).
  - LLM-based analysis may take longer; provide asynchronous processing and progress tracking.
- Throughput and scaling:
  - Horizontally scale API workers behind a load balancer.
  - Use a separate worker (Celery/RQ) for heavy LLM tasks; autoscale worker pool based on queue length.
- Caching:
  - Cache loaded LLM/embedding clients in-process to avoid repeated initialization (`utils/model_loader.py` already provides caching).
  - Cache Faiss indices in memory where applicable.

Backup & data retention
- Vector indexes and any persisted documents should be backed up periodically (daily or per deployment schedule) depending on business needs.
- Retention policy: define how long uploaded documents and derived artifacts will be kept. Provide an automated purge policy.

Maintenance & operational runbook
- Restart procedures, how to re-index FAISS, how to restore from backup, how to revoke compromised keys, and contact/owner details.
- Provide `maintenance.md` (operational runbook) with runbook steps for common incidents (index rebuild, job queue stuck, high error rate).

Compliance
- If handling PII, review GDPR/CCPA requirements and provide data deletion workflows and audit logs.

---

**SDLC CHECKLIST**

Development
- Use `black`/`ruff`/`isort` or project-preferred formatters and linters.
- Write unit tests for all new code paths and add regression tests for bug fixes.
- Keep functions small and well-documented with docstrings.

Code review
- Ensure PRs include rationale, test coverage notes, and steps to validate manually.

CI
- Linting + type checking + unit tests must pass.
- Build Docker image as part of CI for integration tests.

Release
- Tag releases semantically.
- Publish changelog entries for user-facing changes.

Operations
- Use automated health checks and readiness/liveness probes for the container.
- Keep secrets out of the codebase and stored in a secure store.

Security
- Run dependency vulnerability scans automatically.
- Rotate keys and review access periodically.

Monitoring & Feedback
- Collect logs centrally (ELK/CloudWatch) and set up dashboards for key metrics.
- Create SLOs and SLAs for the service.

---

**APPROVAL & OWNERSHIP**
- Primary owner: engineering team responsible for `Document_Portal` (update with actual owner name/email).
- QA owner: QA lead (update as appropriate).

**APPENDIX & RECOMMENDED TOOLS**
- FastAPI (API)
- pytest (tests)
- faiss-cpu (vector search; or FAISS via GPU if needed)
- rapidfuzz (fuzzy matching; fallback to difflib)
- OpenCV, Pillow, pytesseract, pdf2image (ingestion/ocr)
- LangChain / provider SDKs (LLM integration)
- Docker + Docker Compose
- GitHub Actions for CI
- Prometheus + Grafana for metrics
- OpenTelemetry for tracing
- Celery/RQ + Redis for background workers (or cloud-managed alternatives)

**NEXT STEPS / ROADMAP**
1. Review this document with stakeholders and add owners and SLAs.
2. Add `maintenance.md` with runbook procedures.
3. Implement CI pipeline (if not already present) with unit tests and Docker build.
4. Replace demo in-memory job scaffold with Celery and persistent job state (Redis + DB).
5. (Optional) Integrate NER model for better entity normalization.

---

If you want, I can:
- Add the `maintenance.md` runbook file next.
- Create CI workflow file (`.github/workflows/ci.yml`) to enforce lint/test/build.
- Integrate a small Prometheus export example and a sample `docker-compose.yml` to run the app and a worker locally.

Tell me which next step you'd like me to implement first and I'll add it to the todo list and start work.
