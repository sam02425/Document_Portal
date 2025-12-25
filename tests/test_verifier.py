import json
from document_portal_core.verifier import Verifier


def test_verify_entity_exact():
    v = Verifier()
    doc = "This contract is between Alice Corp and Bob LLC located at 123 Main St."
    res = v.verify_entity("Alice Corp", doc)
    assert res["result"] == "pass"
    assert res["method"] in ("exact", "normalized_exact")


def test_verify_entity_fuzzy():
    v = Verifier()
    doc = "This agreement is made with International Business Machines Incorporated."
    # intentionally slightly different
    res = v.verify_entity("IBM", doc)
    # fuzzy match should produce warn or fail but should return a numeric score
    assert "score" in res
    assert isinstance(res["score"], float)


def test_verify_clause():
    v = Verifier()
    doc = "The term of this agreement shall be two (2) years from the Effective Date."
    res = v.verify_clause("term of this agreement shall be two years", doc)
    assert res["result"] in ("pass", "warn")


def test_quick_verify_and_enqueue():
    v = Verifier()
    doc = "Alice Corp located at 123 Main St. agrees with Bob LLC located at 456 Side Ave."
    claims = {
        "party_a": {"name": "Alice Corp", "address": "123 Main St."},
        "party_b": {"name": "Bob LLC", "address": "456 Side Ave."},
        "expected_changes": [{"expected_text": "Alice Corp"}]
    }
    report = v.quick_verify(claims, doc)
    assert "checks" in report
    job_id = v.enqueue_llm_verification(claims, doc)
    assert isinstance(job_id, str)
    job = v.get_job_result(job_id)
    assert job["status"] in ("completed", "failed")
