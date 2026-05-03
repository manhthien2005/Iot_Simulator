"""AlertService — extracted from SimulatorRuntime (Task 3.5).

Owns alert push logic, event recording, and the ``event_history`` deque.

Thread-safety: methods that touch shared state acquire ``self._lock``
(the *same* ``threading.RLock`` instance shared with ``SimulatorRuntime``).
"""

from __future__ import annotations

import collections
import json as _json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from time import monotonic
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from api_server.dependencies import DeviceRecord, PreparedAlertPush, EventRecord

# Dual import path: supports both package-level execution
#   (`python -m Iot_Simulator.api_server.main`)
# and direct execution from the project root
#   (`uvicorn api_server.main:app`).
try:
    from Iot_Simulator.api_server.schemas import AlertEvent
    from Iot_Simulator.api_server.utils import _utc_now_iso
except ModuleNotFoundError:
    from api_server.schemas import AlertEvent
    from api_server.utils import _utc_now_iso


logger = logging.getLogger(__name__)

_ALERT_PUSH_MAX_RETRIES = 3
_ALERT_PUSH_BACKOFF_BASE = 1  # seconds; actual delays: 1, 2, 4


class AlertService:
    """Manages alert pushing, event recording, and event history."""

    def __init__(
        self,
        *,
        devices: dict[str, "DeviceRecord"],
        event_history: collections.deque["EventRecord"],
        lock: RLock,
        last_alert_pushes: dict[tuple[str, str, str], float],
        alert_pushes_in_flight: set[tuple[str, str, str]],
        push_interval: int,
        health_backend_url: str,
        http_sender: Any,  # callable(endpoint, payload_json, headers=None) -> int
        telemetry_alert_endpoint_fn: Any,  # callable(base_url) -> str
        publish_device_log_fn: Any,  # callable(sim_device_id, *, level, message, timestamp) -> None
        dashboard_cache_ref: list,  # mutable container: [DashboardSummary | None]
        internal_secret: str | None = None,
    ) -> None:
        # Shared mutable state — same object references as SimulatorRuntime
        self.devices = devices
        self.event_history = event_history
        self._lock = lock
        self._last_alert_pushes = last_alert_pushes
        self._alert_pushes_in_flight = alert_pushes_in_flight
        self._push_interval = push_interval
        self._health_backend_url = health_backend_url
        self._http_sender = http_sender
        self._telemetry_alert_endpoint = telemetry_alert_endpoint_fn
        self._publish_device_log = publish_device_log_fn
        self._dashboard_cache_ref = dashboard_cache_ref
        self._internal_secret = internal_secret

        # Dedicated thread pool for alert push retries so that
        # time.sleep() backoff does NOT block the background tick thread.
        # (CRITICAL #1 fix)
        self._alert_executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="alert-push"
        )

    # ------------------------------------------------------------------
    # Alert push
    # ------------------------------------------------------------------

    def _prepare_alert_push_locked(
        self,
        sim_device_id: str,
        event_type: str,
        severity: str,
        metadata: dict[str, Any] | None = None,
    ) -> "PreparedAlertPush | None":
        try:
            from Iot_Simulator.api_server.dependencies import PreparedAlertPush
        except ModuleNotFoundError:
            from api_server.dependencies import PreparedAlertPush

        device = self.devices.get(sim_device_id)
        if device is None or device.bound_db_device_id is None:
            return None

        normalized_event_type = str(event_type or "").strip().lower() or "generic_alert"
        normalized_severity = str(severity or "").strip().lower() or "warning"
        signature = (sim_device_id, normalized_event_type, normalized_severity)
        if signature in self._alert_pushes_in_flight:
            return None

        now = monotonic()
        cooldown_seconds = max(float(self._push_interval), 10.0)
        last_sent_at = self._last_alert_pushes.get(signature)
        if last_sent_at is not None and now - last_sent_at < cooldown_seconds:
            return None

        alert_metadata = dict(metadata or {})
        timestamp = str(
            alert_metadata.pop("timestamp", None)
            or alert_metadata.pop("emitted_at", None)
            or _utc_now_iso()
        )
        explicit_user_id = alert_metadata.pop("user_id", None)
        payload = {
            "db_device_id": device.bound_db_device_id,
            "user_id": explicit_user_id,
            "event_type": normalized_event_type,
            "severity": normalized_severity,
            "timestamp": timestamp,
            "metadata": alert_metadata,
        }
        self._alert_pushes_in_flight.add(signature)
        return PreparedAlertPush(
            sim_device_id=sim_device_id,
            signature=signature,
            event_type=normalized_event_type,
            severity=normalized_severity,
            timestamp=timestamp,
            payload_json=_json.dumps(payload),
        )

    def _push_alert_to_backend(
        self,
        sim_device_id: str,
        event_type: str,
        severity: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            prepared = self._prepare_alert_push_locked(
                sim_device_id,
                event_type=event_type,
                severity=severity,
                metadata=metadata,
            )
        if prepared is None:
            return
        endpoint = self._telemetry_alert_endpoint(self._health_backend_url)

        last_exc: Exception | None = None
        status_code: int | None = None

        _iot_headers: dict[str, str] = {"X-Internal-Service": "iot-simulator"}
        if self._internal_secret:
            _iot_headers["X-Internal-Secret"] = self._internal_secret
        for attempt in range(1, _ALERT_PUSH_MAX_RETRIES + 1):
            try:
                status_code = self._http_sender(endpoint, prepared.payload_json, _iot_headers)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt < _ALERT_PUSH_MAX_RETRIES:
                    delay = _ALERT_PUSH_BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "Alert push attempt %d/%d failed for %s/%s, retrying in %ds: %s",
                        attempt,
                        _ALERT_PUSH_MAX_RETRIES,
                        prepared.event_type,
                        prepared.severity,
                        delay,
                        exc,
                    )
                    time.sleep(delay)

        if last_exc is not None:
            logger.error(
                "Alert push failed after %d attempts for %s/%s: %s",
                _ALERT_PUSH_MAX_RETRIES,
                prepared.event_type,
                prepared.severity,
                last_exc,
                exc_info=True,
            )
            with self._lock:
                self._alert_pushes_in_flight.discard(prepared.signature)
            self._publish_device_log(
                prepared.sim_device_id,
                level="ERROR",
                message=f"alert push failed after {_ALERT_PUSH_MAX_RETRIES} retries: {prepared.event_type}/{prepared.severity} ({last_exc})",
                timestamp=prepared.timestamp,
            )
            return

        with self._lock:
            self._alert_pushes_in_flight.discard(prepared.signature)
            if 200 <= status_code < 300:
                self._last_alert_pushes[prepared.signature] = monotonic()
                publish_ok = True
            else:
                publish_ok = False

        if publish_ok:
            self._publish_device_log(
                prepared.sim_device_id,
                level="INFO",
                message=f"alert push OK: {prepared.event_type}/{prepared.severity} -> HTTP {status_code}",
                timestamp=prepared.timestamp,
            )
            return

        self._publish_device_log(
            prepared.sim_device_id,
            level="ERROR",
            message=f"alert push failed: {prepared.event_type}/{prepared.severity} -> HTTP {status_code}",
            timestamp=prepared.timestamp,
        )

    # ------------------------------------------------------------------
    # Event recording
    # ------------------------------------------------------------------

    def _record_event(
        self,
        *,
        device_id: str,
        event_type: str,
        severity: str,
        message: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        try:
            from Iot_Simulator.api_server.dependencies import EventRecord
        except ModuleNotFoundError:
            from api_server.dependencies import EventRecord

        event = EventRecord(
            id=uuid4().hex,
            timestamp=_utc_now_iso(),
            device_id=device_id,
            event_type=event_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
        )
        # HIGH #2 fix: acquire lock before mutating shared event_history
        # and invalidating dashboard cache.
        with self._lock:
            self.event_history.append(event)
            # Invalidate dashboard cache
            if self._dashboard_cache_ref:
                self._dashboard_cache_ref[0] = None

    # ------------------------------------------------------------------
    # Event queries
    # ------------------------------------------------------------------

    def recent_events(self, limit: int = 10) -> list[AlertEvent]:
        with self._lock:
            selected = list(self.event_history)[-max(1, limit):]
            return [event.to_schema() for event in reversed(selected)]
