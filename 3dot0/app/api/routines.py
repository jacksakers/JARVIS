"""API router: routines / automations (CRUD)."""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    Routine,
    RoutineCreate,
    RoutineRead,
    RoutineUpdate,
    User,
)

router = APIRouter(prefix="/routines", tags=["routines"])


def _get_default_user(session: Session) -> User:
    """Return the primary user (used when no auth is in place yet)."""
    user = session.exec(select(User).where(User.is_primary == True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No primary user found. Boot the app first.")
    return user


@router.get("/", response_model=List[RoutineRead])
def list_routines(session: Session = Depends(get_session)):
    """List all routines for the primary user."""
    user = _get_default_user(session)
    routines = session.exec(select(Routine).where(Routine.user_id == user.id)).all()
    return routines


@router.get("/{routine_id}", response_model=RoutineRead)
def get_routine(routine_id: int, session: Session = Depends(get_session)):
    routine = session.get(Routine, routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found.")
    return routine


@router.post("/", response_model=RoutineRead, status_code=status.HTTP_201_CREATED)
def create_routine(
    payload: RoutineCreate,
    session: Session = Depends(get_session),
):
    user = _get_default_user(session)
    routine = Routine(**payload.model_dump(), user_id=user.id)
    session.add(routine)
    session.commit()
    session.refresh(routine)
    return routine


@router.patch("/{routine_id}", response_model=RoutineRead)
def update_routine(
    routine_id: int,
    payload: RoutineUpdate,
    session: Session = Depends(get_session),
):
    routine = session.get(Routine, routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(routine, key, value)
    routine.updated_at = datetime.now(timezone.utc)

    session.add(routine)
    session.commit()
    session.refresh(routine)
    return routine


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(routine_id: int, session: Session = Depends(get_session)):
    routine = session.get(Routine, routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found.")
    session.delete(routine)
    session.commit()


@router.post("/{routine_id}/run", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
def run_routine_now(routine_id: int, session: Session = Depends(get_session)):
    """
    Immediately enqueue a one-off run of the routine (bypass its schedule).
    Returns the created task ID so the frontend can track it.
    """
    from app.models import Task, TaskStatus
    routine = session.get(Routine, routine_id)
    if not routine:
        raise HTTPException(status_code=404, detail="Routine not found.")

    task = Task(
        user_id=routine.user_id,
        routine_id=routine_id,
        prompt=(
            f"[Manual run: {routine.name}] "
            "Please execute this routine now and produce a complete report."
        ),
        status=TaskStatus.queued,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    from app.worker.connection_manager import manager
    manager.broadcast_from_thread(
        "task_queued",
        {"task_id": task.id, "routine_id": routine_id, "prompt": task.prompt[:100]},
    )
    return {"task_id": task.id, "status": "queued"}


@router.post("/generate", response_model=dict)
def generate_routine_with_ai(
    payload: dict,
    session: Session = Depends(get_session),
):
    """
    Call the LLM with a description of what routine the user wants.
    Returns a partially-filled RoutineCreate dict for the frontend to pre-populate.
    """
    description = payload.get("description", "").strip()
    if not description:
        raise HTTPException(status_code=422, detail="description is required.")

    # Build skill list context
    from app.core.tool_registry import ToolRegistry
    registry = ToolRegistry()
    registry.discover_skills()
    skill_names = list(registry.tools.keys())
    skill_descs = "\n".join(
        f"- {name}: {cls.description[:120]}"
        for name, cls in registry.tools.items()
    )

    system_prompt = (
        "You are a JARVIS routine generator. Output ONLY a JSON object that matches this schema:\n"
        "{\n"
        '  "name": "string",\n'
        '  "description": "string",\n'
        '  "trigger_type": "cron" | "manual",\n'
        '  "trigger_value": "cron expression if cron, else empty string",\n'
        '  "system_prompt": "detailed instructions for JARVIS when this routine runs",\n'
        '  "allowed_skill_names": ["array", "of", "skill", "names"],\n'
        '  "active": true\n'
        "}\n\n"
        f"Available skills (only pick from this list):\n{skill_descs}\n\n"
        "Rules:\n"
        "- system_prompt must be detailed and tell JARVIS exactly what to do, in what order, and how to format the output.\n"
        "- Only include skills that are actually needed for this routine.\n"
        "- For cron triggers use standard 5-field cron (e.g. '0 8 * * 1-5' = 8 AM weekdays).\n"
        "- Output ONLY valid JSON, no markdown fences, no explanation."
    )

    user_prompt = f"Generate a JARVIS routine for: {description}"

    from app.config import load_config
    from app.providers.ollama_provider import OllamaProvider
    cfg = load_config()
    llm_cfg = cfg.get("llm", {})
    llm = OllamaProvider(
        model=llm_cfg.get("model", "gemma4:e4b"),
        base_url=llm_cfg.get("ollama_url", "http://localhost:11434"),
        options={**llm_cfg.get("options", {}), "temperature": 0.3},
    )

    import json
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    content = ""
    for chunk in llm.stream(messages, tools=None):
        if chunk.content:
            content += chunk.content

    # Strip markdown fences if model wraps it anyway
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"LLM returned invalid JSON: {content[:300]}")

    # Validate skill names against actual registry
    if "allowed_skill_names" in result:
        result["allowed_skill_names"] = [
            s for s in result["allowed_skill_names"] if s in skill_names
        ]

    return result
