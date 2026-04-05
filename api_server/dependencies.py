from __future__ import annotations

import asyncio
import collections
import json as _json
import logging
import math
import os
import random as _random
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Event, RLock, Thread
from time import monotonic
from typing import Any
from uuid import uuid4
import httpx

from sqlalchemy import text

# Dual import path: supports both package-level execution
#   (`python -m Iot_Simulator.api_server.main`)
# and direct execution from the project root
#   (`uvicorn api_server.main:app`).
try:
    from Iot_Simulator.api_server.config import load_sleep_scenarios
    from Iot_Simulator.api_server.backend_admin_client import BackendAdminClient
    from Iot_Simulator.api_server.db import session_scope
    from Iot_Simulator.api_server.utils import _utc_now_iso, _safe_float, _coerce_date, _normalize_gender, _is_sleeping_state
    from Iot_Simulator.api_server.schemas import (
        AlertEvent,
        CreateDeviceRequest,
        DataBindingConfig,
        DashboardSummary,
        DbSleepHistoryRow,
        RiskContribution,
        RiskHistoryPoint,
        RiskInjectRequest,
        RiskScoreResponse,
        RiskTriggerRequest,
        SimulatedDevice,
        SleepHistoryRow,
        SleepSessionResponse,
        SleepStageSegment,
        VerificationResult,
        VitalsSample,
    )
    from Iot_Simulator.api_server.sim_admin_service import SimAdminService
    from Iot_Simulator.api_server.services.device_service import DeviceService
    from Iot_Simulator.api_server.services.vitals_service import VitalsService
    from Iot_Simulator.api_server.services.alert_service import AlertService
    from Iot_Simulator.api_server.services.session_service import SessionService
    from Iot_Simulator.api_server.services.sleep_service import SleepService
    from Iot_Simulator.simulator_core.dataset_registry import DatasetRegistry
    from Iot_Simulator.simulator_core.session import DataBinding as SimDataBinding, SimulatorSession, build_device
    from Iot_Simulator.simulator_core.sleep_ai_client import SleepAIClient
    from Iot_Simulator.simulator_core.sleep_vitals_enricher import enrich_sleep_record
    from Iot_Simulator.transport import HttpPublisher, MqttPublisher, TransportRouter
except ModuleNotFoundError:
    from api_server.config import load_sleep_scenarios
    from api_server.backend_admin_client import BackendAdminClient
    from api_server.db import session_scope
    from api_server.utils import _utc_now_iso, _safe_float, _coerce_date, _normalize_gender, _is_sleeping_state  # noqa: F811
    from api_server.schemas import (
        AlertEvent,
        CreateDeviceRequest,
        DataBindingConfig,
        DashboardSummary,
        DbSleepHistoryRow,
        RiskContribution,
        RiskHistoryPoint,
        RiskInjectRequest,
        RiskScoreResponse,
        RiskTriggerRequest,
        SimulatedDevice,
        SleepHistoryRow,
        SleepSessionResponse,
        SleepStageSegment,
        VerificationResult,
        VitalsSample,
    )
    from api_server.sim_admin_service import SimAdminService
    from api_server.services.device_service import DeviceService
    from api_server.services.vitals_service import VitalsService
    from api_server.services.alert_service import AlertService
    from api_server.services.session_service import SessionService
    from api_server.services.sleep_service import SleepService
    from simulator_core.dataset_registry import DatasetRegistry
    from simulator_core.session import DataBinding as SimDataBinding, SimulatorSession, build_device
    from simulator_core.sleep_ai_client import SleepAIClient
    from simulator_core.sleep_vitals_enricher import enrich_sleep_record
    from transport import HttpPublisher, MqttPublisher, TransportRouter


logger = logging.getLogger(__name__)


# _utc_now_iso, _coerce_date, _safe_float, _normalize_gender, _is_sleeping_state
# imported from api_server.utils (MEDIUM #7 dedup)


def _derive_age(value: Any, default: int = 35) -> int:
    dob = _coerce_date(value)
    if dob is None:
        return default
    today = datetime.now(timezone.utc).date()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return max(years, 0)



def _build_db_device_persona(device_info: dict[str, Any], db_device_id: int) -> dict[str, Any]:
    return {
        "age": _derive_age(device_info.get("date_of_birth")),
        "weight_kg": _safe_float(device_info.get("weight_kg"), 70.0),
        "height_cm": _safe_float(device_info.get("height_cm"), 170.0),
        "gender": _normalize_gender(device_info.get("gender")),
        "seed": db_device_id % 97,
    }


# Sleep scenario data loaded from external YAML config (see api_server/config/sleep_scenarios.yaml)
SLEEP_SCENARIO_PHASES, SLEEP_SCENARIO_PROFILES = load_sleep_scenarios()

# MEDIUM #8: Threshold constants centralised in vitals_service.py
# Import them here for backward compatibility.
try:
    from Iot_Simulator.api_server.services.vitals_service import DAYTIME_THRESHOLDS, SLEEP_THRESHOLDS
except ModuleNotFoundError:
    from api_server.services.vitals_service import DAYTIME_THRESHOLDS, SLEEP_THRESHOLDS



@dataclass
class DeviceRecord:
    id: str
    name: str
    serial_number: str
    mqtt_client_id: str
    device_type: str
    battery_level: int = 100
    is_online: bool = True
    bind_status: str = "bindable"
    last_seen_at: str | None = None
    has_pending_sync: bool = False
    state: str = "provisioned"
    bound_db_device_id: int | None = None
    persona_config: dict[str, Any] = field(default_factory=dict)
    data_binding: dict[str, Any] | None = None

    def to_schema(self) -> SimulatedDevice:
        return SimulatedDevice(
            id=self.id,
            name=self.name,
            serialNumber=self.serial_number,
            mqttClientId=self.mqtt_client_id,
            deviceType=self.device_type,  # type: ignore[arg-type]
            batteryLevel=self.battery_level,
            isOnline=self.is_online,
            bindStatus=self.bind_status,  # type: ignore[arg-type]
            lastSeenAt=self.last_seen_at,
            hasPendingSync=self.has_pending_sync,
            state=self.state,  # type: ignore[arg-type]
            boundDbDeviceId=self.bound_db_device_id,
            personaConfig=self.persona_config or None,
            dataBinding=DataBindingConfig(**self.data_binding) if self.data_binding else None,
        )


@dataclass
class SessionRecord:
    id: str
    device_ids: list[str]
    speed: int
    simulator: SimulatorSession
    status: str = "idle"
    created_at: str = field(default_factory=_utc_now_iso)
    last_tick_at: str | None = None
    last_tick_outputs: list[dict[str, Any]] = field(default_factory=list)
    last_publish_ok: bool = False
    last_publish_ack_count: int = 0
    last_publish_count: int = 0
    last_publish_latency_ms: int | None = None
    alert_received: bool = False
    last_tick_monotonic: float = field(default_factory=monotonic)
    source_modes: dict[str, str] = field(default_factory=dict)


@dataclass
class EventRecord:
    id: str
    timestamp: str
    device_id: str
    event_type: str
    severity: str
    message: str
    metadata: dict[str, str] = field(default_factory=dict)

    def to_schema(self) -> AlertEvent:
        return AlertEvent(
            id=self.id,
            timestamp=self.timestamp,
            deviceId=self.device_id,
            eventType=self.event_type,
            severity=self.severity,  # type: ignore[arg-type]
            message=self.message,
            metadata=self.metadata,
        )


@dataclass
class RiskSnapshot:
    device_id: str
    score: float
    risk_level: str
    risk_type: str
    calculated_at: str
    explanation: list[RiskContribution]
    model: str = "healthguard-v1.2"
    algorithm: str = "ONNX RF+LGBM"


@dataclass
class PendingTickPublish:
    messages: list[dict[str, Any]]
    clear_count: int


@dataclass
class PendingHeartbeatUpdate:
    db_device_id: int
    battery_level: int


@dataclass
class PendingAlertCall:
    sim_device_id: str
    event_type: str
    severity: str
    metadata: dict[str, Any] | None = None


