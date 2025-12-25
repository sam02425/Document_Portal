"""
Verifier module for Document Portal.

Provides quick deterministic and fuzzy verification of claimed metadata against
extracted document text. Optionally uses Faiss index (if available) for fast
candidate lookup. Includes a simple background-job scaffold for optional
LLM-based verification (use Celery or other worker for production).
"""
from __future__ import annotations
import re
import sys
import uuid
from typing import Dict, Any, Optional, List
from difflib import SequenceMatcher
from logger import GLOBAL_LOGGER as log
from exception.custom_exception import DocumentPortalException

try:
    from rapidfuzz import fuzz
    _HAS_RAPIDFUZZ = True
except Exception:
    _HAS_RAPIDFUZZ = False

# Simple in-memory job store for background verification results (demo only)
JOB_STORE: Dict[str, Dict[str, Any]] = {}


def _normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return s.strip()


def _fuzzy_score(a: str, b: str) -> float:
    if _HAS_RAPIDFUZZ:
        try:
            return float(fuzz.token_sort_ratio(a, b))
        except Exception:
            pass
    # fallback
    return float(SequenceMatcher(None, a, b).ratio() * 100)


class Verifier:
    """Performs verification checks between claimed metadata and document text."""

    def __init__(self, faiss_index_path: Optional[str] = None) -> None:
        self.faiss_index_path = faiss_index_path

    def verify_entity(self, claimed: str, document_text: str) -> Dict[str, Any]:
        """Verify a single claimed entity against the document text.

        Returns a dict with result, score, method, and matched excerpt (if any).
        """
        try:
            norm_claim = _normalize_text(claimed)
            if not norm_claim:
                return {"result": "missing", "score": 0.0, "method": "none"}

            # exact substring
            if claimed in document_text:
                return {"result": "pass", "score": 100.0, "method": "exact", "excerpt": claimed}

            # normalized exact
            if _normalize_text(claimed) in _normalize_text(document_text):
                return {"result": "pass", "score": 95.0, "method": "normalized_exact"}

            # fuzzy
            score = _fuzzy_score(claimed, document_text)
            if score >= 90:
                return {"result": "pass", "score": score, "method": "fuzzy"}
            elif score >= 70:
                return {"result": "warn", "score": score, "method": "fuzzy"}
            else:
                return {"result": "fail", "score": score, "method": "fuzzy"}
        except Exception as e:
            log.error("Verifier.verify_entity failed", error=str(e))
            raise DocumentPortalException("Verifier failed", sys)

    def verify_clause(self, expected_text: str, document_text: str) -> Dict[str, Any]:
        """Verify whether an expected clause exists or was updated in the document.

        Returns result, score, and evidence excerpt.
        """
        try:
            if expected_text in document_text:
                return {"result": "pass", "score": 100.0, "method": "exact", "excerpt": expected_text}
            score = _fuzzy_score(expected_text, document_text)
            if score >= 85:
                return {"result": "pass", "score": score, "method": "semantic/fuzzy"}
            elif score >= 60:
                return {"result": "warn", "score": score, "method": "semantic/fuzzy"}
            else:
                return {"result": "fail", "score": score, "method": "semantic/fuzzy"}
        except Exception as e:
            log.error("Verifier.verify_clause failed", error=str(e))
            raise DocumentPortalException("Verifier failed", sys)

    def quick_verify(self, claims: Dict[str, Any], document_text: str) -> Dict[str, Any]:
        """Run a quick verification pass for common claim structures.

        Supported claim keys: party_a, party_b, expected_changes (list of dicts with 'clause'/'expected_text').
        """
        report: Dict[str, Any] = {"checks": [], "summary": {}}
        try:
            # Parties
            for party_key in ("party_a", "party_b"):
                party = claims.get(party_key)
                if not party:
                    continue
                name = party.get("name")
                address = party.get("address")
                if name:
                    res = self.verify_entity(name, document_text)
                    report["checks"].append({"id": f"{party_key}_name", "type": "party_name", "value": name, **res})
                if address:
                    res = self.verify_entity(address, document_text)
                    report["checks"].append({"id": f"{party_key}_address", "type": "address", "value": address, **res})

            # Expected clause changes
            for idx, change in enumerate(claims.get("expected_changes", []) or []):
                expected_text = change.get("expected_text") or change.get("clause")
                if not expected_text:
                    continue
                res = self.verify_clause(expected_text, document_text)
                report["checks"].append({"id": f"clause_{idx}", "type": "clause_change", "value": expected_text, **res})

            # Compute simple summary
            scores = [c.get("score", 0) for c in report["checks"] if isinstance(c.get("score", None), (int, float))]
            if scores:
                avg = sum(scores) / len(scores)
            else:
                avg = 0.0
            report["summary"] = {"average_score": avg}
            return report
        except Exception as e:
            log.error("Verifier.quick_verify failed", error=str(e))
            raise DocumentPortalException("Verifier failed", sys)

    # Background LLM-based verification scaffold (demo)
    def enqueue_llm_verification(self, claims: Dict[str, Any], document_text: str) -> str:
        """Enqueue LLM-based verification job; returns job_id. For production, replace with Celery/RQ.
        This function stores a placeholder result and returns job_id immediately.
        """
        job_id = str(uuid.uuid4())
        JOB_STORE[job_id] = {"status": "queued", "result": None}

        # For demo, we run a synchronous placeholder that marks job as completed.
        # In production, this should be executed by a worker process.
        try:
            # Placeholder LLM check: mark as completed with existing quick_verify
            result = self.quick_verify(claims, document_text)
            JOB_STORE[job_id]["status"] = "completed"
            JOB_STORE[job_id]["result"] = {"llm_enhanced": True, "base": result}
        except Exception as e:
            JOB_STORE[job_id]["status"] = "failed"
            JOB_STORE[job_id]["result"] = {"error": str(e)}

        return job_id

    def get_job_result(self, job_id: str) -> Dict[str, Any]:
        return JOB_STORE.get(job_id, {"status": "not_found"})


__all__ = ["Verifier"]
