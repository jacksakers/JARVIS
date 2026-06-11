from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, List, Optional


@dataclass
class ToolCall:
    """Provider-agnostic representation of a single tool call from the LLM."""
    name: str
    arguments: dict


@dataclass
class StreamChunk:
    """Provider-agnostic streaming chunk. Carries content and/or tool calls."""
    content: str = ""
    # A chunk may carry multiple tool calls (Gemma4 / parallel tool calling)
    tool_calls: Optional[List[ToolCall]] = field(default=None)
    done: bool = False


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

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the provider is reachable and the model is available."""
