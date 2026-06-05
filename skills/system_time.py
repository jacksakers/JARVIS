from pydantic import BaseModel
from skills.base_skill import BaseSkill
from datetime import datetime

class SystemTimeInput(BaseModel):
    pass # No arguments needed to get the time!

class SystemTimeSkill(BaseSkill):
    name = "get_system_time"
    description = "Returns the current local date and time. Use this when the user asks what time or day it is."
    keywords = ["time", "date", "day", "clock", "today", "now"]
    
    input_model = SystemTimeInput

    def execute(self, params: SystemTimeInput) -> str:
        # Get the current time and format it nicely
        now = datetime.now()
        formatted_time = now.strftime("%A, %B %d, %Y at %I:%M %p")
        return f"The current system date and time is: {formatted_time}"