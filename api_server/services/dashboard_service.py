"""DashboardService — extracted from SimulatorRuntime.

Owns:
- ``health_payload()``  — v2 health probe aggregation
- ``dashboard_summary()`` — lightweight stats panel with TTL cache
- ``_probe_backend_cached()`` — TTL-cached backend HTTP probe
- ``_probe_model_api_cached()`` — TTL-cached model-api probe via SleepAIClient

Thread-safety: probes and summary use the same shared ``_lock`` (RLock) that
SimulatorRuntime passes in at construction time.
"""
from __future__ import annotations

import collections
import logging
import os
import time
from threading import RLock
from time import monotonic
from typing import TYPE_CHECKING, Any, Callable
from urllib.request import Request, urlopen

from api_server.runtime_state import HealthRuntimeState
from api_server.schemas import DashboardSummary
from api_server.utils import _utc_now_iso

if TYPE_CHECKING:
    from api_server.models import DeviceRecord, SessionRecord
    from api_server.backend_admin_client import BackendAdminClient
    from pre_model_trigger import TriggerOrchestrator
    from simulator_core.sleep_ai_client import SleepAIClient

logger = logging.getLogger(__name__)

_PRE_MODEL_TRIGGER_ENABLED: bool = os.environ.get(
    "PRE_MODEL_TRIGGER_ENABLED", ""
).lower() in ("1", "true", "yes")


