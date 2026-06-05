from pydantic import BaseModel
from skills.base_skill import BaseSkill
from core.memory import MemoryDB


class MemorySearchInput(BaseModel):
    keywords: str  # space-separated search terms


class MemorySearchSkill(BaseSkill):
    name = "search_memory"
    description = (
        "Search long-term memory for stored facts, preferences, or notes. "
        "Pass space-separated keywords. Always call this before claiming you "
        "don't know something about the user."
    )
    keywords = ["remember", "recall", "memory", "know", "fact", "stored", "what did", "do i"]

    input_model = MemorySearchInput

    def execute(self, params: MemorySearchInput) -> str:
        results = MemoryDB().search(params.keywords)
        if not results:
            return "No memories found for those keywords."
        lines = [f"- [{r['entity']}] {r['attribute']}: {r['value']}" for r in results]
        return "Found memories:\n" + "\n".join(lines)
