"""
JARVIS v3.0 — Background Worker

The worker runs in a dedicated thread and is the only thing that directly
interacts with the Ollama API.  It continuously polls the tasks table for
queued jobs and processes them one at a time.

Processing flow for each task:
─────────────────────────────
1. Select the oldest queued task.
2. Mark it "running" and notify WebSocket clients.
3. Resolve the system prompt + allowed skills (from its routine, or defaults).
4. Build AgentLoop and IntelligentMemoryManager.
5. Run AgentLoop.run_turn(task.prompt).
6. Render the markdown result to HTML.
7. Create a FeedItem and mark the task "done".
8. Notify WebSocket clients.
9. If any exception occurs, mark the task "failed" and write the error.
"""
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import load_config
from app.core.agent_loop import AgentLoop
from app.core.markdown_utils import extract_title, render_markdown
from app.core.memory_manager import IntelligentMemoryManager
from app.core.tool_registry import ToolRegistry
from app.database import session_scope
from app.models import FeedItem, FeedItemType, Routine, Task, TaskStatus
from app.providers.ollama_provider import OllamaProvider
from app.worker.connection_manager import manager

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "You are JARVIS, a highly capable and efficient AI assistant. "
    "You are concise, direct, and proactive. Always format your final responses "
    "in well-structured Markdown with headings, bullet points, and code blocks "
    "where appropriate. Use tools when you need real-time data or need to take "
    "an action — after using a tool, respond naturally based on the result."
)


