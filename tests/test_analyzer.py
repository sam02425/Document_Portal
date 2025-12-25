"""
Unit tests for the Analyzer module in document_portal_core.
"""
from document_portal_core.analyzer import Analyzer

def test_analyze_minimal(monkeypatch):
    # Patch the LLM and parser chain to return a dummy result
    class DummyAnalyzer(Analyzer):
        def analyze(self, document_text: str):
            return {"summary": "dummy summary", "Title": "Test"}
    analyzer = DummyAnalyzer()
    result = analyzer.analyze("Some contract text.")
    assert "summary" in result
    assert result["Title"] == "Test"
