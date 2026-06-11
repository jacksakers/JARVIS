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
