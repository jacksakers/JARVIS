import json

class ConversationBuffer:
    def __init__(self, system_prompt: str, max_tokens: int = 3000):
        """
        Manages short-term memory to ensure we never overflow the LLM's context window.
        """
        self.max_tokens = max_tokens
        # Reserve slot 0 strictly for the system prompt
        self.system_message = {"role": "system", "content": system_prompt}
        # This will hold the shifting user/assistant/tool history
        self.history = []

    def _estimate_tokens(self, text: str) -> int:
        """
        A fast, lightweight token estimator. 
        On average, 1 token = 4 characters of English text.
        """
        return len(text) // 4

    def _get_total_tokens(self) -> int:
        """Calculates total tokens currently in the system prompt + history."""
        total = self._estimate_tokens(self.system_message["content"])
        for msg in self.history:
            total += self._estimate_tokens(msg["content"])
        return total

    def append(self, role: str, content: str):
        """Adds a new message to the history and automatically enforces the sliding window."""
        self.history.append({"role": role, "content": content})
        self._enforce_window()

    def _enforce_window(self):
        """
        Slices away the oldest conversation turns if the total token count 
        exceeds our safety limit, always preserving the system prompt.
        """
        while self._get_total_tokens() > self.max_tokens and len(self.history) > 0:
            # Drop the oldest message in history (index 0 of the history list)
            removed = self.history.pop(0)
            print(f"\n[Context Manager: Slicing window. Dropped oldest message to save space.]")

    def get_messages(self) -> list:
        """Returns the properly formatted list of messages to pass straight to Ollama."""
        return [self.system_message] + self.history