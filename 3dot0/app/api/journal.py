"""API router: journal entries (Quick Capture)."""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import JournalEntry, JournalEntryCreate, JournalEntryRead, JournalEntryUpdate, User

router = APIRouter(prefix="/journal", tags=["journal"])


def _get_default_user(session: Session) -> User:
    user = session.exec(select(User).where(User.is_primary == True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No primary user found.")
    return user


@router.get("/", response_model=List[JournalEntryRead])
def list_entries(
    unprocessed_only: bool = Query(default=False),
    limit: int = Query(default=50, le=200),
    search: str = Query(default=None, description="Filter by keyword in title or content"),
    session: Session = Depends(get_session),
):
    user = _get_default_user(session)
    query = select(JournalEntry).where(JournalEntry.user_id == user.id)
    if unprocessed_only:
        query = query.where(JournalEntry.processed == False)
    if search:
        term = f"%{search}%"
        from sqlmodel import or_
        query = query.where(
            or_(
                JournalEntry.content.ilike(term),
                JournalEntry.title.ilike(term),
            )
        )
    query = query.order_by(JournalEntry.created_at.desc()).limit(limit)
    return session.exec(query).all()


@router.post("/", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: JournalEntryCreate,
    session: Session = Depends(get_session),
):
    """Quick capture — save a raw thought to the journal."""
    user = _get_default_user(session)
    now = datetime.now(timezone.utc)
    entry = JournalEntry(
        user_id=user.id,
        title=payload.title,
        content=payload.content,
        llm_readable=payload.llm_readable,
        llm_editable=payload.llm_editable,
        created_at=now,
        updated_at=now,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.patch("/{entry_id}", response_model=JournalEntryRead)
def update_entry(
    entry_id: int,
    payload: JournalEntryUpdate,
    session: Session = Depends(get_session),
):
    """Update a journal entry's content, title, or settings."""
    entry = session.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    update_data = payload.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(entry, key, val)
    entry.updated_at = datetime.now(timezone.utc)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, session: Session = Depends(get_session)):
    entry = session.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    session.delete(entry)
    session.commit()
