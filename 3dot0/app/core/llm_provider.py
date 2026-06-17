from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional


@dataclass
class ToolCall:
    """Provider-agnostic representation of a single tool call from the LLM."""
    name: str
    arguments: dict
    # Gemini-specific: function call ID for correlating responses with thought signatures
    id: Optional[str] = field(default=None)
    # Gemini thinking models: opaque bytes that must be echoed back verbatim
    thought_signature: Optional[bytes] = field(default=None)


@dataclass
class TokenUsage:
    """Token counts returned by the provider for a single API call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    thinking_tokens: int = 0   # Gemini thinking models only

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens + self.thinking_tokens

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            thinking_tokens=self.thinking_tokens + other.thinking_tokens,
        )


@dataclass
class StreamChunk:
    """Provider-agnostic streaming chunk. Carries content and/or tool calls."""
    content: str = ""
    # A chunk may carry multiple tool calls (Gemma4 / parallel tool calling)
    tool_calls: Optional[List[ToolCall]] = field(default=None)
    done: bool = False
    # Token usage — only populated on the final chunk (done=True) for Gemini
    usage: Optional[TokenUsage] = field(default=None)


class BaseLLM(ABC):
    """
    Abstract base class for all LLM providers.
    The agent loop and worker only depend on this interface, never on a
    specific SDK, keeping them provider-agnostic.
    """

    @abstractmethod
    def generate(self, messages: List[Dict[str, Any]]) -> Generator[str, None, None]:
        """
        Simple streaming text generation without tool calling.
        Used for memory summarisation and internal tasks.
        Yields plain text strings.
        """

    @abstractmethod
    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[dict]] = None,
    ) -> Generator[StreamChunk, None, None]:
        """
        Full streaming generation with optional tool support.
        Yields StreamChunk objects.  tool_calls on a chunk may contain
        multiple entries — callers must handle parallel tool calls.
        """

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[dict]] = None,
    ) -> StreamChunk:
        """
        Non-streaming single-shot chat with optional tool support.
        Returns a single StreamChunk with the complete content and/or tool_calls.
        Default implementation collects the stream — providers should override
        for a direct non-streaming API call when available.
        """
        content = ""
        tool_calls: Optional[List[ToolCall]] = None
        usage: Optional[TokenUsage] = None
        for chunk in self.stream(messages, tools):
            content += chunk.content
            if chunk.tool_calls:
                tool_calls = (tool_calls or []) + chunk.tool_calls
            if chunk.usage:
                usage = (usage + chunk.usage) if usage else chunk.usage
        return StreamChunk(content=content, tool_calls=tool_calls, done=True, usage=usage)

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the provider is reachable and the model is available."""
