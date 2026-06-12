"""
JARVIS v3.0 — Database Models
All SQLModel table definitions live here so there is one source of truth
for the schema. Models follow the "Data-Driven" rule from the architecture
docs: routines, skills, and automations are rows in the DB, not hard-coded
Python functions.
"""
import json
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    waiting = "waiting"  # Paused — waiting for user reply to a question


class TriggerType(str, Enum):
    cron = "cron"
    event = "event"
    manual = "manual"


class FeedItemType(str, Enum):
    briefing = "briefing"
    report = "report"
    question = "question"
    action = "action"
    error = "error"
    reflection = "reflection"
    journal_analysis = "journal_analysis"


# ─────────────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────────────

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    is_primary: bool = Field(default=False)
    # JSON-encoded dict of user preferences (timezone, language, etc.)
    preferences: str = Field(default="{}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    tasks: List["Task"] = Relationship(back_populates="user")
    feed_items: List["FeedItem"] = Relationship(back_populates="user")
    routines: List["Routine"] = Relationship(back_populates="user")
    journal_entries: List["JournalEntry"] = Relationship(back_populates="user")

    def get_preferences(self) -> dict:
        try:
            return json.loads(self.preferences)
        except (json.JSONDecodeError, TypeError):
            return {}


# ─────────────────────────────────────────────────────────────────────────────
# Skills (auto-populated on startup by ToolRegistry)
# ─────────────────────────────────────────────────────────────────────────────

class Skill(SQLModel, table=True):
    __tablename__ = "skills"

    id: Optional[int] = Field(default=None, primary_key=True)
    # Python class name (e.g. "CalculatorSkill")
    module_name: str = Field(unique=True, index=True)
    # Tool name used in LLM schemas (e.g. "calculate")
    name: str = Field(unique=True, index=True)
    description: str = Field(default="")
    # Full Ollama-compatible JSON tool schema (serialised)
    tool_schema: str = Field(default="{}")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_schema(self) -> dict:
        try:
            return json.loads(self.tool_schema)
        except (json.JSONDecodeError, TypeError):
            return {}


# ─────────────────────────────────────────────────────────────────────────────
# Routines / Automations (the "Data-Driven" core)
# ─────────────────────────────────────────────────────────────────────────────

class Routine(SQLModel, table=True):
    __tablename__ = "routines"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    name: str
    description: str = Field(default="")

    trigger_type: TriggerType = Field(default=TriggerType.manual)
    # Cron expression (e.g. "0 6 * * *") or event name
    trigger_value: str = Field(default="")

    # The system prompt / persona for this specific routine.
    # Allows routines to behave differently: morning briefer vs. philosopher.
    system_prompt: str = Field(default="You are JARVIS, a helpful AI assistant.")

    # JSON array of skill *names* this routine is allowed to use.
    # Empty list = all skills. This prevents context bloat and security issues.
    # e.g. '["get_system_time", "calculate"]'
    allowed_skill_names: str = Field(default="[]")

    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    user: Optional["User"] = Relationship(back_populates="routines")
    tasks: List["Task"] = Relationship(back_populates="routine")

    def get_allowed_skills(self) -> List[str]:
        try:
            return json.loads(self.allowed_skill_names)
        except (json.JSONDecodeError, TypeError):
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Tasks / Job Queue
# ─────────────────────────────────────────────────────────────────────────────

class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    # nullable — manual delegation tasks have no routine
    routine_id: Optional[int] = Field(default=None, foreign_key="routines.id")

    prompt: str
    # Custom system prompt override (for manual delegation; otherwise from routine)
    system_prompt_override: Optional[str] = Field(default=None)

    status: TaskStatus = Field(default=TaskStatus.queued, index=True)
    error_message: Optional[str] = Field(default=None)
    # Set when the task is paused waiting for a user reply (ask_user skill)
    question_feed_item_id: Optional[int] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="tasks")
    routine: Optional["Routine"] = Relationship(back_populates="tasks")
    feed_items: List["FeedItem"] = Relationship(back_populates="task")


