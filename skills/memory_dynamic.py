from pydantic import BaseModel
from skills.base_skill import BaseSkill
from core.memory import MemoryDB


class DynamicRecordInput(BaseModel):
    category: str  # e.g. "Shopping_List", "Car_Maintenance", "Recipe"
    data: str       # JSON string or plain-text note


class DynamicRecordSkill(BaseSkill):
    name = "save_dynamic_record"
    description = (
        "Save a flexible record to long-term memory under a named category. "
        "Use for lists, logs, or any structured data that doesn't fit the simple "
        "entity/attribute/value format. Pass data as a JSON string or plain text note. "
        "Examples: category='Shopping_List', data='{\"item\": \"milk\", \"qty\": 2}'"
    )
    keywords = ["track", "log", "record", "list", "shopping", "maintenance", "recipe", "task"]

    input_model = DynamicRecordInput

    def execute(self, params: DynamicRecordInput) -> str:
        return MemoryDB().save_dynamic_record(params.category, params.data)
