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
import json
import logging
import threading
import time
import base64
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import load_config
from app.core.agent_loop import AgentLoop, UserInputRequired
from app.core.markdown_utils import extract_title, render_markdown
from app.core.memory_manager import IntelligentMemoryManager
from app.core.model_registry import create_llm, is_gemini_model
from app.core.tool_registry import ToolRegistry
from app.database import session_scope
from app.models import Conversation, ConversationMessage, FeedItem, FeedItemType, Routine, Task, TaskStatus
from app.providers.ollama_provider import OllamaProvider
from app.worker.connection_manager import manager
from app.providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)


class _BytesEncoder(json.JSONEncoder):
    """JSON encoder that converts bytes to a base64 wrapper so Gemini's
    thought_signature (opaque bytes) can be stored in the Task.conversation_state
    column and restored when a waiting task is resumed."""

    def default(self, obj):
        if isinstance(obj, bytes):
            return {"__b64bytes__": base64.b64encode(obj).decode("ascii")}
        return super().default(obj)


def _bytes_decoder(obj: dict):
    """Paired object_hook for _BytesEncoder: converts base64 wrappers back to bytes."""
    if "__b64bytes__" in obj:
        return base64.b64decode(obj["__b64bytes__"])
    return obj


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

    Each instance is scoped to a provider family ("local" or "gemini") so that
    two workers can run in parallel — one for on-device Ollama models and one
    for cloud Gemini models — without competing for the same tasks.
    """

    def __init__(self, cfg: Optional[dict] = None, provider_filter: str = "all") -> None:
        self._cfg = cfg or load_config()
        self._provider_filter = provider_filter  # "local", "gemini", or "all"
        self._stop_event = threading.Event()
        thread_name = f"jarvis-worker-{provider_filter}"
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name=thread_name)
        self._registry = ToolRegistry()
        self._registry.discover_skills()

        # Cache of model_id -> BaseLLM instances (avoid re-creating per task)
        self._llm_cache: dict = {}

        # Pre-warm the default LLM so the first task starts immediately
        llm_cfg = self._cfg.get("llm", {})
        default_model = llm_cfg.get("model", "gemma4:e4b")
        self._llm_cache[default_model] = create_llm(default_model, self._cfg)

        worker_cfg = self._cfg.get("worker", {})
        self._poll_interval = worker_cfg.get("poll_interval_seconds", 2)
        self._max_tool_iterations = worker_cfg.get("max_tool_iterations", 6)

        mem_cfg = self._cfg.get("memory", {})
        self._max_recent_turns = mem_cfg.get("max_recent_turns", 8)
        self._max_tokens = mem_cfg.get("max_tokens", 8000)

    def _get_llm(self, model_id: Optional[str]):
        """Return a cached LLM for the given model_id, creating one if needed."""
        if not model_id:
            llm_cfg = self._cfg.get("llm", {})
            model_id = llm_cfg.get("model", "gemma4:e4b")
        if model_id not in self._llm_cache:
            self._llm_cache[model_id] = create_llm(model_id, self._cfg)
        return self._llm_cache[model_id]

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
                model_id=routine.model_id,  # propagate routine's model preference
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
            query = (
                select(Task)
                .where(Task.status == TaskStatus.queued)
                .order_by(Task.created_at.asc())
                .limit(1)
            )
            # Filter by provider so the local and Gemini workers don't compete
            if self._provider_filter == "gemini":
                query = query.where(Task.model_id.like("gemini-%"))
            elif self._provider_filter == "local":
                from sqlmodel import or_, col
                query = query.where(
                    or_(Task.model_id == None, ~col(Task.model_id).like("gemini-%"))  # noqa: E711
                )
            # "all" — no filter (backward-compatible single-worker mode)

            task = session.exec(query).first()

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
            task_conversation_id = task.conversation_id
            task_conv_state = task.conversation_state
            task_gen_config = task.routine_generation_config
            task_allowed_skills_override = task.allowed_skill_names_override
            task_model_id = task.model_id
            task_max_tool_iterations = task.max_tool_iterations

        manager.broadcast_from_thread(
            "task_started",
            {"task_id": task_id},
        )
        logger.info("Processing task %d: %s…", task_id, task_prompt[:60])

        try:
            # Check if this is a routine generation task
            if task_gen_config:
                self._process_routine_generation(task_id, task_user_id, task_gen_config, task_model_id)
            else:
                result_md, memory, token_usage = self._run_agent(
                    task_id=task_id,
                    prompt=task_prompt,
                    routine_id=task_routine_id,
                    system_prompt_override=task_system_override,
                    saved_state=task_conv_state,
                    conversation_id=task_conversation_id,
                    allowed_skill_names_override=task_allowed_skills_override,
                    model_id=task_model_id,
                    max_tool_iterations_override=task_max_tool_iterations,
                )
                self._save_result(
                    task_id=task_id,
                    user_id=task_user_id,
                    routine_id=task_routine_id,
                    conversation_id=task_conversation_id,
                    content_markdown=result_md or "",
                    token_usage=token_usage,
                )
        except UserInputRequired as exc:
            self._mark_waiting(task_id, exc.feed_item_id, exc.memory)
        except Exception as exc:
            logger.exception("Task %d failed: %s", task_id, exc)
            self._mark_failed(task_id, str(exc))

    def _run_agent(
        self,
        task_id: int,
        prompt: str,
        routine_id: Optional[int],
        system_prompt_override: Optional[str],
        saved_state: Optional[str] = None,
        conversation_id: Optional[int] = None,
        allowed_skill_names_override: Optional[str] = None,
        model_id: Optional[str] = None,
        max_tool_iterations_override: Optional[int] = None,
    ):
        """Set up and run the AgentLoop for this task. Returns (result_md, memory)."""
        system_prompt = system_prompt_override or _DEFAULT_SYSTEM_PROMPT
        allowed_skills: Optional[List[str]] = None  # None = all skills

        # Resolve model_id: task → routine → config default
        resolved_model_id = model_id
        if routine_id:
            with session_scope() as session:
                routine = session.get(Routine, routine_id)
                if routine:
                    if routine.system_prompt:
                        system_prompt = routine.system_prompt
                    allowed_skills = routine.get_allowed_skills()
                    if not resolved_model_id:
                        resolved_model_id = routine.model_id
        elif allowed_skill_names_override is not None:
            try:
                parsed = json.loads(allowed_skill_names_override)
                if isinstance(parsed, list):
                    allowed_skills = parsed
            except Exception:
                pass

        # Resolve model from conversation if still None
        if not resolved_model_id and conversation_id:
            with session_scope() as session:
                conv = session.get(Conversation, conversation_id)
                if conv:
                    resolved_model_id = conv.model_id

        llm = self._get_llm(resolved_model_id)

        # Restore conversation state if this task was paused (ask_user resume)
        if saved_state:
            try:
                state_dict = json.loads(saved_state, object_hook=_bytes_decoder)
                memory = IntelligentMemoryManager.from_dict(
                    state_dict,
                    max_recent_turns=self._max_recent_turns,
                    max_tokens=self._max_tokens,
                )
                logger.info("Task %d: restored conversation state (%d turns).", task_id, len(memory._turns))
            except Exception as exc:
                logger.warning("Task %d: could not restore state: %s — starting fresh.", task_id, exc)
                memory = IntelligentMemoryManager(
                    system_prompt=system_prompt,
                    max_recent_turns=self._max_recent_turns,
                    max_tokens=self._max_tokens,
                )
        else:
            memory = IntelligentMemoryManager(
                system_prompt=system_prompt,
                max_recent_turns=self._max_recent_turns,
                max_tokens=self._max_tokens,
            )
            # Load prior conversation messages as context for chat tasks
            if conversation_id:
                from sqlmodel import select
                with session_scope() as session:
                    from sqlmodel import or_, col as _col
                    prior_msgs = session.exec(
                        select(ConversationMessage)
                        .where(ConversationMessage.conversation_id == conversation_id)
                        .where(ConversationMessage.content != "")
                        # Include messages that belong to OTHER tasks (prior turns) OR have no
                        # task_id at all (user messages created before the fix that sets task_id).
                        # Plain `!= task_id` excludes NULLs in SQL (NULL != X = NULL = falsy),
                        # which previously hid all user messages and broke conversation history.
                        .where(
                            or_(
                                _col(ConversationMessage.task_id).is_(None),
                                ConversationMessage.task_id != task_id,
                            )
                        )
                        .order_by(ConversationMessage.created_at.asc())
                    ).all()
                    # Inject prior messages as completed turns in memory
                    i = 0
                    while i < len(prior_msgs):
                        msg = prior_msgs[i]
                        if msg.role == "user":
                            turn: List[Dict[str, Any]] = [{"role": "user", "content": msg.content}]
                            if i + 1 < len(prior_msgs) and prior_msgs[i + 1].role == "assistant":
                                turn.append({"role": "assistant", "content": prior_msgs[i + 1].content})
                                i += 2
                            else:
                                i += 1
                            memory._turns.append(turn)
                        else:
                            i += 1
                    if prior_msgs:
                        logger.info("Task %d: loaded %d prior messages as context.", task_id, len(prior_msgs))

        # Capture token usage emitted by the agent loop
        _token_usage: Dict[str, int] = {}

        def on_event(event_type: str, data: Dict[str, Any]) -> None:
            if event_type == "token_usage":
                _token_usage.update(data)
            manager.broadcast_from_thread(event_type, {"task_id": task_id, **data})

        # Set thread-local task_id so skills like ask_user can reference it
        import app.skills.ask_user_skill as _ask_mod
        _ask_mod._current_task.task_id = task_id
        _ask_mod._current_task.user_id = 1 # TODO: Get real user id
        _ask_mod._current_task.memory = memory

        agent = AgentLoop(
            llm=llm,
            registry=self._registry,
            memory=memory,
            on_event=on_event,
        )

        # Dev tasks need more iterations (explore → search → read → branch → edit × N → commit)
        is_dev_task = (
            allowed_skill_names_override is not None
            and "dev_list_repos" in (allowed_skill_names_override or "")
        )
        if max_tool_iterations_override is not None:
            max_iters = max_tool_iterations_override
        elif is_dev_task:
            max_iters = 20
        else:
            max_iters = self._max_tool_iterations

        result = agent.run_turn(prompt, allowed_skill_names=allowed_skills, max_iterations=max_iters)
        return result, memory, _token_usage

    def _process_routine_generation(
        self,
        task_id: int,
        user_id: int,
        generation_config: str,
        model_id: Optional[str] = None,
    ) -> None:
        """Generate a routine via LLM and save it to the database."""
        try:
            gen_config_dict = json.loads(generation_config)
        except json.JSONDecodeError:
            self._mark_failed(task_id, "Invalid routine generation config JSON")
            return

        description = gen_config_dict.get("description", "").strip()
        if not description:
            self._mark_failed(task_id, "No description provided for routine generation")
            return

        # Build skill list context
        skill_names = list(self._registry.tools.keys())
        skill_descs = "\n".join(
            f"- {name}: {cls.description[:120]}"
            for name, cls in self._registry.tools.items()
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
            "- For cron triggers use standard 5-field cron (e.g. '0 8 * * 1-5' = 8 AM weekdays). These times MUST be in UTC.\n"
            "- Output ONLY valid JSON, no markdown fences, no explanation."
        )

        user_prompt = f"Generate a JARVIS routine for: {description}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        content = ""
        try:
            llm = self._get_llm(model_id)
            for chunk in llm.stream(messages, tools=None):
                if chunk.content:
                    content += chunk.content
        except Exception as exc:
            logger.exception("Routine generation LLM call failed for task %d", task_id)
            self._mark_failed(task_id, f"LLM error: {str(exc)[:200]}")
            return

        # Strip markdown fences if model wraps it anyway
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1]) if len(lines) > 1 and lines[-1].startswith("```") else "\n".join(lines[1:])

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            logger.error("Routine generation LLM returned invalid JSON for task %d: %s", task_id, content[:300])
            self._mark_failed(task_id, f"LLM returned invalid JSON")
            return

        # Validate and sanitize the result
        routine_data = {
            "name": result.get("name", "Unnamed Routine").strip()[:255],
            "description": result.get("description", "").strip()[:255],
            "trigger_type": result.get("trigger_type", "manual"),
            "trigger_value": result.get("trigger_value", "").strip(),
            "system_prompt": result.get("system_prompt", "").strip(),
            "allowed_skill_names": json.dumps(
                [s for s in result.get("allowed_skill_names", []) if s in skill_names]
            ),
            "active": result.get("active", True),
        }

        # Validate required fields
        if not routine_data["name"]:
            self._mark_failed(task_id, "Generated routine has no name")
            return

        # Save the routine to the database
        try:
            with session_scope() as session:
                from app.models import Routine
                routine = Routine(user_id=user_id, **routine_data)
                session.add(routine)
                session.flush()
                routine_id = routine.id
                
                # Mark task as done
                task = session.get(Task, task_id)
                if task:
                    task.status = TaskStatus.done
                    task.completed_at = datetime.now(timezone.utc)
                    session.add(task)
                session.commit()

            logger.info("Generated routine %d from task %d: %s", routine_id, task_id, routine_data["name"])
            manager.broadcast_from_thread(
                "task_done",
                {"task_id": task_id, "routine_id": routine_id, "routine_name": routine_data["name"]},
            )
        except Exception as exc:
            logger.exception("Failed to save generated routine for task %d", task_id)
            self._mark_failed(task_id, f"Database error: {str(exc)[:200]}")

    def _save_result(
        self,
        task_id: int,
        user_id: int,
        routine_id: Optional[int],
        content_markdown: str,
        conversation_id: Optional[int] = None,
        token_usage: Optional[Dict[str, int]] = None,
    ) -> None:
        """Render markdown, create a FeedItem, update conversation if needed, and mark the task done."""
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
                if token_usage:
                    task.tokens_prompt = token_usage.get("prompt_tokens", 0)
                    task.tokens_completion = token_usage.get("completion_tokens", 0)
                    task.tokens_thinking = token_usage.get("thinking_tokens", 0)
                session.add(task)

            # Update the pending assistant ConversationMessage if this is a chat task
            if conversation_id:
                from sqlmodel import select
                pending = session.exec(
                    select(ConversationMessage)
                    .where(ConversationMessage.conversation_id == conversation_id)
                    .where(ConversationMessage.task_id == task_id)
                    .where(ConversationMessage.role == "assistant")
                ).first()
                if pending:
                    pending.content = content_markdown
                    pending.content_html = content_html
                    session.add(pending)
                # Touch conversation updated_at
                conv = session.get(Conversation, conversation_id)
                if conv:
                    conv.updated_at = datetime.now(timezone.utc)
                    session.add(conv)

        manager.broadcast_from_thread(
            "task_done",
            {
                "task_id": task_id,
                "feed_item_id": feed_item_id,
                "title": title,
                **({"token_usage": token_usage} if token_usage else {}),
            },
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

    def _mark_waiting(self, task_id: int, feed_item_id: int, memory=None) -> None:
        state_json = None
        if memory:
            try:
                state_json = json.dumps(memory.to_dict(), cls=_BytesEncoder)
            except Exception as exc:
                logger.warning("Could not serialize memory state for task %d: %s", task_id, exc)

        with session_scope() as session:
            task = session.get(Task, task_id)
            if task:
                task.status = TaskStatus.waiting
                task.question_feed_item_id = feed_item_id
                task.conversation_state = state_json
                session.add(task)

        manager.broadcast_from_thread(
            "task_waiting",
            {"task_id": task_id, "feed_item_id": feed_item_id},
        )
        logger.info("Task %d is waiting for user reply (feed item %d).", task_id, feed_item_id)

    @staticmethod
    def _infer_feed_type(routine_id: Optional[int]) -> FeedItemType:
        """Use 'report' for manual tasks; routine tasks keep their type for now."""
        return FeedItemType.report if routine_id is None else FeedItemType.briefing
