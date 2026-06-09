import sqlite3
from pathlib import Path

from pydantic import BaseModel, Field

from skills.base_skill import BaseSkill

# Stored in the working directory (set by jarvis2.py to the 2dot0/ folder).
_DB_PATH = "jarvis_memory.db"


def _get_db() -> sqlite3.Connection:
    """
    Open (or create) the SQLite memory database with FTS5 full-text search.
    Uses WAL mode for better concurrent read performance.
    """
    db = sqlite3.connect(_DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS core_memories (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            entity    TEXT    NOT NULL,
            attribute TEXT    NOT NULL,
            value     TEXT    NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            entity, attribute, value,
            content=core_memories,
            content_rowid=id
        );

        CREATE TRIGGER IF NOT EXISTS memories_ai
            AFTER INSERT ON core_memories
        BEGIN
            INSERT INTO memory_fts(rowid, entity, attribute, value)
            VALUES (new.id, new.entity, new.attribute, new.value);
        END;
        """
    )
    db.commit()
    return db


# ──────────────────────────────────────────────────────────────────────────────
# save_memory
# ──────────────────────────────────────────────────────────────────────────────

class SaveMemoryInput(BaseModel):
    entity: str = Field(
        description="Who or what the memory is about, e.g. 'User', 'Wife', 'Car'."
    )
    attribute: str = Field(
        description="The property being stored, e.g. 'Favourite Food', 'Birthday', 'Allergy'."
    )
    value: str = Field(
        description="The value to remember, e.g. 'Sushi', 'October 12', 'Peanuts'."
    )


class SaveMemorySkill(BaseSkill):
    name = "save_memory"
    description = (
        "Saves a fact, preference, or piece of information to long-term memory "
        "so it can be recalled in future conversations."
    )
    input_model = SaveMemoryInput

    def execute(self, params: SaveMemoryInput) -> str:
        db = _get_db()
        try:
            db.execute(
                "INSERT INTO core_memories (entity, attribute, value) VALUES (?, ?, ?)",
                (params.entity, params.attribute, params.value),
            )
            db.commit()
            return (
                f"Memory saved — {params.entity} / {params.attribute}: {params.value}"
            )
        except Exception as exc:
            return f"Failed to save memory: {exc}"
        finally:
            db.close()


# ──────────────────────────────────────────────────────────────────────────────
# search_memory
# ──────────────────────────────────────────────────────────────────────────────

class SearchMemoryInput(BaseModel):
    query: str = Field(
        description=(
            "Keywords or a short phrase to search for in long-term memory, "
            "e.g. 'diet food allergy' or 'car maintenance'."
        )
    )


class SearchMemorySkill(BaseSkill):
    name = "search_memory"
    description = (
        "Searches long-term memory for stored facts and preferences. "
        "Use this before answering personalised questions."
    )
    input_model = SearchMemoryInput

    def execute(self, params: SearchMemoryInput) -> str:
        db = _get_db()
        try:
            cursor = db.execute(
                """
                SELECT entity, attribute, value
                FROM   memory_fts
                WHERE  memory_fts MATCH ?
                ORDER  BY rank
                LIMIT  5
                """,
                (params.query,),
            )
            rows = cursor.fetchall()
            if not rows:
                return "No memories found for that query."

            lines = [
                f"• {row['entity']} / {row['attribute']}: {row['value']}"
                for row in rows
            ]
            return "Found memories:\n" + "\n".join(lines)

        except Exception as exc:
            return f"Memory search error: {exc}"
        finally:
            db.close()
