from abc import ABC, abstractmethod
from typing import List, Dict, Any, Generator

class BaseLLM(ABC):
    """
    Abstract Base Class for all LLM providers. 
    """
    
    @abstractmethod
    def generate(self, messages: List[Dict[str, Any]]) -> Generator[str, None, None]:
        """
        Takes a list of message dictionaries and YIELDS string chunks (streaming).
        """
        pass