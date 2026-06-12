"""API router: tasks / job queue."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import Task, TaskCreate, TaskRead, TaskStatus, User
from app.worker.connection_manager import manager

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_default_user(session: Session) -> User:
    user = session.exec(select(User).where(User.is_primary == True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No primary user found.")
    return user


@router.get("/", response_model=List[TaskRead])
def list_tasks(
    status_filter: Optional[TaskStatus] = Query(default=None, alias="status"),
    limit: int = Query(default=20, le=100),
    session: Session = Depends(get_session),
):
    """List tasks for the primary user, optionally filtered by status."""
    user = _get_default_user(session)
    query = select(Task).where(Task.user_id == user.id)
    if status_filter:
        query = query.where(Task.status == status_filter)
    query = query.order_by(Task.created_at.desc()).limit(limit)
    return session.exec(query).all()


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def submit_task(
    payload: TaskCreate,
    session: Session = Depends(get_session),
):
    """
    Submit a manual delegation task (the primary 'Delegate Task' action).
    The background worker will pick it up and process it asynchronously.
    """
    user = _get_default_user(session)
    task = Task(
        user_id=user.id,
        prompt=payload.prompt,
        routine_id=payload.routine_id,
        system_prompt_override=payload.system_prompt_override,
        status=TaskStatus.queued,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    # Notify any connected WebSocket clients
    manager.broadcast_from_thread(
        "task_queued",
        {"task_id": task.id, "prompt": task.prompt[:100]},
    )

    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_task(task_id: int, session: Session = Depends(get_session)):
    """Cancel a queued task (only allowed if status is 'queued')."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    # if task.status != TaskStatus.queued:
    #     raise HTTPException(
    #         status_code=status.HTTP_409_CONFLICT,
    #         detail=f"Cannot cancel a task with status '{task.status}'.",
    #     )
    session.delete(task)
    session.commit()


@router.post("/{task_id}/retry", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def retry_task(task_id: int, session: Session = Depends(get_session)):
    """Re-queue a failed task as a new task with the same prompt."""
    original = session.get(Task, task_id)
    if not original:
        raise HTTPException(status_code=404, detail="Task not found.")
    if original.status != TaskStatus.failed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed tasks can be retried.",
        )
    new_task = Task(
        user_id=original.user_id,
        routine_id=original.routine_id,
        prompt=original.prompt,
        system_prompt_override=original.system_prompt_override,
        status=TaskStatus.queued,
    )
    session.add(new_task)
    session.commit()
    session.refresh(new_task)

    manager.broadcast_from_thread(
        "task_queued",
        {"task_id": new_task.id, "prompt": new_task.prompt[:100]},
    )
    return new_task


@router.delete("/", status_code=status.HTTP_200_OK)
def bulk_delete_tasks(
    status_filter: Optional[str] = Query(
        default="done,failed",
        description="Comma-separated statuses to delete, e.g. 'done,failed'. Use 'all' to delete everything.",
    ),
    session: Session = Depends(get_session),
):
    """Bulk-delete tasks by status (defaults to done + failed)."""
    user = _get_default_user(session)
    query = select(Task).where(Task.user_id == user.id)

    if status_filter and status_filter.lower() != "all":
        statuses = [s.strip() for s in status_filter.split(",")]
        query = query.where(Task.status.in_(statuses))

    tasks = session.exec(query).all()
    count = len(tasks)
    for t in tasks:
        session.delete(t)
    session.commit()
    return {"deleted": count}
