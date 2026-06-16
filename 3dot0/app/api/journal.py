"""API router: journal entries and categories."""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select, or_, func

from app.database import get_session
from app.models import (
    JournalCategory, JournalCategoryCreate, JournalCategoryRead, JournalCategoryUpdate,
    JournalEntry, JournalEntryCreate, JournalEntryRead, JournalEntryUpdate, User,
)

router = APIRouter(prefix="/journal", tags=["journal"])


def _get_default_user(session: Session) -> User:
    user = session.exec(select(User).where(User.is_primary == True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No primary user found.")
    return user


def _enrich(entry: JournalEntry) -> JournalEntryRead:
    """Convert a JournalEntry ORM row to JournalEntryRead, injecting category fields."""
    cat = entry.category
    return JournalEntryRead(
        id=entry.id,
        user_id=entry.user_id,
        category_id=entry.category_id,
        title=entry.title,
        content=entry.content,
        pinned=entry.pinned,
        processed=entry.processed,
        llm_readable=entry.llm_readable,
        llm_editable=entry.llm_editable,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        category_name=cat.name if cat else None,
        category_color=cat.color if cat else None,
        category_icon=cat.icon if cat else None,
    )


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories/", response_model=List[JournalCategoryRead])
def list_categories(session: Session = Depends(get_session)):
    user = _get_default_user(session)
    categories = session.exec(
        select(JournalCategory)
        .where(JournalCategory.user_id == user.id)
        .order_by(JournalCategory.name)
    ).all()
    result = []
    for cat in categories:
        count = session.exec(
            select(func.count(JournalEntry.id)).where(JournalEntry.category_id == cat.id)
        ).one()
        result.append(JournalCategoryRead(
            id=cat.id,
            user_id=cat.user_id,
            name=cat.name,
            color=cat.color,
            icon=cat.icon,
            description=cat.description,
            entry_count=count,
            created_at=cat.created_at,
        ))
    return result


@router.post("/categories/", response_model=JournalCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: JournalCategoryCreate, session: Session = Depends(get_session)):
    user = _get_default_user(session)
    cat = JournalCategory(
        user_id=user.id,
        name=payload.name,
        color=payload.color,
        icon=payload.icon,
        description=payload.description,
    )
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return JournalCategoryRead(
        id=cat.id, user_id=cat.user_id, name=cat.name, color=cat.color,
        icon=cat.icon, description=cat.description, entry_count=0, created_at=cat.created_at,
    )


@router.patch("/categories/{category_id}", response_model=JournalCategoryRead)
def update_category(
    category_id: int, payload: JournalCategoryUpdate, session: Session = Depends(get_session)
):
    cat = session.get(JournalCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(cat, key, val)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    count = session.exec(
        select(func.count(JournalEntry.id)).where(JournalEntry.category_id == cat.id)
    ).one()
    return JournalCategoryRead(
        id=cat.id, user_id=cat.user_id, name=cat.name, color=cat.color,
        icon=cat.icon, description=cat.description, entry_count=count, created_at=cat.created_at,
    )


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, session: Session = Depends(get_session)):
    cat = session.get(JournalCategory, category_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")
    # Detach entries from this category before deleting
    entries = session.exec(select(JournalEntry).where(JournalEntry.category_id == category_id)).all()
    for e in entries:
        e.category_id = None
        session.add(e)
    session.delete(cat)
    session.commit()


# ── Entries ───────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[JournalEntryRead])
def list_entries(
    unprocessed_only: bool = Query(default=False),
    pinned_only: bool = Query(default=False),
    category_id: Optional[int] = Query(default=None, description="Filter by category ID"),
    limit: int = Query(default=50, le=200),
    search: str = Query(default=None, description="Filter by keyword in title or content"),
    sort: str = Query(default="newest", description="Sort order: newest | oldest | title | updated"),
    session: Session = Depends(get_session),
):
    user = _get_default_user(session)
    query = select(JournalEntry).where(JournalEntry.user_id == user.id)
    if unprocessed_only:
        query = query.where(JournalEntry.processed == False)
    if pinned_only:
        query = query.where(JournalEntry.pinned == True)
    if category_id is not None:
        query = query.where(JournalEntry.category_id == category_id)
    if search:
        term = f"%{search}%"
        query = query.where(
            or_(
                JournalEntry.content.ilike(term),
                JournalEntry.title.ilike(term),
            )
        )
    # Pinned entries always bubble to the top, then apply chosen sort
    if sort == "oldest":
        query = query.order_by(JournalEntry.pinned.desc(), JournalEntry.created_at.asc())
    elif sort == "title":
        query = query.order_by(JournalEntry.pinned.desc(), JournalEntry.title.asc())
    elif sort == "updated":
        query = query.order_by(JournalEntry.pinned.desc(), JournalEntry.updated_at.desc())
    else:  # newest (default)
        query = query.order_by(JournalEntry.pinned.desc(), JournalEntry.created_at.desc())
    entries = session.exec(query.limit(limit)).all()
    return [_enrich(e) for e in entries]


@router.post("/", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(payload: JournalEntryCreate, session: Session = Depends(get_session)):
    """Quick capture — save a raw thought to the journal."""
    user = _get_default_user(session)
    # Validate category ownership
    if payload.category_id is not None:
        cat = session.get(JournalCategory, payload.category_id)
        if not cat or cat.user_id != user.id:
            raise HTTPException(status_code=400, detail="Invalid category.")
    now = datetime.now(timezone.utc)
    entry = JournalEntry(
        user_id=user.id,
        category_id=payload.category_id,
        title=payload.title,
        content=payload.content,
        pinned=payload.pinned,
        llm_readable=payload.llm_readable,
        llm_editable=payload.llm_editable,
        created_at=now,
        updated_at=now,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return _enrich(entry)


@router.patch("/{entry_id}", response_model=JournalEntryRead)
def update_entry(
    entry_id: int, payload: JournalEntryUpdate, session: Session = Depends(get_session)
):
    """Update a journal entry's content, title, category, pin state, or settings."""
    entry = session.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    user = _get_default_user(session)
    update_data = payload.model_dump(exclude_unset=True)
    # Validate category ownership if being changed
    if "category_id" in update_data and update_data["category_id"] is not None:
        cat = session.get(JournalCategory, update_data["category_id"])
        if not cat or cat.user_id != user.id:
            raise HTTPException(status_code=400, detail="Invalid category.")
    for key, val in update_data.items():
        setattr(entry, key, val)
    entry.updated_at = datetime.now(timezone.utc)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return _enrich(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, session: Session = Depends(get_session)):
    entry = session.get(JournalEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    session.delete(entry)
    session.commit()
