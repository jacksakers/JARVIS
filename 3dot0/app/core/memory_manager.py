"""
IntelligentMemoryManager — ported from JARVIS v2.0 with no changes.
Groups messages into turns, keeps a sliding window of recent turns, and
summarises old context via the LLM when the window fills up.
"""
from typing import Any, Dict, List, Optional


class IntelligentMemoryManager:
    """
    Manages conversation history as discrete *turns*.
    One turn = the user message + all tool calls + the assistant's final reply.

    When the completed-turn count exceeds `max_recent_turns`:
    • Older turns are fed to the LLM and compressed into bullet-point prose.
    • The raw tool-call payloads are replaced by that compact summary.
    • Only the most recent N turns are kept as live messages.

    This prevents stale tool-call structures from polluting fresh questions
    and keeps the context window from ballooning.
    """

    def __init__(
        self,
        system_prompt: str,
        max_recent_turns: int = 8,
        max_tokens: int = 8000,
    ) -> None:
        self.system_prompt = system_prompt
        self.max_recent_turns = max_recent_turns
        self.max_tokens = max_tokens

        self.session_summary: str = ""
        self._turns: List[List[Dict[str, Any]]] = []
        self._current_turn: List[Dict[str, Any]] = []

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def estimated_tokens(self) -> int:
        """Rough token estimate: ~4 chars per token across all messages."""
        total_chars = sum(
            len(str(msg.get("content", "")))
            for turn in self._turns
            for msg in turn
        )
        return total_chars // 4

    # ── Append helpers ────────────────────────────────────────────────────────

    def append_user(self, content: str) -> None:
        if self._current_turn:
            self._turns.append(self._current_turn)
        self._current_turn = [{"role": "user", "content": content}]

    def append_assistant(self, content: str) -> None:
        self._current_turn.append({"role": "assistant", "content": content})

    def append_tool_turn(
        self,
        assistant_msg: Dict[str, Any],
        tool_results: List[Dict[str, Any]],
    ) -> None:
        """Add tool-call message + all results as one atomic block."""
        self._current_turn.append(assistant_msg)
        self._current_turn.extend(tool_results)

    def close_turn(self) -> None:
        if self._current_turn:
            self._turns.append(self._current_turn)
            self._current_turn = []

    def clear(self) -> None:
        self._turns = []
        self._current_turn = []
        self.session_summary = ""

    # ── Context window construction ────────────────────────────────────────

    def get_messages(self) -> List[Dict[str, Any]]:
        """
        Build the full message list to send to the LLM.

        Slot 0  – system prompt
        Slot 1  – session summary of compressed turns (if any)
        Slots … – most recent N completed turns
        Tail    – in-progress messages for the current turn
        """
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

        if self.session_summary:
            messages.append({
                "role": "system",
                "content": "Summary of earlier conversation:\n" + self.session_summary,
            })

        recent = self._turns[-self.max_recent_turns:]
        for turn in recent:
            messages.extend(turn)

        messages.extend(self._current_turn)
        return messages

    # ── Automatic summarisation ───────────────────────────────────────────

    def should_summarize(self) -> bool:
        return len(self._turns) > self.max_recent_turns

    def summarize(self, llm) -> None:
        """
        Compress turns outside the sliding window into bullet-point prose,
        then discard the raw messages for those turns.
        """
        old_turns = self._turns[: -self.max_recent_turns]
        if not old_turns:
            return

        flat: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]
        for turn in old_turns:
            for msg in turn:
                if msg.get("role") in ("user", "assistant"):
                    flat.append(msg)

        flat.append({
            "role": "user",
            "content": (
                "Please summarise the conversation above as a concise bullet-point "
                "list. Focus on key facts, decisions, and answers. "
                "Do not include tool call details — only the information exchanged."
            ),
        })

        summary_chunks = []
        for chunk in llm.generate(flat):
            summary_chunks.append(chunk)
        new_summary = "".join(summary_chunks).strip()

        if self.session_summary:
            self.session_summary = self.session_summary + "\n" + new_summary
        else:
            self.session_summary = new_summary

        self._turns = self._turns[-self.max_recent_turns:]
