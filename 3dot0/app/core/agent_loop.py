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

from app.core.llm_provider import BaseLLM, StreamChunk, TokenUsage, ToolCall
from app.core.memory_manager import IntelligentMemoryManager
from app.core.tool_registry import ToolRegistry


# ── Event callback type ───────────────────────────────────────────────────────
# Signature: on_event(event_type: str, data: dict)
# event_type values: "tool_call", "tool_result", "content_chunk", "error"
EventCallback = Callable[[str, Dict[str, Any]], None]

SENTINEL_WAITING = "__WAITING_FOR_USER__:"


class UserInputRequired(Exception):
    """Raised when the ask_user skill pauses execution pending a user reply."""
    def __init__(self, feed_item_id: int, memory=None, tool_call_id: Optional[str] = None, tool_name: str = "ask_user") -> None:
        self.feed_item_id = feed_item_id
        self.memory = memory  # IntelligentMemoryManager instance to serialize
        self.tool_call_id = tool_call_id  # Gemini function call ID — echoed in placeholder result
        self.tool_name = tool_name
        super().__init__(f"Waiting for user reply on feed item {feed_item_id}")


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
        task_id: Optional[int] = None,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.memory = memory
        self.on_event = on_event or (lambda _t, _d: None)
        self.stop_event = stop_event or threading.Event()
        self.task_id = task_id
        # Accumulated token usage across all LLM calls in this turn
        self._accumulated_usage: TokenUsage = TokenUsage()

    # ── Public entry point ────────────────────────────────────────────────────

    def run_turn(
        self,
        user_input: str,
        allowed_skill_names: Optional[List[str]] = None,
        max_iterations: Optional[int] = None,
    ) -> Optional[str]:
        """
        Process one full user turn.

        allowed_skill_names:
          - None → expose ALL skills (default for manual tasks)
          - []   → expose NO skills (routine with nothing checked)
          - ['x'] → expose only skill 'x'

        max_iterations: override MAX_TOOL_ITERATIONS for this turn.

        Returns the final assistant text (Markdown), or None if interrupted.
        """
        self.memory.append_user(user_input)
        max_iters = max_iterations if max_iterations is not None else self.MAX_TOOL_ITERATIONS

        tools = (
            self.registry.get_filtered_schemas(allowed_skill_names)
            if allowed_skill_names is not None
            else self.registry.get_all_tool_schemas()
        )
        # Empty tool list → send None so the LLM doesn't get an empty array
        if tools is not None and len(tools) == 0:
            tools = None
        content = ""
        for iteration in range(max_iters):
            if self.stop_event.is_set():
                self.memory.close_turn()
                return None

            if self.task_id:
                try:
                    from app.database import session_scope
                    from app.models import Task, FeedItem, FeedItemType
                    from app.core.markdown_utils import render_markdown

                    with session_scope() as session:
                        task = session.get(Task, self.task_id)
                        if task and task.pause_requested:
                            task.pause_requested = False
                            session.add(task)
                            session.flush()

                            title = "Task Paused"
                            content_md = (
                                f"## Task Paused\n\n"
                                f"JARVIS is paused on task #{self.task_id}. "
                                f"Please provide your feedback or instructions below to resume."
                            )
                            content_html = render_markdown(content_md)

                            feed_item = FeedItem(
                                user_id=task.user_id,
                                task_id=self.task_id,
                                type=FeedItemType.question,
                                title=title,
                                content_markdown=content_md,
                                content_html=content_html,
                                is_read=False,
                            )
                            session.add(feed_item)
                            session.flush()
                            feed_item_id = feed_item.id

                            raise UserInputRequired(
                                feed_item_id=feed_item_id,
                                memory=self.memory,
                            )
                except UserInputRequired:
                    raise
                except Exception:
                    pass

            messages = self.memory.get_messages()
            # On the final iteration suppress tools to force a plain-text response
            active_tools = tools if iteration < max_iters - 1 else None

            content, tool_calls = self._stream_response(messages, active_tools)

            if self.stop_event.is_set():
                self.memory.close_turn()
                return None

            if not tool_calls:
                # ── Final answer ──────────────────────────────────────────
                # If model returned nothing, ask it to summarise what it did
                if not content.strip() and iteration > 0:
                    self.on_event("status", {"message": "Generating summary…"})
                    summary_msgs = self.memory.get_messages() + [
                        {"role": "user", "content": (
                            "Please provide a clear Markdown summary of everything you "
                            "accomplished in this task, including which files you read/edited "
                            "and what changes were made."
                        )}
                    ]
                    summary_content, _ = self._stream_response(summary_msgs, None)
                    content = summary_content or "Task completed (no summary generated)."

                self.memory.append_assistant(content)
                self.memory.close_turn()

                if self.memory.should_summarize():
                    self.memory.summarize(self.llm)

                self._emit_token_usage()
                return content

            # ── Parallel tool execution ───────────────────────────────────
            assistant_msg = _build_assistant_tool_msg(content, tool_calls)
            try:
                tool_results = self._execute_tool_calls(tool_calls)
            except UserInputRequired as exc:
                # Persist the pending tool call and a placeholder result to memory
                # so that when the task resumes the LLM has full context of the exchange.
                placeholder: Dict[str, Any] = {
                    "role": "tool",
                    "content": "[Awaiting your response]",
                    "name": exc.tool_name,
                }
                # Gemini uses a function-call ID to correlate tool responses with calls;
                # include it so the model can correctly match the placeholder on resume.
                if exc.tool_call_id:
                    placeholder["tool_call_id"] = exc.tool_call_id
                self.memory.append_tool_turn(assistant_msg, [placeholder])
                self.memory.close_turn()
                raise

            if self.stop_event.is_set():
                self.memory.close_turn()
                return None

            self.memory.append_tool_turn(assistant_msg, tool_results)

        # Exceeded max iterations — force a plain-text summary
        self.on_event("status", {"message": "Max iterations reached — generating summary…"})
        summary_msgs = self.memory.get_messages() + [
            {"role": "user", "content": (
                "You have reached the tool call limit. Please provide a clear Markdown summary "
                "of everything you accomplished so far, and what (if anything) still needs to be done."
            )}
        ]
        final_content, _ = self._stream_response(summary_msgs, None)
        self.memory.append_assistant(final_content or content or "Iteration limit reached.")
        self.memory.close_turn()
        self._emit_token_usage()
        return final_content or content or "Iteration limit reached."

    # ── LLM call ─────────────────────────────────────────────────────────────

    def _stream_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[list],
    ):
        """
        Call the LLM and return (content: str, tool_calls: list[ToolCall] | None).

        When tools are provided we use the non-streaming API — streaming is
        unreliable for tool extraction because many models (including Gemma)
        only populate tool_calls on the final chunk, and quantised models
        sometimes write tool invocations as plain text in content instead.

        When no tools are provided (final answer turn) we stream so the user
        can see progress via WebSocket events.
        """
        if tools:
            # Non-streaming: reliable tool-call extraction
            try:
                chunk = self.llm.chat(messages, tools=tools)
                if chunk.usage:
                    self._accumulated_usage = self._accumulated_usage + chunk.usage
                if getattr(chunk, "thought", None):
                    self.on_event("thought", {"message": chunk.thought})
                return chunk.content, chunk.tool_calls or None
            except Exception as exc:
                self.on_event("error", {"message": str(exc)})
                return "", None
        else:
            # Streaming: show content progress for final text answer
            content = ""
            try:
                for chunk in self.llm.stream(messages, tools=None):
                    if self.stop_event.is_set():
                        break
                    if getattr(chunk, "thought", None):
                        self.on_event("thought", {"message": chunk.thought})
                    if chunk.content:
                        content += chunk.content
                        self.on_event("content_chunk", {"content": chunk.content})
                    if chunk.usage:
                        self._accumulated_usage = self._accumulated_usage + chunk.usage
            except Exception as exc:
                self.on_event("error", {"message": str(exc)})
            return content, None

    # ── Token usage ───────────────────────────────────────────────────────────

    def _emit_token_usage(self) -> None:
        """Emit accumulated token usage as a 'token_usage' event."""
        u = self._accumulated_usage
        if u.total_tokens > 0:
            self.on_event("token_usage", {
                "prompt_tokens": u.prompt_tokens,
                "completion_tokens": u.completion_tokens,
                "thinking_tokens": u.thinking_tokens,
                "total_tokens": u.total_tokens,
            })

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

            # Detect ask_user sentinel — pause the agent loop
            if result.startswith(SENTINEL_WAITING):
                feed_item_id = int(result[len(SENTINEL_WAITING):])
                raise UserInputRequired(
                    feed_item_id,
                    memory=self.memory,
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                )

            self.on_event("tool_result", {"name": tc.name, "result": result[:300]})

            results.append({
                "role": "tool",
                "content": result,
                "name": tc.name,
                **({"tool_call_id": tc.id} if tc.id else {}),
            })

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
            {
                "function": {"name": tc.name, "arguments": tc.arguments},
                "id": tc.id,
                "thought_signature": tc.thought_signature,
            }
            for tc in tool_calls
        ],
    }
