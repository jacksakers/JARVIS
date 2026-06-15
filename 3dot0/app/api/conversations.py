"""API router: chat conversations."""
import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, select

from app.database import get_session
from app.models import (
    Conversation,
    ConversationCreate,
    ConversationMessage,
    ConversationMessageRead,
    ConversationRead,
    ConversationUpdate,
    Task,
    TaskCreate,
    TaskStatus,
    User,
)
from app.worker.connection_manager import manager

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_default_user(session: Session) -> User:
    user = session.exec(select(User).where(User.is_primary == True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No primary user found.")
    return user


def _conv_read(conv: Conversation, session: Session) -> ConversationRead:
    count = session.exec(
        select(func.count(ConversationMessage.id)).where(
            ConversationMessage.conversation_id == conv.id
        )
    ).one()
    return ConversationRead(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        system_prompt_override=conv.system_prompt_override,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=count or 0,
    )


@router.get("/", response_model=List[ConversationRead])
def list_conversations(
    limit: int = Query(default=20, le=100),
    session: Session = Depends(get_session),
):
    user = _get_default_user(session)
    convs = session.exec(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    ).all()
    return [_conv_read(c, session) for c in convs]


@router.post("/", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    session: Session = Depends(get_session),
):
    user = _get_default_user(session)
    now = datetime.now(timezone.utc)
    conv = Conversation(
        user_id=user.id,
        title=payload.title,
        system_prompt_override=payload.system_prompt_override,
        created_at=now,
        updated_at=now,
    )
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return _conv_read(conv, session)


@router.patch("/{conv_id}", response_model=ConversationRead)
def update_conversation(
    conv_id: int,
    payload: ConversationUpdate,
    session: Session = Depends(get_session),
):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if payload.title is not None:
        conv.title = payload.title
    if payload.system_prompt_override is not None:
        conv.system_prompt_override = payload.system_prompt_override
    conv.updated_at = datetime.now(timezone.utc)
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return _conv_read(conv, session)


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conv_id: int, session: Session = Depends(get_session)):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    # Delete all messages
    msgs = session.exec(
        select(ConversationMessage).where(ConversationMessage.conversation_id == conv_id)
    ).all()
    for m in msgs:
        session.delete(m)
    session.delete(conv)
    session.commit()


@router.get("/{conv_id}/messages", response_model=List[ConversationMessageRead])
def list_messages(
    conv_id: int,
    session: Session = Depends(get_session),
):
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    msgs = session.exec(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conv_id)
        .order_by(ConversationMessage.created_at.asc())
    ).all()
    return msgs


@router.post("/{conv_id}/messages", status_code=status.HTTP_201_CREATED)
def send_message(
    conv_id: int,
    payload: dict,
    session: Session = Depends(get_session),
):
    """
    Add a user message to a conversation and queue a task for the assistant reply.
    Returns the user message + a placeholder assistant message (with task_id for polling).
    """
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    user = _get_default_user(session)
    prompt = payload.get("content", "").strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="content is required.")

    # Optional per-message tool allowlist (None = all tools)
    allowed_skill_names = payload.get("allowed_skill_names", None)
    allowed_skill_names_json: Optional[str] = None
    if isinstance(allowed_skill_names, list):
        allowed_skill_names_json = json.dumps(allowed_skill_names)

    now = datetime.now(timezone.utc)

    # Save the user message
    user_msg = ConversationMessage(
        conversation_id=conv_id,
        role="user",
        content=prompt,
        created_at=now,
    )
    session.add(user_msg)

    # Queue a Task tied to this conversation
    task = Task(
        user_id=user.id,
        prompt=prompt,
        conversation_id=conv_id,
        system_prompt_override=conv.system_prompt_override,
        allowed_skill_names_override=allowed_skill_names_json,
        status=TaskStatus.queued,
    )
    session.add(task)
    session.flush()
    task_id = task.id

    # Create a pending assistant message (content filled in by worker)
    asst_msg = ConversationMessage(
        conversation_id=conv_id,
        role="assistant",
        content="",
        task_id=task_id,
        created_at=now,
    )
    session.add(asst_msg)

    # Touch conversation updated_at
    conv.updated_at = now
    session.add(conv)

    session.commit()
    session.refresh(user_msg)
    session.refresh(asst_msg)

    manager.broadcast_from_thread(
        "task_queued",
        {"task_id": task_id, "prompt": prompt[:100], "conversation_id": conv_id},
    )

    return {
        "user_message": ConversationMessageRead.model_validate(user_msg),
        "assistant_message": ConversationMessageRead.model_validate(asst_msg),
        "task_id": task_id,
    }
