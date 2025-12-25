"""
Unit tests for the GraphExtractor module in document_portal_core.
"""
from document_portal_core.graph import GraphExtractor

def test_extract_graph_basic():
    doc1 = "PartyA agrees to pay PartyB."
    doc2 = "PartyB receives payment from PartyA."
    extractor = GraphExtractor()
    graph = extractor.extract_graph(doc1, doc2)
    assert "nodes" in graph
    assert "edges" in graph
    assert any(n["id"] == "PartyA" for n in graph["nodes"])
    assert any(n["id"] == "PartyB" for n in graph["nodes"])
