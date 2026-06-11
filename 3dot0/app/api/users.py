"""API router: users."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=List[UserRead])
def list_users(session: Session = Depends(get_session)):
    return session.exec(select(User)).all()


@router.get("/me", response_model=UserRead)
def get_primary_user(session: Session = Depends(get_session)):
    """Return the primary user (shortcut for the frontend)."""
    user = session.exec(select(User).where(User.is_primary == True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No primary user configured.")
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user
