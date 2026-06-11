"""
Tests for the AgentLoop with a mock LLM provider.
No Ollama required — the mock provider is injected.
"""
import threading
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import MagicMock

import pytest

from app.core.agent_loop import AgentLoop
from app.core.llm_provider import BaseLLM, StreamChunk, ToolCall
from app.core.memory_manager import IntelligentMemoryManager
from app.core.tool_registry import ToolRegistry


# ── Mock LLM ─────────────────────────────────────────────────────────────────

class _MockLLM(BaseLLM):
    """
    A controllable mock LLM.
    Set `responses` to a list of StreamChunk lists — each inner list is
    yielded as the response for one call to stream().
    """

    def __init__(self, responses: List[List[StreamChunk]]) -> None:
        self._responses = iter(responses)

    def generate(self, messages):
        yield "Summary text."

    def stream(self, messages, tools=None):
        try:
            chunks = next(self._responses)
        except StopIteration:
            chunks = [StreamChunk(content="(no more responses)", done=True)]
        yield from chunks

    def test_connection(self) -> bool:
        return True


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def registry():
    r = ToolRegistry()
    r.discover_skills()
    return r


@pytest.fixture
def memory():
    return IntelligentMemoryManager(
        system_prompt="You are a test assistant.",
        max_recent_turns=4,
        max_tokens=2000,
    )


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestAgentLoopNoTools:
    def test_plain_response_returned(self, registry, memory):
        llm = _MockLLM([[
            StreamChunk(content="Hello, I am JARVIS."),
            StreamChunk(content=" How can I help?", done=True),
        ]])
        agent = AgentLoop(llm=llm, registry=registry, memory=memory)
        result = agent.run_turn("Hello")

        assert result == "Hello, I am JARVIS. How can I help?"

    def test_memory_updated_after_turn(self, registry, memory):
        llm = _MockLLM([[StreamChunk(content="Test response.", done=True)]])
        agent = AgentLoop(llm=llm, registry=registry, memory=memory)
        agent.run_turn("Test input")

        messages = memory.get_messages()
        # system + user + assistant (in completed turn)
        assert any(m["role"] == "user" for m in messages)
        assert any(m["role"] == "assistant" for m in messages)


class TestAgentLoopWithTools:
    def test_single_tool_call_then_answer(self, registry, memory):
        """LLM calls 'calculate', gets result, then returns final text."""
        llm = _MockLLM([
            # First response: request a tool call
            [StreamChunk(
                content="",
                tool_calls=[ToolCall(name="calculate", arguments={"expression": "2 + 2"})],
                done=True,
            )],
            # Second response: final answer after tool result
            [StreamChunk(content="The answer is 4.", done=True)],
        ])
        agent = AgentLoop(llm=llm, registry=registry, memory=memory)
        result = agent.run_turn("What is 2 + 2?")

        assert result == "The answer is 4."

    def test_parallel_tool_calls(self, registry, memory):
        """LLM returns two tool calls in one chunk (parallel calling)."""
        llm = _MockLLM([
            [StreamChunk(
                content="",
                tool_calls=[
                    ToolCall(name="calculate", arguments={"expression": "3 * 3"}),
                    ToolCall(name="get_system_time", arguments={}),
                ],
                done=True,
            )],
            [StreamChunk(content="Both results retrieved.", done=True)],
        ])
        agent = AgentLoop(llm=llm, registry=registry, memory=memory)

        events = []
        agent.on_event = lambda t, d: events.append((t, d))

        result = agent.run_turn("What is 9 and what time is it?")

        assert result == "Both results retrieved."
        tool_call_events = [e for e in events if e[0] == "tool_call"]
        assert len(tool_call_events) == 2

    def test_unknown_tool_returns_error(self, registry, memory):
        """Agent handles unknown tool name gracefully."""
        llm = _MockLLM([
            [StreamChunk(
                content="",
                tool_calls=[ToolCall(name="nonexistent_tool", arguments={})],
                done=True,
            )],
            [StreamChunk(content="I couldn't use that tool.", done=True)],
        ])
        agent = AgentLoop(llm=llm, registry=registry, memory=memory)
        result = agent.run_turn("Use nonexistent tool")

        assert result is not None  # Should not crash


class TestAgentLoopInterrupt:
    def test_stop_event_halts_loop(self, registry, memory):
        stop = threading.Event()
        stop.set()  # Pre-set: simulate immediate interrupt

        llm = _MockLLM([[StreamChunk(content="This should not be returned.", done=True)]])
        agent = AgentLoop(llm=llm, registry=registry, memory=memory, stop_event=stop)
        result = agent.run_turn("Hello")

        assert result is None


class TestMarkdownUtils:
    def test_render_basic_markdown(self):
        from app.core.markdown_utils import render_markdown
        html = render_markdown("# Hello\n\nThis is a **test**.")
        assert "<h1>" in html
        assert "<strong>test</strong>" in html

    def test_render_empty_string(self):
        from app.core.markdown_utils import render_markdown
        assert render_markdown("") == ""
        assert render_markdown("   ") == ""

    def test_extract_title_h1(self):
        from app.core.markdown_utils import extract_title
        md = "# Morning Briefing\n\nSome content."
        assert extract_title(md) == "Morning Briefing"

    def test_extract_title_fallback(self):
        from app.core.markdown_utils import extract_title
        md = "No heading here."
        assert extract_title(md, fallback="Report") == "Report"

    def test_render_code_block(self):
        from app.core.markdown_utils import render_markdown
        md = "```python\nprint('hello')\n```"
        html = render_markdown(md)
        assert "print" in html

    def test_render_table(self):
        from app.core.markdown_utils import render_markdown
        md = "| Col A | Col B |\n|---|---|\n| 1 | 2 |"
        html = render_markdown(md)
        assert "<table" in html
