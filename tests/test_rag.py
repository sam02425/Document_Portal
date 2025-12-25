"""
Unit tests for the ConversationalRAG module in document_portal_core.
"""
from document_portal_core.rag import ConversationalRAG

def test_rag_init():
    # Patch LLM and retriever for fast init
    class DummyRAG(ConversationalRAG):
        def _load_llm(self):
            return object()
        def _build_lcel_chain(self):
            self.chain = lambda payload: "dummy answer"
    rag = DummyRAG(session_id="test")
    assert rag.session_id == "test"
