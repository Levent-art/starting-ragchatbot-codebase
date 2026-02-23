"""
Tests for AIGenerator using a mocked Anthropic client.

Critical test: test_second_call_has_tools_param
  — verifies that _handle_tool_execution includes 'tools' in the second API call
  — if it FAILS, Bug C is confirmed: Anthropic rejects the second call because
    messages contain tool_use/tool_result blocks but no 'tools' parameter

Reference: Anthropic API requires 'tools' whenever messages contain tool_use
or tool_result content blocks (even in the follow-up call).
"""

import pytest
from unittest.mock import MagicMock, patch
from ai_generator import AIGenerator


# ---------------------------------------------------------------------------
# Helper factories for mock Anthropic responses
# ---------------------------------------------------------------------------

def make_text_response(text: str):
    """Mock response where Claude replies with plain text (stop_reason='end_turn')."""
    content_block = MagicMock()
    content_block.type = "text"
    content_block.text = text

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [content_block]
    return response


def make_tool_use_response(name: str, input_data: dict, tool_id: str = "tool_001"):
    """Mock response where Claude requests a tool call (stop_reason='tool_use')."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = name
    tool_block.input = input_data
    tool_block.id = tool_id

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_block]
    return response


# ---------------------------------------------------------------------------
# Tests: direct (no-tool) responses
# ---------------------------------------------------------------------------

class TestDirectResponse:

    def test_direct_response_returns_text(self):
        """Without tool use, generate_response returns the text directly."""
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = make_text_response("Hello!")

            gen = AIGenerator(api_key="test", model="claude-test")
            result = gen.generate_response(query="What is Python?")

            assert result == "Hello!"
            mock_client.messages.create.assert_called_once()

    def test_tool_manager_not_called_without_tool_use(self):
        """tool_manager.execute_tool is NOT called when stop_reason != 'tool_use'."""
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = make_text_response("Direct answer")

            tool_manager = MagicMock()
            gen = AIGenerator(api_key="test", model="claude-test")
            gen.generate_response(query="Hello", tool_manager=tool_manager)

            tool_manager.execute_tool.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: tool execution flow
# ---------------------------------------------------------------------------

class TestToolExecution:

    def test_tool_is_called_on_tool_use(self):
        """When Claude requests a tool, it is executed and two API calls are made."""
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            mock_client.messages.create.side_effect = [
                make_tool_use_response(
                    name="search_course_content",
                    input_data={"query": "Python basics"},
                    tool_id="tool_001",
                ),
                make_text_response("Python is a high-level language."),
            ]

            tool_manager = MagicMock()
            tool_manager.execute_tool.return_value = "Python content from search"

            gen = AIGenerator(api_key="test", model="claude-test")
            result = gen.generate_response(
                query="What is Python?",
                tools=[{"name": "search_course_content"}],
                tool_manager=tool_manager,
            )

            assert result == "Python is a high-level language."
            assert mock_client.messages.create.call_count == 2
            tool_manager.execute_tool.assert_called_once_with(
                "search_course_content", query="Python basics"
            )

    def test_second_call_includes_tool_results(self):
        """Second API call messages include a tool_result block with the right tool_use_id."""
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            mock_client.messages.create.side_effect = [
                make_tool_use_response(
                    name="search_course_content",
                    input_data={"query": "variables"},
                    tool_id="tool_42",
                ),
                make_text_response("Final answer"),
            ]

            tool_manager = MagicMock()
            tool_manager.execute_tool.return_value = "search results here"

            gen = AIGenerator(api_key="test", model="claude-test")
            gen.generate_response(
                query="Python variables?",
                tools=[{"name": "search_course_content"}],
                tool_manager=tool_manager,
            )

            second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs
            messages = second_call_kwargs.get("messages", [])

            # Find messages with tool_result content
            tool_result_messages = [
                m for m in messages
                if m.get("role") == "user"
                and isinstance(m.get("content"), list)
                and any(c.get("type") == "tool_result" for c in m["content"])
            ]
            assert len(tool_result_messages) == 1

            result_block = tool_result_messages[0]["content"][0]
            assert result_block["tool_use_id"] == "tool_42"
            assert result_block["content"] == "search results here"

    def test_second_call_has_tools_param(self):
        """
        BUG C DIAGNOSTIC: second API call must include the 'tools' parameter.

        Anthropic's API requires 'tools' whenever messages contain tool_use or
        tool_result blocks. _handle_tool_execution currently omits 'tools' from
        the second call, causing the API to return a 400 error which propagates
        as HTTP 500 to the frontend ("query failed").

        This test is expected to FAIL with the current code, confirming Bug C.
        Fix C: add 'tools' to final_params in _handle_tool_execution.
        """
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            tools_definition = [{"name": "search_course_content", "input_schema": {}}]

            mock_client.messages.create.side_effect = [
                make_tool_use_response(
                    name="search_course_content",
                    input_data={"query": "test"},
                    tool_id="tool_99",
                ),
                make_text_response("Done"),
            ]

            tool_manager = MagicMock()
            tool_manager.execute_tool.return_value = "results"

            gen = AIGenerator(api_key="test", model="claude-test")
            gen.generate_response(
                query="Test query",
                tools=tools_definition,
                tool_manager=tool_manager,
            )

            second_call_kwargs = mock_client.messages.create.call_args_list[1].kwargs

            # The second call MUST include 'tools' — Anthropic requires it when
            # messages contain tool_use/tool_result blocks
            assert "tools" in second_call_kwargs, (
                "BUG C CONFIRMED: second API call is missing the 'tools' parameter. "
                "Anthropic returns 400 when messages have tool_use/tool_result blocks "
                "but no 'tools' param. Fix: add tools to final_params in "
                "_handle_tool_execution()."
            )


# ---------------------------------------------------------------------------
# Tests: sequential tool calling (loop up to MAX_TOOL_ROUNDS)
# ---------------------------------------------------------------------------

class TestSequentialToolCalling:

    def test_two_round_happy_path(self):
        """Two tool-use rounds followed by a text response — 3 API calls, 2 tool executions."""
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            mock_client.messages.create.side_effect = [
                make_tool_use_response("get_course_outline", {"course": "Python"}, "t1"),
                make_tool_use_response("search_course_content", {"query": "lesson 1"}, "t2"),
                make_text_response("Here is the final answer."),
            ]

            tool_manager = MagicMock()
            tool_manager.execute_tool.side_effect = ["outline result", "search result"]

            gen = AIGenerator(api_key="test", model="claude-test")
            result = gen.generate_response(
                query="Tell me about lesson 1 of Python",
                tools=[{"name": "get_course_outline"}, {"name": "search_course_content"}],
                tool_manager=tool_manager,
            )

            assert result == "Here is the final answer."
            assert mock_client.messages.create.call_count == 3
            assert tool_manager.execute_tool.call_count == 2

    def test_early_termination_after_round1(self):
        """Single tool-use round followed by text — 2 API calls, 1 tool execution."""
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            mock_client.messages.create.side_effect = [
                make_tool_use_response("search_course_content", {"query": "variables"}, "t1"),
                make_text_response("Variables store data."),
            ]

            tool_manager = MagicMock()
            tool_manager.execute_tool.return_value = "search results"

            gen = AIGenerator(api_key="test", model="claude-test")
            result = gen.generate_response(
                query="What are variables?",
                tools=[{"name": "search_course_content"}],
                tool_manager=tool_manager,
            )

            assert result == "Variables store data."
            assert mock_client.messages.create.call_count == 2
            assert tool_manager.execute_tool.call_count == 1

    def test_max_rounds_reached_final_is_tool_use(self):
        """When MAX_TOOL_ROUNDS is exhausted and last response is still tool_use, return ''."""
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            mock_client.messages.create.side_effect = [
                make_tool_use_response("search_course_content", {"query": "q1"}, "t1"),
                make_tool_use_response("search_course_content", {"query": "q2"}, "t2"),
                make_tool_use_response("search_course_content", {"query": "q3"}, "t3"),
            ]

            tool_manager = MagicMock()
            tool_manager.execute_tool.return_value = "some result"

            gen = AIGenerator(api_key="test", model="claude-test")
            result = gen.generate_response(
                query="Keep searching",
                tools=[{"name": "search_course_content"}],
                tool_manager=tool_manager,
            )

            assert result == ""
            assert mock_client.messages.create.call_count == 3

    def test_tool_error_is_captured_loop_continues(self):
        """A tool raising an exception records an error string and the loop proceeds normally."""
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            mock_client.messages.create.side_effect = [
                make_tool_use_response("search_course_content", {"query": "bad"}, "t1"),
                make_text_response("Recovered answer."),
            ]

            tool_manager = MagicMock()
            tool_manager.execute_tool.side_effect = RuntimeError("DB is down")

            gen = AIGenerator(api_key="test", model="claude-test")
            result = gen.generate_response(
                query="Search something",
                tools=[{"name": "search_course_content"}],
                tool_manager=tool_manager,
            )

            assert result == "Recovered answer."
            assert mock_client.messages.create.call_count == 2

            # Confirm the error was captured in the tool_result sent to the second call
            second_call_messages = mock_client.messages.create.call_args_list[1].kwargs["messages"]
            tool_result_msg = next(
                m for m in second_call_messages
                if m.get("role") == "user" and isinstance(m.get("content"), list)
                and any(c.get("type") == "tool_result" for c in m["content"])
            )
            error_content = tool_result_msg["content"][0]["content"]
            assert "Error:" in error_content
            assert "DB is down" in error_content

    def test_messages_accumulate_across_rounds(self):
        """The third API call's messages contain all turns from both rounds."""
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            mock_client.messages.create.side_effect = [
                make_tool_use_response("get_course_outline", {"course": "Go"}, "t1"),
                make_tool_use_response("search_course_content", {"query": "goroutines"}, "t2"),
                make_text_response("Goroutines are lightweight threads."),
            ]

            tool_manager = MagicMock()
            tool_manager.execute_tool.side_effect = ["outline", "search result"]

            gen = AIGenerator(api_key="test", model="claude-test")
            gen.generate_response(
                query="Explain goroutines",
                tools=[{"name": "get_course_outline"}, {"name": "search_course_content"}],
                tool_manager=tool_manager,
            )

            third_call_messages = mock_client.messages.create.call_args_list[2].kwargs["messages"]
            # Expected: user query, assistant round1, tool_results round1,
            #           assistant round2, tool_results round2
            assert len(third_call_messages) == 5
            assert third_call_messages[0]["role"] == "user"
            assert third_call_messages[1]["role"] == "assistant"
            assert third_call_messages[2]["role"] == "user"
            assert third_call_messages[3]["role"] == "assistant"
            assert third_call_messages[4]["role"] == "user"

            # Both user turns after the first must contain tool_result blocks
            for idx in (2, 4):
                content = third_call_messages[idx]["content"]
                assert isinstance(content, list)
                assert any(c.get("type") == "tool_result" for c in content)

    def test_no_text_block_returns_empty_string(self):
        """A direct response with no text blocks returns '' without raising."""
        with patch("ai_generator.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            # Response with only a non-text block (e.g., tool_use) and no text
            empty_block = MagicMock()
            empty_block.type = "image"
            response = MagicMock()
            response.stop_reason = "end_turn"
            response.content = [empty_block]
            mock_client.messages.create.return_value = response

            gen = AIGenerator(api_key="test", model="claude-test")
            result = gen.generate_response(query="Show me something")

            assert result == ""
