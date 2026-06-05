"""
The recursive agent loop.

run_agent_turn() drives a single user turn end-to-end:
  LLM responds → tool detected → execute → feed result → LLM responds again …
  … until the LLM replies with no tool call (the final answer).

extract_tool_call() parses the LLM's plain-text tool format:

  TOOL: <tool_name>
  <arg>: <value>
  <arg>: <value>
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.llm_provider import BaseLLM
    from core.tool_registry import ToolRegistry


_MAX_ITERATIONS = 10  # hard cap to prevent infinite loops


def extract_tool_call(text: str) -> dict | None:
    """
    Scan the LLM output for a plain-text tool invocation block.
    Returns {"tool": str, "args": dict} or None.
    """
    lines = text.strip().split("\n")
    tool_name: str | None = None
    args: dict[str, str] = {}

    for line in lines:
        line = line.strip()

        if line.startswith("TOOL:"):
            tool_name = line.removeprefix("TOOL:").strip()
            args = {}          # reset args for this tool block
            continue

        if tool_name:
            if ":" in line:
                key, _, val = line.partition(":")
                args[key.strip()] = val.strip()
            # blank lines or non-colon lines after a tool block → keep scanning;
            # a second TOOL: line is handled by the next iteration naturally

    return {"tool": tool_name, "args": args} if tool_name else None


def run_agent_turn(
    messages: list[dict],
    llm: "BaseLLM",
    registry: "ToolRegistry",
) -> str:
    """
    Execute one full user turn with recursive tool calling.
    Mutates `messages` in-place (appends assistant + tool-result turns).
    Returns the final assistant reply text.
    """
    for iteration in range(_MAX_ITERATIONS):
        # --- LLM inference (streaming) ---
        response_text = ""
        print("JARVIS: ", end="", flush=True)

        for chunk in llm.generate(messages):
            print(chunk, end="", flush=True)
            response_text += chunk

        print()  # newline after stream ends

        messages.append({"role": "assistant", "content": response_text})

        # --- Check for a tool call ---
        tool_call = extract_tool_call(response_text)

        if not tool_call:
            # Clean response — we're done
            return response_text

        tool_name = tool_call["tool"]
        args = tool_call.get("args", {})

        print(f"\n[Executing tool: {tool_name}]")

        # --- Execute the tool ---
        if tool_name not in registry.tools:
            result = f"Error: tool '{tool_name}' does not exist. Available: {list(registry.tools.keys())}"
            print(f"[Tool Error: {result}]")
        else:
            tool_class = registry.tools[tool_name]
            tool_instance = tool_class()
            try:
                validated = tool_instance.input_model(**args)
                result = tool_instance.execute(validated)
                print(f"[Tool Result: {result}]")
            except Exception as e:
                result = f"Tool execution error: {e}"
                print(f"[Tool Error: {result}]")

        # Feed result back so the next iteration can decide what to do next
        messages.append({
            "role": "system",
            "content": (
                f"Tool '{tool_name}' returned: {result}\n"
                "Continue your reasoning. Call another tool if still needed, "
                "or give your final answer to the user."
            ),
        })

    # Safety fallback
    fallback = "[Reached maximum tool iterations without a final answer.]"
    print(f"\n{fallback}")
    return fallback
