"""
JARVIS v3.0 — Routine Scheduler (APScheduler)

On startup, reads all active routines from the database and registers their
cron triggers with APScheduler.  When a cron fires, it creates a Task row
via the BackgroundWorker (decoupling scheduling from inference).

Dynamic updates:
    Call reload_routines() to re-sync the scheduler after the Routines table
    changes (e.g. a routine was created or toggled via the API).
"""
import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import session_scope

if TYPE_CHECKING:
    from app.worker.background_worker import BackgroundWorker

logger = logging.getLogger(__name__)

_JOB_ID_PREFIX = "routine_"


class RoutineScheduler:
    """
    Wraps APScheduler and keeps scheduled jobs in sync with the Routines table.
    """

    def __init__(self, worker: "BackgroundWorker") -> None:
        self._worker = worker
        from app.config import load_config
        cfg = load_config()
        tz = cfg.get("server", {}).get("timezone", "UTC")
        self._scheduler = BackgroundScheduler(
            job_defaults={"coalesce": True, "max_instances": 1},
            timezone=tz,
        )

    def start(self) -> None:
        self._scheduler.start()
        self.reload_routines()

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def reload_routines(self) -> None:
        """
        Clear all scheduled routine jobs and re-register from the DB.
        Call this after any routine is created, updated, or toggled.
        """
        # Remove all previously registered routine jobs
        for job in list(self._scheduler.get_jobs()):
            if job.id.startswith(_JOB_ID_PREFIX):
                job.remove()

        with session_scope() as session:
            from sqlmodel import select
            from app.models import Routine, TriggerType

            routines = session.exec(
                select(Routine).where(
                    Routine.active == True,
                    Routine.trigger_type == TriggerType.cron,
                )
            ).all()

            registered = 0
            for routine in routines:
                if not routine.trigger_value:
                    continue
                try:
                    self._register_cron(
                        routine_id=routine.id,
                        routine_name=routine.name,
                        cron_expr=routine.trigger_value,
                        prompt=routine.system_prompt,
                    )
                    registered += 1
                except Exception as exc:
                    logger.warning(
                        "Could not schedule routine %d (%s): %s",
                        routine.id,
                        routine.name,
                        exc,
                    )

        logger.info("Scheduler: registered %d cron routine(s).", registered)

    # ── Private ────────────────────────────────────────────────────────────────

    def _register_cron(
        self,
        routine_id: int,
        routine_name: str,
        cron_expr: str,
        prompt: str,
    ) -> None:
        """Parse a cron expression and add it to APScheduler."""
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression '{cron_expr}'. "
                "Expected 5 fields: minute hour day month day-of-week."
            )
        minute, hour, day, month, day_of_week = parts

        trigger = CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        )

        job_id = f"{_JOB_ID_PREFIX}{routine_id}"

        # Build the prompt that the scheduler passes to the worker.
        # By convention, the routine's system_prompt IS the task prompt for
        # automated runs (the worker also sets it as the system prompt).
        task_prompt = (
            f"[Automated routine: {routine_name}] "
            "Please execute this routine now and produce a complete report."
        )

        self._scheduler.add_job(
            func=self._worker.enqueue_routine,
            trigger=trigger,
            id=job_id,
            name=routine_name,
            kwargs={"routine_id": routine_id, "prompt": task_prompt},
            replace_existing=True,
        )
        logger.debug(
            "Scheduled routine %d (%s) with cron '%s'.", routine_id, routine_name, cron_expr
        )
