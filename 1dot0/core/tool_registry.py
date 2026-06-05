import os
import importlib
import inspect
from typing import Dict, Type
from skills.base_skill import BaseSkill

class ToolRegistry:
    """
    Scans the skills directory and automatically registers any class 
    that inherits from BaseSkill.
    """
    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = skills_dir
        self.tools: Dict[str, Type[BaseSkill]] = {}

    def discover_skills(self):
        """Iterates through the skills directory and loads valid tools."""
        for filename in os.listdir(self.skills_dir):
            if filename.endswith(".py") and filename != "__init__.py" and filename != "base_skill.py":
                module_name = filename[:-3]
                
                try:
                    # Dynamically import the module (e.g., skills.system_time)
                    module = importlib.import_module(f"{self.skills_dir}.{module_name}")
                    
                    # Inspect the module for classes
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        # Check if it inherits from BaseSkill and IS NOT the BaseSkill itself
                        if issubclass(obj, BaseSkill) and obj is not BaseSkill:
                            self.tools[obj.name] = obj
                            
                except Exception as e:
                    print(f"Warning: Failed to load skill from {filename}. Error: {e}")

    def get_all_schemas(self) -> list:
        """Returns the JSON schemas for all discovered tools."""
        return [tool.get_schema() for tool in self.tools.values()]