@dataclass
class PreparedAlertPush:
    sim_device_id: str
    signature: tuple[str, str, str]
    event_type: str
    severity: str
    timestamp: str
    payload_json: str


@dataclass
class SessionSideEffects:
    pending_publish: PendingTickPublish | None = None
    pending_heartbeats: list[PendingHeartbeatUpdate] = field(default_factory=list)
    pending_alerts: list[PendingAlertCall] = field(default_factory=list)

    def extend(self, other: "SessionSideEffects") -> None:
        if self.pending_publish is None and other.pending_publish is not None:
            self.pending_publish = other.pending_publish
        self.pending_heartbeats.extend(other.pending_heartbeats)
        self.pending_alerts.extend(other.pending_alerts)


class LogHub:
    def __init__(self) -> None:
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._lock = RLock()
        self._loop: asyncio.AbstractEventLoop | None = None
        # LOW #5: track dropped messages
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
                    # Loop closed or queue invalidated — skip gracefully
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


class SimulatorRuntime:
    """Thin orchestration facade over extracted domain services.

    Delegates business logic to:
    - :class:`DeviceService`   – device CRUD, binding, admin-DB lifecycle
    - :class:`VitalsService`   – vitals retrieval & severity classification
    - :class:`AlertService`    – alert push, event recording & history
    - :class:`SessionService`  – session CRUD (create/start/stop/list)
    - :class:`SleepService`    – sleep session construction, scoring, push, history

    Retains cross-cutting orchestration: ``_tick_session_locked``,
    ``set_device_scenario``, ``inject_event``, ``tick_active``, background tick,
    risk scoring, dashboard summary, and transport/publish plumbing.
    """

    def __init__(self) -> None:
        self.registry = DatasetRegistry(self._resolve_artifacts_dir())
        self._sleep_ai_client = SleepAIClient()
        self._last_sleep_score_source = "heuristic"
        try:
            if self._sleep_ai_client.check_availability():
                logger.info("Sleep AI model available at http://localhost:8001")
            else:
                logger.warning("Sleep AI model not available — heuristic fallback active")
        except Exception:
            logger.warning("Sleep AI availability check failed", exc_info=True)
        self.devices: dict[str, DeviceRecord] = {}
        self.device_scenarios: dict[str, str] = {}
        self.sessions: dict[str, SessionRecord] = {}
        self.event_history: collections.deque[EventRecord] = collections.deque(maxlen=2000)
        self.risk_snapshots: dict[str, RiskSnapshot] = {}
        # Removed dead attribute: self._dashboard_cache (actual cache uses _dashboard_cache_ref[0])
        self._dashboard_cache_ts: float = 0.0
        # HIGH #1 fix: pre-computed alert counter so dashboard_summary()
        # does not need to iterate event_history under lock.
        self._alert_count_1h: int = 0
        self._alert_timestamps_1h: collections.deque[float] = collections.deque()
        self.risk_history: dict[str, list[RiskHistoryPoint]] = {}
        self.logs = LogHub()
        self._lock = RLock()
        try:
            self._push_interval = max(1, int(os.environ.get("SIM_PUSH_INTERVAL_SECONDS", "5")))
        except ValueError:
            self._push_interval = 5
        self._tick_buffer: list[dict[str, Any]] = []
        self._last_push_time = 0.0
        self._publish_in_flight = False
        self._health_backend_url = self._resolve_backend_base_url()
        self.backend_base_url = self._health_backend_url
        self.admin_client = BackendAdminClient(self._health_backend_url)
        mqtt = MqttPublisher(topic_prefix="devices/sim", client=lambda topic, payload: True)
        http = HttpPublisher(
            endpoint=self._telemetry_ingest_endpoint(self._health_backend_url),
            sender=self._http_sender,
        )
        self.transport_router = TransportRouter(mqtt, http)
        self._bp_last_observed: dict[str, float] = {}
        self._last_alert_pushes: dict[tuple[str, str, str], float] = {}
        self._alert_pushes_in_flight: set[tuple[str, str, str]] = set()
        self._sleep_phase_tracker: dict[str, tuple[int, float]] = {}
        self._db_device_active_cache: dict[int, bool] = {}
        try:
            self._background_tick_interval = max(0.1, float(os.environ.get("SIM_TICK_INTERVAL_SECONDS", "1")))
        except ValueError:
            self._background_tick_interval = 1.0
        self._background_tick_stop = Event()
        self._background_tick_thread: Thread | None = None

        # ── Service layer (Task 3.1) ─────────────────────────────────────
        self._dashboard_cache_ref: list = [None]
        self.device_service = DeviceService(
            devices=self.devices,
            sessions=self.sessions,
            device_scenarios=self.device_scenarios,
            risk_snapshots=self.risk_snapshots,
            risk_history=self.risk_history,
            tick_buffer=self._tick_buffer,
            event_history=self.event_history,
            dashboard_cache_ref=self._dashboard_cache_ref,
            db_device_active_cache=self._db_device_active_cache,
            lock=self._lock,
            admin_client=self.admin_client,
            record_event_fn=self._record_event,
            publish_device_log_fn=self._publish_device_log,
            # HIGH #6 fix: pass tracker dicts for cleanup on device delete
            sleep_phase_tracker=self._sleep_phase_tracker,
            bp_last_observed=self._bp_last_observed,
            last_alert_pushes=self._last_alert_pushes,
        )
        self.device_service.set_runtime_session_ops(self)

        # ── VitalsService (Task 3.3) ─────────────────────────────────────
        self.vitals_service = VitalsService(
            sessions=self.sessions,
            bp_last_observed=self._bp_last_observed,
            lock=self._lock,
        )

        # ── AlertService (Task 3.5) ──────────────────────────────────────
        self.alert_service = AlertService(
            devices=self.devices,
            event_history=self.event_history,
            lock=self._lock,
            last_alert_pushes=self._last_alert_pushes,
            alert_pushes_in_flight=self._alert_pushes_in_flight,
            push_interval=self._push_interval,
            health_backend_url=self._health_backend_url,
            http_sender=self._http_sender,
            telemetry_alert_endpoint_fn=self._telemetry_alert_endpoint,
            publish_device_log_fn=self._publish_device_log,
            dashboard_cache_ref=self._dashboard_cache_ref,
        )

        # ── SessionService (Task 3.2) ────────────────────────────────────
        self.session_service = SessionService(
            devices=self.devices,
            sessions=self.sessions,
            lock=self._lock,
            registry=self.registry,
            record_event_fn=self._record_event,
            rebuild_db_device_active_cache_fn=self._rebuild_db_device_active_cache_locked,
            tick_session_locked_fn=self._tick_session_locked,
            run_session_side_effects_fn=self._run_session_side_effects,
        )

        self.sleep_service = SleepService(
            devices=self.devices,
            sessions=self.sessions,
            device_scenarios=self.device_scenarios,
            lock=self._lock,
            registry=self.registry,
            sleep_ai_client=self._sleep_ai_client,
            sleep_phase_tracker=self._sleep_phase_tracker,
            health_backend_url=self._health_backend_url,
            http_sender=self._http_sender,
            publish_device_log_fn=self._publish_device_log,
            require_device_fn=self.device_service._require_device,
            # MEDIUM #9: pass pre-loaded scenario data to avoid double load
            sleep_scenario_phases=SLEEP_SCENARIO_PHASES,
            sleep_scenario_profiles=SLEEP_SCENARIO_PROFILES,
        )

    @staticmethod
    def _resolve_artifacts_dir() -> Path:
        root = Path(__file__).resolve().parents[1]
        artifacts_dir = root / "normalized_artifacts"
        return artifacts_dir

    @staticmethod
    def _resolve_backend_base_url() -> str:
        base_url = os.environ.get("HEALTH_BACKEND_URL", "http://localhost:8000").strip()
        return base_url.rstrip("/") or "http://localhost:8000"

    @staticmethod
    def _telemetry_ingest_endpoint(base_url: str) -> str:
        # FastAPI Uvicorn local listens at /mobile/... without /api
        # In production behind proxy, base_url should include the /api (e.g. http://domain/api/v1)
        return f"{base_url.rstrip('/')}/mobile/telemetry/ingest"

    @staticmethod
    def _telemetry_alert_endpoint(base_url: str) -> str:
        # Mirrors the ingest endpoint path strategy: direct local calls hit /mobile/...
        return f"{base_url.rstrip('/')}/mobile/telemetry/alert"

    @staticmethod
    def _risk_calculate_endpoint(base_url: str) -> str:
        return f"{base_url.rstrip('/')}/mobile/risk/calculate"

    @staticmethod
    def _http_sender(endpoint: str, payload: str, headers: dict[str, str] | None = None) -> int:
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        try:
            response = httpx.post(
                endpoint,
                content=payload.encode("utf-8"),
                headers=request_headers,
                timeout=10,
            )
            return response.status_code
        except httpx.HTTPStatusError as exc:
            return exc.response.status_code
        except httpx.HTTPError:
            raise

    def _publish_device_log(self, sim_device_id: str, *, level: str, message: str, timestamp: str | None = None) -> None:
        ts = timestamp or _utc_now_iso()
        with self._lock:
            session_ids = [
                session.id
                for session in self.sessions.values()
                if sim_device_id in session.device_ids
            ]
        if not session_ids:
            session_ids = ["system"]
        for session_id in session_ids:
            self.logs.publish(
                session_id,
                {
                    "level": level,
                    "session_id": session_id,
                    "device_id": sim_device_id,
                    "message": message,
                    "ts": ts,
                },
            )

    # ── Thread-safe session accessor for WebSocket keepalive ─────────────

    def get_session_last_tick(self, session_id: str) -> str | None:
        """Return ``last_tick_at`` for the given session under lock (thread-safe)."""
        with self._lock:
            session = self.sessions.get(session_id)
            return session.last_tick_at if session is not None else None

    # ── Alert push — delegated to AlertService (Task 3.5) ────────────────

    def _push_alert_to_backend(
        self,
        sim_device_id: str,
        event_type: str,
        severity: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        # CRITICAL #1 fix: offload alert push (with retry/sleep) to a
        # dedicated ThreadPoolExecutor so the background tick thread is
        # never blocked by exponential-backoff sleeps.
        self.alert_service._alert_executor.submit(
            self.alert_service._push_alert_to_backend,
            sim_device_id, event_type, severity, metadata,
        )

    def _update_device_heartbeat(self, db_device_id: int, battery_level: int) -> None:
        try:
            with session_scope() as db:
                SimAdminService.update_heartbeat(
                    db_device_id,
                    db,
                    battery_level=battery_level,
                    signal_strength=None,
                )
        except Exception:
            logger.warning("Failed to update device heartbeat for db_device_id=%s", db_device_id, exc_info=True)
            return

    def _execute_pending_tick_publish(self, pending_publish: PendingTickPublish | None) -> None:
        if pending_publish is None:
            return

        publish_started = monotonic()
        publish_result = None
        try:
            publish_result = self.transport_router.publish(pending_publish.messages, mode="http")
        except Exception:
            logger.warning("Transport publish failed for pending tick", exc_info=True)
            publish_result = None
        publish_latency_ms = max(0, int(round((monotonic() - publish_started) * 1000)))

        publish_ok = False
        ack_count = 0
        message_count = len(pending_publish.messages)
        if publish_result is not None:
            publish_ok = publish_result.primary.ok or (
                publish_result.fallback is not None and publish_result.fallback.ok
            )
            ack_count = publish_result.primary.ack_count + (
                publish_result.fallback.ack_count if publish_result.fallback else 0
            )
            message_count = publish_result.primary.message_count

        with self._lock:
            self._publish_in_flight = False
            for session in self.sessions.values():
                if session.status == "running":
                    session.last_publish_ok = publish_ok
                    session.last_publish_ack_count = ack_count
                    session.last_publish_count = message_count
                    session.last_publish_latency_ms = publish_latency_ms
            if publish_ok:
                del self._tick_buffer[: pending_publish.clear_count]
                self._last_push_time = monotonic()
                self._refresh_pending_sync_flags()

    def _run_session_side_effects(self, effects: SessionSideEffects) -> None:
        self._execute_pending_tick_publish(effects.pending_publish)

        if effects.pending_heartbeats:
            latest_heartbeats: dict[int, int] = {}
            for item in effects.pending_heartbeats:
                latest_heartbeats[item.db_device_id] = item.battery_level
            for db_device_id, battery_level in latest_heartbeats.items():
                self._update_device_heartbeat(db_device_id, battery_level)

        for alert in effects.pending_alerts:
            self._push_alert_to_backend(
                alert.sim_device_id,
                event_type=alert.event_type,
                severity=alert.severity,
                metadata=alert.metadata,
            )


    # ── Sleep — delegated to SleepService (Task 3.4) ─────────────────────

    def sleep_db_history(self, device_id: str, days: int = 30) -> list[DbSleepHistoryRow]:
        return self.sleep_service.sleep_db_history(device_id, days)

    def _trigger_risk_inference(self, sim_device_id: str) -> int | None:
        with self._lock:
            device = self.devices.get(sim_device_id)
            bound_db_device_id = device.bound_db_device_id if device is not None else None
        if bound_db_device_id is None:
            return None

        payload = {"device_id": bound_db_device_id}
        endpoint = self._risk_calculate_endpoint(self._health_backend_url)
        try:
            status_code = self._http_sender(
                endpoint,
                _json.dumps(payload),
                headers={"X-Internal-Service": "iot-simulator"},
            )
        except Exception as exc:
            self._publish_device_log(
                sim_device_id,
                level="WARN",
                message=f"Risk trigger skipped: {exc}",
                timestamp=_utc_now_iso(),
            )
            return None

        level = "INFO" if 200 <= status_code < 300 else "WARN"
        self._publish_device_log(
            sim_device_id,
            level=level,
            message=f"Risk inference triggered, HTTP {status_code}",
            timestamp=_utc_now_iso(),
        )
        return status_code

    # ── Device CRUD — delegated to DeviceService (Task 3.1) ──────────────

    def list_devices(self) -> list[SimulatedDevice]:
        return self.device_service.list_devices()

    def create_device(self, request: CreateDeviceRequest) -> SimulatedDevice:
        return self.device_service.create_device(request)

    def delete_device(self, device_id: str) -> None:
        self.device_service.delete_device(device_id)

    def bind_device(self, sim_device_id: str, db_device_id: int) -> DeviceRecord:
        return self.device_service.bind_device(sim_device_id, db_device_id)

    def unbind_device(self, sim_device_id: str) -> DeviceRecord:
        return self.device_service.unbind_device(sim_device_id)

    # ── Admin device methods — delegated to DeviceService ────────────────

    def admin_list_db_devices(self) -> list[dict[str, Any]]:
        return self.device_service.admin_list_db_devices()

    def admin_find_user(self, email: str) -> dict[str, Any] | None:
        return self.device_service.admin_find_user(email)

    def admin_create_db_device(
        self,
        device_name: str,
        device_type: str = "smartwatch",
        serial_number: str | None = None,
        user_email: str | None = None,
    ) -> dict[str, Any]:
        return self.device_service.admin_create_db_device(device_name, device_type, serial_number, user_email)

    def admin_assign_db_device(self, device_id: int, user_email: str) -> dict[str, Any]:
        return self.device_service.admin_assign_db_device(device_id, user_email)

    def admin_activate_db_device(self, device_id: int) -> dict[str, Any]:
        return self.device_service.admin_activate_db_device(device_id)

    def admin_deactivate_db_device(self, device_id: int) -> dict[str, Any]:
        return self.device_service.admin_deactivate_db_device(device_id)

    def admin_delete_db_device(self, device_id: int) -> None:
        self.device_service.admin_delete_db_device(device_id)

    # ── Admin helpers — delegated to DeviceService ───────────────────────

    def _find_sim_id_for_db_device(self, db_device_id: int) -> str | None:
        return self.device_service._find_sim_id_for_db_device(db_device_id)

    def _find_running_session_for_sim_device(self, sim_id: str) -> SessionRecord | None:
        return self.device_service._find_running_session_for_sim_device(sim_id)

    def _rebuild_db_device_active_cache_locked(self) -> None:
        self.device_service._rebuild_db_device_active_cache_locked()

    def list_running_db_device_ids(self) -> set[int]:
        return self.device_service.list_running_db_device_ids()

    def is_db_device_sim_running(self, db_device_id: int) -> bool:
        return self.device_service.is_db_device_sim_running(db_device_id)

    def _ensure_sim_session_for_db_device(self, db_device_id: int, device_info: dict[str, Any]) -> None:
        self.device_service._ensure_sim_session_for_db_device(db_device_id, device_info)

    def _stop_sim_session_for_db_device(self, db_device_id: int) -> None:
        self.device_service._stop_sim_session_for_db_device(db_device_id)

    # ── Session CRUD — delegated to SessionService (Task 3.2) ────────────

    def list_sessions(self) -> list[dict[str, Any]]:
        return self.session_service.list_sessions()

    def create_session(self, device_ids: list[str], speed: int) -> dict[str, Any]:
        return self.session_service.create_session(device_ids, speed)

    def start_session(self, session_id: str) -> None:
        self.session_service.start_session(session_id)

    def stop_session(self, session_id: str) -> None:
        self.session_service.stop_session(session_id)

    def set_device_scenario(self, device_id: str, scenario_id: str) -> None:
        known = {
            "normal_rest",
            "tachycardia_warning",
            "hypoxia_critical",
            "hypertension_moderate",
            "fall_high_confidence",
            "fall_false_alarm",
            "fall_no_response",
            "good_sleep_night",
            "fragmented_sleep",
            "high_risk_cardiac",
            "medium_risk_general",
            # HIGH #3 fix: 4 sleep scenarios from YAML that were missing
            "sleep_apnea_mild",
            "sleep_apnea_severe",
            "insomnia_pattern",
            "elderly_normal",
        }
        _WAKING_SCENARIOS = {
            "normal_rest",
            "tachycardia_warning",
            "hypoxia_critical",
            "hypertension_moderate",
            "high_risk_cardiac",
            "medium_risk_general",
        }
        effects = SessionSideEffects()
        with self._lock:
            self._require_device(device_id)
            if scenario_id not in known:
                raise KeyError(f"Unknown scenario id: {scenario_id}")
            self.device_scenarios[device_id] = scenario_id
            # Fall scenarios auto-inject a fall_detected event so PersonaEngine
            # transitions to activity_state="fall". Vitals are then: base_profile
            # + fall_surge below. No hardcoded fall profile needed.
            _FALL_EVENT_MAP = {
                "fall_high_confidence": "fall_1",
                "fall_no_response":     "fall_no_response",
                "fall_false_alarm":     "fall_brief",
            }
            if scenario_id in _FALL_EVENT_MAP:
                for _sr in self.sessions.values():
                    if _sr.status == "running" and device_id in _sr.device_ids:
                        _sr.simulator.inject_event(device_id, "fall_detected", _FALL_EVENT_MAP[scenario_id])
            sleep_started = False
            if scenario_id in SLEEP_SCENARIO_PHASES:
                initial_phase = SLEEP_SCENARIO_PHASES[scenario_id][0][0]
                for _sr in self.sessions.values():
                    if _sr.status == "running" and device_id in _sr.device_ids:
                        _sr.simulator.inject_event(device_id, "sleep_start", initial_phase)
                        sleep_started = True
                if sleep_started:
                    self._sleep_phase_tracker[device_id] = (0, monotonic())
            elif scenario_id in _WAKING_SCENARIOS:
                for _sr in self.sessions.values():
                    if _sr.status != "running" or device_id not in _sr.device_ids:
                        continue
                    for _device in _sr.simulator.devices:
                        if _device.device_id != device_id:
                            continue
                        if (
                            _device.engine.state.activity_state == "sleeping"
                            or _device.engine.state.sleep_phase is not None
                        ):
                            _sr.simulator.inject_event(device_id, "sleep_end", None)
                            self._sleep_phase_tracker.pop(device_id, None)
                        break
            if self.devices[device_id].state not in {"offline"}:
                self.devices[device_id].state = self._scenario_state_hint(scenario_id)
            for record in self.sessions.values():
                if record.status == "running" and device_id in record.device_ids:
                    effects.extend(self._tick_session_locked(record, force=True))
            self._record_event(
                device_id=device_id,
                event_type="scenario_applied",
                severity="normal",
                message=f"Scenario applied: {scenario_id}",
                metadata={"scenario_id": scenario_id},
            )
        self._run_session_side_effects(effects)

    def tick_active(self) -> None:
        effects = SessionSideEffects()
        with self._lock:
            for record in self.sessions.values():
                if record.status == "running":
                    effects.extend(self._tick_session_locked(record, force=False))
        self._run_session_side_effects(effects)

    def start_background_tick(self) -> None:
        with self._lock:
            if self._background_tick_thread is not None and self._background_tick_thread.is_alive():
                return
            self._background_tick_stop.clear()
            self._background_tick_thread = Thread(
                target=self._background_tick_loop,
                name="iot-simulator-runtime-tick",
                daemon=True,
            )
            self._background_tick_thread.start()

    def shutdown(self, *, timeout: float = 1.0) -> None:
        with self._lock:
            thread = self._background_tick_thread
            self._background_tick_thread = None
            self._background_tick_stop.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

    def _background_tick_loop(self) -> None:
        while not self._background_tick_stop.wait(self._background_tick_interval):
            try:
                self.tick_active()
            except Exception as exc:
                self.logs.publish(
                    "system",
                    {
                        "level": "ERROR",
                        "session_id": "system",
                        "device_id": "system",
                        "message": f"Background tick failed: {exc}",
                        "ts": _utc_now_iso(),
                    },
                )

    def inject_event(self, device_id: str, event_type: str, variant: str | None) -> None:
        effects = SessionSideEffects()
        with self._lock:
            for record in self.sessions.values():
                if device_id in record.device_ids:
                    record.simulator.inject_event(device_id, event_type, variant)
                    if event_type == "fall_detected":
                        record.alert_received = True
                        if device_id in self.devices:
                            self.devices[device_id].state = "fall_countdown"
                    if event_type == "device_offline" and device_id in self.devices:
                        self.devices[device_id].state = "offline"
                        self.devices[device_id].is_online = False
                    if event_type == "device_online" and device_id in self.devices:
                        self.devices[device_id].state = "streaming"
                        self.devices[device_id].is_online = True
                    severity = "warning"
                    if event_type == "fall_detected":
                        severity = "critical"
                    elif event_type == "device_offline":
                        severity = "offline"
                    elif event_type == "device_online":
                        severity = "normal"
                    self._record_event(
                        device_id=device_id,
                        event_type=event_type,
                        severity=severity,
                        message=f"Injected event {event_type}",
                        metadata={"variant": variant or ""},
                    )
                    if event_type == "fall_detected":
                        effects.pending_alerts.append(
                            PendingAlertCall(
                                sim_device_id=device_id,
                                event_type="fall_detected",
                                severity="critical",
                                metadata={
                                    "variant": variant or "",
                                    "source": "inject_event",
                                    "timestamp": _utc_now_iso(),
                                },
                            )
                        )
                    if record.status == "running":
                        effects.extend(self._tick_session_locked(record, force=True))
                    break
            else:
                raise KeyError(f"Device not found in active sessions: {device_id}")
        self._run_session_side_effects(effects)

    def recent_events(self, limit: int = 10) -> list[AlertEvent]:
        return self.alert_service.recent_events(limit=limit)

    def _increment_alert_counter(self) -> None:
        """Bump the pre-computed 1-hour alert counter (called from _record_event).

        HIGH #1 fix: keeps a deque of timestamps so ``dashboard_summary``
        only reads a counter instead of scanning all 2 000 events.
        """
        now = time.time()
        self._alert_timestamps_1h.append(now)
        # Prune entries older than 1 hour
        cutoff = now - 3600
        while self._alert_timestamps_1h and self._alert_timestamps_1h[0] < cutoff:
            self._alert_timestamps_1h.popleft()
        self._alert_count_1h = len(self._alert_timestamps_1h)

    def dashboard_summary(self) -> DashboardSummary:
        _DASHBOARD_CACHE_TTL = 5.0  # seconds
        with self._lock:
            now_mono = monotonic()
            cached = self._dashboard_cache_ref[0]
            if cached is not None and (now_mono - self._dashboard_cache_ts) < _DASHBOARD_CACHE_TTL:
                return cached

            total = len(self.devices)
            active = len([device for device in self.devices.values() if device.state == "streaming"])

            # HIGH #1 fix: prune stale entries then read counter directly,
            # instead of iterating the full event_history and parsing ISO timestamps.
            now_ts = time.time()
            cutoff = now_ts - 3600
            while self._alert_timestamps_1h and self._alert_timestamps_1h[0] < cutoff:
                self._alert_timestamps_1h.popleft()
            self._alert_count_1h = len(self._alert_timestamps_1h)
            alerts = self._alert_count_1h

            latencies = [
                session.last_publish_latency_ms
                for session in self.sessions.values()
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
            self._dashboard_cache_ts = now_mono
            return result

    def health_payload(self) -> dict[str, str]:
        with self._lock:
            api_status = "running"
            mqtt_status = "connected"
            db_status = "local-ok"
            if not self.sessions:
                mqtt_status = "idle"
            return {
                "status": "ok",
                "api": api_status,
                "mqtt": mqtt_status,
                "db": db_status,
                "version": "simulator-api-0.3.0",
            }


    def sleep_session(self, device_id: str) -> SleepSessionResponse:
        return self.sleep_service.sleep_session(device_id)

    def push_sleep_session(self, device_id: str) -> SleepSessionResponse:
        return self.sleep_service.push_sleep_session(device_id)

    def push_sleep_session_for_date(
        self,
        device_id: str,
        target_date: date,
        scenario_id: str = "good_sleep_night",
    ) -> dict[str, Any]:
        return self.sleep_service.push_sleep_session_for_date(device_id, target_date, scenario_id)

    def risk_score(self, device_id: str) -> RiskScoreResponse:
        with self._lock:
            self._require_device(device_id)
            snapshot = self.risk_snapshots.get(device_id)
            if snapshot is None:
                score = self._calculate_dynamic_risk(device_id)
                level = self._risk_level_from_score(score)
                snapshot = self._upsert_risk_snapshot(
                    device_id=device_id,
                    score=score,
                    risk_level=level,
                    risk_type="general",
                    explanation=self._build_risk_explanation(device_id=device_id, score=score, risk_type="general"),
                    calculated_at=_utc_now_iso(),
                )
            history = self.risk_history.get(device_id)
            if not history:
                history = self._build_risk_history(device_id, snapshot.score)
                self.risk_history[device_id] = history
            return RiskScoreResponse(
                deviceId=device_id,
                score=snapshot.score,
                riskLevel=snapshot.risk_level,  # type: ignore[arg-type]
                model=snapshot.model,
                algorithm=snapshot.algorithm,
                calculatedAt=snapshot.calculated_at,
                explanation=snapshot.explanation,
                history=history,
            )

    def inject_risk_score(self, request: RiskInjectRequest) -> None:
        with self._lock:
            self._require_device(request.device_id)
            score = max(0.0, min(1.0, round(float(request.score), 3)))
            explanation = self._build_risk_explanation(
                device_id=request.device_id,
                score=score,
                risk_type=request.risk_type,
            )
            self._upsert_risk_snapshot(
                device_id=request.device_id,
                score=score,
                risk_level=request.risk_level,
                risk_type=request.risk_type,
                explanation=explanation,
                calculated_at=_utc_now_iso(),
            )
            self._append_risk_history(request.device_id, score)
            self._record_event(
                device_id=request.device_id,
                event_type="risk_injected",
                severity=self._severity_from_risk_level(request.risk_level),
                message=f"Risk injected ({request.risk_type})",
                metadata={"score": f"{score:.2f}", "risk_level": request.risk_level, "risk_type": request.risk_type},
            )

    def trigger_risk_calculation(self, request: RiskTriggerRequest) -> None:
        with self._lock:
            self._require_device(request.device_id)

        status_code = self._trigger_risk_inference(request.device_id)
        metadata: dict[str, str] = {}
        if status_code is not None:
            metadata["http_status"] = str(status_code)

        if status_code is not None and 200 <= status_code < 300:
            severity = "normal"
            message = "Backend risk inference requested"
        else:
            severity = "warning"
            message = "Backend risk inference request failed"

        with self._lock:
            self._record_event(
                device_id=request.device_id,
                event_type="risk_inference_triggered",
                severity=severity,
                message=message,
                metadata=metadata,
            )

    def latest_vitals(self, device_id: str) -> VitalsSample:
        return self.vitals_service.latest_vitals(device_id)

    def verification(self, session_id: str) -> VerificationResult:
        with self._lock:
            record = self._require_session(session_id)
            device_id = record.device_ids[0] if record.device_ids else "unknown"
            status = "PENDING"
            if record.status == "running":
                status = "PASS" if record.last_publish_ok else "FAILED"
            elif record.status == "stopped" and record.last_tick_outputs:
                status = "DELAYED"
            risk_received = device_id in self.risk_snapshots
            return VerificationResult(
                deviceId=device_id,
                vitalsReceived=bool(record.last_tick_outputs),
                alertReceived=record.alert_received,
                riskScoreReceived=risk_received,
                latencyMs=record.last_publish_latency_ms or 0,
                status=status,  # type: ignore[arg-type]
                lastCheckedAt=_utc_now_iso(),
            )

    def _require_session(self, session_id: str) -> SessionRecord:
        return self.session_service._require_session(session_id)

    def _tick_session_locked(self, record: SessionRecord, force: bool) -> SessionSideEffects:
        effects = SessionSideEffects()
        if record.status != "running":
            return effects
        target_interval = float(max(record.speed, 1))
        now = monotonic()
        if not force and now - record.last_tick_monotonic < target_interval:
            return effects
        outputs = record.simulator.tick()
        buffered_messages: list[dict[str, Any]] = []
        for payload in outputs:
            device_id = str(payload.get("device_id") or "")
            if device_id in self.devices:
                device = self.devices[device_id]
                payload["persona_config"] = device.persona_config
                if device.bound_db_device_id is not None:
                    payload["db_device_id"] = device.bound_db_device_id
                    buffered_messages.append(payload)
            scenario_id = self.device_scenarios.get(device_id, "normal_rest")
            device_source_mode = str(record.source_modes.get(device_id, "synthetic") or "synthetic").strip().lower()
            if device_source_mode == "replay":
                self._annotate_scenario_replay(payload, scenario_id)
            else:
                self._apply_scenario_overrides(payload, scenario_id)
        for payload in outputs:
            device_id = str(payload.get("device_id") or "")
            if device_id in self.devices:
                self.sleep_service._advance_sleep_phase_if_due(device_id)
        record.last_tick_monotonic = now
        record.last_tick_outputs = outputs
        record.last_tick_at = _utc_now_iso()
        if buffered_messages:
            self._tick_buffer.extend(buffered_messages)
        self._refresh_pending_sync_flags()
        effects.pending_publish = self._publish_tick_buffer_locked(now=now, force=force)
        for payload in outputs:
            device_id = payload.get("device_id")
            if device_id in self.devices:
                device = self.devices[device_id]
                state = payload.get("state") or {}
                scenario_id = self.device_scenarios.get(str(device_id), "normal_rest")
                device.battery_level = int(state.get("battery_level", device.battery_level))
                device.is_online = bool(state.get("is_online", True))
                device.last_seen_at = payload.get("emitted_at")
                if device.state not in {"fall_countdown", "offline"}:
                    device.state = self._scenario_state_hint(scenario_id)
                if device.bound_db_device_id is not None:
                    effects.pending_heartbeats.append(
                        PendingHeartbeatUpdate(
                            db_device_id=device.bound_db_device_id,
                            battery_level=device.battery_level,
                        )
                    )
            self.logs.publish(
                record.id,
                {
                    "level": "INFO",
                    "session_id": record.id,
                    "device_id": device_id,
                    "message": "tick emitted",
                    "ts": payload.get("emitted_at") or _utc_now_iso(),
                },
            )
            state = payload.get("state") or {}
            emitted_at = str(payload.get("emitted_at") or _utc_now_iso())
            if state.get("activity_state") == "fall":
                self._record_event(
                    device_id=str(device_id),
                    event_type="fall_detected",
                    severity="critical",
                    message="Fall-like motion detected during session tick",
                )
                effects.pending_alerts.append(
                    PendingAlertCall(
                        sim_device_id=str(device_id),
                        event_type="fall_detected",
                        severity="critical",
                        metadata={
                            "variant": str(state.get("fall_variant") or ""),
                            "source": "tick",
                            "timestamp": emitted_at,
                        },
                    )
                )
                continue

            vitals_payload = payload.get("vitals") or {}
            vitals_sample = self._to_vitals(
                vitals_payload,
                stale=False,
                emitted_at=emitted_at,
                activity_state=str(state.get("activity_state") or "unknown"),
                is_sleeping=_is_sleeping_state(state.get("activity_state")),
                source_mode=str(vitals_payload.get("source_mode") or record.source_modes.get(str(device_id), "synthetic")),
                device_id=str(device_id),
            )
            is_sleeping = _is_sleeping_state(state.get("activity_state"))
            if is_sleeping:
                spo2 = vitals_sample.spo2 or 99.0
                rr = vitals_sample.respiratoryRate or 15.0
                hr = vitals_sample.heartRate or 60.0
                if spo2 < SLEEP_THRESHOLDS["osa_alert_spo2_threshold"]:
                    effects.pending_alerts.append(
                        PendingAlertCall(
                            sim_device_id=str(device_id),
                            event_type="sleep_apnea_suspected",
                            severity="critical",
                            metadata={
                                "source": "tick",
                                "timestamp": emitted_at,
                                "spo2": spo2,
                                "sleep_context": "true",
                                "priority": "critical",
                                "scenario_id": self.device_scenarios.get(str(device_id), "normal_rest"),
                                "message": "SpO2 < 88% khi ngủ — nghi ngờ ngưng thở",
                            },
                        )
                    )
                elif rr < SLEEP_THRESHOLDS["apnea_rr_threshold"]:
                    effects.pending_alerts.append(
                        PendingAlertCall(
                            sim_device_id=str(device_id),
                            event_type="respiratory_arrest_risk",
                            severity="critical",
                            metadata={
                                "source": "tick",
                                "timestamp": emitted_at,
                                "respiratory_rate": rr,
                                "sleep_context": "true",
                                "priority": "critical",
                                "scenario_id": self.device_scenarios.get(str(device_id), "normal_rest"),
                            },
                        )
                    )
                elif hr > SLEEP_THRESHOLDS["nocturnal_tachy_hr"]:
                    effects.pending_alerts.append(
                        PendingAlertCall(
                            sim_device_id=str(device_id),
                            event_type="nocturnal_tachycardia",
                            severity="warning",
                            metadata={
                                "source": "tick",
                                "timestamp": emitted_at,
                                "heart_rate": hr,
                                "sleep_context": "true",
                                "priority": "high",
                                "scenario_id": self.device_scenarios.get(str(device_id), "normal_rest"),
                            },
                        )
                    )
                continue
            if vitals_sample.severity in {"warning", "critical"}:
                effects.pending_alerts.append(
                    PendingAlertCall(
                        sim_device_id=str(device_id),
                        event_type="vitals_out_of_range",
                        severity=vitals_sample.severity,
                        metadata={
                            "source": "tick",
                            "timestamp": emitted_at,
                            "heart_rate": vitals_sample.heartRate,
                            "spo2": vitals_sample.spo2,
                            "temperature": vitals_sample.temperature,
                            "blood_pressure_sys": vitals_sample.bloodPressureSys,
                            "blood_pressure_dia": vitals_sample.bloodPressureDia,
                            "respiratory_rate": vitals_sample.respiratoryRate,
                            "activity_label": vitals_sample.activityLabel,
                            "scenario_id": self.device_scenarios.get(str(device_id), "normal_rest"),
                        },
                    )
                )
        return effects

    def _publish_tick_buffer_locked(self, now: float, force: bool) -> PendingTickPublish | None:
        if not self._tick_buffer:
            return None
        if self._publish_in_flight:
            return None
        if not force and now - self._last_push_time < float(self._push_interval):
            return None
        messages = list(self._tick_buffer)
        self._publish_in_flight = True
        return PendingTickPublish(messages=messages, clear_count=len(messages))

    def _refresh_pending_sync_flags(self) -> None:
        self.device_service._refresh_pending_sync_flags()

    @staticmethod
    def _scenario_state_hint(scenario_id: str) -> str:
        if scenario_id in {"hypoxia_critical", "high_risk_cardiac", "fall_no_response", "sleep_apnea_severe"}:
            return "critical"
        if scenario_id in {
            "tachycardia_warning", "hypertension_moderate", "fragmented_sleep",
            "medium_risk_general", "fall_false_alarm",
            # HIGH #3 fix: new sleep scenarios mapped to appropriate state hints
            "sleep_apnea_mild", "insomnia_pattern",
        }:
            return "warning"
        if scenario_id == "fall_high_confidence":
            return "fall_countdown"
        if scenario_id in {"normal_rest", "good_sleep_night", "elderly_normal"}:
            return "streaming"
        return "streaming"

    @staticmethod
    def _annotate_scenario_replay(payload: dict[str, Any], scenario_id: str) -> None:
        """Replay mode may annotate scenario context but must not rewrite real vitals."""
        annotation = payload.get("scenario_annotation")
        if not isinstance(annotation, dict):
            annotation = {}
            payload["scenario_annotation"] = annotation
        annotation["scenario_id"] = scenario_id
        annotation["overlay_blocked"] = True
        annotation["state_hint"] = SimulatorRuntime._scenario_state_hint(scenario_id)
        if scenario_id.startswith("fall_"):
            annotation["event_hint"] = "fall_detected"

    @staticmethod
    def _apply_scenario_overrides(payload: dict[str, Any], scenario_id: str) -> None:
        vitals = payload.get("vitals") or {}
        emitted_at = str(payload.get("emitted_at") or _utc_now_iso())
        try:
            phase = datetime.fromisoformat(emitted_at).timestamp()
        except ValueError:
            phase = monotonic()

        device_id_str = str(payload.get("device_id") or "")
        device_offset = float(hash(device_id_str) % 97)

        def wave(scale: float, shift: float = 0.0) -> float:
            return (math.sin((phase + shift + device_offset) / 9.0) * scale
                    + math.cos((phase + shift + device_offset) / 13.0) * (scale * 0.4))

        def clamp(value: float, lower: float, upper: float) -> float:
            return max(lower, min(upper, value))

        profiles: dict[str, tuple[float, ...]] = {
            # AHA resting adult. HR 60-100, BP <120/80, SpO2 95-100%
            "normal_rest": (65.0, 4.0, 97.5, 0.7, 36.6, 0.15, 115.0, 75.0, 5.0, 3.5, 15.0),
            # AHA tachycardia >100bpm. SNS activation.
            "tachycardia_warning": (108.0, 7.0, 96.0, 0.8, 37.1, 0.20, 130.0, 84.0, 6.5, 4.5, 20.0),
            # WHO SpO2 <90% = hypoxia. Compensatory tachycardia, tachypnea.
            "hypoxia_critical": (118.0, 10.0, 88.0, 1.5, 37.5, 0.25, 148.0, 94.0, 9.0, 6.0, 26.0),
            # ACC/AHA Stage 2 HTN. bp_dia_base=100 keeps DBP above warning threshold
            # even after wave trough and current persona adjustments.
            "hypertension_moderate": (80.0, 5.5, 96.5, 0.7, 37.0, 0.18, 138.0, 100.0, 8.0, 5.5, 16.0),
            # AASM deep NREM: HR 50-60, BP dips 10-20%, RR 12-14.
            "good_sleep_night": (55.0, 3.0, 96.5, 1.0, 36.3, 0.15, 105.0, 65.0, 4.0, 3.0, 13.0),
            # AASM fragmented: arousals, SpO2 dips, HR spikes.
            "fragmented_sleep": (76.0, 7.0, 93.0, 1.5, 36.8, 0.22, 126.0, 82.0, 7.5, 5.0, 17.0),
            # ACC/AHA ACS/STEMI: severe ischemia, HR++, BP++, SpO2 drop.
            "high_risk_cardiac": (128.0, 12.0, 91.0, 1.8, 38.0, 0.30, 165.0, 104.0, 12.0, 8.0, 24.0),
            # Pre-HTN + mild tachycardia. Composite medium-risk.
            "medium_risk_general": (94.0, 7.0, 94.5, 1.0, 37.3, 0.22, 142.0, 90.0, 8.5, 5.5, 18.0),
            # NOTE: fall_* scenarios intentionally absent. Fall vitals = surge (Phase 3).
        }
        (hr_base, hr_amp, spo2_base, spo2_amp, temp_base, temp_amp,
         bp_sys_base, bp_dia_base, bp_sys_amp, bp_dia_amp, rr_base) = profiles.get(
            scenario_id, profiles["normal_rest"]
        )

        heart_rate = clamp(hr_base + wave(hr_amp, 0.0), 40, 190)
        spo2 = clamp(spo2_base + wave(spo2_amp, 3.0), 78, 100)
        temperature = clamp(temp_base + wave(temp_amp, 7.0), 34.5, 41.5)
        blood_pressure_sys = clamp(bp_sys_base + wave(bp_sys_amp, 11.0), 85, 225)
        blood_pressure_dia = clamp(bp_dia_base + wave(bp_dia_amp, 15.0), 50, 140)
        respiratory_rate = clamp(rr_base + wave(1.5, 5.0), 4.0, 35.0)

        # Fall physiological response — variant-dependent (ATLS 10th ed.)
        _fall_activity = str((payload.get("state") or {}).get("activity_state") or "")
        _fall_variant  = str((payload.get("state") or {}).get("fall_variant") or "fall_generic")

        if _fall_activity == "fall":
            if _fall_variant == "fall_no_response":
                # Neurogenic shock / vagal syncope: parasympathetic dominance.
                # NO catecholamine surge. Bradycardia + hypotension + hypoxia + agonal breathing.
                # Source: ATLS 10th ed. ch.3; Guyton & Hall ch.18 (vasovagal).
                heart_rate         = clamp(heart_rate - 10.0, 40, 220)
                spo2               = clamp(spo2 - 14.0, 78, 100)
                blood_pressure_sys = clamp(blood_pressure_sys - 22.0, 85, 225)
                blood_pressure_dia = clamp(blood_pressure_dia - 12.0, 50, 140)
                respiratory_rate   = clamp(respiratory_rate - 8.0, 4, 35)
            elif _fall_variant == "fall_brief":
                # Minor fall — small sympathetic response, quick recovery expected.
                heart_rate         = clamp(heart_rate + 15.0, 40, 220)
                spo2               = clamp(spo2 - 2.0, 78, 100)
                blood_pressure_sys = clamp(blood_pressure_sys + 8.0, 85, 225)
            else:
                # fall_1, fall_generic, fall_high_confidence — catecholamine surge (ATLS).
                heart_rate         = clamp(heart_rate + 32.0, 40, 220)
                spo2               = clamp(spo2 - 6.0, 78, 100)
                blood_pressure_sys = clamp(blood_pressure_sys + 22.0, 85, 225)
        elif _fall_activity == "recovery":
            heart_rate         = clamp(heart_rate + 15.0, 40, 220)
            spo2               = clamp(spo2 - 3.0, 78, 100)
            blood_pressure_sys = clamp(blood_pressure_sys + 10.0, 85, 225)

        # Stress state: cortisol/adrenaline surge -> HR+, BP+, Temp+ (slight)
        # Source: APA 2023 stress physiology; cortisol cardiovascular effects
        _stress = str((payload.get("state") or {}).get("stress_state") or "")
        if _stress == "stress":
            heart_rate         = clamp(heart_rate + 12.0, 40, 220)
            blood_pressure_sys = clamp(blood_pressure_sys + 10.0, 85, 225)
            blood_pressure_dia = clamp(blood_pressure_dia + 7.0, 50, 140)
            temperature        = clamp(temperature + 0.2, 34.5, 41.5)

        # ── Persona-aware adjustments ────────────────────────────────────────────
        _pcfg    = payload.get("persona_config") or {}
        _age     = float(_pcfg.get("age", 70.0))
        _wkg     = float(_pcfg.get("weight_kg", 65.0))
        _hm      = float(_pcfg.get("height_cm", 165.0)) / 100.0
        _bmi     = max(10.0, min(70.0, _wkg / (_hm ** 2) if _hm > 0 else 22.0))

        # Age: AHA 2023 (HR), Framingham 2022 (BP), J Appl Physiol (SpO2), ATS 2019 (RR)
        _hr_age   = max(0.0, (_age - 40.0)) * 0.25
        _spo2_age = -(max(0.0, _age - 50.0) * 0.03)
        _sys_age  = max(0.0, (_age - 30.0)) * 0.6
        _dia_age  = (min(_age, 55.0) - 30.0) * 0.3 - max(0.0, _age - 55.0) * 0.2
        _tmp_age  = -(max(0.0, _age - 40.0) * 0.01)
        _rr_age   = max(0.0, (_age - 50.0) * 0.1)

        # BMI: NHANES III (HR/BP), Obesity Reviews 2020 (SpO2)
        if _bmi > 25.0:
            _ex = _bmi - 25.0
            _hr_bmi, _sys_bmi, _dia_bmi = _ex*0.5, _ex*1.0, _ex*0.6
            _spo2_bmi, _tmp_bmi = -(_ex*0.08), _ex*0.015
        elif _bmi < 18.5:
            _df = 18.5 - _bmi
            _hr_bmi, _sys_bmi, _dia_bmi = _df*0.4, -(_df*0.7), -(_df*0.4)
            _spo2_bmi, _tmp_bmi = 0.0, -(_df*0.01)
        else:
            _hr_bmi = _sys_bmi = _dia_bmi = _spo2_bmi = _tmp_bmi = 0.0

        heart_rate         = clamp(heart_rate + _hr_age + _hr_bmi,           40, 220)
        spo2               = clamp(spo2 + _spo2_age + _spo2_bmi,             78, 100)
        temperature        = clamp(temperature + _tmp_age + _tmp_bmi,        34.5, 41.5)
        blood_pressure_sys = clamp(blood_pressure_sys + _sys_age + _sys_bmi, 85, 225)
        blood_pressure_dia = clamp(blood_pressure_dia + _dia_age + _dia_bmi, 50, 140)
        respiratory_rate   = clamp(respiratory_rate + _rr_age,               4, 35)
        # ── Inter-signal coupling ────────────────────────────────────────────────
        # SpO2 → RR: carotid body chemoreceptor reflex (Guyton & Hall, Ch. 42)
        # When SpO2 < 95%, peripheral chemoreceptors fire → ventilatory drive increases.
        # Rate: approximately 0.5 breath/min per % SpO2 drop below 95%.
        if spo2 < 95.0:
            _rr_hypoxia = (95.0 - spo2) * 0.5
            respiratory_rate = clamp(respiratory_rate + _rr_hypoxia, 4, 35)
        # ─────────────────────────────────────────────────────────────────────────

        # Temperature → HR: fever-induced tachycardia (Wunderlich 1851; Mackowiak JAMA 1992)
        # Every 1°C above 37.5°C (fever threshold) adds ~10 bpm.
        # This is additive on top of scenario profile and persona adjustments.
        if temperature > 37.5:
            _hr_fever = (temperature - 37.5) * 10.0
            heart_rate = clamp(heart_rate + _hr_fever, 40, 220)

        vitals["heart_rate"] = round(heart_rate, 2)
        vitals["spo2"] = round(spo2, 2)
        vitals["temperature"] = round(temperature, 2)
        vitals["blood_pressure_sys"] = round(blood_pressure_sys, 2)
        vitals["blood_pressure_dia"] = round(blood_pressure_dia, 2)
        vitals["respiratory_rate"] = round(respiratory_rate, 1)
        payload["vitals"] = vitals

    @staticmethod
    def _to_vitals(
        vitals: dict[str, Any],
        stale: bool,
        emitted_at: str | None = None,
        activity_state: str = "unknown",
        is_sleeping: bool = False,
        source_mode: str = "synthetic",
        device_id: str = "",
        bp_observation_age_sec: float | None = None,
        bp_is_stale: bool | None = None,
    ) -> VitalsSample:
        return VitalsService.to_vitals(
            vitals,
            stale=stale,
            emitted_at=emitted_at,
            activity_state=activity_state,
            is_sleeping=is_sleeping,
            source_mode=source_mode,
            device_id=device_id,
            bp_observation_age_sec=bp_observation_age_sec,
            bp_is_stale=bp_is_stale,
        )

    # Delegate to module-level _safe_float for backward compatibility
    _safe_float = staticmethod(_safe_float)

    def _require_device(self, device_id: str) -> DeviceRecord:
        return self.device_service._require_device(device_id)


    def _upsert_risk_snapshot(
        self,
        *,
        device_id: str,
        score: float,
        risk_level: str,
        risk_type: str,
        explanation: list[RiskContribution],
        calculated_at: str,
    ) -> RiskSnapshot:
        snapshot = RiskSnapshot(
            device_id=device_id,
            score=round(score, 3),
            risk_level=risk_level,
            risk_type=risk_type,
            explanation=explanation,
            calculated_at=calculated_at,
        )
        self.risk_snapshots[device_id] = snapshot
        return snapshot

    def _append_risk_history(self, device_id: str, score: float) -> None:
        score = round(max(0.0, min(1.0, score)), 3)
        today = datetime.now(timezone.utc).date().isoformat()
        history = self.risk_history.get(device_id)
        if history is None:
            history = self._build_risk_history(device_id, score)
        if history and history[-1].date == today:
            history[-1] = RiskHistoryPoint(date=today, score=score)
        else:
            history.append(RiskHistoryPoint(date=today, score=score))
        self.risk_history[device_id] = history[-30:]

    @staticmethod
    def _build_risk_history(device_id: str, baseline_score: float) -> list[RiskHistoryPoint]:
        seed = int(device_id[:8], 16)
        today = datetime.now(timezone.utc).date()
        history: list[RiskHistoryPoint] = []
        current = max(0.05, min(0.95, baseline_score))
        for offset in range(29, -1, -1):
            date_value = (today - timedelta(days=offset)).isoformat()
            drift = ((seed + offset * 17) % 11 - 5) / 200
            current = max(0.01, min(0.99, current + drift))
            history.append(RiskHistoryPoint(date=date_value, score=round(current, 3)))
        return history

    def _calculate_dynamic_risk(self, device_id: str) -> float:
        score = 0.18
        try:
            vitals = self.latest_vitals(device_id)
            score += max(0.0, (vitals.heartRate - 72.0) / 220.0)
            score += max(0.0, (96.0 - vitals.spo2) / 35.0)
            score += max(0.0, (vitals.bloodPressureSys - 125.0) / 220.0)
        except KeyError:
            pass

        device = self.devices[device_id]
        if device.battery_level < 20:
            score += 0.06
        if device.state in {"warning", "critical", "fall_countdown", "sos_active"}:
            score += 0.14

        now = datetime.now(timezone.utc)
        for event in reversed(self.event_history):
            if event.device_id != device_id:
                continue
            age = now - datetime.fromisoformat(event.timestamp)
            if age.total_seconds() > 3600:
                break
            if event.severity == "critical":
                score += 0.1
            elif event.severity == "warning":
                score += 0.05
        return round(max(0.0, min(1.0, score)), 3)

    def _build_risk_explanation(self, *, device_id: str, score: float, risk_type: str) -> list[RiskContribution]:
        try:
            vitals = self.latest_vitals(device_id)
            hr = f"{round(vitals.heartRate)} bpm"
            spo2 = f"{round(vitals.spo2)}%"
            bp_sys = f"{round(vitals.bloodPressureSys)} mmHg"
        except KeyError:
            hr = "72 bpm"
            spo2 = "98%"
            bp_sys = "120 mmHg"

        type_weight = {
            "general": 0.08,
            "stroke": 0.11,
            "cardiac": 0.13,
        }.get(risk_type, 0.08)
        baseline_age = 65 if risk_type != "general" else 58

        return [
            RiskContribution(feature="heart_rate", value=hr, weight=0.18, direction="up"),
            RiskContribution(feature="spo2", value=spo2, weight=0.12, direction="up"),
            RiskContribution(feature="blood_pressure_sys", value=bp_sys, weight=0.1, direction="up"),
            RiskContribution(feature="risk_type_bias", value=risk_type, weight=type_weight, direction="up"),
            RiskContribution(feature="age", value=f"{baseline_age} years", weight=0.07, direction="up"),
            RiskContribution(feature="sleep_efficiency", value="~estimated", weight=-0.04, direction="down"),
            RiskContribution(feature="stability_guard", value=f"{score:.2f}", weight=0.03, direction="flat"),
        ]

    @staticmethod
    def _risk_level_from_score(score: float) -> str:
        if score >= 0.85:
            return "CRITICAL"
        if score >= 0.65:
            return "HIGH"
        if score >= 0.4:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _severity_from_risk_level(level: str) -> str:
        mapping = {
            "LOW": "normal",
            "MEDIUM": "warning",
            "HIGH": "warning",
            "CRITICAL": "critical",
        }
        return mapping.get(level.upper(), "warning")

    def _record_event(
        self,
        *,
        device_id: str,
        event_type: str,
        severity: str,
        message: str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.alert_service._record_event(
            device_id=device_id,
            event_type=event_type,
            severity=severity,
            message=message,
            metadata=metadata,
        )
        # HIGH #1 fix: keep the pre-computed 1-hour alert counter in sync.
        if severity in {"warning", "critical"}:
            self._increment_alert_counter()


class _RuntimeHolder:
    """Indirection layer so tests can swap the singleton via
    ``app.dependency_overrides[get_runtime]`` **or** by calling
    ``set_runtime`` / ``reset_runtime_for_tests`` directly.

    This replaces the old bare ``global _runtime_singleton`` pattern
    and makes the codebase compatible with FastAPI's dependency-override
    mechanism used in integration / unit tests.
    """

    __slots__ = ("instance",)

    def __init__(self) -> None:
        self.instance: SimulatorRuntime | None = None

    def get(self) -> SimulatorRuntime:
        if self.instance is None:
            self.instance = SimulatorRuntime()
            # Start background tick only once on first creation.
            # HIGH #5 fix: removed per-request start_background_tick()
            # call that acquired RLock on every HTTP request.
            self.instance.start_background_tick()
        return self.instance

    def set(self, runtime: SimulatorRuntime) -> None:  # noqa: A003
        self.instance = runtime

    def reset(self) -> SimulatorRuntime:
        if self.instance is not None:
            self.instance.shutdown()
        self.instance = SimulatorRuntime()
        return self.instance


_holder = _RuntimeHolder()


def get_runtime() -> SimulatorRuntime:
    """FastAPI dependency — returns the running :class:`SimulatorRuntime`.

    Override in tests::

        from api_server.dependencies import get_runtime

        app.dependency_overrides[get_runtime] = lambda: my_mock_runtime
    """
    return _holder.get()


def set_runtime(runtime: SimulatorRuntime) -> None:
    """Explicitly install a runtime instance (e.g. during app lifespan)."""
    _holder.set(runtime)


def reset_runtime_for_tests() -> None:
    """Tear down & recreate the singleton — kept for backward compat."""
    _holder.reset()
