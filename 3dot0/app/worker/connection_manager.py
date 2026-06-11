"""
WebSocket connection manager.
Maintains the set of active connections and provides a thread-safe broadcast
mechanism so the background worker can push events from a non-async thread.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages all active WebSocket connections.

    The background worker runs in a regular Python thread and cannot directly
    await coroutines.  It calls `broadcast_from_thread()` which uses
    `asyncio.run_coroutine_threadsafe()` to safely schedule the broadcast on
    the event loop that is running the FastAPI application.
    """

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store a reference to the running event loop (called on app startup)."""
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        logger.debug("WebSocket connected. Active: %d", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        logger.debug("WebSocket disconnected. Active: %d", len(self._connections))

    async def broadcast(self, event: str, data: Dict[str, Any]) -> None:
        """Send a JSON event to all connected WebSocket clients."""
        if not self._connections:
            return

        message = json.dumps({"event": event, "data": data})
        dead: Set[WebSocket] = set()

        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)

        for ws in dead:
            self._connections.discard(ws)

    def broadcast_from_thread(self, event: str, data: Dict[str, Any]) -> None:
        """
        Thread-safe broadcast. Call this from the background worker thread.
        No-ops if no event loop is registered or there are no connections.
        """
        if self._loop is None or not self._connections:
            return

        asyncio.run_coroutine_threadsafe(
            self.broadcast(event, data),
            self._loop,
        )


# Singleton — imported by both the FastAPI app and the worker
manager = ConnectionManager()
