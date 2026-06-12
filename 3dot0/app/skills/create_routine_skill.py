"""
Create Routine skill — allows JARVIS to create and schedule its own routines.
"""
import json
from typing import List, Optional

from pydantic import BaseModel, Field

from app.skills.base_skill import BaseSkill


class CreateRoutineInput(BaseModel):
    name: str = Field(
        description="Short, descriptive name for the routine (e.g. 'Morning Briefing')."
    )
    description: Optional[str] = Field(
        default="",
        description="What this routine does (optional).",
    )
    trigger_type: str = Field(
        default="manual",
        description="Trigger type: 'cron' for scheduled, 'manual' for on-demand only.",
    )
    trigger_value: Optional[str] = Field(
        default="",
        description=(
            "Cron expression if trigger_type is 'cron' (e.g. '0 6 * * *' for 6 AM daily). "
            "Must be in UTC. If trigger_type is 'manual', leave empty."
        ),
    )
    system_prompt: str = Field(
        description=(
            "Detailed instructions for JARVIS when this routine runs. "
            "Tell it what to do, in what order, and how to format the output."
        )
    )
    allowed_skill_names: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of skill names this routine can use (e.g. ['get_system_time', 'search_memory']). "
            "Empty list = no tools. None or omitted = all skills available."
        ),
    )
    active: bool = Field(
        default=True,
        description="Whether the routine is active immediately after creation.",
    )


class CreateRoutineSkill(BaseSkill):
    name = "create_routine"
    description = (
        "Creates a new routine that JARVIS can run on a schedule or on-demand. "
        "Use this to set up automated tasks, scheduled reports, or recurring workflows."
    )
    input_model = CreateRoutineInput

    def execute(self, params: CreateRoutineInput) -> str:
        """Create a routine in the database and return the result."""
        from datetime import datetime, timezone

        from app.database import session_scope
        from app.models import Routine

        # Validate input
        if not params.name or not params.name.strip():
            return "Error: routine name is required."

        if params.trigger_type == "cron" and not params.trigger_value:
            return "Error: cron expression required when trigger_type is 'cron'."

        if params.trigger_type not in ("cron", "manual"):
            return f"Error: trigger_type must be 'cron' or 'manual', got '{params.trigger_type}'."

        # Get the user ID from the current task context
        try:
            import app.skills.ask_user_skill as _ask_mod
            user_id = getattr(_ask_mod._current_task, "user_id", None)
            if not user_id:
                return "Error: could not determine current user."
        except (AttributeError, ImportError):
            return "Error: routine creation requires an active user context."

        # Prepare routine data
        routine_data = {
            "user_id": user_id,
            "name": params.name.strip()[:255],
            "description": (params.description or "").strip()[:255],
            "trigger_type": params.trigger_type,
            "trigger_value": (params.trigger_value or "").strip(),
            "system_prompt": params.system_prompt.strip(),
            "allowed_skill_names": json.dumps(params.allowed_skill_names or []),
            "active": params.active,
        }

        try:
            with session_scope() as session:
                routine = Routine(**routine_data)
                session.add(routine)
                session.flush()
                routine_id = routine.id

            return (
                f"✓ Routine created successfully!\n"
                f"  • Name: {params.name}\n"
                f"  • ID: {routine_id}\n"
                f"  • Type: {params.trigger_type}\n"
                f"  • Active: {params.active}"
            )
        except Exception as exc:
            return f"Error creating routine: {str(exc)[:200]}"