# ─────────────────────────────────────────────────────────────────────────────
# Feed Items (the "inbox" / output table)
# ─────────────────────────────────────────────────────────────────────────────

class FeedItem(SQLModel, table=True):
    __tablename__ = "feed_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    # nullable — system-generated items may not tie to a task
    task_id: Optional[int] = Field(default=None, foreign_key="tasks.id")

    type: FeedItemType = Field(default=FeedItemType.report)
    title: str = Field(default="Report")

    # Raw markdown as returned by the LLM
    content_markdown: str = Field(default="")
    # Pre-rendered HTML for fast serving to the frontend
    content_html: str = Field(default="")

    is_read: bool = Field(default=False)
    # Stored when the user replies to a 'question' type feed item
    reply_text: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    user: Optional["User"] = Relationship(back_populates="feed_items")
    task: Optional["Task"] = Relationship(back_populates="feed_items")


# ─────────────────────────────────────────────────────────────────────────────
# Journal Entries (Quick Capture)
# ─────────────────────────────────────────────────────────────────────────────

class JournalEntry(SQLModel, table=True):
    __tablename__ = "journal_entries"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)

    # Optional title (e.g. "Shopping List", "Project Ideas")
    title: str = Field(default="", index=True)
    content: str
    # Set to True after the background Journal Analysis routine processes this entry
    processed: bool = Field(default=False, index=True)
    # Whether the AI is allowed to read this entry
    llm_readable: bool = Field(default=True)
    # Whether the AI is allowed to edit (append/replace) this entry
    llm_editable: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    user: Optional["User"] = Relationship(back_populates="journal_entries")


# ─────────────────────────────────────────────────────────────────────────────
# API-level Pydantic schemas (not table=True — used for request/response bodies)
# ─────────────────────────────────────────────────────────────────────────────

class UserRead(SQLModel):
    id: int
    name: str
    is_primary: bool
    created_at: datetime


class RoutineCreate(SQLModel):
    name: str
    description: str = ""
    trigger_type: TriggerType = TriggerType.manual
    trigger_value: str = ""
    system_prompt: str = "You are JARVIS, a helpful AI assistant."
    allowed_skill_names: str = "[]"
    active: bool = True


class RoutineUpdate(SQLModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[TriggerType] = None
    trigger_value: Optional[str] = None
    system_prompt: Optional[str] = None
    allowed_skill_names: Optional[str] = None
    active: Optional[bool] = None


class RoutineRead(SQLModel):
    id: int
    user_id: int
    name: str
    description: str
    trigger_type: TriggerType
    trigger_value: str
    system_prompt: str
    allowed_skill_names: str
    active: bool
    created_at: datetime
    updated_at: datetime


class TaskCreate(SQLModel):
    prompt: str
    routine_id: Optional[int] = None
    system_prompt_override: Optional[str] = None


class TaskRead(SQLModel):
    id: int
    user_id: int
    routine_id: Optional[int]
    prompt: str
    status: TaskStatus
    error_message: Optional[str]
    question_feed_item_id: Optional[int]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class FeedItemRead(SQLModel):
    id: int
    user_id: int
    task_id: Optional[int]
    type: FeedItemType
    title: str
    content_markdown: str
    content_html: str
    is_read: bool
    reply_text: Optional[str]
    created_at: datetime


class JournalEntryCreate(SQLModel):
    title: str = ""
    content: str
    llm_readable: bool = True
    llm_editable: bool = False


class JournalEntryUpdate(SQLModel):
    title: Optional[str] = None
    content: Optional[str] = None
    processed: Optional[bool] = None
    llm_readable: Optional[bool] = None
    llm_editable: Optional[bool] = None


class JournalEntryRead(SQLModel):
    id: int
    user_id: int
    title: str
    content: str
    processed: bool
    llm_readable: bool
    llm_editable: bool
    created_at: datetime
    updated_at: datetime


class SkillRead(SQLModel):
    id: int
    name: str
    description: str
    module_name: str
    tool_schema: str
    updated_at: datetime
