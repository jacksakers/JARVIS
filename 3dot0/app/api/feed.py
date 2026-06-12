"""API router: activity feed."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import FeedItem, FeedItemRead, FeedItemType, Task, TaskStatus, User
from app.worker.connection_manager import manager

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


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed_item(item_id: int, session: Session = Depends(get_session)):
    """Delete a feed item."""
    item = session.get(FeedItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feed item not found.")
    session.delete(item)
    session.commit()


@router.delete("/", status_code=status.HTTP_200_OK)
def bulk_delete_feed(
    read_only: bool = Query(default=True, description="If true, only delete read items. If false, delete all."),
    session: Session = Depends(get_session),
):
    """Bulk-delete feed items for the primary user."""
    user = _get_default_user(session)
    query = select(FeedItem).where(FeedItem.user_id == user.id)
    if read_only:
        query = query.where(FeedItem.is_read == True)
    items = session.exec(query).all()
    count = len(items)
    for item in items:
        session.delete(item)
    session.commit()
    return {"deleted": count}


class ReplyPayload(dict):
    pass


@router.post("/{item_id}/reply", response_model=FeedItemRead)
def reply_to_question(
    item_id: int,
    payload: dict,
    session: Session = Depends(get_session),
):
    """
    Submit a user reply to a 'question' feed item.
    This re-queues the associated waiting task so the agent can continue.
    """
    item = session.get(FeedItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feed item not found.")
    if item.type != FeedItemType.question:
        raise HTTPException(status_code=400, detail="Feed item is not a question.")

    reply_text = payload.get("reply_text", "").strip()
    if not reply_text:
        raise HTTPException(status_code=422, detail="reply_text is required.")

    # Store the reply
    item.reply_text = reply_text
    item.is_read = True
    session.add(item)

    # Find the waiting task tied to this feed item
    from sqlmodel import select as sel
    waiting_task = session.exec(
        sel(Task).where(Task.question_feed_item_id == item_id)
    ).first()

    if waiting_task and waiting_task.status == TaskStatus.waiting:
        # Re-queue with the reply injected into the prompt
        waiting_task.prompt = (
            waiting_task.prompt
            + f"\n\n[User answered your question: {reply_text}]"
        )
        waiting_task.status = TaskStatus.queued
        waiting_task.question_feed_item_id = None
        session.add(waiting_task)
        manager.broadcast_from_thread(
            "task_queued",
            {"task_id": waiting_task.id, "prompt": waiting_task.prompt[:100]},
        )

    session.commit()
    session.refresh(item)
    return item
