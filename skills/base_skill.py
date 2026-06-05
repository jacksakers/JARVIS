from abc import ABC, abstractmethod
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
    def get_schema(cls) -> dict:
        """
        Automatically generates the JSON schema that the LLM needs to understand the tool.
        """
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": cls.input_model.schema()
        }