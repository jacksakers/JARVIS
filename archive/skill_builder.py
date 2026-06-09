import os
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field
from skills.base_skill import BaseSkill


class SkillAction(str, Enum):
    LIST = "list"
    READ = "read"
    WRITE = "write"


class SkillBuilderInput(BaseModel):
    action: SkillAction = Field(
        description="The file operation to execute: 'list' to look at available skills, 'read' to view an existing skill's code, or 'write' to create/overwrite a skill file."
    )
    filename: str = Field(
        default="",
        description="The name of the target file (e.g., 'reminder_skill.py'). Must end with '.py'. This parameter is ignored when using the 'list' action."
    )
    code: str = Field(
        default="",
        description="The full, valid Python source code string to be written into the file. Only required when the action is set to 'write'."
    )


class SkillBuilderSkill(BaseSkill):
    name = "manage_skills"
    description = (
        "Enables reading, writing, and listing Python files strictly inside the 'skills' directory. "
        "Use this tool to create new custom tools or read existing ones to debug compilation errors."
    )
    input_model = SkillBuilderInput

    def execute(self, params: SkillBuilderInput) -> str:
        # 1. Resolve the safe base directory relative to where JARVIS is running
        sandbox_dir = (Path.cwd() / "skills").resolve()
        sandbox_dir.mkdir(parents=True, exist_ok=True)

        # ── Action: LIST ──────────────────────────────────────────────
        if params.action == SkillAction.LIST:
            try:
                files = [
                    f.name for f in sandbox_dir.iterdir() 
                    if f.is_file() and f.suffix == ".py"
                ]
                if not files:
                    return "The skills directory is currently empty."
                
                return "Available skill files:\n" + "\n".join(f"- {f}" for f in files)
            except Exception as exc:
                return f"Error listing skills directory: {exc}"

        # ── Parameter Validation for File I/O ─────────────────────────
        if not params.filename:
            return "Error: The 'filename' parameter is required for 'read' and 'write' actions."

        # Safety Check 1: Enforce code-only file extensions
        if not params.filename.endswith(".py"):
            return "Security Error: Unauthorized file extension. You are strictly restricted to modifying '.py' files."

        # Safety Check 2: Block Path Traversal
        # Combines the sandbox root with the filename and completely resolves absolute paths
        target_path = (sandbox_dir / params.filename).resolve()

        # Confirm the canonical path stays physically within the sandbox folder boundary
        if not target_path.is_relative_to(sandbox_dir):
            return "Security Error: Directory traversal detected. You do not have permission to access files outside the 'skills/' folder."

        # ── Action: READ ──────────────────────────────────────────────
        if params.action == SkillAction.READ:
            if not target_path.exists():
                return f"Error: The skill file '{params.filename}' does not exist."
            try:
                content = target_path.read_text(encoding="utf-8")
                return f"--- Content of skills/{params.filename} ---\n{content}"
            except Exception as exc:
                return f"Error reading skill file: {exc}"

        # ── Action: WRITE ─────────────────────────────────────────────
        if params.action == SkillAction.WRITE:
            if not params.code.strip():
                return "Error: The 'code' parameter cannot be empty when performing a write action."
            try:
                # Safely writes or completely replaces the targeted python script
                target_path.write_text(params.code, encoding="utf-8")
                return f"Success: Code safely deployed to 'skills/{params.filename}'."
            except Exception as exc:
                return f"Error writing code to disk: {exc}"