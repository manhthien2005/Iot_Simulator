"""Fixed-size ring buffer for recent vitals history.

The ``VitalsHistoryBuffer`` stores the last *N* vitals snapshots per
device so that the rule engine can evaluate time-series rules (drift,
rapid-change, recurrence) without reading from the database.

Architecture reference: plans/alert-threshold-architecture-plan.md §5.1
"""
from __future__ import annotations

from collections import deque
from typing import Any


class VitalsHistoryBuffer:
    """Per-device ring buffer that retains the most recent vitals ticks.

    Parameters
    ----------
    max_size:
        Maximum number of vitals snapshots kept *per device*.  Older
        entries are evicted automatically.  Default ``60`` corresponds
        to ~5 minutes at one tick per 5 seconds.

    Usage in ``dependencies.py``::

        vitals_buffer = VitalsHistoryBuffer(max_size=60)
    """

    def __init__(self, max_size: int = 60) -> None:
        if max_size < 1:
            raise ValueError(f"max_size must be >= 1, got {max_size}")
        self._max_size = max_size
        self._buffers: dict[str, deque[dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push(self, device_id: str, vitals: dict[str, Any]) -> None:
        """Append a vitals snapshot for *device_id*.

        If the buffer for this device is full, the oldest entry is
        automatically evicted.
        """
        buf = self._buffers.get(device_id)
        if buf is None:
            buf = deque(maxlen=self._max_size)
            self._buffers[device_id] = buf
        buf.append(vitals)

    def get_history(self, device_id: str) -> list[dict[str, Any]]:
        """Return the buffered vitals for *device_id* (oldest first).

        Returns an empty list when no data has been recorded yet.
        """
        buf = self._buffers.get(device_id)
        if buf is None:
            return []
        return list(buf)

    def latest(self, device_id: str) -> dict[str, Any] | None:
        """Return the most recent vitals snapshot, or ``None``."""
        buf = self._buffers.get(device_id)
        if not buf:
            return None
        return buf[-1]

    def size(self, device_id: str) -> int:
        """Return the number of buffered entries for *device_id*."""
        buf = self._buffers.get(device_id)
        return len(buf) if buf else 0

    def clear(self, device_id: str | None = None) -> None:
        """Clear buffered data.

        Parameters
        ----------
        device_id:
            When provided, clear only that device's buffer.  When
            ``None``, clear **all** device buffers.
        """
        if device_id is not None:
            self._buffers.pop(device_id, None)
        else:
            self._buffers.clear()

    @property
    def max_size(self) -> int:
        """Maximum entries per device."""
        return self._max_size


__all__ = ["VitalsHistoryBuffer"]
