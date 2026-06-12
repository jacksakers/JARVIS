"""
API router: authentication.
Simple token-based auth stored in localStorage on the client.
Tokens are UUIDs stored in the users table (hashed for security).
"""
import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import LoginRequest, LoginResponse, User, UserRead, UserUpdate

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(plain: str) -> str:
    """SHA-256 of the password (sufficient for a local single-user app)."""
    return hashlib.sha256(plain.encode()).hexdigest()


def _verify_password(plain: str, hashed: str) -> bool:
    return _hash_password(plain) == hashed


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


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    """
    Log in with username + password.
    Returns a token to store in localStorage for subsequent requests.
    For users with no password set, any password is accepted (first-time setup).
    """
    user = session.exec(
        select(User).where(User.name == payload.username)
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if user.password_hash:
        if not _verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password.")
    # If no password set, any password accepted — prompt user to set one in Settings

    # Generate a new token
    token = secrets.token_urlsafe(32)
    # Store SHA-256 of token as password_hash only if not already set
    # Actually, store the token itself (hashed) in a separate field.
    # For simplicity, we use a dedicated token field on the user — stored as plain
    # (acceptable for a local Tailscale-only app, but hash it anyway).
    # We overload password_hash for the token only if no explicit password.
    # Better: store token separately. We'll put it in preferences.
    prefs = user.get_preferences()
    prefs["_session_token"] = hashlib.sha256(token.encode()).hexdigest()
    user.preferences = __import__("json").dumps(prefs)
    session.add(user)
    session.commit()

    return LoginResponse(token=token, user=_user_to_read(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    token: str,
    session: Session = Depends(get_session),
):
    """Invalidate the session token."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    users = session.exec(select(User)).all()
    for user in users:
        prefs = user.get_preferences()
        if prefs.get("_session_token") == token_hash:
            del prefs["_session_token"]
            user.preferences = __import__("json").dumps(prefs)
            session.add(user)
            session.commit()
            return


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(payload: LoginRequest, session: Session = Depends(get_session)):
    """Create a new user account."""
    existing = session.exec(select(User).where(User.name == payload.username)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken.")

    user = User(
        name=payload.username,
        password_hash=_hash_password(payload.password),
        is_primary=False,
        bio="",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = secrets.token_urlsafe(32)
    prefs = {}
    prefs["_session_token"] = hashlib.sha256(token.encode()).hexdigest()
    user.preferences = __import__("json").dumps(prefs)
    session.add(user)
    session.commit()
    session.refresh(user)

    return LoginResponse(token=token, user=_user_to_read(user))


@router.get("/me", response_model=UserRead)
def get_me(
    token: str,
    session: Session = Depends(get_session),
):
    """Validate a token and return the associated user."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    users = session.exec(select(User)).all()
    for user in users:
        prefs = user.get_preferences()
        if prefs.get("_session_token") == token_hash:
            return _user_to_read(user)
    raise HTTPException(status_code=401, detail="Invalid or expired token.")


@router.patch("/me", response_model=UserRead)
def update_me(
    token: str,
    payload: UserUpdate,
    session: Session = Depends(get_session),
):
    """Update the authenticated user's profile."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    user = None
    all_users = session.exec(select(User)).all()
    for u in all_users:
        prefs = u.get_preferences()
        if prefs.get("_session_token") == token_hash:
            user = u
            break
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    if payload.name is not None:
        # Check uniqueness
        conflict = session.exec(select(User).where(User.name == payload.name)).first()
        if conflict and conflict.id != user.id:
            raise HTTPException(status_code=409, detail="Username already taken.")
        user.name = payload.name
    if payload.bio is not None:
        user.bio = payload.bio
    if payload.preferences is not None:
        # Merge, preserving _session_token
        try:
            import json
            new_prefs = json.loads(payload.preferences)
            old_prefs = user.get_preferences()
            new_prefs["_session_token"] = old_prefs.get("_session_token", "")
            user.preferences = json.dumps(new_prefs)
        except Exception:
            pass
    if payload.password is not None and payload.password.strip():
        user.password_hash = _hash_password(payload.password)

    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_to_read(user)
