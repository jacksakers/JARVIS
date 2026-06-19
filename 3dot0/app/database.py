"""
Database engine and session management.
All code that needs a DB session should import `get_session` and use it as
a FastAPI dependency, OR call `make_session()` directly in background threads.
"""
from contextlib import contextmanager
from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_db_path

_engine = None


def get_engine():
    """Return the singleton SQLite engine, creating it on first call."""
    global _engine
    if _engine is None:
        db_url = f"sqlite:///{get_db_path()}"
        # check_same_thread=False is required for SQLite when used across threads
        # (the background worker runs in a different thread from FastAPI).
        _engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return _engine


def init_db() -> None:
    """Create all tables if they don't exist. Called once on startup."""
    # Import models so SQLModel sees them before create_all
    import app.models  # noqa: F401
    SQLModel.metadata.create_all(get_engine())
    _run_migrations()


def _run_migrations() -> None:
    """Apply incremental schema migrations for new columns added after initial release."""
    import sqlite3
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        def _column_exists(table: str, column: str) -> bool:
            cursor.execute(f"PRAGMA table_info({table})")
            return any(row[1] == column for row in cursor.fetchall())

        migrations = [
            # Journal entry enhancements
            ("journal_entries", "title",        "ALTER TABLE journal_entries ADD COLUMN title TEXT NOT NULL DEFAULT ''"),
            ("journal_entries", "llm_readable",  "ALTER TABLE journal_entries ADD COLUMN llm_readable INTEGER NOT NULL DEFAULT 1"),
            ("journal_entries", "llm_editable",  "ALTER TABLE journal_entries ADD COLUMN llm_editable INTEGER NOT NULL DEFAULT 0"),
            ("journal_entries", "updated_at",    "ALTER TABLE journal_entries ADD COLUMN updated_at DATETIME"),
            # Journal categories (added with category feature)
            ("journal_entries", "category_id",   "ALTER TABLE journal_entries ADD COLUMN category_id INTEGER DEFAULT NULL REFERENCES journal_categories(id)"),
            ("journal_entries", "pinned",         "ALTER TABLE journal_entries ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"),
            # Task: waiting-for-user support
            ("tasks",           "question_feed_item_id", "ALTER TABLE tasks ADD COLUMN question_feed_item_id INTEGER DEFAULT NULL"),
            # Task: conversation state & chat conversation link
            ("tasks",           "conversation_state",    "ALTER TABLE tasks ADD COLUMN conversation_state TEXT DEFAULT NULL"),
            ("tasks",           "conversation_id",       "ALTER TABLE tasks ADD COLUMN conversation_id INTEGER DEFAULT NULL"),
            # Task: routine generation config
            ("tasks",           "routine_generation_config", "ALTER TABLE tasks ADD COLUMN routine_generation_config TEXT DEFAULT NULL"),
            # Feed item: store user reply
            ("feed_items",      "reply_text",   "ALTER TABLE feed_items ADD COLUMN reply_text TEXT DEFAULT NULL"),
            # User: auth & bio
            ("users",           "password_hash", "ALTER TABLE users ADD COLUMN password_hash TEXT DEFAULT NULL"),
            ("users",           "bio",           "ALTER TABLE users ADD COLUMN bio TEXT NOT NULL DEFAULT ''"),
            # Task: per-task tool allowlist (for chat tool-selection feature)
            ("tasks", "allowed_skill_names_override", "ALTER TABLE tasks ADD COLUMN allowed_skill_names_override TEXT DEFAULT NULL"),
            # Model selection
            ("tasks",          "model_id", "ALTER TABLE tasks ADD COLUMN model_id TEXT DEFAULT NULL"),
            ("conversations",  "model_id", "ALTER TABLE conversations ADD COLUMN model_id TEXT DEFAULT NULL"),
            ("routines",       "model_id", "ALTER TABLE routines ADD COLUMN model_id TEXT DEFAULT NULL"),
            # Token usage tracking
            ("tasks", "tokens_prompt",     "ALTER TABLE tasks ADD COLUMN tokens_prompt INTEGER NOT NULL DEFAULT 0"),
            ("tasks", "tokens_completion", "ALTER TABLE tasks ADD COLUMN tokens_completion INTEGER NOT NULL DEFAULT 0"),
            ("tasks", "tokens_thinking",   "ALTER TABLE tasks ADD COLUMN tokens_thinking INTEGER NOT NULL DEFAULT 0"),
            # Per-task max tool iterations override
            ("tasks", "max_tool_iterations", "ALTER TABLE tasks ADD COLUMN max_tool_iterations INTEGER DEFAULT NULL"),
            ("feed_items",      "last_conversation_state",   "ALTER TABLE feed_items ADD COLUMN last_conversation_state TEXT DEFAULT NULL"),
        ]

        for table, column, sql in migrations:
            if not _column_exists(table, column):
                cursor.execute(sql)

        # Create journal_categories table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS journal_categories (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                name TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#06b6d4',
                icon TEXT NOT NULL DEFAULT '\U0001f4dd',
                description TEXT NOT NULL DEFAULT '',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_journal_categories_user_id ON journal_categories (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_journal_categories_name ON journal_categories (name)")

        # Create dev_pull_requests table if it doesn't exist
        # (SQLModel.create_all handles new installs; this covers existing DBs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dev_pull_requests (
                id INTEGER PRIMARY KEY,
                project_name TEXT NOT NULL,
                branch_name TEXT NOT NULL,
                task_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                commit_message TEXT NOT NULL DEFAULT '',
                diff TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
    finally:
        conn.close()


def make_session() -> Session:
    """
    Return a new DB session. Caller is responsible for closing it.
    Use this in background threads where FastAPI DI is unavailable.
    """
    return Session(get_engine())


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Context manager for safe session usage in background code.

        with session_scope() as session:
            session.add(obj)
    """
    session = make_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_session() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a DB session per request.

        @router.get("/")
        def list_items(session: Session = Depends(get_session)):
            ...
    """
    with Session(get_engine()) as session:
        yield session
