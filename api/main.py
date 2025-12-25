from document_portal_core.graph import GraphExtractor
# ---------- GRAPH EXTRACTION ----------
@app.post("/graph")
async def extract_graph(reference: UploadFile = File(...), actual: UploadFile = File(...)) -> Any:
    """
    Extract a relationship graph from two contract documents (image, PDF, or Word).
    Returns nodes and edges for visualization or further analysis.
    """
    try:
        log.info(f"Extracting graph from: {reference.filename} and {actual.filename}")
        # Save uploaded files to disk
        ref_path = f"/tmp/{reference.filename}"
        act_path = f"/tmp/{actual.filename}"
        with open(ref_path, "wb") as f:
            f.write(await reference.read())
        with open(act_path, "wb") as f:
            f.write(await actual.read())
        # Ingest and extract text from both
        ingestion = Ingestion()
        ref_text = ingestion.ingest(ref_path)
        act_text = ingestion.ingest(act_path)
        # Extract graph
        extractor = GraphExtractor()
        graph_data = extractor.extract_graph(ref_text, act_text)
        log.info("Graph extraction complete.")
        return graph_data
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Graph extraction failed")
        raise HTTPException(status_code=500, detail=f"Graph extraction failed: {e}")
import os
from typing import List, Optional, Any, Dict
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from document_portal_core.ingestion import Ingestion
from document_portal_core.analyzer import Analyzer
from document_portal_core.comparator import Comparator
from document_portal_core.rag import ConversationalRAG
from document_portal_core.verifier import Verifier
from utils.document_ops import FastAPIFileAdapter
from logger import GLOBAL_LOGGER as log

FAISS_BASE = os.getenv("FAISS_BASE", "faiss_index")
UPLOAD_BASE = os.getenv("UPLOAD_BASE", "data")
FAISS_INDEX_NAME = os.getenv("FAISS_INDEX_NAME", "index")  # <--- keep consistent with save_local()

app = FastAPI(title="Document Portal API", version="0.1")

BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    log.info("Serving UI homepage.")
    resp = templates.TemplateResponse("index.html", {"request": request})
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.get("/health")
def health() -> Dict[str, str]:
    log.info("Health check passed.")
    return {"status": "ok", "service": "document-portal"}

# ---------- ANALYZE ----------
@app.post("/analyze")
async def analyze_document(file: UploadFile = File(...)) -> Any:
    """
    Analyze a document (image, PDF, or Word). Handles orientation, OCR, and text extraction.
    Returns structured analysis using the Analyzer core module.
    """
    try:
        log.info(f"Received file for analysis: {file.filename}")
        # Save uploaded file to disk
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        # Ingest and extract text
        ingestion = Ingestion()
        text = ingestion.ingest(temp_path)
        analyzer = Analyzer()
        result = analyzer.analyze(text)
        log.info("Document analysis complete.")
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Error during document analysis")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

# ---------- COMPARE ----------
@app.post("/compare")
async def compare_documents(reference: UploadFile = File(...), actual: UploadFile = File(...)) -> Any:
    """
    Compare two documents (image, PDF, or Word). Handles orientation, OCR, and text extraction.
    Returns structured comparison using the Comparator core module.
    """
    try:
        log.info(f"Comparing files: {reference.filename} vs {actual.filename}")
        # Save uploaded files to disk
        ref_path = f"/tmp/{reference.filename}"
        act_path = f"/tmp/{actual.filename}"
        with open(ref_path, "wb") as f:
            f.write(await reference.read())
        with open(act_path, "wb") as f:
            f.write(await actual.read())
        # Ingest and extract text from both
        ingestion = Ingestion()
        ref_text = ingestion.ingest(ref_path)
        act_text = ingestion.ingest(act_path)
        # Combine for comparison (customize as needed)
        combined_text = f"Reference Document:\n{ref_text}\n\nActual Document:\n{act_text}"
        comparator = Comparator()
        df = comparator.compare(combined_text)
        log.info("Document comparison completed.")
        return {"rows": df.to_dict(orient="records")}
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Comparison failed")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")


