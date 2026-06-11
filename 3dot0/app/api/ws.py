"""
API router: WebSocket endpoint.
Clients connect here to receive real-time event pushes from the background worker.

Event schema (JSON):
    { "event": "<event_type>", "data": { ... } }

Event types:
    task_queued     – A new task was added to the queue
    task_started    – Worker picked up a task
    task_done       – Task completed, feed item available
    task_failed     – Task failed
    feed_new        – A new feed item was created
    tool_call       – Worker is currently calling a tool
"""
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.worker.connection_manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        # Keep the connection alive; we only push, not pull via WebSocket
        while True:
            # Receive and discard any client pings / keep-alives
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("WebSocket error: %s", exc)
    finally:
        manager.disconnect(websocket)
