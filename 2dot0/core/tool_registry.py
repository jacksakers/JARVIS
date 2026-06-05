import os
import importlib
import inspect
from typing import Dict, Type

from skills.base_skill import BaseSkill


class ToolRegistry:
    """
    Scans the skills/ directory and auto-registers every class
    that inherits from BaseSkill. Returns Ollama-compatible tool schemas.
    """

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = skills_dir
        self.tools: Dict[str, Type[BaseSkill]] = {}

    def discover_skills(self) -> None:
        """Walk the skills directory and load all valid skill classes."""
        for filename in os.listdir(self.skills_dir):
            if (
                not filename.endswith(".py")
                or filename in ("__init__.py", "base_skill.py")
            ):
                continue

            module_name = filename[:-3]
            try:
                module = importlib.import_module(f"{self.skills_dir}.{module_name}")
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseSkill) and obj is not BaseSkill:
                        self.tools[obj.name] = obj
            except Exception as exc:
                print(f"[ToolRegistry] Warning: failed to load {filename}: {exc}")

    def get_all_tool_schemas(self) -> list:
        """Return Ollama-compatible JSON tool schemas for every registered skill."""
        return [tool.get_ollama_tool_schema() for tool in self.tools.values()]
