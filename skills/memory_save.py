from pydantic import BaseModel
from skills.base_skill import BaseSkill
from core.memory import MemoryDB


class MemorySaveInput(BaseModel):
    entity: str     # e.g. "User", "Wife", "Car"
    attribute: str  # e.g. "Favorite Food", "Birthday"
    value: str      # e.g. "Sushi", "October 12"


class MemorySaveSkill(BaseSkill):
    name = "save_memory"
    description = (
        "Save a structured fact or preference to long-term memory using an "
        "entity / attribute / value format. Use for personal facts, preferences, "
        "and relationships. Example: entity='User', attribute='Diet', value='Keto'."
    )
    keywords = ["save", "remember", "store", "note", "learn", "fact", "preference"]

    input_model = MemorySaveInput

    def execute(self, params: MemorySaveInput) -> str:
        return MemoryDB().save_core_memory(params.entity, params.attribute, params.value)
