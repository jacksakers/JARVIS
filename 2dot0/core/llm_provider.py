from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Generator, Optional


@dataclass
class ToolCall:
    """Provider-agnostic representation of a tool call from the LLM."""
    name: str
    arguments: dict


@dataclass
class StreamChunk:
    """Provider-agnostic streaming chunk. Carries either content or tool calls."""
    content: str = ""
    tool_calls: Optional[List[ToolCall]] = field(default=None)
    done: bool = False


class BaseLLM(ABC):
    """
    Abstract Base Class for all LLM providers.
    Implementors must return provider-agnostic StreamChunk objects,
    keeping the agent loop decoupled from any specific SDK.
    """

    @abstractmethod
    def generate(self, messages: List[Dict[str, Any]]) -> Generator[str, None, None]:
        """
        Simple streaming text generation without tool calling.
        Used for summarisation and internal tasks.
        Yields plain text strings.
        """
        pass

    @abstractmethod
    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[dict]] = None,
    ) -> Generator[StreamChunk, None, None]:
        """
        Full streaming generation with optional tool support.
        Yields StreamChunk objects so the agent loop stays provider-agnostic.
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the provider is reachable and the model is available."""
        pass
