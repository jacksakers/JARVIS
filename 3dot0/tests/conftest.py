"""
Pytest configuration and shared fixtures for JARVIS v3.0 tests.
Uses an in-memory SQLite database so tests never touch the real jarvis.db.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

# Ensure the 3dot0/ directory is on sys.path
_ROOT = Path(__file__).parent.parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── In-memory DB engine (session-scoped: shared across all tests) ─────────────

@pytest.fixture(name="engine", scope="session")
def engine_fixture():
    """Shared in-memory SQLite engine. Tables are created once per test run."""
    import app.models  # noqa: F401 — registers all SQLModel tables
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine, primary_user):
    """DB session per test. Does NOT roll back — tests share the same in-memory DB."""
    with Session(engine) as session:
        yield session


# ── Primary user (session-scoped so it exists for the whole test run) ─────────

@pytest.fixture(name="primary_user", scope="session")
def primary_user_fixture(engine):
    """Seed a primary user once per test session."""
    from app.models import User

    with Session(engine) as s:
        user = s.exec(select(User).where(User.is_primary == True)).first()
        if not user:
            user = User(name="TestUser", is_primary=True)
            s.add(user)
            s.commit()
            s.refresh(user)
        return user


# ── FastAPI test client ───────────────────────────────────────────────────────

@pytest.fixture(name="client")
def client_fixture(engine):
    """
    FastAPI TestClient that overrides the DB dependency to use the in-memory
    engine.  The lifespan (worker, scheduler) is suppressed.
    """
    from app.database import get_session
    from app.main import app

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session

    # Disable lifespan so worker/scheduler threads don't start during tests
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()
