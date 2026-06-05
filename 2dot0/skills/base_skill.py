from abc import ABC, abstractmethod
from typing import Type

from pydantic import BaseModel


class BaseSkill(ABC):
    """
    Every skill/tool in the JARVIS framework must inherit from this class.

    Class-level attributes
    ──────────────────────
    name        – Unique tool identifier (snake_case). Used as the function
                  name in the Ollama tool schema.
    description – Plain-English description fed directly to the LLM.
    input_model – A Pydantic BaseModel subclass that defines and validates
                  the arguments the LLM must supply.
    """

    name: str = "base_skill"
    description: str = "Base skill description."
    input_model: Type[BaseModel] = BaseModel

    @abstractmethod
    def execute(self, params: BaseModel) -> str:
        """
        Run the skill logic and return a plain-text result for the LLM to read.
        """
        pass

    @classmethod
    def get_ollama_tool_schema(cls) -> dict:
        """
        Auto-generate an Ollama-compatible JSON tool schema from the Pydantic
        input model. No manual schema writing required when you add a skill.
        """
        schema = cls.input_model.model_json_schema()
        # Strip Pydantic metadata that Ollama doesn't need
        schema.pop("title", None)

        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": schema,
            },
        }