class DashboardService:
    """Aggregates health probe state and computes dashboard summary stats.

    All heavy state is injected via constructor — DashboardService holds only
    references, never ownership, so SimulatorRuntime remains the single source
    of truth for all shared dicts/deques.
    """

    _HEALTH_PROBE_TTL_SECONDS = 5.0
    _HEALTH_BACKEND_SLOW_LATENCY_MS = 1500
    _SIMULATOR_VERSION = "simulator-api-0.4.0"

    def __init__(
        self,
        *,
        devices: dict[str, "DeviceRecord"],
        sessions: dict[str, "SessionRecord"],
        event_history: collections.deque,
        alert_count_1h_ref: list[int],
        alert_timestamps_1h: collections.deque,
        health_state: HealthRuntimeState,
        admin_client: "BackendAdminClient",
        trigger_orchestrator: "TriggerOrchestrator | None",
        dashboard_cache_ref: list,
        dashboard_cache_ts_ref: list[float],
        lock: RLock,
        health_backend_url: str,
        sleep_ai_client: "SleepAIClient",
        compute_pre_trigger_block_fn: Callable[[], dict[str, Any]],
        compute_telemetry_block_fn: Callable[[], dict[str, int]],
        measure_database_health_fn: Callable[[], tuple[bool, int | None]],
    ) -> None:
        self._devices = devices
        self._sessions = sessions
        self._event_history = event_history
        self._alert_count_1h_ref = alert_count_1h_ref          # mutable single-element list
        self._alert_timestamps_1h = alert_timestamps_1h
        self._health_state = health_state
        self._admin_client = admin_client
        self._trigger_orchestrator = trigger_orchestrator
        self._dashboard_cache_ref = dashboard_cache_ref          # mutable single-element list
        self._dashboard_cache_ts_ref = dashboard_cache_ts_ref    # mutable single-element list[float]
        self._lock = lock
        self._health_backend_url = health_backend_url
        self._sleep_ai_client = sleep_ai_client
        self._compute_pre_trigger_block = compute_pre_trigger_block_fn
        self._compute_telemetry_block = compute_telemetry_block_fn
        self._measure_database_health = measure_database_health_fn

    # ── TTL-cached upstream probes ────────────────────────────────────────

    def probe_backend_cached(self) -> None:
        """Refresh ``_health_state.backend_probe`` if its TTL has expired."""
        probe = self._health_state.backend_probe
        now_mono = self._health_state.now_monotonic()
        if now_mono < probe.next_eligible_at:
            return
        endpoint = f"{self._health_backend_url.rstrip('/')}/api/v1/mobile/health"
        start = monotonic()
        latency_ms: int | None = None
        try:
            with urlopen(Request(endpoint, method="GET"), timeout=3.0) as response:
                latency_ms = int((monotonic() - start) * 1000)
                ok = int(response.getcode() or 0) == 200
            with self._health_state.lock:
                if not ok:
                    probe.state = "down"
                    probe.last_error = f"HTTP {response.getcode()}"
                elif latency_ms is not None and latency_ms > self._HEALTH_BACKEND_SLOW_LATENCY_MS:
                    probe.state = "slow"
                    probe.last_error = None
                else:
                    probe.state = "connected"
                    probe.last_error = None
                probe.latency_ms = latency_ms
                probe.checked_at = _utc_now_iso()
                probe.next_eligible_at = now_mono + self._HEALTH_PROBE_TTL_SECONDS
        except Exception as exc:
            with self._health_state.lock:
                probe.state = "down"
                probe.latency_ms = None
                probe.last_error = f"{type(exc).__name__}: {exc}"
                probe.checked_at = _utc_now_iso()
                probe.next_eligible_at = now_mono + self._HEALTH_PROBE_TTL_SECONDS

    def probe_model_api_cached(self) -> None:
        """Refresh ``_health_state.model_api_probe`` via ``SleepAIClient``."""
        probe = self._health_state.model_api_probe
        now_mono = self._health_state.now_monotonic()
        if now_mono < probe.next_eligible_at:
            return
        try:
            available = self._sleep_ai_client.check_availability()
        except Exception as exc:
            with self._health_state.lock:
                probe.state = "unavailable"
                probe.last_error = f"{type(exc).__name__}: {exc}"
                probe.checked_at = _utc_now_iso()
                probe.next_eligible_at = now_mono + self._HEALTH_PROBE_TTL_SECONDS
            return
        with self._health_state.lock:
            probe.state = "ready" if available else "unavailable"
            probe.last_error = None if available else "check_availability returned False"
            probe.checked_at = _utc_now_iso()
            probe.next_eligible_at = now_mono + self._HEALTH_PROBE_TTL_SECONDS

    # ── Dashboard summary (with TTL cache) ────────────────────────────────

    def dashboard_summary(self) -> DashboardSummary:
        _DASHBOARD_CACHE_TTL = 5.0  # seconds
        with self._lock:
            now_mono = monotonic()
            cached = self._dashboard_cache_ref[0]
            if cached is not None and (now_mono - self._dashboard_cache_ts_ref[0]) < _DASHBOARD_CACHE_TTL:
                return cached

            total = len(self._devices)
            active = len([device for device in self._devices.values() if device.state == "streaming"])

            # HIGH #1 fix: prune stale entries then read counter directly.
            now_ts = time.time()
            cutoff = now_ts - 3600
            while self._alert_timestamps_1h and self._alert_timestamps_1h[0] < cutoff:
                self._alert_timestamps_1h.popleft()
            self._alert_count_1h_ref[0] = len(self._alert_timestamps_1h)
            alerts = self._alert_count_1h_ref[0]

            latencies = [
                session.last_publish_latency_ms
                for session in self._sessions.values()
                if session.last_publish_count > 0 and session.last_publish_latency_ms is not None
            ]
            avg_latency = int(round(sum(latencies) / len(latencies))) if latencies else 0
            result = DashboardSummary(
                totalDevices=total,
                activeDevices=active,
                alertsLastHour=alerts,
                avgLatencyMs=avg_latency,
            )
            self._dashboard_cache_ref[0] = result
            self._dashboard_cache_ts_ref[0] = now_mono
            return result

    # ── Full v2 health payload ────────────────────────────────────────────

    def health_payload(self) -> dict[str, Any]:
        """Return the v2 health payload merged with legacy flat keys.

        v2 callers (Module A dashboard hero) read the nested blocks; legacy
        callers (current ``HealthStatusPanel``) keep using the flat keys for
        one release cycle before they are removed.
        """
        # Refresh probes (TTL-gated, so cheap when called often).
        self.probe_backend_cached()
        self.probe_model_api_cached()
        db_ok, db_latency_ms = self._measure_database_health()

        with self._lock:
            session_count = len(self._sessions)
            running_sessions = sum(
                1 for session in self._sessions.values() if session.status == "running"
            )
        with self._health_state.lock:
            backend_state = self._health_state.backend_probe.state
            backend_latency = self._health_state.backend_probe.latency_ms
            backend_error = self._health_state.backend_probe.last_error
            model_state = self._health_state.model_api_probe.state
            model_checked_at = self._health_state.model_api_probe.checked_at
            model_error = self._health_state.model_api_probe.last_error
            last_score_source = self._health_state.last_score_source
            uptime_seconds = self._health_state.uptime_seconds()

        # Runtime state derivation
        if not db_ok:
            runtime_state: str = "degraded"
        elif backend_state == "down" or model_state == "unavailable":
            runtime_state = "degraded"
        elif running_sessions == 0:
            runtime_state = "idle"
        else:
            runtime_state = "running"

        # MQTT status — legacy view: idle when no sessions, otherwise connected
        mqtt_status = "idle" if session_count == 0 else "connected"

        pre_trigger_block = self._compute_pre_trigger_block()
        telemetry_block = self._compute_telemetry_block()

        degraded_reasons: list[str] = []
        if not db_ok:
            degraded_reasons.append("database_down")
        if backend_state == "down":
            degraded_reasons.append("backend_unreachable")
        elif backend_state == "slow":
            degraded_reasons.append("backend_slow")
        if model_state == "unavailable":
            degraded_reasons.append("model_api_unavailable")
        if (
            pre_trigger_block["mode"] == "off"
            and _PRE_MODEL_TRIGGER_ENABLED
            and self._trigger_orchestrator is None
        ):
            degraded_reasons.append("pre_trigger_misconfigured")

        v2_payload: dict[str, Any] = {
            "schemaVersion": "2.0",
            "runtime": {
                "state": runtime_state,
                "version": self._SIMULATOR_VERSION,
                "uptimeSeconds": uptime_seconds,
            },
            "database": {
                "state": "connected" if db_ok else "down",
                "lastCheckMs": db_latency_ms,
            },
            "backend": {
                "state": backend_state,
                "url": self._health_backend_url,
                "lastLatencyMs": backend_latency,
                "lastError": backend_error,
            },
            "modelApi": {
                "state": model_state,
                "url": getattr(self._sleep_ai_client, "base_url", "http://localhost:8001"),
                "lastCheckedAt": model_checked_at,
                "lastScoreSource": last_score_source,
                "lastError": model_error,
            },
            "preTrigger": pre_trigger_block,
            "telemetry": telemetry_block,
            "degradedReasons": degraded_reasons,
        }

        # Legacy keys (kept for one release cycle while consumers migrate).
        legacy_keys: dict[str, Any] = {
            "status": runtime_state if runtime_state != "idle" else "running",
            "api": "running",
            "backendStatus": "connected" if backend_state == "connected" else "down",
            "mqtt": mqtt_status,
            "db": "healthy" if db_ok else "down",
            "version": self._SIMULATOR_VERSION,
        }

        return {**v2_payload, **legacy_keys}
