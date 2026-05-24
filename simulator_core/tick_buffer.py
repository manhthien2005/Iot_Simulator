"""TickBuffer — bounded per-device buffer with TTL eviction.

Does NOT import api_server/. PendingDevicePublish imported for flush_ready return type.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

from api_server.models import PendingDevicePublish


class TickBuffer:
    """Thread-safe per-device buffer with max_per_device cap and TTL eviction.

    Each device gets its own deque. append() drops the oldest entry when
    max_per_device is reached. evict_stale() removes entries older than ttl.
    """

    def __init__(self, max_per_device: int = 500, ttl_seconds: float = 60.0) -> None:
        self._max = max_per_device
        self._ttl = ttl_seconds
        self._buffers: dict[str, list[tuple[float, dict[str, Any]]]] = {}
        self._lock = Lock()
        self._last_push_time: float = time.monotonic()

    def append(self, device_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            entries = self._buffers.setdefault(device_id, [])
            entries.append((time.monotonic(), payload))
            if len(entries) > self._max:
                entries.pop(0)

    def flush(self, device_id: str) -> list[dict[str, Any]]:
        with self._lock:
            entries = self._buffers.pop(device_id, [])
            return [p for _, p in entries]

    def flush_ready(
        self, *, push_interval: int, now: float
    ) -> list[PendingDevicePublish]:
        """Return PendingDevicePublish for devices ready to publish.

        A device is ready when its buffer has at least one payload with
        a db_device_id AND (now - last_push_time) >= push_interval.
        """
        if push_interval > 0 and (now - self._last_push_time) < push_interval:
            return []

        results: list[PendingDevicePublish] = []
        with self._lock:
            for device_id, entries in list(self._buffers.items()):
                if not entries:
                    continue
                payloads = [p for _, p in entries]
                # Only devices with at least one bound payload (has db_device_id)
                if not any(p.get("db_device_id") is not None for p in payloads):
                    continue
                results.append(PendingDevicePublish(
                    device_id=device_id,
                    messages=list(payloads),
                    clear_count=len(payloads),
                ))
        return results

    def evict_stale(self) -> int:
        """Remove entries older than ttl_seconds. Returns count evicted."""
        cutoff = time.monotonic() - self._ttl
        evicted = 0
        with self._lock:
            for device_id in list(self._buffers.keys()):
                before = len(self._buffers[device_id])
                self._buffers[device_id] = [
                    (ts, p) for ts, p in self._buffers[device_id] if ts >= cutoff
                ]
                after = len(self._buffers[device_id])
                evicted += before - after
                if not self._buffers[device_id]:
                    del self._buffers[device_id]
        return evicted

    def has_pending(self, device_id: str) -> bool:
        with self._lock:
            return bool(self._buffers.get(device_id))

    def pending_device_ids(self) -> set[str]:
        with self._lock:
            return {did for did, entries in self._buffers.items() if entries}
