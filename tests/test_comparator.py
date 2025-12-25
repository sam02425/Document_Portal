"""
Unit tests for the Comparator module in document_portal_core.
"""
from document_portal_core.comparator import Comparator
import pandas as pd

def test_compare_minimal(monkeypatch):
    # Patch the LLM and parser chain to return a dummy DataFrame
    class DummyComparator(Comparator):
        def compare(self, combined_docs: str):
            return pd.DataFrame([{"Page": 1, "Changes": "None"}])
    comparator = DummyComparator()
    df = comparator.compare("doc1\ndoc2")
    assert isinstance(df, pd.DataFrame)
    assert "Page" in df.columns
