"""
API endpoint tests for the RAG chatbot.

Uses a lightweight test FastAPI app (defined in conftest.py) that exposes the
same /api/query and /api/courses routes as app.py but without mounting the
../frontend/ static files — which do not exist in the test environment.

All RAGSystem interactions go through mock_rag_system (a MagicMock), so no
real ChromaDB, SentenceTransformer, or Anthropic API calls are made.
"""

import pytest


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

class TestQueryEndpoint:

    def test_returns_200_for_valid_request(self, client):
        """A well-formed query returns HTTP 200."""
        response = client.post("/api/query", json={"query": "What is Python?"})
        assert response.status_code == 200

    def test_response_contains_required_fields(self, client):
        """Response body must include answer, sources, and session_id."""
        response = client.post("/api/query", json={"query": "What is Python?"})
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data

    def test_answer_is_string(self, client):
        """answer field must be a non-empty string."""
        response = client.post("/api/query", json={"query": "What is Python?"})
        assert isinstance(response.json()["answer"], str)
        assert len(response.json()["answer"]) > 0

    def test_sources_is_list(self, client):
        """sources field must be a list."""
        response = client.post("/api/query", json={"query": "What is Python?"})
        assert isinstance(response.json()["sources"], list)

    def test_generates_session_id_when_not_provided(self, client):
        """When session_id is omitted, the endpoint generates one via session_manager."""
        response = client.post("/api/query", json={"query": "What is Python?"})
        assert response.json()["session_id"] == "generated-session-id"

    def test_echoes_provided_session_id(self, client):
        """When session_id is supplied in the request, the same value is returned."""
        response = client.post(
            "/api/query",
            json={"query": "What is Python?", "session_id": "my-session-abc"},
        )
        assert response.json()["session_id"] == "my-session-abc"

    def test_passes_query_text_to_rag_system(self, client, mock_rag_system):
        """RAGSystem.query() is called with the exact query string from the request."""
        client.post("/api/query", json={"query": "Explain decorators"})
        mock_rag_system.query.assert_called_once()
        positional_args = mock_rag_system.query.call_args[0]
        assert positional_args[0] == "Explain decorators"

    def test_passes_session_id_to_rag_system(self, client, mock_rag_system):
        """RAGSystem.query() receives the session_id as the second positional argument."""
        client.post(
            "/api/query",
            json={"query": "Explain decorators", "session_id": "sess-42"},
        )
        positional_args = mock_rag_system.query.call_args[0]
        assert positional_args[1] == "sess-42"

    def test_returns_500_when_rag_system_raises(self, client, mock_rag_system):
        """An exception from RAGSystem.query() surfaces as HTTP 500."""
        mock_rag_system.query.side_effect = RuntimeError("vector store unavailable")
        response = client.post("/api/query", json={"query": "crash?"})
        assert response.status_code == 500

    def test_500_response_contains_error_detail(self, client, mock_rag_system):
        """HTTP 500 body contains a 'detail' field with the exception message."""
        mock_rag_system.query.side_effect = RuntimeError("vector store unavailable")
        response = client.post("/api/query", json={"query": "crash?"})
        assert "vector store unavailable" in response.json()["detail"]

    def test_missing_query_field_returns_422(self, client):
        """Omitting the required 'query' field triggers FastAPI's validation (HTTP 422)."""
        response = client.post("/api/query", json={})
        assert response.status_code == 422

    def test_empty_query_string_is_accepted(self, client):
        """An empty string is a valid value for 'query' (business logic, not HTTP layer)."""
        response = client.post("/api/query", json={"query": ""})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

class TestCoursesEndpoint:

    def test_returns_200(self, client):
        """GET /api/courses returns HTTP 200."""
        response = client.get("/api/courses")
        assert response.status_code == 200

    def test_response_contains_required_fields(self, client):
        """Response body must include total_courses and course_titles."""
        response = client.get("/api/courses")
        data = response.json()
        assert "total_courses" in data
        assert "course_titles" in data

    def test_total_courses_is_integer(self, client):
        """total_courses must be an integer."""
        assert isinstance(client.get("/api/courses").json()["total_courses"], int)

    def test_course_titles_is_list(self, client):
        """course_titles must be a list."""
        assert isinstance(client.get("/api/courses").json()["course_titles"], list)

    def test_returns_correct_course_count(self, client):
        """total_courses matches the value returned by get_course_analytics()."""
        data = client.get("/api/courses").json()
        assert data["total_courses"] == 2

    def test_returns_correct_course_titles(self, client):
        """course_titles matches the list returned by get_course_analytics()."""
        data = client.get("/api/courses").json()
        assert data["course_titles"] == ["Python Basics", "Advanced Python"]

    def test_empty_catalog_returns_zero_count(self, client, mock_rag_system):
        """When there are no courses, total_courses == 0 and course_titles == []."""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": [],
        }
        data = client.get("/api/courses").json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []

    def test_returns_500_when_analytics_raises(self, client, mock_rag_system):
        """An exception from get_course_analytics() surfaces as HTTP 500."""
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("DB connection lost")
        response = client.get("/api/courses")
        assert response.status_code == 500

    def test_500_response_contains_error_detail(self, client, mock_rag_system):
        """HTTP 500 body contains a 'detail' field with the exception message."""
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("DB connection lost")
        response = client.get("/api/courses")
        assert "DB connection lost" in response.json()["detail"]

    def test_calls_get_course_analytics_once(self, client, mock_rag_system):
        """get_course_analytics() is called exactly once per request."""
        client.get("/api/courses")
        mock_rag_system.get_course_analytics.assert_called_once()
