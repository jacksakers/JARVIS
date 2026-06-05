from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseLLM(ABC):
    """
    Abstract Base Class for all LLM providers. 
    This ensures that whether you use Ollama, OpenAI, or Anthropic,
    the master script always calls the exact same method.
    """
    
    @abstractmethod
    def generate(self, messages: List[Dict[str, Any]]) -> str:
        """
        Takes a list of message dictionaries:
        [{"role": "system", "content": "You are JARVIS..."}, {"role": "user", "content": "Hello"}]
        and returns the string response.
        """
        pass