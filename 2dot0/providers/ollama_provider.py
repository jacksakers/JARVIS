from typing import List, Dict, Any, Generator, Optional

import ollama as _sdk

from core.llm_provider import BaseLLM, StreamChunk, ToolCall


class OllamaProvider(BaseLLM):
    """
    LLM provider backed by the official Ollama Python SDK.
    Uses native tool-calling support instead of prompt-level text parsing.
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        options: Optional[dict] = None,
    ) -> None:
        self.model = model
        self.options = options or {}
        self._client = _sdk.Client(host=base_url)

    # ------------------------------------------------------------------
    # BaseLLM interface
    # ------------------------------------------------------------------

    def generate(self, messages: List[Dict[str, Any]]) -> Generator[str, None, None]:
        """
        Simple streaming generation with no tools.
        Used internally for summarisation and one-shot tasks.
        """
        # Print what we are sending to Ollama for debugging (can be removed later)
        print(f"\n[DEBUG] Sending to Ollama: {messages}\n")
        try:
            for chunk in self._client.chat(
                model=self.model,
                messages=messages,
                stream=True,
                options=self.options,
            ):
                if chunk.message.content:
                    yield chunk.message.content
        except _sdk.ResponseError as exc:
            yield f"\n[Ollama error: {exc.error}]"
        except Exception as exc:
            yield f"\n[Connection error: {exc}]"

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[dict]] = None,
    ) -> Generator[StreamChunk, None, None]:
        """
        Full streaming with optional tool-calling support.
        Wraps Ollama SDK chunks in provider-agnostic StreamChunk objects.
        """
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": self.options,
        }
        if tools:
            kwargs["tools"] = tools

        # print what we are sending to Ollama for debugging (can be removed later)
        print(f"\n[DEBUG] Sending to Ollama: {kwargs}\n")

        try:
            for chunk in self._client.chat(**kwargs):
                # print the raw chunk for debugging (can be removed later)
                # print(f"\n[DEBUG] Received chunk from Ollama: {chunk}\n")
                tool_calls: Optional[List[ToolCall]] = None
                if chunk.message.tool_calls:
                    print(f"\n[DEBUG] Detected tool calls in chunk: {chunk.message.tool_calls}\n")
                    tool_calls = [
                        ToolCall(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        )
                        for tc in chunk.message.tool_calls
                    ]
                yield StreamChunk(
                    content=chunk.message.content or "",
                    tool_calls=tool_calls,
                    done=chunk.done,
                )
        except _sdk.ResponseError as exc:
            yield StreamChunk(content=f"\n[Ollama error: {exc.error}]", done=True)
        except Exception as exc:
            yield StreamChunk(content=f"\n[Connection error: {exc}]", done=True)

    def test_connection(self) -> bool:
        """Ping Ollama and verify the configured model is available."""
        try:
            available = [m.model for m in self._client.list().models]
            # Accept if model name is a prefix match (e.g. "llama3.2:3b" in "llama3.2:3b")
            return any(self.model.lower() in m.lower() for m in available)
        except Exception:
            return False
