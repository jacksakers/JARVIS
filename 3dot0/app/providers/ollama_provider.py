from typing import Any, Dict, Generator, List, Optional

import ollama as _sdk

from app.core.llm_provider import BaseLLM, StreamChunk, ToolCall


class OllamaProvider(BaseLLM):
    """
    LLM provider backed by the official Ollama Python SDK.
    Uses native tool-calling support with the JSON function-calling spec.

    Parallel tool calls: Gemma4 and other models may return multiple tool_calls
    in a single response. The StreamChunk.tool_calls list handles this natively.
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

    # ── BaseLLM interface ─────────────────────────────────────────────────────

    def generate(self, messages: List[Dict[str, Any]]) -> Generator[str, None, None]:
        """
        Simple streaming generation with no tools.
        Used for memory summarisation and internal tasks.
        """
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

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[dict]] = None,
    ) -> "StreamChunk":
        """
        Non-streaming single call. Used for tool-calling iterations where
        streaming is unreliable (tool_calls only appear in the final chunk
        for many models, and some models write tool calls as text instead).
        """
        from app.core.llm_provider import StreamChunk, ToolCall as TC
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": self.options,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            response = self._client.chat(**kwargs)
            tool_calls = None
            if response.message.tool_calls:
                tool_calls = [
                    TC(
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                    for tc in response.message.tool_calls
                ]
            return StreamChunk(
                content=response.message.content or "",
                tool_calls=tool_calls,
                done=True,
            )
        except _sdk.ResponseError as exc:
            return StreamChunk(content=f"\n[Ollama error: {exc.error}]", done=True)
        except Exception as exc:
            return StreamChunk(content=f"\n[Connection error: {exc}]", done=True)

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[dict]] = None,
    ) -> Generator[StreamChunk, None, None]:
        """
        Full streaming with optional tool-calling support.
        A single chunk may carry multiple tool_calls (parallel calling).
        """
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": self.options,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            for chunk in self._client.chat(**kwargs):
                tool_calls: Optional[List[ToolCall]] = None

                if chunk.message.tool_calls:
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
            return any(self.model.lower() in m.lower() for m in available)
        except Exception:
            return False
