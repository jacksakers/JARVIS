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
    Task,
    TaskStatus,
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
    Queue a task to generate a routine with AI based on a description.
    Returns the task_id for the frontend to poll.
    """
    description = payload.get("description", "").strip()
    if not description:
        raise HTTPException(status_code=422, detail="description is required.")

    user = _get_default_user(session)

    # Create a Task with the routine_generation_config set
    import json
    task = Task(
        user_id=user.id,
        prompt=f"Generate a routine: {description}",
        status=TaskStatus.queued,
        routine_generation_config=json.dumps({"description": description}),
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    from app.worker.connection_manager import manager
    manager.broadcast_from_thread(
        "task_queued",
        {"task_id": task.id, "type": "routine_generation", "description": description[:100]},
    )

    return {"task_id": task.id, "status": "queued"}
