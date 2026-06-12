"""API router: users."""
import json
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def _user_to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        name=user.name,
        is_primary=user.is_primary,
        bio=user.bio or "",
        preferences=user.preferences or "{}",
        has_password=bool(user.password_hash),
        created_at=user.created_at,
    )


@router.get("/", response_model=List[UserRead])
def list_users(session: Session = Depends(get_session)):
    return [_user_to_read(u) for u in session.exec(select(User)).all()]


@router.get("/me", response_model=UserRead)
def get_primary_user(session: Session = Depends(get_session)):
    """Return the primary user (shortcut for the frontend)."""
    user = session.exec(select(User).where(User.is_primary == True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No primary user configured.")
    return _user_to_read(user)


@router.patch("/me", response_model=UserRead)
def update_primary_user(
    payload: UserUpdate,
    session: Session = Depends(get_session),
):
    """Update the primary user's profile, bio, and preferences."""
    user = session.exec(select(User).where(User.is_primary == True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No primary user configured.")

    if payload.name is not None:
        conflict = session.exec(select(User).where(User.name == payload.name)).first()
        if conflict and conflict.id != user.id:
            raise HTTPException(status_code=409, detail="Username already taken.")
        user.name = payload.name
    if payload.bio is not None:
        user.bio = payload.bio
    if payload.preferences is not None:
        try:
            json.loads(payload.preferences)  # validate JSON
            user.preferences = payload.preferences
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="preferences must be valid JSON.")
    if payload.password is not None and payload.password.strip():
        import hashlib
        user.password_hash = hashlib.sha256(payload.password.encode()).hexdigest()

    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_to_read(user)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _user_to_read(user)

