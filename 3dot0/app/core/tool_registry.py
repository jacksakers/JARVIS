"""
ToolRegistry — adapted from JARVIS v2.0.
Auto-discovers BaseSkill subclasses from the app/skills/ directory.
Supports per-routine skill filtering (allowed_skill_names).
"""
import importlib
import inspect
import os
from pathlib import Path
from typing import Dict, List, Optional, Type

from app.skills.base_skill import BaseSkill


class ToolRegistry:
    """
    Scans the skills directory and registers every class that inherits from
    BaseSkill.  Returns Ollama-compatible tool schemas and supports filtering
    by an allowlist of skill names (used for per-routine tool gating).
    """

    def __init__(self, skills_dir: Optional[Path] = None) -> None:
        _default = Path(__file__).parent.parent / "skills"
        self.skills_dir: Path = skills_dir or _default
        self.tools: Dict[str, Type[BaseSkill]] = {}

    def discover_skills(self) -> None:
        """Walk the skills directory and load all valid BaseSkill subclasses."""
        for filename in os.listdir(self.skills_dir):
            if not filename.endswith(".py") or filename in ("__init__.py", "base_skill.py"):
                continue

            module_name = filename[:-3]
            # Build dotted import path relative to the package root
            module_path = f"app.skills.{module_name}"

            try:
                module = importlib.import_module(module_path)
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BaseSkill)
                        and obj is not BaseSkill
                        and hasattr(obj, "name")
                        and obj.name != "base_skill"
                    ):
                        self.tools[obj.name] = obj
            except Exception as exc:
                print(f"[ToolRegistry] Warning: could not load {filename}: {exc}")

    def get_all_tool_schemas(self) -> List[dict]:
        """Return Ollama-compatible schemas for every registered skill."""
        return [cls.get_ollama_tool_schema() for cls in self.tools.values()]

    def get_filtered_schemas(self, allowed_names: List[str]) -> List[dict]:
        """
        Return schemas filtered to the given allowlist.
        An empty allowlist means all skills are permitted.
        """
        if not allowed_names:
            return self.get_all_tool_schemas()
        return [
            cls.get_ollama_tool_schema()
            for name, cls in self.tools.items()
            if name in allowed_names
        ]

    def get_skill_metadata(self) -> List[dict]:
        """Return lightweight metadata dicts for each skill (for the DB sync)."""
        return [
            {
                "module_name": cls.__name__,
                "name": cls.name,
                "description": cls.description,
                "tool_schema": __import__("json").dumps(cls.get_ollama_tool_schema()),
            }
            for cls in self.tools.values()
        ]
