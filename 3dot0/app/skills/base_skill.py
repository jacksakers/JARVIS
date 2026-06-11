from abc import ABC, abstractmethod
from typing import Type

from pydantic import BaseModel


class BaseSkill(ABC):
    """
    Every JARVIS skill must inherit from this class.

    Class-level attributes
    ──────────────────────
    name        – Unique tool identifier (snake_case). Used as the function
                  name in the Ollama tool schema.
    description – Plain-English description fed directly to the LLM.
    input_model – A Pydantic BaseModel that defines and validates arguments.
    """

    name: str = "base_skill"
    description: str = "Base skill."
    input_model: Type[BaseModel] = BaseModel

    @abstractmethod
    def execute(self, params: BaseModel) -> str:
        """Run the skill and return a plain-text result for the LLM to read."""

    @classmethod
    def get_ollama_tool_schema(cls) -> dict:
        """
        Auto-generate an Ollama-compatible JSON tool schema from the Pydantic
        input model.  No manual JSON writing needed when adding a skill.
        """
        schema = cls.input_model.model_json_schema()
        schema.pop("title", None)

        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": schema,
            },
        }
