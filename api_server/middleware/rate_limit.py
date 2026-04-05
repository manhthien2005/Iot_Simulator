"""Simple in-memory sliding-window rate limiter (no external dependencies).

Configuration via environment variables
----------------------------------------
* ``SIM_RATE_LIMIT_READ``  — max requests/min for read methods (GET/HEAD/OPTIONS).
                             Default **60**.
* ``SIM_RATE_LIMIT_WRITE`` — max requests/min for write methods (POST/PUT/PATCH/DELETE).
                             Default **10**.
* ``SIM_RATE_LIMIT_ENABLED`` — set to ``0`` or ``false`` to disable entirely.
"""

from __future__ import annotations

import collections
import os
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(int(raw), 1)
    except ValueError:
        return default


def _is_enabled() -> bool:
    raw = os.environ.get("SIM_RATE_LIMIT_ENABLED", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


class _SlidingWindowCounter:
    """Per-key sliding-window request counter (1-minute window)."""

    __slots__ = ("_window_seconds", "_max_requests", "_buckets", "_call_count")

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self._window_seconds = window_seconds
        self._max_requests = max_requests
        # key -> deque of timestamps
        self._buckets: dict[str, collections.deque[float]] = collections.defaultdict(collections.deque)
        self._call_count: int = 0

    def _evict_stale(self) -> None:
        """Remove keys whose deques are empty to prevent unbounded memory growth."""
        stale_keys = [key for key, deque in self._buckets.items() if not deque]
        for key in stale_keys:
            del self._buckets[key]

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """Return (allowed, remaining) for *key*.

        Prunes expired entries, then checks whether a new request fits.
        Periodically evicts stale (empty) keys to prevent memory leak.
        """
        self._call_count += 1
        if self._call_count % 100 == 0:
            self._evict_stale()

        now = time.monotonic()
        cutoff = now - self._window_seconds
        bucket = self._buckets[key]

        # Evict timestamps outside the window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        remaining = max(self._max_requests - len(bucket), 0)
        if len(bucket) >= self._max_requests:
            return False, 0

        bucket.append(now)
        return True, remaining - 1


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that enforces per-IP rate limits."""

    def __init__(self, app: Callable, **kwargs) -> None:  # type: ignore[type-arg]
        super().__init__(app, **kwargs)
        self._read_limiter = _SlidingWindowCounter(
            max_requests=_env_int("SIM_RATE_LIMIT_READ", 300),
        )
        self._write_limiter = _SlidingWindowCounter(
            max_requests=_env_int("SIM_RATE_LIMIT_WRITE", 10),
        )
        self._enabled = _is_enabled()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:  # type: ignore[type-arg]
        if not self._enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        method = request.method.upper()

        limiter = self._write_limiter if method in _WRITE_METHODS else self._read_limiter

        allowed, remaining = limiter.is_allowed(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests — please slow down"},
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
