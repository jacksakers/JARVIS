"""
JARVIS v3.0 — Agent Loop

Key differences from v2.0:
─────────────────────────
• No TTS or Rich console dependency — runs headless in a background worker.
• Supports parallel tool calls: a single LLM response may request multiple
  tools simultaneously (Gemma4 does this regularly). All are executed before
  the next LLM call.
• Event callbacks let the worker push real-time status to WebSocket clients
  without coupling this module to the web layer.
• Returns the final assistant content as a plain string (Markdown).
• stop_event is optional — useful for future UI-level interrupts.
"""
import threading
from typing import Any, Callable, Dict, List, Optional

from app.core.llm_provider import BaseLLM, StreamChunk, ToolCall
from app.core.memory_manager import IntelligentMemoryManager
from app.core.tool_registry import ToolRegistry


# ── Event callback type ───────────────────────────────────────────────────────
# Signature: on_event(event_type: str, data: dict)
# event_type values: "tool_call", "tool_result", "content_chunk", "error"
EventCallback = Callable[[str, Dict[str, Any]], None]


class AgentLoop:
    """
    Drives a single conversation turn end-to-end, including recursive
    tool-call sub-steps.

    Flow per turn
    ─────────────
    1. Append the user message to memory.
    2. Stream the LLM response (tool schemas injected).
    3. If the model emits tool_calls:
       a. Execute ALL tool calls (parallel batch).
       b. Append results to memory.
       c. Repeat from step 2 (up to MAX_TOOL_ITERATIONS).
    4. When the model returns plain content → close the turn.
    5. Optionally run the history summariser if the buffer is getting large.
    """

    MAX_TOOL_ITERATIONS = 6

    def __init__(
        self,
        llm: BaseLLM,
        registry: ToolRegistry,
        memory: IntelligentMemoryManager,
        on_event: Optional[EventCallback] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.memory = memory
        self.on_event = on_event or (lambda _t, _d: None)
        self.stop_event = stop_event or threading.Event()

    # ── Public entry point ────────────────────────────────────────────────────

    def run_turn(
        self,
        user_input: str,
        allowed_skill_names: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Process one full user turn.

        allowed_skill_names: if provided, only those skills are exposed to the
        LLM.  Pass None or [] to expose all skills.

        Returns the final assistant text (Markdown), or None if interrupted.
        """
        self.memory.append_user(user_input)

        tools = (
            self.registry.get_filtered_schemas(allowed_skill_names)
            if allowed_skill_names is not None
            else self.registry.get_all_tool_schemas()
        )

        for iteration in range(self.MAX_TOOL_ITERATIONS):
            if self.stop_event.is_set():
                self.memory.close_turn()
                return None

            messages = self.memory.get_messages()
            # On the final iteration suppress tools to force a plain-text response
            active_tools = tools if iteration < self.MAX_TOOL_ITERATIONS - 1 else None

            content, tool_calls = self._stream_response(messages, active_tools)

            if self.stop_event.is_set():
                self.memory.close_turn()
                return None

            if not tool_calls:
                # ── Final answer ──────────────────────────────────────────
                self.memory.append_assistant(content)
                self.memory.close_turn()

                if self.memory.should_summarize():
                    self.memory.summarize(self.llm)

                return content

            # ── Parallel tool execution ───────────────────────────────────
            assistant_msg = _build_assistant_tool_msg(content, tool_calls)
            tool_results = self._execute_tool_calls(tool_calls)

            if self.stop_event.is_set():
                self.memory.close_turn()
                return None

            self.memory.append_tool_turn(assistant_msg, tool_results)

        # Exceeded max iterations — return whatever content we have
        self.memory.close_turn()
        return content or "I was unable to complete the task within the iteration limit."

    # ── Streaming ────────────────────────────────────────────────────────────

    def _stream_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[list],
    ):
        """
        Stream the LLM response.
        Returns (content: str, tool_calls: list[ToolCall] | None).
        """
        content = ""
        tool_calls: Optional[List[ToolCall]] = None

        try:
            for chunk in self.llm.stream(messages, tools=tools):
                if self.stop_event.is_set():
                    break

                if chunk.content:
                    content += chunk.content
                    self.on_event("content_chunk", {"chunk": chunk.content})

                # Accumulate tool calls — a single chunk may carry multiple
                if chunk.tool_calls:
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.extend(chunk.tool_calls)

        except Exception as exc:
            self.on_event("error", {"message": str(exc)})
            return content, None

        return content, tool_calls

    # ── Tool execution ────────────────────────────────────────────────────────

    def _execute_tool_calls(
        self, tool_calls: List[ToolCall]
    ) -> List[Dict[str, Any]]:
        """
        Execute all tool calls in the list and return tool-result messages.
        Parallel calls from the LLM are executed sequentially here
        (parallelism at the LLM level, safety at execution level).
        """
        results = []

        for tc in tool_calls:
            if self.stop_event.is_set():
                break

            self.on_event("tool_call", {"name": tc.name, "arguments": tc.arguments})

            result = self._run_one_tool(tc.name, tc.arguments)

            self.on_event("tool_result", {"name": tc.name, "result": result[:300]})

            results.append({"role": "tool", "content": result, "name": tc.name})

        return results

    def _run_one_tool(self, tool_name: str, arguments: dict) -> str:
        if tool_name not in self.registry.tools:
            return f"Error: tool '{tool_name}' not found in registry."

        tool_class = self.registry.tools[tool_name]
        instance = tool_class()

        try:
            params = tool_class.input_model(**arguments)
            return instance.execute(params)
        except Exception as exc:
            return f"Tool execution failed ({tool_name}): {exc}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_assistant_tool_msg(
    content: str, tool_calls: List[ToolCall]
) -> Dict[str, Any]:
    """Build the assistant message that echoes tool calls back to the API."""
    return {
        "role": "assistant",
        "content": content,
        "tool_calls": [
            {"function": {"name": tc.name, "arguments": tc.arguments}}
            for tc in tool_calls
        ],
    }
