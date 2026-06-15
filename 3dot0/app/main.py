"""
JARVIS v3.0 — FastAPI Application
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.api import feed, journal, routines, skills, tasks, users, ws
from app.api import auth as auth_router
from app.api import conversations as convs_router
from app.api import development as dev_router
from app.config import load_config
from app.database import init_db, session_scope
from app.models import Skill, User
from app.worker.background_worker import BackgroundWorker
from app.worker.connection_manager import manager
from app.worker.scheduler import RoutineScheduler

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Shared worker / scheduler instances (created in lifespan)
# ─────────────────────────────────────────────────────────────────────────────
_worker: BackgroundWorker = None
_scheduler: RoutineScheduler = None


# ─────────────────────────────────────────────────────────────────────────────
# Startup / shutdown helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bootstrap_db(cfg: dict) -> None:
    """Create tables, seed the default user, and sync skills to the DB."""
    init_db()

    with session_scope() as session:
        from sqlmodel import select
        from app.core.tool_registry import ToolRegistry

        # ── Seed primary user ────────────────────────────────────────────────
        user_cfg = cfg.get("default_user", {})
        user_name = user_cfg.get("name", "User")
        existing = session.exec(select(User).where(User.name == user_name)).first()
        if not existing:
            session.add(User(
                name=user_name,
                is_primary=user_cfg.get("is_primary", True),
            ))
            session.flush()
            logger.info("Created default user: %s", user_name)

        # ── Sync skills to DB ────────────────────────────────────────────────
        registry = ToolRegistry()
        registry.discover_skills()

        for meta in registry.get_skill_metadata():
            existing_skill = session.exec(
                select(Skill).where(Skill.name == meta["name"])
            ).first()
            if existing_skill:
                existing_skill.description = meta["description"]
                existing_skill.tool_schema = meta["tool_schema"]
                existing_skill.updated_at = datetime.now(timezone.utc)
                session.add(existing_skill)
            else:
                session.add(Skill(
                    module_name=meta["module_name"],
                    name=meta["name"],
                    description=meta["description"],
                    tool_schema=meta["tool_schema"],
                ))

        skill_names = [m["name"] for m in registry.get_skill_metadata()]
        logger.info("Skills synced to DB: %s", ", ".join(skill_names))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: run setup on startup, teardown on shutdown."""
    global _worker, _scheduler

    cfg = load_config()

    # ── Database setup ───────────────────────────────────────────────────────
    _bootstrap_db(cfg)

    # ── WebSocket event loop ──────────────────────────────────────────────────
    manager.set_event_loop(asyncio.get_event_loop())

    # ── Background worker ─────────────────────────────────────────────────────
    _worker = BackgroundWorker(cfg)
    _worker.start()
    logger.info("Background worker started.")

    # ── Routine scheduler ─────────────────────────────────────────────────────
    _scheduler = RoutineScheduler(_worker)
    _scheduler.start()
    logger.info("Routine scheduler started.")

    yield  # ── Application running ──────────────────────────────────────────

    # ── Shutdown ──────────────────────────────────────────────────────────────
    _scheduler.stop()
    _worker.stop()
    logger.info("JARVIS v3.0 shut down cleanly.")


# ─────────────────────────────────────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="JARVIS v3.0",
    description=(
        "Data-Driven Asynchronous AI Assistant — backend API. "
        "The frontend connects to /api/v1/* for REST and /ws for real-time events."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

# Allow all origins for development.
# In production, restrict to your Tailscale MagicDNS domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routers ───────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(routines.router, prefix=API_PREFIX)
app.include_router(tasks.router, prefix=API_PREFIX)
app.include_router(feed.router, prefix=API_PREFIX)
app.include_router(journal.router, prefix=API_PREFIX)
app.include_router(skills.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(auth_router.router, prefix=API_PREFIX)
app.include_router(convs_router.router, prefix=API_PREFIX)
app.include_router(dev_router.router, prefix=API_PREFIX)
app.include_router(ws.router)  # WebSocket at /ws (no version prefix)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
def health():
    """Quick liveness check."""
    return {"status": "ok", "version": "3.0.0"}
