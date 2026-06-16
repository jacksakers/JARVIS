from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field
from sqlmodel import Session, select, or_, func

from app.database import make_session
from app.models import JournalCategory, JournalEntry, User
from app.skills.base_skill import BaseSkill


# ── list_journal_categories ───────────────────────────────────────────────────

class ListCategoriesInput(BaseModel):
    pass


class ListCategoriesSkill(BaseSkill):
    name = "list_journal_categories"
    description = (
        "List all journal categories (name, icon, colour, description, and entry count). "
        "Call this first to discover available categories before searching or reading entries."
    )
    input_model = ListCategoriesInput

    def execute(self, params: ListCategoriesInput) -> str:
        session = make_session()
        try:
            user = session.exec(select(User).where(User.is_primary == True)).first()
            if not user:
                return "Error: No primary user found."
            categories = session.exec(
                select(JournalCategory).where(JournalCategory.user_id == user.id).order_by(JournalCategory.name)
            ).all()
            if not categories:
                return "No journal categories found. All entries are uncategorised."
            lines = []
            for cat in categories:
                count = session.exec(
                    select(func.count(JournalEntry.id)).where(JournalEntry.category_id == cat.id)
                ).one()
                lines.append(f"[CAT:{cat.id}] {cat.icon} {cat.name} ({count} entries) — {cat.description or 'no description'}")
            return "\n".join(lines)
        finally:
            session.close()


# ── read_journal ──────────────────────────────────────────────────────────────

class ReadJournalInput(BaseModel):
    limit: int = Field(
        default=10, ge=1, le=100,
        description="Maximum number of journal entries to retrieve (default 10, max 100).",
    )
    category_id: Optional[int] = Field(
        default=None,
        description="If set, only return entries from this category (use list_journal_categories to get IDs).",
    )
    category_name: Optional[str] = Field(
        default=None,
        description="Category name to filter by (case-insensitive). Alternative to category_id.",
    )
    unprocessed_only: bool = Field(
        default=False,
        description="If True, only return unprocessed journal entries.",
    )
    pinned_only: bool = Field(
        default=False,
        description="If True, only return pinned entries.",
    )
    search: Optional[str] = Field(
        default=None,
        description="Keyword to search for in entry titles and content.",
    )
    mark_as_processed: bool = Field(
        default=True,
        description="If True, automatically mark the returned entries as processed.",
    )
    llm_readable_only: bool = Field(
        default=True,
        description="If True (default), only return entries the user has allowed the AI to read.",
    )


class ReadJournalSkill(BaseSkill):
    name = "read_journal"
    description = (
        "Retrieve journal entries with optional filtering by category, keyword search, pin state, or processed status. "
        "Returns the most recent entries first. "
        "Use list_journal_categories first to discover category IDs/names. "
        "Entries marked as 'processed' have already been analysed. "
        "Set mark_as_processed=True to automatically flag retrieved entries as processed."
    )
    input_model = ReadJournalInput

    def execute(self, params: ReadJournalInput) -> str:
        session = make_session()
        try:
            user = session.exec(select(User).where(User.is_primary == True)).first()
            if not user:
                return "Error: No primary user found."

            # Resolve category_name → category_id
            resolved_category_id = params.category_id
            if resolved_category_id is None and params.category_name:
                cat = session.exec(
                    select(JournalCategory).where(
                        JournalCategory.user_id == user.id,
                        JournalCategory.name.ilike(f"%{params.category_name}%"),
                    )
                ).first()
                if not cat:
                    return f"Error: No category matching '{params.category_name}' found."
                resolved_category_id = cat.id

            query = select(JournalEntry).where(JournalEntry.user_id == user.id)
            if params.unprocessed_only:
                query = query.where(JournalEntry.processed == False)
            if params.pinned_only:
                query = query.where(JournalEntry.pinned == True)
            if params.llm_readable_only:
                query = query.where(JournalEntry.llm_readable == True)
            if resolved_category_id is not None:
                query = query.where(JournalEntry.category_id == resolved_category_id)
            if params.search:
                term = f"%{params.search}%"
                query = query.where(
                    or_(JournalEntry.title.ilike(term), JournalEntry.content.ilike(term))
                )

            entries = session.exec(
                query.order_by(JournalEntry.pinned.desc(), JournalEntry.created_at.desc()).limit(params.limit)
            ).all()

            if not entries:
                return "No journal entries found matching the given filters."

            lines = []
            ids_to_mark = []
            for entry in reversed(entries):
                timestamp = entry.created_at.strftime("%Y-%m-%d %H:%M:%S")
                status_tag = " [UNPROCESSED]" if not entry.processed else ""
                title_part = f" | {entry.title}" if entry.title else ""
                editable_part = " [EDITABLE]" if entry.llm_editable else ""
                pinned_part = " [PINNED]" if entry.pinned else ""
                # Resolve category label
                cat_part = ""
                if entry.category_id:
                    cat = session.get(JournalCategory, entry.category_id)
                    if cat:
                        cat_part = f" | {cat.icon} {cat.name}"
                lines.append(
                    f"[ID:{entry.id} | {timestamp}{title_part}{cat_part}{pinned_part}{status_tag}{editable_part}]"
                )
                lines.append(entry.content)
                lines.append("")
                if not entry.processed:
                    ids_to_mark.append(entry.id)

            if params.mark_as_processed and ids_to_mark:
                for entry in entries:
                    if entry.id in ids_to_mark:
                        entry.processed = True
                        session.add(entry)
                session.commit()

            return "\n".join(lines)

        finally:
            session.close()


# ── edit_journal ──────────────────────────────────────────────────────────────

class EditJournalInput(BaseModel):
    entry_id: int = Field(
        description="The numeric ID of the journal entry to edit (shown as ID: in read_journal output).",
    )
    new_content: str = Field(
        description="The complete new content to replace the entry with. "
                    "For list entries (e.g. Shopping List), provide the full updated list.",
    )
    append_only: bool = Field(
        default=False,
        description="If True, append new_content to the existing content instead of replacing it.",
    )


class EditJournalSkill(BaseSkill):
    name = "edit_journal"
    description = (
        "Edit or append to a journal entry by its ID. "
        "Only entries that have llm_editable=True (marked as [EDITABLE] in read_journal) can be modified. "
        "Use this to update shopping lists, project notes, or any user-maintained living document."
    )
    input_model = EditJournalInput

    def execute(self, params: EditJournalInput) -> str:
        session = make_session()
        try:
            entry = session.get(JournalEntry, params.entry_id)
            if not entry:
                return f"Error: Journal entry ID {params.entry_id} not found."
            if not entry.llm_editable:
                return (
                    f"Error: Journal entry ID {params.entry_id} is not editable by the AI. "
                    "The user must enable AI editing for this entry."
                )

            if params.append_only:
                entry.content = entry.content.rstrip("\n") + "\n" + params.new_content
            else:
                entry.content = params.new_content

            entry.updated_at = datetime.now(timezone.utc)
            session.add(entry)
            session.commit()

            return f"Journal entry ID {params.entry_id} updated successfully."

        except Exception as exc:
            return f"Failed to edit journal entry: {exc}"
        finally:
            session.close()

