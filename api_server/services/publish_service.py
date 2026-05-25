"""PublishService — extracted from SimulatorRuntime.

Owns all transport/publish logic:
- ``publish_vitals_http()``               — HTTP batch push to mobile BE
- ``execute_pending_tick_publish()``       — fan-out over per-device publish units
- ``execute_single_device_publish()``      — isolate state update per device
- ``refresh_session_publish_aggregate_locked()`` — recompute flat publish fields (static)
- ``push_alert_to_backend()``             — thin wrapper that offloads to alert_service executor
- ``update_device_heartbeat()``           — DB heartbeat update
- ``publish_tick_buffer_locked()``        — build per-device publish units from buffer
- ``run_session_side_effects()``          — dispatch effects (publish + heartbeats + alerts)

Thread-safety: methods that read/write ``sessions``, ``device_buffers``, or
``device_in_flight`` acquire ``self._lock`` (the same RLock shared with
SimulatorRuntime).
"""
from __future__ import annotations

import json as _json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import RLock
from time import monotonic
from typing import TYPE_CHECKING, Any, Callable

# Max worker threads for parallel per-device HTTP publish.
# Each device gets its own thread so N-device fleets publish in ~1× latency.
_PUBLISH_WORKER_THREADS = int(os.environ.get("SIM_PUBLISH_WORKERS", "8"))

import httpx

from api_server.db import session_scope
from api_server.models import (
    DevicePublishStatus,
    PendingDevicePublish,
    SessionSideEffects,
)
from api_server.sim_admin_service import SimAdminService
from api_server.utils import _utc_now_iso

if TYPE_CHECKING:
    from api_server.models import DeviceRecord, SessionRecord
    from api_server.log_hub import LogHub

logger = logging.getLogger(__name__)


