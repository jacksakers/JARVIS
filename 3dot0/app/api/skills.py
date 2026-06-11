"""API router: skills (read-only, populated by registry on startup)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.database import get_session
from app.models import Skill, SkillRead

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/", response_model=List[SkillRead])
def list_skills(session: Session = Depends(get_session)):
    """List all skills that were discovered and registered on startup."""
    return session.exec(select(Skill)).all()


@router.get("/{skill_name}", response_model=SkillRead)
def get_skill(skill_name: str, session: Session = Depends(get_session)):
    skill = session.exec(select(Skill).where(Skill.name == skill_name)).first()
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found.")
    return skill
