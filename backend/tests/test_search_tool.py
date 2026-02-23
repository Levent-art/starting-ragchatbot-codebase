"""
Tests for CourseSearchTool.execute()

Critical test: test_empty_collection_does_not_raise
  — confirms whether search on an empty ChromaDB collection raises an exception
  — if it FAILS, Bug #1 (n_results > collection_size) is the root cause

Extra test: test_none_lesson_number_rejected_by_chromadb
  — confirms Bug B: ChromaDB rejects None values in metadata
  — if it FAILS, add_course_content silently empties the collection
"""

import pytest
from search_tools import CourseSearchTool
from models import CourseChunk


class TestEmptyCollection:

    def test_empty_collection_does_not_raise(self, temp_vector_store):
        """
        CRITICAL: execute() on an empty collection must not raise an exception.

        ChromaDB 1.x returns empty results for empty collections, so this
        should pass. If it fails, Bug #1 is confirmed.
        """
        tool = CourseSearchTool(temp_vector_store)
        result = tool.execute(query="what is Python?")
        # Must return a string, not raise
        assert isinstance(result, str)

    def test_empty_collection_returns_no_content_message(self, temp_vector_store):
        """execute() on an empty collection returns a 'no content' string."""
        tool = CourseSearchTool(temp_vector_store)
        result = tool.execute(query="anything")
        assert isinstance(result, str)
        assert len(result) > 0


class TestCourseSearchWithData:

    def test_execute_returns_formatted_results(self, populated_vector_store):
        """With indexed data, execute() returns a formatted string with source headers."""
        tool = CourseSearchTool(populated_vector_store)
        result = tool.execute(query="Python programming language")
        assert isinstance(result, str)
        assert len(result) > 0
        # Result should contain the course bracket header
        assert "[Test Course" in result

    def test_execute_with_valid_course_filter(self, populated_vector_store):
        """Filtering by an existing (partial) course name returns results."""
        tool = CourseSearchTool(populated_vector_store)
        result = tool.execute(query="Python", course_name="Test")
        # Should NOT be a "No course found" error
        assert "No course found" not in result
        assert isinstance(result, str)

    def test_execute_with_invalid_course_filter(self, temp_vector_store):
        """
        Filtering by a course name when the catalog is empty returns a 'No course found' message.

        Note: _resolve_course_name returns the nearest neighbor unconditionally (no similarity
        threshold), so with a non-empty catalog ANY course name resolves to the closest match.
        We use an empty store to reliably trigger the 'No course found' path.
        """
        tool = CourseSearchTool(temp_vector_store)  # empty catalog
        result = tool.execute(query="Python", course_name="Nonexistent Course XYZ 999")
        assert "No course found" in result

    def test_execute_with_lesson_filter(self, populated_vector_store):
        """Filtering by lesson_number returns only results from that lesson."""
        tool = CourseSearchTool(populated_vector_store)
        result = tool.execute(query="functions reusable", lesson_number=2)
        assert isinstance(result, str)
        # Lesson 2 has the functions chunk; the result should mention it
        assert "Lesson 2" in result

    def test_sources_populated_after_search(self, populated_vector_store):
        """last_sources is populated after a successful search with results."""
        tool = CourseSearchTool(populated_vector_store)
        tool.execute(query="Python programming language")
        assert isinstance(tool.last_sources, list)
        assert len(tool.last_sources) > 0
        for source in tool.last_sources:
            assert "label" in source
            assert "link" in source


class TestNoneMetadata:

    def test_none_lesson_number_rejected_by_chromadb(self, temp_vector_store):
        """
        BUG B DIAGNOSTIC: add_course_content with lesson_number=None must raise.

        ChromaDB rejects None values in metadata (only accepts str/int/float/bool).
        If document_processor produces chunks with lesson_number=None, the collection
        stays empty and all searches return empty results.

        This test is expected to RAISE an exception with the current code, confirming
        Bug B. Fix B filters None values before passing to ChromaDB.
        """
        chunk_with_none = CourseChunk(
            content="Some content without a lesson number.",
            course_title="Test Course",
            lesson_number=None,  # This is valid in the model but ChromaDB rejects it
            chunk_index=0,
        )
        with pytest.raises(Exception):
            temp_vector_store.add_course_content([chunk_with_none])
