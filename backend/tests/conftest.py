"""
Shared fixtures for RAG chatbot tests.

All fixtures use a DummyEmbeddingFunction so no SentenceTransformer model
is downloaded or loaded during the test run.
"""

import sys
import os
from dataclasses import dataclass

import pytest
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import EmbeddingFunction, Documents, Embeddings

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
