import os
from pathlib import Path
from pydantic import BaseModel, Field

from .base_skill import BaseSkill

# ── Configuration ────────────────────────────────────────────────────────────

# Change this path whenever you want JARVIS to look at a different project.
# Using .resolve() ensures we have the absolute, canonical path.
PROJECT_ROOT = Path("/home/jack/src/Frigishare").resolve()

# Folders JARVIS should probably ignore to save context space
IGNORE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".idea"}


def _get_safe_path(relative_path: str) -> Path:
    """
    Resolves the target path and ensures it is safely within the PROJECT_ROOT.
    Raises a ValueError if JARVIS tries to path-traverse (e.g., using '../../').
    """
    target = (PROJECT_ROOT / relative_path).resolve()
    
    # Check if the target is the root itself or contained within the root
    if target == PROJECT_ROOT or PROJECT_ROOT in target.parents:
        return target
    else:
        raise ValueError("Security Sandbox Violation: Path is outside the allowed project directory.")


# ── list_directory ───────────────────────────────────────────────────────────

class ListDirectoryInput(BaseModel):
    directory_path: str = Field(
        default=".",
        description="The relative path of the directory to list. Use '.' for the root of the project."
    )

class ListDirectorySkill(BaseSkill):
    name = "list_directory"
    description = (
        "Lists the files and folders within a specific directory of the project. "
        "Use this to understand the project structure and find specific files to read."
    )
    input_model = ListDirectoryInput

    def execute(self, params: ListDirectoryInput) -> str:
        try:
            target_dir = _get_safe_path(params.directory_path)
            
            if not target_dir.exists():
                return f"Error: Directory '{params.directory_path}' does not exist."
            if not target_dir.is_dir():
                return f"Error: '{params.directory_path}' is a file, not a directory. Use read_file instead."

            items = []
            for item in target_dir.iterdir():
                if item.name in IGNORE_DIRS:
                    continue
                
                # Format to show if it's a file or directory
                if item.is_dir():
                    items.append(f"[DIR]  {item.name}/")
                else:
                    items.append(f"[FILE] {item.name}")
            
            if not items:
                return f"The directory '{params.directory_path}' is empty."

            # Sort alphabetically with directories likely grouped together naturally
            items.sort()
            
            header = f"Contents of directory: {params.directory_path}\n"
            return header + "\n".join(items)

        except Exception as exc:
            return f"Failed to list directory: {exc}"


# ── read_file ────────────────────────────────────────────────────────────────

class ReadFileInput(BaseModel):
    file_path: str = Field(
        description="The relative path to the file you want to read (e.g., 'src/main.py')."
    )

class ReadFileSkill(BaseSkill):
    name = "read_file"
    description = (
        "Reads the text content of a specific file in the project directory. "
        "Use this to inspect code so you can suggest edits or find bugs."
    )
    input_model = ReadFileInput

    def execute(self, params: ReadFileInput) -> str:
        try:
            target_file = _get_safe_path(params.file_path)
            
            if not target_file.exists():
                return f"Error: File '{params.file_path}' does not exist."
            if not target_file.is_file():
                return f"Error: '{params.file_path}' is a directory, not a file. Use list_directory instead."

            # Read the file strictly in read-only mode ('r')
            with open(target_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Truncate to protect the LLM context window (roughly 10,000 characters)
            max_chars = 10000
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n\n...[FILE TRUNCATED AT {max_chars} CHARACTERS TO SAVE CONTEXT]..."

            return f"--- START OF {params.file_path} ---\n{content}\n--- END OF {params.file_path} ---"

        except UnicodeDecodeError:
            return f"Error: '{params.file_path}' appears to be a binary file or uses an unsupported encoding."
        except Exception as exc:
            return f"Failed to read file: {exc}"