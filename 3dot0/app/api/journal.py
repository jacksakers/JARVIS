"""API router: journal entries (Quick Capture)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import JournalEntry, JournalEntryCreate, JournalEntryRead, User

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
    session: Session = Depends(get_session),
):
    user = _get_default_user(session)
    query = select(JournalEntry).where(JournalEntry.user_id == user.id)
    if unprocessed_only:
        query = query.where(JournalEntry.processed == False)
    query = query.order_by(JournalEntry.created_at.desc()).limit(limit)
    return session.exec(query).all()


@router.post("/", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: JournalEntryCreate,
    session: Session = Depends(get_session),
):
    """Quick capture — save a raw thought to the journal."""
    user = _get_default_user(session)
    entry = JournalEntry(user_id=user.id, content=payload.content)
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
