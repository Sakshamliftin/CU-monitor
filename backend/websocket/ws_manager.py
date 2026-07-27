"""
websocket/ws_manager.py — WebSocket connection manager.

Maintains a set of active WebSocket connections and provides a
``broadcast()`` method to push JSON payloads to all connected
clients simultaneously.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages active WebSocket connections and broadcasts data to them.

    Thread-safety note: ``broadcast()`` is called from the scheduler
    thread, so it schedules the actual sends onto the asyncio event
    loop via ``asyncio.run_coroutine_threadsafe``.
    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store a reference to the running asyncio event loop."""
        self._loop = loop

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a new WebSocket client."""
        await ws.accept()
        self._connections.add(ws)
        logger.info("WebSocket client connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        """Unregister a WebSocket client."""
        self._connections.discard(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(self._connections))

    def broadcast(self, data: dict[str, Any]) -> None:
        """
        Send a JSON payload to every connected WebSocket client.

        This is safe to call from a non-async thread (e.g. the
        scheduler thread).  It schedules the async sends onto the
        event loop.
        """
        if not self._connections:
            return

        if self._loop is None or self._loop.is_closed():
            logger.warning("No event loop available for broadcast")
            return

        asyncio.run_coroutine_threadsafe(
            self._async_broadcast(data), self._loop,
        )

    async def _async_broadcast(self, data: dict[str, Any]) -> None:
        """Internal: send data to all clients, removing dead ones."""
        message = json.dumps(data)
        dead: list[WebSocket] = []

        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.discard(ws)
