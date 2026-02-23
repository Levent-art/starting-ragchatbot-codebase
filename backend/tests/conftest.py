"""
Shared fixtures for RAG chatbot tests.

All fixtures use a DummyEmbeddingFunction so no SentenceTransformer model
is downloaded or loaded during the test run.
"""

import sys
import os
from dataclasses import dataclass
from typing import List, Optional
from unittest.mock import MagicMock

import pytest
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import EmbeddingFunction, Documents, Embeddings
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

# Make backend/ importable without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vector_store import VectorStore
from models import Course, Lesson, CourseChunk


# ---------------------------------------------------------------------------
# Lightweight embedding function — no model download, deterministic output
# ---------------------------------------------------------------------------

class DummyEmbeddingFunction(EmbeddingFunction[Documents]):
    """16-dim hash-based embeddings for testing. No model loading."""

    def __init__(self):
        pass

    def __call__(self, input: Documents) -> Embeddings:
        import hashlib
        result = []
        for text in input:
            h = hashlib.md5(text.encode()).digest()
            # 16 bytes → 16 floats in [-1, 1]
            vec = [(b / 127.5) - 1.0 for b in h]
            result.append(vec)
        return result


# ---------------------------------------------------------------------------
# Helper: build a VectorStore without loading SentenceTransformer
# ---------------------------------------------------------------------------

def make_vector_store(chroma_path: str) -> VectorStore:
    """Construct a VectorStore using DummyEmbeddingFunction (bypasses __init__)."""
    store = VectorStore.__new__(VectorStore)
    store.max_results = 5
    store.client = chromadb.PersistentClient(
        path=chroma_path,
        settings=Settings(anonymized_telemetry=False),
    )
    store.embedding_function = DummyEmbeddingFunction()
    store.course_catalog = store.client.get_or_create_collection(
        name="course_catalog",
        embedding_function=store.embedding_function,
    )
    store.course_content = store.client.get_or_create_collection(
        name="course_content",
        embedding_function=store.embedding_function,
    )
    return store


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_vector_store(tmp_path):
    """Empty VectorStore backed by a temporary ChromaDB directory."""
    return make_vector_store(str(tmp_path))


@pytest.fixture
def populated_vector_store(tmp_path):
    """VectorStore with 1 indexed course and 3 content chunks."""
    store = make_vector_store(str(tmp_path))

    course = Course(
        title="Test Course",
        course_link="https://example.com/course",
        instructor="Test Instructor",
        lessons=[
            Lesson(lesson_number=1, title="Introduction", lesson_link="https://example.com/l1"),
            Lesson(lesson_number=2, title="Advanced Topics", lesson_link="https://example.com/l2"),
        ],
    )
    store.add_course_metadata(course)

    chunks = [
        CourseChunk(
            content="Python is a high-level programming language.",
            course_title="Test Course",
            lesson_number=1,
            chunk_index=0,
        ),
        CourseChunk(
            content="Variables store data values in Python.",
            course_title="Test Course",
            lesson_number=1,
            chunk_index=1,
        ),
        CourseChunk(
            content="Functions are reusable blocks of code.",
            course_title="Test Course",
            lesson_number=2,
            chunk_index=2,
        ),
    ]
    store.add_course_content(chunks)

    return store


@dataclass
class MockConfig:
    """Minimal config for RAGSystem tests."""
    CHROMA_PATH: str
    ANTHROPIC_API_KEY: str = "test-key-not-real"
    ANTHROPIC_MODEL: str = "claude-test-model"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RESULTS: int = 5
    MAX_HISTORY: int = 2


@pytest.fixture
def mock_config(tmp_path):
    """Config pointing to a temporary ChromaDB directory."""
    return MockConfig(CHROMA_PATH=str(tmp_path))


# ---------------------------------------------------------------------------
# API test fixtures — build a test FastAPI app without the static-file mount
# ---------------------------------------------------------------------------

# Pydantic models mirroring app.py (kept local so tests never import app.py)
class _QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class _QueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    session_id: str

class _CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


@pytest.fixture
def mock_rag_system():
    """
    MagicMock that stands in for RAGSystem.

    Defaults:
    - query()               → ("Test answer", [{"label": "Src", "link": "http://x"}])
    - get_course_analytics()→ {"total_courses": 2, "course_titles": ["A", "B"]}
    - session_manager.create_session() → "generated-session-id"
    """
    mock = MagicMock()
    mock.query.return_value = (
        "Test answer",
        [{"label": "Source 1", "link": "http://example.com/1"}],
    )
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Python Basics", "Advanced Python"],
    }
    mock.session_manager.create_session.return_value = "generated-session-id"
    return mock


@pytest.fixture
def test_app(mock_rag_system):
    """
    Minimal FastAPI app exposing only the API routes — no static-file mount.

    The real app.py mounts ../frontend/ which does not exist in the test
    environment. This fixture re-implements the two API endpoints with the
    same request/response contracts, using mock_rag_system instead of a
    live RAGSystem.
    """
    app = FastAPI()

    @app.post("/api/query", response_model=_QueryResponse)
    async def query_documents(request: _QueryRequest):
        try:
            session_id = request.session_id or mock_rag_system.session_manager.create_session()
            answer, sources = mock_rag_system.query(request.query, session_id)
            return _QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/courses", response_model=_CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return _CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return app


@pytest.fixture
def client(test_app):
    """Synchronous httpx TestClient wrapping the test FastAPI app."""
    return TestClient(test_app)
