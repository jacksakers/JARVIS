"""API router: activity feed (read-only from the frontend's perspective)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.database import get_session
from app.models import FeedItem, FeedItemRead, FeedItemType, User

router = APIRouter(prefix="/feed", tags=["feed"])


def _get_default_user(session: Session) -> User:
    user = session.exec(select(User).where(User.is_primary == True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No primary user found.")
    return user


@router.get("/", response_model=List[FeedItemRead])
def list_feed(
    type_filter: Optional[FeedItemType] = Query(default=None, alias="type"),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=30, le=100),
    offset: int = Query(default=0),
    session: Session = Depends(get_session),
):
    """Paginated feed for the primary user, newest first."""
    user = _get_default_user(session)
    query = select(FeedItem).where(FeedItem.user_id == user.id)

    if type_filter:
        query = query.where(FeedItem.type == type_filter)
    if unread_only:
        query = query.where(FeedItem.is_read == False)

    query = query.order_by(FeedItem.created_at.desc()).offset(offset).limit(limit)
    return session.exec(query).all()


@router.get("/{item_id}", response_model=FeedItemRead)
def get_feed_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(FeedItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feed item not found.")
    return item


@router.post("/{item_id}/read", response_model=FeedItemRead)
def mark_as_read(item_id: int, session: Session = Depends(get_session)):
    """Mark a feed item as read."""
    item = session.get(FeedItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feed item not found.")
    item.is_read = True
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.post("/read-all", response_model=dict)
def mark_all_read(session: Session = Depends(get_session)):
    """Mark every unread feed item as read."""
    user = _get_default_user(session)
    items = session.exec(
        select(FeedItem).where(
            FeedItem.user_id == user.id,
            FeedItem.is_read == False,
        )
    ).all()
    for item in items:
        item.is_read = True
        session.add(item)
    session.commit()
    return {"marked_read": len(items)}
