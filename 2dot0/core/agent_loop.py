import sys
import threading
from typing import Optional, List, Dict, Any

from rich.console import Console

from core.llm_provider import BaseLLM, StreamChunk, ToolCall
from core.memory_manager import IntelligentMemoryManager
from core.tool_registry import ToolRegistry
from core.tts_engine import TTSEngine


class AgentLoop:
    """
    The core agentic loop that drives a single user turn end-to-end.

    Flow per turn
    ─────────────
    1. Append the user message to memory.
    2. Stream the LLM response (with tool schemas injected).
    3. If the model emits tool_calls → execute them, add results to memory,
       repeat from step 2 (up to MAX_TOOL_ITERATIONS).
    4. When the model returns plain content → flush TTS, close the turn.
    5. Optionally run the history summariser if the buffer is getting large.

    Interrupt safety
    ────────────────
    A shared threading.Event (stop_event) is checked inside the streaming
    loop. Setting it (via Ctrl+C in jarvis2.py) cuts the stream and silences
    the TTS immediately.
    """

    MAX_TOOL_ITERATIONS = 10

    def __init__(
        self,
        llm: BaseLLM,
        registry: ToolRegistry,
        memory: IntelligentMemoryManager,
        tts: TTSEngine,
        console: Console,
        stop_event: threading.Event,
    ) -> None:
        self.llm = llm
        self.registry = registry
        self.memory = memory
        self.tts = tts
        self.console = console
        self.stop_event = stop_event

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run_turn(self, user_input: str) -> Optional[str]:
        """
        Process one full user turn, including any tool-calling sub-steps.
        Returns the final assistant text, or None if interrupted.
        """
        self.memory.append_user(user_input)
        tools = self.registry.get_all_tool_schemas()

        for iteration in range(self.MAX_TOOL_ITERATIONS):
            messages = self.memory.get_messages()

            # On the final iteration, suppress tools to force a text response
            active_tools = tools if iteration < self.MAX_TOOL_ITERATIONS - 1 else None

            content, tool_calls = self._stream_response(messages, active_tools)

            if self.stop_event.is_set():
                self.memory.close_turn()
                return None

            if not tool_calls:
                # ── Final answer ──────────────────────────────────────────
                self.tts.flush_buffer()
                self.memory.append_assistant(content)
                self.memory.close_turn()

                if self.memory.should_summarize():
                    self.console.print(
                        "\n[dim][Memory: compressing old context...][/dim]"
                    )
                    self.memory.summarize(self.llm)

                return content

            # ── Tool execution ────────────────────────────────────────────
            self.console.print()  # blank line before tool status

            assistant_msg = self._build_assistant_tool_msg(content, tool_calls)
            tool_results = self._execute_tool_calls(tool_calls)

            if self.stop_event.is_set():
                self.memory.close_turn()
                return None

            self.memory.append_tool_turn(assistant_msg, tool_results)
            self.console.print()  # blank line after tool status

        # Should never reach here in normal operation
        self.memory.close_turn()
        return None

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    def _stream_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[list],
    ):
        """
        Stream the LLM response.
        Returns (content: str, tool_calls: list | None).
        Shows a spinner until the first content token arrives.
        """
        content = ""
        tool_calls = None  # Or initialize as [] if your backend prefers an empty list over None
        started_output = False

        status = self.console.status("[cyan]Thinking...[/cyan]", spinner="dots")
        status.start()

        try:
            for chunk in self.llm.stream(messages, tools=tools):
                if self.stop_event.is_set():
                    break

                if chunk.content and not started_output:
                    status.stop()
                    started_output = True
                    # Print the JARVIS label; subsequent chunks go to raw stdout
                    self.console.print()
                    self.console.print("[bold cyan]JARVIS:[/bold cyan] ", end="")

                if chunk.content:
                    sys.stdout.write(chunk.content)
                    sys.stdout.flush()
                    content += chunk.content
                    self.tts.feed_chunk(chunk.content)

                # ── Accumulate tool calls instead of overwriting them ──
                if chunk.tool_calls:
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.extend(chunk.tool_calls)

        except Exception as exc:
            status.stop()
            self.console.print(f"\n[red]Stream error: {exc}[/red]")
            return content, None
        finally:
            status.stop()
            if started_output:
                sys.stdout.write("\n")
                sys.stdout.flush()

        return content, tool_calls

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    def _execute_tool_calls(
        self, tool_calls: List[ToolCall]
    ) -> List[Dict[str, Any]]:
        """Execute all tool calls and return a list of tool-result messages."""
        results = []
        for tc in tool_calls:
            if self.stop_event.is_set():
                break

            self.console.print(
                f"  [bold yellow]⚙  Calling:[/bold yellow] [yellow]{tc.name}[/yellow]"
                + (f"  [dim]{tc.arguments}[/dim]" if tc.arguments else "")
            )

            result = self._run_one_tool(tc.name, tc.arguments)
            snippet = result[:120] + ("…" if len(result) > 120 else "")
            self.console.print(f"  [bold green]✓  Result:[/bold green] [dim]{snippet}[/dim]")

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
            return f"Tool execution failed: {exc}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_assistant_tool_msg(
        content: str, tool_calls: List[ToolCall]
    ) -> Dict[str, Any]:
        """Build the assistant message dict that echoes tool calls back to the API."""
        return {
            "role": "assistant",
            "content": content,
            "tool_calls": [
                {"function": {"name": tc.name, "arguments": tc.arguments}}
                for tc in tool_calls
            ],
        }
