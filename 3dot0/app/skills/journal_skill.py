from typing import Optional

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.database import make_session
from app.models import JournalEntry, User
from app.skills.base_skill import BaseSkill


class ReadJournalInput(BaseModel):
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of journal entries to retrieve (default 10, max 100).",
    )
    unprocessed_only: bool = Field(
        default=False,
        description="If True, only return unprocessed journal entries.",
    )


class ReadJournalSkill(BaseSkill):
    name = "read_journal"
    description = (
        "Retrieve recent journal entries. Returns the most recent entries first. "
        "Use this to review your thoughts, capture history, or analyze patterns."
    )
    input_model = ReadJournalInput

    def execute(self, params: ReadJournalInput) -> str:
        session = make_session()
        try:
            # Get the primary user
            user = session.exec(
                select(User).where(User.is_primary == True)
            ).first()
            if not user:
                return "Error: No primary user found."

            # Build query for journal entries
            query = select(JournalEntry).where(JournalEntry.user_id == user.id)
            if params.unprocessed_only:
                query = query.where(JournalEntry.processed == False)

            entries = session.exec(
                query.order_by(JournalEntry.created_at.desc()).limit(params.limit)
            ).all()

            if not entries:
                return (
                    "No journal entries found."
                    if not params.unprocessed_only
                    else "No unprocessed journal entries found."
                )

            # Format entries for LLM consumption
            lines = []
            for entry in reversed(entries):  # Show oldest first after reversing
                timestamp = entry.created_at.strftime("%Y-%m-%d %H:%M:%S")
                status = " [UNPROCESSED]" if not entry.processed else ""
                lines.append(f"[{timestamp}]{status}")
                lines.append(entry.content)
                lines.append("")

            return "\n".join(lines)

        finally:
            session.close()
