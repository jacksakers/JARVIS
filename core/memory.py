"""
SQLite + FTS5 memory backend for JARVIS.

Tables:
  Core_Memories   – structured entity/attribute/value facts
  Dynamic_Records – flexible JSON blobs under a category
  Memory_FTS      – FTS5 virtual table for fast keyword search across all stored text
"""

import sqlite3
import json
from typing import Any

_DEFAULT_DB = "jarvis_memory.db"


class MemoryDB:
    def __init__(self, db_path: str = _DEFAULT_DB):
        self.db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS Core_Memories (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity    TEXT    NOT NULL,
                    attribute TEXT    NOT NULL,
                    value     TEXT    NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS Dynamic_Records (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    category  TEXT NOT NULL,
                    data      TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # FTS5 table that mirrors searchable text from both tables above.
            # We store: entity, attribute, value columns plus a source tag.
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS Memory_FTS USING fts5(
                    entity,
                    attribute,
                    value,
                    source        UNINDEXED
                )
            """)
            conn.commit()

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    def save_core_memory(self, entity: str, attribute: str, value: str) -> str:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO Core_Memories (entity, attribute, value) VALUES (?, ?, ?)",
                (entity, attribute, value),
            )
            conn.execute(
                "INSERT INTO Memory_FTS (entity, attribute, value, source) VALUES (?, ?, ?, 'core')",
                (entity, attribute, value),
            )
            conn.commit()
        return f"Saved: [{entity}] {attribute} = {value}"

    def save_dynamic_record(self, category: str, data: Any) -> str:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {"note": data}

        data_json = json.dumps(data)
        # Flatten all values into a single searchable string
        searchable = " ".join(str(v) for v in data.values())

        with self._conn() as conn:
            conn.execute(
                "INSERT INTO Dynamic_Records (category, data) VALUES (?, ?)",
                (category, data_json),
            )
            conn.execute(
                "INSERT INTO Memory_FTS (entity, attribute, value, source) VALUES (?, ?, ?, 'dynamic')",
                (category, "data", searchable),
            )
            conn.commit()
        return f"Dynamic record saved under '{category}'."

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def search(self, keywords: str, limit: int = 5) -> list[dict]:
        """
        Full-text search across all stored memories.
        keywords: space-separated terms; matched with OR logic.
        """
        if not keywords.strip():
            return []

        # FTS5 OR query
        fts_query = " OR ".join(keywords.split())

        try:
            with self._conn() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT entity, attribute, value, source FROM Memory_FTS "
                    "WHERE Memory_FTS MATCH ? ORDER BY rank LIMIT ?",
                    (fts_query, limit),
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []
