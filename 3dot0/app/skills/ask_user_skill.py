"""
ask_user skill — pause the current task and display a question to the user.
The task resumes automatically once the user replies via the feed.
"""
import threading

from pydantic import BaseModel, Field

from app.skills.base_skill import BaseSkill

# Thread-local storage so the background worker can tell the skill which task
# is currently running without passing it through the call stack.
_current_task = threading.local()

SENTINEL_PREFIX = "__WAITING_FOR_USER__:"


class AskUserInput(BaseModel):
    question: str = Field(
        description=(
            "The question to display to the user. Be clear and specific. "
            "The task will pause until the user replies via the Activity Feed."
        )
    )
    title: str = Field(
        default="Question from JARVIS",
        description="A short title for the question card shown in the feed.",
    )


class AskUserSkill(BaseSkill):
    name = "ask_user"
    description = (
        "Ask the user a question and pause the current task until they reply. "
        "Use this when you need clarification, a decision, or additional information "
        "before proceeding. The question appears as a card in the Activity Feed. "
        "The task resumes automatically once the user answers."
    )
    input_model = AskUserInput

    def execute(self, params: AskUserInput) -> str:
        task_id = getattr(_current_task, "task_id", None)
        if task_id is None:
            # Fallback if called outside a worker context (e.g. skill tester)
            return f"[QUESTION] {params.question} (Note: no live task context — reply via feed)"

        try:
            from app.core.markdown_utils import render_markdown
            from app.database import session_scope
            from app.models import FeedItem, FeedItemType, Task, User
            from sqlmodel import select

            content_md = f"## {params.title}\n\n{params.question}"
            content_html = render_markdown(content_md)

            with session_scope() as session:
                # Resolve user_id from the task
                task = session.get(Task, task_id)
                user_id = task.user_id if task else 1

                feed_item = FeedItem(
                    user_id=user_id,
                    task_id=task_id,
                    type=FeedItemType.question,
                    title=params.title,
                    content_markdown=content_md,
                    content_html=content_html,
                    is_read=False,
                )
                session.add(feed_item)
                session.flush()
                feed_item_id = feed_item.id

            return f"{SENTINEL_PREFIX}{feed_item_id}"

        except Exception as exc:
            return f"ask_user failed: {exc}"
