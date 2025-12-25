
import pytest
import os
from unittest.mock import MagicMock

# Mock API Keys globally for tests to avoid ModelLoader crashes
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "TEST_KEY")
    monkeypatch.setenv("GROQ_API_KEY", "TEST_KEY")
    monkeypatch.setenv("GEMINI_API_KEY", "TEST_KEY")

# If needed, patch external calls globally
