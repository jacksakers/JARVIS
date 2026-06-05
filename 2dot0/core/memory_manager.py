from typing import List, Dict, Any, Optional


class IntelligentMemoryManager:
    """
    Manages conversation history as discrete *turns* (one turn = user message
    + all assistant messages + tool calls that answer it).

    Key properties
    ──────────────
    • Groups messages by turn so tool-call/result pairs are never split apart.
    • Keeps only the most recent N turns in the active context window.
    • When the buffer exceeds the threshold, older turns are summarised by the
      LLM itself and stored as a compact session summary, resolving the
      "confused by two questions" problem: stale tool structures are replaced
      by plain-language summaries before the next question is answered.
    • The system prompt always occupies slot 0; the summary (if any) slot 1.
    """

    def __init__(
        self,
        system_prompt: str,
        max_recent_turns: int = 6,
        max_tokens: int = 5000,
    ) -> None:
        self.system_prompt = system_prompt
        self.max_recent_turns = max_recent_turns
        self.max_tokens = max_tokens

        self.session_summary: str = ""
        self._turns: List[List[Dict[str, Any]]] = []   # completed turns
        self._current_turn: List[Dict[str, Any]] = []  # turn being assembled

    # ------------------------------------------------------------------
    # Append helpers (called by AgentLoop)
    # ------------------------------------------------------------------

    def append_user(self, content: str) -> None:
        """
        Start a new turn with a user message.
        If a previous turn was left open (shouldn't normally happen), close it.
        """
        if self._current_turn:
            self._turns.append(self._current_turn)
        self._current_turn = [{"role": "user", "content": content}]

    def append_assistant(self, content: str) -> None:
        """Add a plain assistant message to the current turn."""
        self._current_turn.append({"role": "assistant", "content": content})

    def append_tool_turn(
        self,
        assistant_msg: Dict[str, Any],
        tool_results: List[Dict[str, Any]],
    ) -> None:
        """
        Add the assistant's tool-call message together with all tool results
        as a single atomic block inside the current turn.
        """
        self._current_turn.append(assistant_msg)
        self._current_turn.extend(tool_results)

    def close_turn(self) -> None:
        """Finalise the current turn and move it to the completed list."""
        if self._current_turn:
            self._turns.append(self._current_turn)
            self._current_turn = []

    def clear(self) -> None:
        """Wipe all history and the session summary."""
        self._turns = []
        self._current_turn = []
        self.session_summary = ""

    # ------------------------------------------------------------------
    # Context window construction
    # ------------------------------------------------------------------

    def get_messages(self) -> List[Dict[str, Any]]:
        """
        Build the message list that will be sent to the LLM.

        Slot 0  – system prompt (always present)
        Slot 1  – session summary from summarised turns (if any)
        Slots … – the most recent N completed turns
        Tail    – any in-progress messages for the current turn
        """
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

        if self.session_summary:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Summary of earlier conversation:\n" + self.session_summary
                    ),
                }
            )

        recent = self._turns[-self.max_recent_turns :]
        for turn in recent:
            messages.extend(turn)

        messages.extend(self._current_turn)
        return messages

    # ------------------------------------------------------------------
    # Automatic summarisation
    # ------------------------------------------------------------------

    def should_summarize(self) -> bool:
        """True when completed turns exceed the sliding-window size."""
        return len(self._turns) > self.max_recent_turns

    def summarize(self, llm) -> None:
        """
        Ask the LLM to compress turns that have fallen outside the window
        into a bullet-point summary, then trim history in place.

        This converts stale tool-call structures into readable prose so
        they never confuse the model on future turns.
        """
        if not self.should_summarize():
            return

        old_turns = self._turns[: -self.max_recent_turns]
        self._turns = self._turns[-self.max_recent_turns :]

        readable = self._turns_to_text(old_turns)

        summary_messages = [
            {
                "role": "system",
                "content": (
                    "You are a summarisation assistant. "
                    "Compress the conversation below into concise bullet points. "
                    "Capture key facts, user preferences, tool results, and decisions. "
                    "Be brief — a few lines at most."
                ),
            },
            {
                "role": "user",
                "content": f"Conversation to summarise:\n\n{readable}",
            },
        ]

        new_summary = "".join(llm.generate(summary_messages)).strip()

        if self.session_summary:
            self.session_summary = f"{self.session_summary}\n{new_summary}"
        else:
            self.session_summary = new_summary

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def estimated_tokens(self) -> int:
        total = _estimate_tokens(self.system_prompt)
        if self.session_summary:
            total += _estimate_tokens(self.session_summary)
        for turn in self._turns[-self.max_recent_turns :]:
            for msg in turn:
                total += _estimate_tokens(str(msg.get("content", "")))
        return total

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _turns_to_text(turns: List[List[Dict[str, Any]]]) -> str:
        lines: List[str] = []
        for turn in turns:
            for msg in turn:
                role = msg.get("role", "unknown")
                content = str(msg.get("content", "")).strip()
                if not content:
                    continue
                if role == "user":
                    lines.append(f"User: {content}")
                elif role == "assistant":
                    lines.append(f"JARVIS: {content}")
                elif role == "tool":
                    # Truncate long tool results for readability
                    snippet = content[:200] + ("…" if len(content) > 200 else "")
                    lines.append(f"[Tool result]: {snippet}")
        return "\n".join(lines)


def _estimate_tokens(text: str) -> int:
    """Fast approximation: 1 token ≈ 4 characters of English text."""
    return len(text) // 4
