"""
Integration tests for RAGSystem.query()

AIGenerator is fully mocked (no real Anthropic API calls).
VectorStore is replaced with the test fixture (real ChromaDB in tmpdir,
DummyEmbeddingFunction — no model download).

Critical test: test_query_with_empty_db_does_not_crash
  — confirms the full query pipeline survives an empty vector store
  — if it FAILS, an unhandled exception escapes query() and becomes HTTP 500
"""

import pytest
from unittest.mock import MagicMock, patch


class TestRAGSystemQuery:

    def test_query_returns_tuple(self, mock_config, populated_vector_store):
        """query() returns (str, list) — must not raise any exception."""
        with patch("rag_system.AIGenerator") as mock_ai_cls, \
             patch("rag_system.VectorStore") as mock_vs_cls:

            mock_ai = MagicMock()
            mock_ai_cls.return_value = mock_ai
            mock_ai.generate_response.return_value = "Test response"

            mock_vs_cls.return_value = populated_vector_store

            from rag_system import RAGSystem
            system = RAGSystem(mock_config)
            result = system.query("What is Python?")

            assert isinstance(result, tuple)
            assert len(result) == 2
            response, sources = result
            assert isinstance(response, str)
            assert isinstance(sources, list)

    def test_query_calls_ai_generator_with_tools(self, mock_config, populated_vector_store):
        """query() passes both 'tools' and 'tool_manager' to generate_response."""
        with patch("rag_system.AIGenerator") as mock_ai_cls, \
             patch("rag_system.VectorStore") as mock_vs_cls:

            mock_ai = MagicMock()
            mock_ai_cls.return_value = mock_ai
            mock_ai.generate_response.return_value = "Response"

            mock_vs_cls.return_value = populated_vector_store

            from rag_system import RAGSystem
            system = RAGSystem(mock_config)
            system.query("Tell me about Python")

            call_kwargs = mock_ai.generate_response.call_args.kwargs
            assert "tools" in call_kwargs, "generate_response must receive 'tools'"
            assert "tool_manager" in call_kwargs, "generate_response must receive 'tool_manager'"
            assert call_kwargs["tools"] is not None
            assert len(call_kwargs["tools"]) > 0

    def test_query_updates_session_history(self, mock_config, populated_vector_store):
        """
        query() with a session_id stores the exchange in the session manager.
        A second call with the same session_id receives non-None history.
        """
        with patch("rag_system.AIGenerator") as mock_ai_cls, \
             patch("rag_system.VectorStore") as mock_vs_cls:

            mock_ai = MagicMock()
            mock_ai_cls.return_value = mock_ai
            mock_ai.generate_response.return_value = "Answer"

            mock_vs_cls.return_value = populated_vector_store

            from rag_system import RAGSystem
            system = RAGSystem(mock_config)
            system.query("Hello", session_id="test-session-001")

            # After one exchange the session should have history
            history = system.session_manager.get_conversation_history("test-session-001")
            assert history is not None
            assert "Hello" in history
            assert "Answer" in history

    def test_query_with_empty_db_does_not_crash(self, mock_config, temp_vector_store):
        """
        CRITICAL: query() must not raise when the vector store is empty.

        If CourseSearchTool.execute() is called (via tool use) against an empty
        ChromaDB collection and an unhandled exception escapes, it propagates
        through rag_system.query() and app.py raises HTTP 500 → "query failed".

        Here the AI mock returns a direct text response (no tool use), so we
        test the orchestration layer. The search-on-empty-collection path is
        covered separately in test_search_tool.py::test_empty_collection_does_not_raise.
        """
        with patch("rag_system.AIGenerator") as mock_ai_cls, \
             patch("rag_system.VectorStore") as mock_vs_cls:

            mock_ai = MagicMock()
            mock_ai_cls.return_value = mock_ai
            mock_ai.generate_response.return_value = "No content found"

            mock_vs_cls.return_value = temp_vector_store  # empty store

            from rag_system import RAGSystem
            system = RAGSystem(mock_config)

            # Must not raise
            result = system.query("What is Python?")

            assert isinstance(result, tuple)
            response, sources = result
            assert isinstance(response, str)
            assert isinstance(sources, list)