# ---------- VERIFY ----------
@app.post("/verify")
async def verify_document(
    file: UploadFile = File(...),
    claims: str = Form(...),
    enqueue_llm: bool = Form(False),
) -> Any:
    """
    Verify claimed metadata against the provided document.

    - `claims` must be a JSON string containing keys like `party_a`, `party_b`, and
      `expected_changes` (list of {"clause"|"expected_text": str}).
    - If `enqueue_llm` is true, an LLM-based background verification job will be
      enqueued (demo in-memory scaffold) and a `job_id` returned.
    """
    import json

    try:
        log.info(f"Received file for verification: {file.filename}")
        # Save uploaded file to disk
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        # Ingest and extract text
        ingestion = Ingestion()
        text = ingestion.ingest(temp_path)
        # Parse claims
        try:
            claims_obj = json.loads(claims)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON for 'claims' form field")

        verifier = Verifier()
        quick_report = verifier.quick_verify(claims_obj, text)

        response: Dict[str, Any] = {"quick_report": quick_report}

        if enqueue_llm:
            job_id = verifier.enqueue_llm_verification(claims_obj, text)
            response["job_id"] = job_id
            response["job_status"] = verifier.get_job_result(job_id)

        log.info("Verification complete.")
        return JSONResponse(content=response)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Verification failed")
        raise HTTPException(status_code=500, detail=f"Verification failed: {e}")

# ---------- CHAT: INDEX ----------
@app.post("/chat/index")
async def chat_build_index(
    files: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
    use_session_dirs: bool = Form(True),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    k: int = Form(5),
) -> Any:
    try:
        log.info(f"Indexing chat session. Session ID: {session_id}, Files: {[f.filename for f in files]}")
        wrapped = [FastAPIFileAdapter(f) for f in files]
        # this is my main class for storing a data into VDB
        # created a object of ChatIngestor
        ci = ChatIngestor(
            temp_base=UPLOAD_BASE,
            faiss_base=FAISS_BASE,
            use_session_dirs=use_session_dirs,
            session_id=session_id or None,
        )
        # NOTE: ensure your ChatIngestor saves with index_name="index" or FAISS_INDEX_NAME
        # e.g., if it calls FAISS.save_local(dir, index_name=FAISS_INDEX_NAME)
        ci.built_retriver(  # if your method name is actually build_retriever, fix it there as well
            wrapped, chunk_size=chunk_size, chunk_overlap=chunk_overlap, k=k
        )
        log.info(f"Index created successfully for session: {ci.session_id}")
        return {"session_id": ci.session_id, "k": k, "use_session_dirs": use_session_dirs}
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Chat index building failed")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")

# ---------- CHAT: QUERY ----------
@app.post("/chat/query")
async def chat_query(
    question: str = Form(...),
    session_id: Optional[str] = Form(None),
    use_session_dirs: bool = Form(True),
    k: int = Form(5),
) -> Any:
    try:
        log.info(f"Received chat query: '{question}' | session: {session_id}")
        if use_session_dirs and not session_id:
            raise HTTPException(status_code=400, detail="session_id is required when use_session_dirs=True")

        index_dir = os.path.join(FAISS_BASE, session_id) if use_session_dirs else FAISS_BASE  # type: ignore
        if not os.path.isdir(index_dir):
            raise HTTPException(status_code=404, detail=f"FAISS index not found at: {index_dir}")

        rag = ConversationalRAG(session_id=session_id)
        rag.load_retriever_from_faiss(index_dir, k=k, index_name=FAISS_INDEX_NAME)  # build retriever + chain
        response = rag.invoke(question, chat_history=[])
        log.info("Chat query handled successfully.")

        return {
            "answer": response,
            "session_id": session_id,
            "k": k,
            "engine": "LCEL-RAG"
        }
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Chat query failed")
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")

# command for executing the fast api
# uvicorn api.main:app --port 8080 --reload
#uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload