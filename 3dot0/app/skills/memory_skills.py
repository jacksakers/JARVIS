"""
Memory skills — backed by a dedicated SQLite file separate from the main DB.
This keeps long-term factual memory portable and independent of the app schema.
"""
import sqlite3
from pathlib import Path

from pydantic import BaseModel, Field

from app.config import load_config
from app.skills.base_skill import BaseSkill


def _get_memory_db_path() -> str:
    cfg = load_config()
    # Place alongside the main DB by default
    main_db = cfg.get("database", {}).get("path", "jarvis.db")
    parent = Path(main_db).parent if Path(main_db).is_absolute() else Path(".")
    return str(parent / "jarvis_memory.db")


def _get_db() -> sqlite3.Connection:
    """Open (or create) the SQLite long-term memory database."""
    db = sqlite3.connect(_get_memory_db_path())
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


# ── save_memory ───────────────────────────────────────────────────────────────

class SaveMemoryInput(BaseModel):
    entity: str = Field(
        description="Who or what the memory is about, e.g. 'User', 'Wife', 'Car'."
    )
    attribute: str = Field(
        description="The property being stored, e.g. 'Favourite Food', 'Birthday'."
    )
    value: str = Field(
        description="The value to remember, e.g. 'Sushi', 'October 12'."
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
            return f"Memory saved — {params.entity} / {params.attribute}: {params.value}"
        except Exception as exc:
            return f"Failed to save memory: {exc}"
        finally:
            db.close()


# ── search_memory ─────────────────────────────────────────────────────────────

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
        "Use this before answering personalised questions about the user."
    )
    input_model = SearchMemoryInput

    def execute(self, params: SearchMemoryInput) -> str:
        db = _get_db()
        try:
            cursor = db.execute(
                """
                SELECT entity, attribute, value, timestamp
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