class PublishService:
    """Handles batched vitals publish to the health backend and session side-effects."""

    def __init__(
        self,
        *,
        sessions: dict[str, "SessionRecord"],
        devices: dict[str, "DeviceRecord"],
        device_buffers: dict[str, list[dict[str, Any]]],
        device_in_flight: set[str],
        lock: RLock,
        health_backend_url: str,
        push_interval: int,
        last_push_time_ref: list[float],   # mutable single-element list
        http_sender_fn: Callable,          # (endpoint, payload_json, headers) -> int
        publish_flow_event_fn: Callable,   # (session_id, event_dict) -> None
        push_alert_fn: Callable,           # (sim_device_id, event_type, severity, metadata) -> None
        heartbeat_fn: Callable | None = None,  # (db_device_id, battery_level) -> None
        logs: "LogHub" = None,  # type: ignore[assignment]
    ) -> None:
        self._sessions = sessions
        self._devices = devices
        self._device_buffers = device_buffers
        self._device_in_flight = device_in_flight
        self._lock = lock
        self._health_backend_url = health_backend_url
        self._push_interval = push_interval
        self._last_push_time_ref = last_push_time_ref
        self._http_sender = http_sender_fn
        self._publish_flow_event = publish_flow_event_fn
        self._push_alert = push_alert_fn
        self._heartbeat_fn = heartbeat_fn  # injectable; falls back to self.update_device_heartbeat
        self.logs = logs

    # ── Heartbeat ────────────────────────────────────────────────────────

    def update_device_heartbeat(self, db_device_id: int, battery_level: int) -> None:
        try:
            with session_scope() as db:
                SimAdminService.update_heartbeat(
                    db_device_id,
                    db,
                    battery_level=battery_level,
                    signal_strength=None,
                )
        except Exception:
            logger.warning(
                "Failed to update device heartbeat for db_device_id=%s",
                db_device_id,
                exc_info=True,
            )

    # ── HTTP vitals push ─────────────────────────────────────────────────

    @staticmethod
    def _telemetry_ingest_endpoint(base_url: str) -> str:
        return f"{base_url.rstrip('/')}/api/v1/mobile/telemetry/ingest"

    def publish_vitals_http(
        self, pending_publish: PendingDevicePublish
    ) -> tuple[int, set[int], str | None]:
        """ADR-020 S6 — push vitals batch over HTTP to the mobile BE.

        Returns ``(ack_count, synced_device_ids, error_detail)``.
        """
        canonical_vital_keys = (
            "heart_rate",
            "spo2",
            "temperature",
            "hrv",
            "respiratory_rate",
            "blood_pressure_sys",
            "blood_pressure_dia",
            "signal_quality",
            "motion_artifact",
        )

        messages: list[dict[str, Any]] = []
        for msg in pending_publish.messages:
            db_device_id = msg.get("db_device_id")
            if db_device_id is None:
                continue
            emitted_at = msg.get("emitted_at") or _utc_now_iso()
            vitals_raw = msg.get("vitals") or {}
            vitals_payload: dict[str, Any] = {}
            for key in canonical_vital_keys:
                value = vitals_raw.get(key)
                if value is None:
                    continue
                vitals_payload[key] = value
            messages.append(
                {
                    "db_device_id": int(db_device_id),
                    "emitted_at": emitted_at,
                    "vitals": vitals_payload,
                }
            )

        if not messages:
            return 0, set(), "no_valid_messages"

        payload_json = _json.dumps({"messages": messages})
        endpoint = self._telemetry_ingest_endpoint(self._health_backend_url)
        request_headers = {
            "Content-Type": "application/json",
            "X-Internal-Service": "iot-simulator",
        }
        secret = os.environ.get("INTERNAL_SERVICE_SECRET")
        if secret:
            request_headers["X-Internal-Secret"] = secret

        try:
            response = httpx.post(
                endpoint,
                content=payload_json.encode("utf-8"),
                headers=request_headers,
                timeout=10,
            )
        except Exception as exc:
            logger.warning("HTTP vitals publish failed", exc_info=True)
            return 0, set(), f"http_error:{type(exc).__name__}"

        status_code = int(response.status_code)
        if not (200 <= status_code < 300):
            return 0, set(), f"http_status_{status_code}"

        try:
            body = response.json()
        except Exception:
            logger.warning("HTTP vitals publish returned invalid JSON body")
            return 0, set(), "invalid_response_body"

        try:
            ingested = int(body.get("ingested") or 0)
        except (TypeError, ValueError):
            ingested = 0

        synced_device_ids: set[int] = set()
        for raw_device in body.get("risk_evaluated_devices") or []:
            try:
                synced_device_ids.add(int(raw_device))
            except (TypeError, ValueError):
                continue

        return ingested, synced_device_ids, None

    # ── Per-device publish execution ──────────────────────────────────────

    def execute_pending_tick_publish(
        self, pending_publishes: list[PendingDevicePublish] | None
    ) -> None:
        """Publish all pending devices in parallel using a thread pool.

        N devices publish in ~1× HTTP latency instead of N× latency.
        Each device failure is isolated — one device error doesn't block others.
        """
        if not pending_publishes:
            return
        if len(pending_publishes) == 1:
            self.execute_single_device_publish(pending_publishes[0])
            return
        with ThreadPoolExecutor(
            max_workers=min(len(pending_publishes), _PUBLISH_WORKER_THREADS),
            thread_name_prefix="sim-publish",
        ) as pool:
            futures = {
                pool.submit(self.execute_single_device_publish, p): p.device_id
                for p in pending_publishes
            }
            for future in as_completed(futures):
                device_id = futures[future]
                try:
                    future.result()
                except Exception:
                    logger.warning(
                        "Parallel publish failed for device %s",
                        device_id,
                        exc_info=True,
                    )

    def execute_single_device_publish(
        self,
        pending_publish: PendingDevicePublish,
    ) -> None:
        """Publish 1 device's buffer via HTTP; isolate state update per device."""
        device_id = pending_publish.device_id
        publish_started = monotonic()
        message_count = len(pending_publish.messages)

        ack_count, synced_device_ids, publish_error_detail = self.publish_vitals_http(
            pending_publish
        )

        publish_latency_ms = max(0, int(round((monotonic() - publish_started) * 1000)))
        publish_ok = ack_count == message_count if message_count > 0 else False
        attempt_at = _utc_now_iso()
        publish_error: str | None = None
        if message_count == 0:
            publish_error = "Không có message nào để publish"
        elif not publish_ok:
            base_msg = (
                f"Backend ack {ack_count}/{message_count} message — "
                f"kiểm tra MQTT/HTTP downstream"
            )
            publish_error = (
                f"{base_msg} ({publish_error_detail})"
                if publish_error_detail
                else base_msg
            )

        with self._lock:
            self._device_in_flight.discard(device_id)
            for session in self._sessions.values():
                if session.status != "running":
                    continue
                if device_id not in session.device_ids:
                    continue
                status = session.device_publish_status.get(device_id)
                if status is None:
                    status = DevicePublishStatus()
                    session.device_publish_status[device_id] = status
                status.ok = publish_ok
                status.ack_count = ack_count
                status.message_count = message_count
                status.latency_ms = publish_latency_ms
                status.attempt_at = attempt_at
                status.attempt_count += 1
                status.ack_count_total += ack_count
                if publish_ok:
                    status.last_ok_at = attempt_at
                    status.error = None
                else:
                    status.error = publish_error
                # Aggregate flat fields for backward-compat dashboards.
                self.refresh_session_publish_aggregate_locked(session)
            if publish_ok:
                buffer = self._device_buffers.get(device_id)
                if buffer is not None:
                    del buffer[: pending_publish.clear_count]
                self._last_push_time_ref[0] = monotonic()
                self._refresh_pending_sync_flags_noop()

        # ADR-024 S14: emit vitals_ingest flow event for every running session
        # that owns this device (per-device granularity).
        running_session_ids = [
            sid
            for sid, s in self._sessions.items()
            if s.status == "running" and device_id in s.device_ids
        ]
        for sid in running_session_ids:
            self._publish_flow_event(
                sid,
                {
                    "step": "vitals_ingest",
                    "status": "done" if publish_ok else "error",
                    "device_id": device_id,
                    "payload": {
                        "ack_count": ack_count,
                        "message_count": message_count,
                        "latency_ms": publish_latency_ms,
                    },
                },
            )

    def _refresh_pending_sync_flags_noop(self) -> None:
        """Placeholder — callers that need flag refresh inject a callback instead.

        ``SimulatorRuntime._execute_single_device_publish`` used to call
        ``self._refresh_pending_sync_flags()`` directly.  After extraction the
        runtime wires the real method back via ``set_refresh_fn``.
        """

    def set_refresh_fn(self, fn: Callable[[], None]) -> None:
        """Inject the real ``_refresh_pending_sync_flags`` callback post-init."""
        self._refresh_pending_sync_flags_noop = fn  # type: ignore[assignment]

    @staticmethod
    def refresh_session_publish_aggregate_locked(session: "SessionRecord") -> None:
        """Recompute flat ``last_publish_*`` from per-device map.

        Backward-compat: dashboard, health-check, evidence center vẫn đọc
        các field flat này.
        """
        statuses = list(session.device_publish_status.values())
        if not statuses:
            return
        session.last_publish_ack_count = sum(s.ack_count for s in statuses)
        session.last_publish_count = sum(s.message_count for s in statuses)
        session.publish_ack_count_total = sum(s.ack_count_total for s in statuses)
        session.publish_attempt_count = sum(s.attempt_count for s in statuses)
        session.last_publish_ok = all(
            s.ok for s in statuses if s.message_count > 0
        ) and any(s.message_count > 0 for s in statuses)
        latencies = [s.latency_ms for s in statuses if s.latency_ms is not None]
        session.last_publish_latency_ms = max(latencies) if latencies else None
        attempts = [s.attempt_at for s in statuses if s.attempt_at is not None]
        session.last_publish_attempt_at = max(attempts) if attempts else None
        ok_times = [s.last_ok_at for s in statuses if s.last_ok_at is not None]
        session.last_publish_ok_at = max(ok_times) if ok_times else None
        errors = [s.error for s in statuses if s.error]
        session.last_publish_error = errors[-1] if errors else None

    # ── Buffer → pending publish units ───────────────────────────────────

    def publish_tick_buffer_locked(
        self, *, now: float, force: bool
    ) -> list[PendingDevicePublish]:
        """Build per-device publish units (fix bug "dữ liệu đi cùng qua 1 API").

        Mỗi device có buffer riêng → 1 device đang in-flight không block
        device khác.
        """
        if not force and now - self._last_push_time_ref[0] < float(self._push_interval):
            return []
        pending: list[PendingDevicePublish] = []
        for device_id, buffer in self._device_buffers.items():
            if not buffer:
                continue
            if device_id in self._device_in_flight:
                continue
            messages = list(buffer)
            self._device_in_flight.add(device_id)
            pending.append(
                PendingDevicePublish(
                    device_id=device_id,
                    messages=messages,
                    clear_count=len(messages),
                )
            )
        return pending

    # ── Side-effects dispatcher ───────────────────────────────────────────

    def run_session_side_effects(self, effects: SessionSideEffects) -> None:
        self.execute_pending_tick_publish(effects.pending_publishes)

        if effects.pending_heartbeats:
            latest_heartbeats: dict[int, int] = {}
            for item in effects.pending_heartbeats:
                latest_heartbeats[item.db_device_id] = item.battery_level
            for db_device_id, battery_level in latest_heartbeats.items():
                if self._heartbeat_fn is not None:
                    self._heartbeat_fn(db_device_id, battery_level)
                else:
                    self.update_device_heartbeat(db_device_id, battery_level)

        for alert in effects.pending_alerts:
            self._push_alert(
                alert.sim_device_id,
                event_type=alert.event_type,
                severity=alert.severity,
                metadata=alert.metadata,
            )
