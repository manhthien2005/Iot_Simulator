"""Standalone LogHub — WebSocket fan-out for session log streams."""

from __future__ import annotations

import asyncio
import logging
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)


class LogHub:
    def __init__(self) -> None:
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._lock = RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._dropped_count: int = 0

    def _get_loop(self) -> asyncio.AbstractEventLoop | None:
        """Return the cached event loop, lazily resolving on first call."""
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                try:
                    self._loop = asyncio.get_event_loop()
                except RuntimeError:
                    pass
        return self._loop

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Allow external code (e.g. FastAPI startup) to inject the event loop."""
        self._loop = loop

    def publish(self, session_id: str, entry: dict[str, Any]) -> None:
        with self._lock:
            history = self._history.setdefault(session_id, [])
            history.append(entry)
            if len(history) > 500:
                history[:] = history[-500:]
            loop = self._get_loop()
            for queue in self._subscribers.get(session_id, []):
                try:
                    if loop is not None and loop.is_running():
                        loop.call_soon_threadsafe(queue.put_nowait, entry)
                    else:
                        queue.put_nowait(entry)
                except asyncio.QueueFull:
                    self._dropped_count += 1
                    if self._dropped_count % 100 == 0:
                        logger.warning(
                            "LogHub: %d messages dropped (queue full) since startup",
                            self._dropped_count,
                        )
                    continue
                except RuntimeError:
                    continue

    def subscribe(self, session_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)
        with self._lock:
            self._subscribers.setdefault(session_id, []).append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            subscribers = self._subscribers.get(session_id, [])
            self._subscribers[session_id] = [item for item in subscribers if item is not queue]

    def history(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._history.get(session_id, []))
