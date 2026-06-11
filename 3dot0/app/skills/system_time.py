from datetime import datetime

from pydantic import BaseModel

from app.skills.base_skill import BaseSkill


class SystemTimeInput(BaseModel):
    pass  # No arguments needed


class SystemTimeSkill(BaseSkill):
    name = "get_system_time"
    description = (
        "Returns the current local date and time. "
        "Use this whenever the user asks what time, day, or date it is."
    )
    input_model = SystemTimeInput

    def execute(self, params: SystemTimeInput) -> str:
        now = datetime.now()
        return now.strftime("Current date and time: %A, %B %d, %Y at %I:%M %p")
