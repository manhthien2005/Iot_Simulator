"""Runtime state container for SimulatorRuntime health observability.

Holds the cross-cutting state that powers the v2 ``/api/sim/health`` payload:

- ``startup_time`` — wall-clock instant the runtime came up; used for ``uptimeSeconds``.
- ``backend_probe`` / ``model_api_probe`` — TTL-cached results of upstream probes.

The data classes are deliberately tiny and stdlib-only so importing them at
``SimulatorRuntime.__init__`` is free.

Architecture reference: ``plans/iot-sim-ux-refactor-backlog-75c8a6.md`` §4.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from time import monotonic
from typing import Literal


BackendState = Literal["connected", "down", "slow", "unknown"]
ModelApiState = Literal["ready", "unavailable", "unknown"]


@dataclass
class ProbeResult:
    """Cached result of a single upstream probe.

    ``state`` is the canonical status the health payload exposes. ``checked_at``
    is the wall-clock ISO timestamp of the most recent probe (None until the
    first run). ``latency_ms`` records the last successful round-trip; it is
    None when the probe has never succeeded or last failed.

    The class is **mutable** — callers update fields directly under the
    runtime lock. We intentionally avoid pydantic / dataclass(frozen=True) to
    keep this on the hot path of ``health_payload()``.
    """

    state: str = "unknown"
    checked_at: str | None = None
    latency_ms: int | None = None
    last_error: str | None = None
    next_eligible_at: float = 0.0  # monotonic seconds


@dataclass
class HealthRuntimeState:
    """Aggregate health observability state stored on ``SimulatorRuntime``.

    All fields are protected by ``lock``; callers should acquire it before
    reading or writing. The class is created once at runtime startup and
    lives for the process lifetime.
    """

    startup_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    backend_probe: ProbeResult = field(default_factory=ProbeResult)
    model_api_probe: ProbeResult = field(default_factory=ProbeResult)
    last_score_source: Literal["ai", "heuristic"] = "heuristic"
    lock: RLock = field(default_factory=RLock)

    # ── Probe TTL helpers ────────────────────────────────────────────────

    @staticmethod
    def now_monotonic() -> float:
        """Monotonic clock reading used for TTL comparisons."""
        return monotonic()

    def uptime_seconds(self) -> int:
        """Whole seconds since the runtime came up."""
        delta = datetime.now(timezone.utc) - self.startup_time
        return max(int(delta.total_seconds()), 0)


__all__ = [
    "BackendState",
    "ModelApiState",
    "ProbeResult",
    "HealthRuntimeState",
]
