import asyncio
import os
import queue
import re
import threading
import uuid
from typing import Optional

import edge_tts
import pygame


class TTSEngine:
    """
    Edge-TTS voice engine backed by a dedicated worker thread.

    Features
    ────────
    • Sentence-level streaming: feed raw LLM chunks via feed_chunk(); the
      engine splits on sentence boundaries and queues each sentence for
      playback without waiting for the full response.
    • Interruptible: stop_all() clears the queue and halts pygame mid-word,
      enabling Ctrl+C to cut the voice off instantly.
    • Toggle: set enabled = False at runtime to mute without restarting.
    """

    # Sentence-boundary pattern: period / ! / ? followed by whitespace or end
    _SENTENCE_END = re.compile(r'(?<=[.!?])\s+')

    def __init__(self, voice: str = "en-GB-RyanNeural", enabled: bool = True) -> None:
        self.voice = voice
        self.enabled = enabled

        self._queue: queue.Queue = queue.Queue()
        self._stop_flag = threading.Event()
        self._sentence_buffer: str = ""

        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def speak(self, text: str) -> None:
        """Queue a complete sentence/phrase for immediate playback."""
        if self.enabled and text.strip():
            self._queue.put(text.strip())

    def feed_chunk(self, chunk: str) -> None:
        """
        Append a raw streaming chunk. Sentences are detected automatically
        and dispatched to the playback queue as they complete.
        """
        if not self.enabled:
            return

        self._sentence_buffer += chunk

        parts = self._SENTENCE_END.split(self._sentence_buffer)
        if len(parts) > 1:
            for sentence in parts[:-1]:
                sentence = sentence.strip()
                if sentence:
                    self._queue.put(sentence)
            self._sentence_buffer = parts[-1]

    def flush_buffer(self) -> None:
        """Send any remaining text in the sentence buffer to the queue."""
        remainder = self._sentence_buffer.strip()
        if remainder:
            self._queue.put(remainder)
        self._sentence_buffer = ""

    def stop_all(self) -> None:
        """
        Immediately halt the current playback and discard everything queued.
        Resets cleanly so the engine is ready for the next response.
        """
        self._stop_flag.set()
        self._sentence_buffer = ""

        # Drain the queue without blocking
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

        # Cut pygame playback
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
        except Exception:
            pass

        self._stop_flag.clear()

    def shutdown(self) -> None:
        """Gracefully stop the worker thread (call on exit)."""
        self.stop_all()
        self._queue.put(None)  # sentinel
        self._worker.join(timeout=3)

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        while True:
            text: Optional[str] = self._queue.get()

            if text is None:        # shutdown sentinel
                break

            if self._stop_flag.is_set() or not text.strip():
                self._queue.task_done()
                continue

            try:
                self._synthesize_and_play(text)
            except Exception:
                pass  # Never crash the worker

            self._queue.task_done()

    def _synthesize_and_play(self, text: str) -> None:
        audio_file = f"tts_{uuid.uuid4().hex}.mp3"

        async def _generate() -> None:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(audio_file)

        asyncio.run(_generate())

        if self._stop_flag.is_set():
            _safe_remove(audio_file)
            return

        try:
            pygame.mixer.init()
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()

            clock = pygame.time.Clock()
            while pygame.mixer.music.get_busy():
                if self._stop_flag.is_set():
                    pygame.mixer.music.stop()
                    break
                clock.tick(10)

            pygame.mixer.music.unload()
        finally:
            _safe_remove(audio_file)


def _safe_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
