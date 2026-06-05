from abc import ABC, abstractmethod
import json
from pydantic import BaseModel
from typing import Type

class BaseSkill(ABC):
    """
    Every tool/skill in the framework MUST inherit from this class.
    """
    name: str = "BaseSkill"
    description: str = "Base description"
    keywords: list[str] = []
    
    # We use Pydantic models to strictly define what arguments the AI must pass.
    # Each child class will define its own Pydantic model and assign it here.
    input_model: Type[BaseModel] = BaseModel 

    @abstractmethod
    def execute(self, params: BaseModel) -> str:
        """
        The actual Python logic of the tool goes here.
        Must return a string for the LLM to read.
        """
        pass
        
    @classmethod
    def get_schema(cls) -> str:
        """
        Automatically generates the text readable schema that the LLM needs to understand the tool.
        """
        return f"Tool Name: {cls.name}, Description: {cls.description}"