class BackgroundWorker:
    """
    Continuously polls the tasks table and processes jobs using the AgentLoop.
    """

    def __init__(self, cfg: Optional[dict] = None) -> None:
        self._cfg = cfg or load_config()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="jarvis-worker")
        self._registry = ToolRegistry()
        self._registry.discover_skills()

        llm_cfg = self._cfg.get("llm", {})
        self._llm = OllamaProvider(
            model=llm_cfg.get("model", "gemma4:e4b"),
            base_url=llm_cfg.get("ollama_url", "http://localhost:11434"),
            options=llm_cfg.get("options", {}),
        )

        worker_cfg = self._cfg.get("worker", {})
        self._poll_interval = worker_cfg.get("poll_interval_seconds", 2)
        self._max_tool_iterations = worker_cfg.get("max_tool_iterations", 6)

        mem_cfg = self._cfg.get("memory", {})
        self._max_recent_turns = mem_cfg.get("max_recent_turns", 8)
        self._max_tokens = mem_cfg.get("max_tokens", 8000)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=10)

    def enqueue_routine(self, routine_id: int, prompt: str) -> None:
        """
        Called by the scheduler to queue a routine-triggered task.
        Runs in the APScheduler thread.
        """
        with session_scope() as session:
            from sqlmodel import select
            routine = session.get(Routine, routine_id)
            if not routine or not routine.active:
                return

            task = Task(
                user_id=routine.user_id,
                routine_id=routine_id,
                prompt=prompt,
                status=TaskStatus.queued,
            )
            session.add(task)
            session.flush()
            task_id = task.id

        manager.broadcast_from_thread(
            "task_queued",
            {"task_id": task_id, "routine_id": routine_id, "prompt": prompt[:100]},
        )
        logger.info("Routine %d enqueued as task %d.", routine_id, task_id)

    # ── Private ────────────────────────────────────────────────────────────────

    def _poll_loop(self) -> None:
        logger.info("Worker polling every %ds.", self._poll_interval)
        while not self._stop_event.is_set():
            try:
                self._process_next()
            except Exception as exc:
                logger.exception("Unhandled error in worker loop: %s", exc)
            self._stop_event.wait(self._poll_interval)

    def _process_next(self) -> None:
        """Pick up and process the oldest queued task, if any."""
        with session_scope() as session:
            from sqlmodel import select
            task = session.exec(
                select(Task)
                .where(Task.status == TaskStatus.queued)
                .order_by(Task.created_at.asc())
                .limit(1)
            ).first()

            if not task:
                return

            task.status = TaskStatus.running
            task.started_at = datetime.now(timezone.utc)
            session.add(task)
            session.flush()
            task_id = task.id
            task_prompt = task.prompt
            task_routine_id = task.routine_id
            task_user_id = task.user_id
            task_system_override = task.system_prompt_override

        manager.broadcast_from_thread(
            "task_started",
            {"task_id": task_id},
        )
        logger.info("Processing task %d: %s…", task_id, task_prompt[:60])

        try:
            result_md = self._run_agent(
                task_id=task_id,
                prompt=task_prompt,
                routine_id=task_routine_id,
                system_prompt_override=task_system_override,
            )
            self._save_result(
                task_id=task_id,
                user_id=task_user_id,
                routine_id=task_routine_id,
                content_markdown=result_md or "",
            )
        except Exception as exc:
            logger.exception("Task %d failed: %s", task_id, exc)
            self._mark_failed(task_id, str(exc))

    def _run_agent(
        self,
        task_id: int,
        prompt: str,
        routine_id: Optional[int],
        system_prompt_override: Optional[str],
    ) -> Optional[str]:
        """Set up and run the AgentLoop for this task."""
        system_prompt = system_prompt_override or _DEFAULT_SYSTEM_PROMPT
        allowed_skills: List[str] = []

        if routine_id:
            with session_scope() as session:
                routine = session.get(Routine, routine_id)
                if routine:
                    if routine.system_prompt:
                        system_prompt = routine.system_prompt
                    allowed_skills = routine.get_allowed_skills()

        memory = IntelligentMemoryManager(
            system_prompt=system_prompt,
            max_recent_turns=self._max_recent_turns,
            max_tokens=self._max_tokens,
        )

        def on_event(event_type: str, data: Dict[str, Any]) -> None:
            manager.broadcast_from_thread(event_type, {"task_id": task_id, **data})

        agent = AgentLoop(
            llm=self._llm,
            registry=self._registry,
            memory=memory,
            on_event=on_event,
        )
        agent.MAX_TOOL_ITERATIONS = self._max_tool_iterations

        return agent.run_turn(prompt, allowed_skill_names=allowed_skills or None)

    def _save_result(
        self,
        task_id: int,
        user_id: int,
        routine_id: Optional[int],
        content_markdown: str,
    ) -> None:
        """Render markdown, create a FeedItem, and mark the task done."""
        content_html = render_markdown(content_markdown)
        title = extract_title(content_markdown, fallback="Report")
        feed_type = self._infer_feed_type(routine_id)

        with session_scope() as session:
            feed_item = FeedItem(
                user_id=user_id,
                task_id=task_id,
                type=feed_type,
                title=title,
                content_markdown=content_markdown,
                content_html=content_html,
            )
            session.add(feed_item)
            session.flush()
            feed_item_id = feed_item.id

            task = session.get(Task, task_id)
            if task:
                task.status = TaskStatus.done
                task.completed_at = datetime.now(timezone.utc)
                session.add(task)

        manager.broadcast_from_thread(
            "task_done",
            {"task_id": task_id, "feed_item_id": feed_item_id, "title": title},
        )
        manager.broadcast_from_thread(
            "feed_new",
            {
                "id": feed_item_id,
                "title": title,
                "type": feed_type,
            },
        )
        logger.info("Task %d done → feed item %d: %s", task_id, feed_item_id, title)

    def _mark_failed(self, task_id: int, error: str) -> None:
        with session_scope() as session:
            task = session.get(Task, task_id)
            if task:
                task.status = TaskStatus.failed
                task.error_message = error[:1000]
                task.completed_at = datetime.now(timezone.utc)
                session.add(task)

        manager.broadcast_from_thread(
            "task_failed",
            {"task_id": task_id, "error": error[:200]},
        )

    @staticmethod
    def _infer_feed_type(routine_id: Optional[int]) -> FeedItemType:
        """Use 'report' for manual tasks; routine tasks keep their type for now."""
        return FeedItemType.report if routine_id is None else FeedItemType.briefing
