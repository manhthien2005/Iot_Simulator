from __future__ import annotations

import asyncio
import json as _json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Event, RLock, Thread
from time import monotonic
from typing import Any
from uuid import uuid4
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from sqlalchemy import text

try:
    from api_server.backend_admin_client import BackendAdminClient
    from api_server.db import session_scope
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
    from simulator_core.dataset_registry import DatasetRegistry
    from simulator_core.session import DataBinding as SimDataBinding, SimulatorSession, build_device
    from simulator_core.sleep_ai_client import SleepAIClient
    from simulator_core.sleep_vitals_enricher import enrich_sleep_record
    from transport import HttpPublisher, MqttPublisher, TransportRouter
except ModuleNotFoundError:
    from api_server.backend_admin_client import BackendAdminClient
    from api_server.db import session_scope
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
    from simulator_core.dataset_registry import DatasetRegistry
    from simulator_core.session import DataBinding as SimDataBinding, SimulatorSession, build_device
    from simulator_core.sleep_ai_client import SleepAIClient
    from simulator_core.sleep_vitals_enricher import enrich_sleep_record
    from transport import HttpPublisher, MqttPublisher, TransportRouter

# Pre-model trigger imports — lazy-loaded inside _build_trigger_orchestrator
# to avoid hard dependency when module is missing.
_TRIGGER_AVAILABLE = True
try:
    from pre_model_trigger.orchestrator import TriggerOrchestrator
    from pre_model_trigger.settings_provider import (
        SystemSettingsProvider,
        _FALLBACK_DAYTIME as _PROVIDER_FALLBACK_DAYTIME,
        _FALLBACK_SLEEP as _PROVIDER_FALLBACK_SLEEP,
    )
    from pre_model_trigger.rule_engine import RuleEngine
    from pre_model_trigger.fall_pre_trigger import FallPreTrigger
    from pre_model_trigger.healthguard_client import HealthGuardAPIClient as TriggerAPIClient
    from pre_model_trigger.response_handler import ResponseHandler
    from pre_model_trigger.vitals_buffer import VitalsHistoryBuffer
    from pre_model_trigger.types import PersonaProfile as TriggerPersonaProfile, TriggerActionItem
except ImportError:
    _TRIGGER_AVAILABLE = False
    _PROVIDER_FALLBACK_DAYTIME = None  # type: ignore[assignment]
    _PROVIDER_FALLBACK_SLEEP = None  # type: ignore[assignment]

# Feature flag: when True AND _TRIGGER_AVAILABLE, the trigger orchestrator
# replaces hard-coded threshold logic for severity evaluation and alert
# generation.  When False, the orchestrator runs in shadow-only mode.
_PRE_MODEL_TRIGGER_ENABLED = (
    os.environ.get("PRE_MODEL_TRIGGER_ENABLED", "false").strip().lower()
    in {"1", "true", "yes"}
)


logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _derive_age(value: Any, default: int = 35) -> int:
    dob = _coerce_date(value)
    if dob is None:
        return default
    today = datetime.now(timezone.utc).date()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return max(years, 0)


def _coerce_float(value: Any, default: float) -> float:
    try:
        cast = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(cast) or math.isinf(cast):
        return default
    return cast


def _safe_int(value: Any) -> int | None:
    """Convert *value* to int for DB insertion; return ``None`` on failure."""
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _safe_float_db(value: Any) -> float | None:
    """Convert *value* to float for DB insertion; return ``None`` on failure.

    Handles numpy scalars and arrays transparently — arrays are reduced
    to their mean before conversion so callers never need to worry about
    the underlying storage type coming from the dataset registry.
    """
    if value is None:
        return None
    # --- numpy array / scalar handling ---
    if hasattr(value, "ndim"):  # numpy array or scalar
        import numpy as np  # local import to avoid hard dep at module level
        if isinstance(value, np.ndarray):
            if value.size == 0:
                return None
            value = float(value.mean())
        else:
            # numpy scalar (np.float64, np.int32, etc.)
            value = float(value)
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 4)


def _normalize_gender(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"male", "m", "man", "nam"}:
        return "male"
    if normalized in {"female", "f", "woman", "nu", "nữ"}:
        return "female"
    return normalized


def _build_db_device_persona(device_info: dict[str, Any], db_device_id: int) -> dict[str, Any]:
    return {
        "age": _derive_age(device_info.get("date_of_birth")),
        "weight_kg": _coerce_float(device_info.get("weight_kg"), 70.0),
        "height_cm": _coerce_float(device_info.get("height_cm"), 170.0),
        "gender": _normalize_gender(device_info.get("gender")),
        "seed": db_device_id % 97,
    }


# A-system sleep patterns: scenario phase traces for internal simulator state,
# not the separate DB push profiles used elsewhere in the plan set.
SLEEP_SCENARIO_PHASES: dict[str, list[tuple[str, int]]] = {
    "good_sleep_night": [
        ("light", 35),
        ("deep", 60),
        ("rem", 25),
        ("light", 45),
        ("awake", 10),
        ("deep", 55),
        ("rem", 25),
        ("light", 45),
        ("awake", 7),
        ("rem", 28),
        ("light", 75),
    ],
    "fragmented_sleep": [
        ("light", 20),
        ("awake", 15),
        ("light", 25),
        ("awake", 20),
        ("rem", 15),
        ("light", 25),
        ("awake", 12),
        ("rem", 18),
        ("light", 30),
        ("deep", 15),
        ("light", 25),
    ],
}


SLEEP_SCENARIO_PROFILES: dict[str, dict[str, Any]] = {
    "good_sleep_night": {
        "filter": lambda s: (
            (s.get("summary") or {}).get("sleep_efficiency", 0) > 0.82
            and (s.get("summary") or {}).get("wake_count", 99) <= 2
        ),
        "stats_override": None,
        "phases_pattern_override": None,
        "disorder_tags": [],
        "description": "Giấc ngủ lành mạnh theo chuẩn AASM: deep ≥15%, REM ≥20%, hiệu suất ≥85%",
    },
    "fragmented_sleep": {
        "filter": lambda s: (
            (s.get("summary") or {}).get("wake_count", 0) >= 3
            or (s.get("summary") or {}).get("sleep_efficiency", 1) < 0.78
        ),
        "stats_override": None,
        "phases_pattern_override": [
            "light",
            "awake",
            "light",
            "awake",
            "rem",
            "light",
            "awake",
            "rem",
            "light",
            "deep",
            "light",
        ],
        "disorder_tags": ["arousal"],
        "description": "Giấc ngủ phân mảnh: thức nhiều lần, hiệu suất ~72%",
    },
    "sleep_apnea_mild": {
        "filter": None,
        "stats_override": {
            "sleep_efficiency": 0.76,
            "wake_count": 8,
            "stage_proportions": {"deep": 0.10, "rem": 0.15, "light": 0.59, "awake": 0.16},
            "spo2_min_override": 91.0,
        },
        "phases_pattern_override": [
            "light",
            "rem",
            "light",
            "awake",
            "light",
            "rem",
            "light",
            "awake",
            "deep",
            "light",
        ],
        "disorder_tags": ["osa_mild"],
        "description": "Ngưng thở nhẹ (AHI ~10): SpO2 dip đến 91%, 8 lần thức",
    },
    "sleep_apnea_severe": {
        "filter": None,
        "stats_override": {
            "sleep_efficiency": 0.62,
            "wake_count": 18,
            "stage_proportions": {"deep": 0.05, "rem": 0.08, "light": 0.61, "awake": 0.26},
            "spo2_min_override": 84.0,
        },
        "phases_pattern_override": [
            "light",
            "awake",
            "light",
            "awake",
            "light",
            "rem",
            "awake",
            "light",
            "awake",
            "deep",
            "light",
            "awake",
        ],
        "disorder_tags": ["osa_severe", "trigger_osa_alert"],
        "description": "Ngưng thở nặng (AHI >30): SpO2 xuống 84%, 18 lần thức",
    },
    "insomnia_pattern": {
        "filter": lambda s: ((s.get("summary") or {}).get("sleep_efficiency", 1) < 0.70),
        "stats_override": {
            "sleep_efficiency": 0.63,
            "wake_count": 6,
            "stage_proportions": {"deep": 0.08, "rem": 0.12, "light": 0.65, "awake": 0.15},
            "total_sleep_s_override": 270 * 60,
        },
        "phases_pattern_override": [
            "awake",
            "light",
            "awake",
            "light",
            "rem",
            "awake",
            "light",
            "awake",
            "deep",
            "light",
        ],
        "disorder_tags": ["insomnia"],
        "description": "Mất ngủ kinh niên: ngủ < 5h, hiệu suất 63%, deep/REM thiếu hụt",
    },
    "elderly_normal": {
        "filter": None,
        "stats_override": {
            "stage_proportions": {"deep": 0.11, "rem": 0.19, "light": 0.60, "awake": 0.10},
        },
        "phases_pattern_override": [
            "light",
            "deep",
            "light",
            "rem",
            "light",
            "awake",
            "light",
            "rem",
            "light",
        ],
        "disorder_tags": ["age_related"],
        "description": "Giấc ngủ người cao tuổi bình thường: N3 giảm (~11%), nhiều giai đoạn light hơn",
    },
}


# ---------------------------------------------------------------------------
# Threshold defaults — sourced from pre_model_trigger.settings_provider
# (single source of truth).  When the trigger module is unavailable we
# define identical inline fallbacks so that legacy mode still works.
# ---------------------------------------------------------------------------
if _PROVIDER_FALLBACK_DAYTIME is not None:
    DAYTIME_THRESHOLDS: dict[str, float] = dict(_PROVIDER_FALLBACK_DAYTIME)
else:
    DAYTIME_THRESHOLDS = {
        "hr_critical_low": 50.0, "hr_critical_high": 120.0,
        "hr_warning_low": 55.0, "hr_warning_high": 110.0,
        "spo2_critical": 90.0, "spo2_warning": 94.0,
        "rr_critical_low": 10.0, "rr_critical_high": 25.0,
        "bp_sys_critical": 180.0, "bp_dia_critical": 120.0,
        "bp_sys_warning": 140.0, "bp_dia_warning": 90.0,
    }

if _PROVIDER_FALLBACK_SLEEP is not None:
    SLEEP_THRESHOLDS: dict[str, float] = dict(_PROVIDER_FALLBACK_SLEEP)
else:
    SLEEP_THRESHOLDS = {
        "hr_critical_low": 38.0, "hr_critical_high": 100.0,
        "hr_warning_low": 42.0, "hr_warning_high": 90.0,
        "spo2_critical": 85.0, "spo2_warning": 90.0,
        "rr_critical_low": 6.0, "rr_critical_high": 25.0,
        "bp_sys_critical": 180.0, "bp_dia_critical": 120.0,
        "bp_sys_warning": 160.0, "bp_dia_warning": 100.0,
        "osa_alert_spo2_threshold": 88.0, "nocturnal_tachy_hr": 120.0,
        "apnea_rr_threshold": 6.0,
    }


def _is_sleeping_state(activity_state: Any) -> bool:
    return str(activity_state or "").strip().lower() == "sleeping"


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

    def to_schema(self, current_scenario_id: str | None = None) -> SimulatedDevice:
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
            currentScenarioId=current_scenario_id,
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

    def publish(self, session_id: str, entry: dict[str, Any]) -> None:
        with self._lock:
            history = self._history.setdefault(session_id, [])
            history.append(entry)
            if len(history) > 500:
                history[:] = history[-500:]
            for queue in self._subscribers.get(session_id, []):
                try:
                    queue.put_nowait(entry)
                except asyncio.QueueFull:
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
            pass
        self.devices: dict[str, DeviceRecord] = {}
        self.device_scenarios: dict[str, str] = {}
        self.sessions: dict[str, SessionRecord] = {}
        self.event_history: list[EventRecord] = []
        self.risk_snapshots: dict[str, RiskSnapshot] = {}
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
        self._trigger_orchestrator: TriggerOrchestrator | None = None  # type: ignore[name-defined]
        self._pre_model_trigger_active: bool = False
        self._shadow_tick_count: int = 0
        self._shadow_match_count: int = 0
        self._shadow_mismatch_count: int = 0
        if _TRIGGER_AVAILABLE:
            try:
                enable_calls = _PRE_MODEL_TRIGGER_ENABLED
                self._trigger_orchestrator = self._build_trigger_orchestrator(
                    enable_model_calls=enable_calls,
                )
                self._pre_model_trigger_active = _PRE_MODEL_TRIGGER_ENABLED
                mode_label = "ACTIVE" if self._pre_model_trigger_active else "shadow"
                logger.info("Pre-model trigger orchestrator initialized (%s mode)", mode_label)
            except Exception as exc:
                logger.warning("Pre-model trigger init skipped: %s", exc)

    @staticmethod
    def _resolve_artifacts_dir() -> Path:
        root = Path(__file__).resolve().parents[1]
        artifacts_dir = root / "normalized_artifacts"
        return artifacts_dir

    @staticmethod
    def _resolve_backend_base_url() -> str:
        base_url = os.environ.get("HEALTH_BACKEND_URL", "http://localhost:8000").strip()
        return base_url.rstrip("/") or "http://localhost:8000"

    def _build_trigger_orchestrator(  # type: ignore[name-defined]
        self,
        *,
        enable_model_calls: bool = False,
    ) -> TriggerOrchestrator:
        """Build the pre-model trigger orchestrator with all dependencies.

        Uses lazy imports so the module is optional — callers should catch
        ``Exception`` and fall back to ``None``.

        Args:
            enable_model_calls: When *True* the orchestrator will call
                HealthGuard-AI for health/fall predictions.  When *False*
                (default) only rule evaluation runs — suitable for shadow mode.
        """
        settings_provider = SystemSettingsProvider()  # type: ignore[name-defined]
        rule_engine = RuleEngine(settings_provider=settings_provider)  # type: ignore[name-defined]
        fall_trigger = FallPreTrigger(settings_provider=settings_provider)  # type: ignore[name-defined]
        api_client = TriggerAPIClient(  # type: ignore[name-defined]
            base_url=self._health_backend_url,
            http_sender=self._http_sender,
        )
        vitals_buffer = VitalsHistoryBuffer(max_size=60)  # type: ignore[name-defined]
        return TriggerOrchestrator(  # type: ignore[name-defined]
            settings_provider=settings_provider,
            rule_engine=rule_engine,
            fall_pre_trigger=fall_trigger,
            api_client=api_client,
            response_handler=ResponseHandler,  # type: ignore[name-defined]
            vitals_buffer=vitals_buffer,
            enable_model_calls=enable_model_calls,
        )

    def _get_trigger_persona(self, device_id: str) -> TriggerPersonaProfile:  # type: ignore[name-defined]
        """Build a PersonaProfile for the trigger engine from device persona_config."""
        device = self.devices.get(device_id)
        persona_cfg = (device.persona_config if device else None) or {}
        return TriggerPersonaProfile(  # type: ignore[name-defined]
            age=int(persona_cfg.get("age", 35)),
            gender=str(persona_cfg.get("gender", "unknown")).lower(),
            weight_kg=float(persona_cfg.get("weight_kg", 70.0)),
            height_cm=float(persona_cfg.get("height_cm", 170.0)),
            medical_conditions=list(persona_cfg.get("medical_conditions") or []),
        )

    def _log_shadow_comparison(
        self,
        device_id: str,
        shadow_actions: list[TriggerActionItem],  # type: ignore[name-defined]
        existing_effects: SessionSideEffects,
    ) -> None:
        """Compare shadow trigger results with existing alert logic (T2.3).

        Logs MATCH/MISMATCH between the old hard-coded alert system and the
        new DB-driven trigger engine.  Shadow mode never affects behavior.
        """
        self._shadow_tick_count += 1
        old_has_alert = bool(existing_effects.pending_alerts)
        new_has_alert = any(a.action_type == "alert" for a in shadow_actions)
        new_has_urgent = any(
            a.action_type == "alert" and a.severity in {"critical", "urgent"}
            for a in shadow_actions
        )
        if old_has_alert == new_has_alert:
            self._shadow_match_count += 1
            # Sample MATCH logs at 1-in-20 to avoid noise
            if self._shadow_tick_count % 20 == 0:
                logger.debug(
                    "[shadow] MATCH device=%s tick=%d (match_rate=%.1f%%)",
                    device_id,
                    self._shadow_tick_count,
                    self._shadow_match_count / max(self._shadow_tick_count, 1) * 100,
                )
        else:
            self._shadow_mismatch_count += 1
            old_types = [a.event_type for a in existing_effects.pending_alerts]
            new_types = [a.action_type for a in shadow_actions]
            logger.info(
                "[shadow] MISMATCH device=%s old_alert=%s new_alert=%s "
                "old_types=%s new_types=%s tick=%d",
                device_id,
                old_has_alert,
                new_has_alert,
                old_types,
                new_types,
                self._shadow_tick_count,
            )
        if new_has_urgent and not old_has_alert:
            logger.warning(
                "[shadow] NEW_URGENT device=%s — new engine detected urgent but old logic did not alert",
                device_id,
            )

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
        request = Request(
            endpoint,
            data=payload.encode("utf-8"),
            method="POST",
            headers=request_headers,
        )
        try:
            with urlopen(request, timeout=10) as response:
                return int(response.getcode() or 200)
        except HTTPError as exc:
            return int(exc.code)

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

    def _prepare_alert_push_locked(
        self,
        sim_device_id: str,
        event_type: str,
        severity: str,
        metadata: dict[str, Any] | None = None,
    ) -> PreparedAlertPush | None:
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
        try:
            status_code = self._http_sender(endpoint, prepared.payload_json)
        except Exception as exc:
            with self._lock:
                self._alert_pushes_in_flight.discard(prepared.signature)
            self._publish_device_log(
                prepared.sim_device_id,
                level="ERROR",
                message=f"alert push failed: {prepared.event_type}/{prepared.severity} ({exc})",
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
            return

    def _execute_pending_tick_publish(self, pending_publish: PendingTickPublish | None) -> None:
        if pending_publish is None:
            return

        publish_started = monotonic()
        ack_count = 0
        message_count = len(pending_publish.messages)
        synced_device_ids: set[int] = set()

        try:
            with session_scope() as db:
                for msg in pending_publish.messages:
                    db_device_id = msg.get("db_device_id")
                    if db_device_id is None:
                        continue
                    emitted_at = msg.get("emitted_at") or _utc_now_iso()
                    vitals = msg.get("vitals") or {}

                    db.execute(
                        text(
                            "INSERT INTO vitals "
                            "(time, device_id, heart_rate, spo2, temperature, "
                            "blood_pressure_sys, blood_pressure_dia, hrv, "
                            "respiratory_rate, signal_quality, motion_artifact) "
                            "VALUES (:ts, :dev, :hr, :spo2, :temp, :sys, :dia, "
                            ":hrv, :rr, :sq, :ma)"
                        ),
                        {
                            "ts": emitted_at,
                            "dev": int(db_device_id),
                            "hr": _safe_int(vitals.get("heart_rate")),
                            "spo2": _safe_float_db(vitals.get("spo2")),
                            "temp": _safe_float_db(vitals.get("temperature")),
                            "sys": _safe_int(vitals.get("blood_pressure_sys")),
                            "dia": _safe_int(vitals.get("blood_pressure_dia")),
                            "hrv": _safe_int(vitals.get("hrv")),
                            "rr": _safe_int(vitals.get("respiratory_rate")),
                            "sq": None,
                            "ma": None,
                        },
                    )
                    synced_device_ids.add(int(db_device_id))
                    ack_count += 1
                for db_device_id in synced_device_ids:
                    db.execute(
                        text(
                            "UPDATE devices "
                            "SET last_sync_at = NOW(), updated_at = NOW() "
                            "WHERE id = :device_id AND deleted_at IS NULL"
                        ),
                        {"device_id": db_device_id},
                    )
                db.commit()
        except Exception:
            ack_count = 0
            logger.warning("Direct DB write failed for tick publish", exc_info=True)

        publish_ok = ack_count == message_count if message_count > 0 else False

        publish_latency_ms = max(0, int(round((monotonic() - publish_started) * 1000)))

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

    @staticmethod
    def _local_database_healthy() -> bool:
        try:
            with session_scope() as db:
                db.execute(text("SELECT 1")).scalar()
            return True
        except Exception:
            return False

    def _backend_healthy(self) -> bool:
        endpoint = f"{self._health_backend_url.rstrip('/')}/mobile/health"
        request = Request(endpoint, method="GET")
        try:
            with urlopen(request, timeout=3) as response:
                return int(response.getcode() or 0) == 200
        except Exception:
            return False

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

    def _get_device_engine(self, device_id: str) -> Any | None:
        for session in self.sessions.values():
            if session.status != "running" or device_id not in session.device_ids:
                continue
            for device in session.simulator.devices:
                if device.device_id == device_id:
                    return device.engine
        return None

    def _advance_sleep_phase_if_due(self, device_id: str) -> None:
        scenario_id = self.device_scenarios.get(device_id)
        if scenario_id not in SLEEP_SCENARIO_PHASES:
            self._sleep_phase_tracker.pop(device_id, None)
            return

        engine = self._get_device_engine(device_id)
        if engine is None or engine.state.activity_state != "sleeping":
            self._sleep_phase_tracker.pop(device_id, None)
            return

        schedule = SLEEP_SCENARIO_PHASES[scenario_id]
        now = monotonic()

        if device_id not in self._sleep_phase_tracker:
            self._sleep_phase_tracker[device_id] = (0, now)

        phase_idx, phase_started_at = self._sleep_phase_tracker[device_id]
        if phase_idx >= len(schedule):
            engine.inject_event("sleep_end", None)
            self._sleep_phase_tracker.pop(device_id, None)
            return

        _, phase_duration_minutes = schedule[phase_idx]
        elapsed_seconds = now - phase_started_at
        phase_duration_seconds = phase_duration_minutes * 60
        try:
            speed_factor = float(os.environ.get("SIM_SLEEP_SPEED_FACTOR", "60"))
        except (TypeError, ValueError):
            speed_factor = 60.0
        if speed_factor <= 0:
            speed_factor = 60.0
        phase_duration_sim_seconds = phase_duration_seconds / speed_factor
        if elapsed_seconds < phase_duration_sim_seconds:
            return

        next_idx = phase_idx + 1
        if next_idx >= len(schedule):
            engine.inject_event("sleep_end", None)
            self._sleep_phase_tracker.pop(device_id, None)
            return

        current_phase, _ = schedule[phase_idx]
        next_phase, _ = schedule[next_idx]
        engine.inject_event("sleep_phase_change", next_phase)
        self._sleep_phase_tracker[device_id] = (next_idx, now)
        self._publish_device_log(
            device_id,
            level="DEBUG",
            message=f"Sleep phase advanced: {current_phase} -> {next_phase}",
            timestamp=_utc_now_iso(),
        )

    @staticmethod
    def _compute_sleep_window(duration_minutes: int) -> tuple[date, datetime, datetime]:
        """
        Return a stable `(sleep_date, start_time, end_time)` window for sleep pushes.

        Rules:
        - Always assign the sleep session to yesterday to avoid future-dated payloads
        - Start between 21:00 and 01:00 UTC (inclusive) based on a random minute offset
        - End at `start_time + duration_minutes`
        - Clamp the end time to `now` and never move the recomputed start before 20:00 UTC
        """
        import random as _random

        duration = max(1, int(duration_minutes))
        now = datetime.now(timezone.utc)
        yesterday = (now - timedelta(days=1)).date()

        start_floor = datetime(
            yesterday.year,
            yesterday.month,
            yesterday.day,
            21,
            0,
            0,
            tzinfo=timezone.utc,
        )
        start_time = start_floor + timedelta(minutes=_random.randint(0, 240))
        end_time = start_time + timedelta(minutes=duration)

        absolute_floor = datetime(
            yesterday.year,
            yesterday.month,
            yesterday.day,
            20,
            0,
            0,
            tzinfo=timezone.utc,
        )
        if end_time > now:
            end_time = now
            start_time = max(end_time - timedelta(minutes=duration), absolute_floor)

        return yesterday, start_time, end_time

    @staticmethod
    def _compute_sleep_window_for_date(target_date: date, duration_minutes: int) -> tuple[date, datetime, datetime]:
        import random as _random

        duration = max(1, int(duration_minutes))
        start_floor = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            21,
            0,
            0,
            tzinfo=timezone.utc,
        )
        start_time = start_floor + timedelta(minutes=_random.randint(0, 240))
        end_time = start_time + timedelta(minutes=duration)
        return target_date, start_time, end_time

    @staticmethod
    def _phase_minutes_from_segments(
        phases: list[SleepStageSegment],
        fallback_duration_minutes: int | None = None,
    ) -> tuple[dict[str, int], int]:
        phases_dict: dict[str, int] = {}
        for seg in phases:
            try:
                start = datetime.fromisoformat(seg.start.replace("Z", "+00:00"))
                end = datetime.fromisoformat(seg.end.replace("Z", "+00:00"))
                minutes = max(0, int((end - start).total_seconds() // 60))
                stage = str(seg.stage)
                phases_dict[stage] = phases_dict.get(stage, 0) + minutes
            except Exception:
                continue

        if not phases_dict:
            phases_dict = {"awake": 30, "light": 180, "deep": 90, "rem": 60}

        duration_minutes = sum(phases_dict.values())
        if duration_minutes <= 0:
            try:
                duration_minutes = int(fallback_duration_minutes or 0)
            except (TypeError, ValueError):
                duration_minutes = 1
        return phases_dict, max(1, duration_minutes)

    def _push_sleep_to_backend(
        self,
        sim_device_id: str,
        sleep_resp: SleepSessionResponse,
        user_id: int | None = None,
    ) -> None:
        with self._lock:
            device = self.devices.get(sim_device_id)
            bound_db_device_id = device.bound_db_device_id if device is not None else None
        if bound_db_device_id is None:
            return
        resolved_user_id = user_id if user_id is not None else self._resolve_bound_device_user_id(bound_db_device_id)
        if resolved_user_id is None:
            self._publish_device_log(
                sim_device_id,
                level="ERROR",
                message=f"Sleep push failed: no owner found for db_device_id={bound_db_device_id}",
                timestamp=_utc_now_iso(),
            )
            return

        phases_dict, duration_minutes = self._phase_minutes_from_segments(
            sleep_resp.phases,
            fallback_duration_minutes=sleep_resp.durationMinutes,
        )
        sleep_date, start_time, end_time = self._compute_sleep_window(duration_minutes)

        payload = {
            "db_device_id": bound_db_device_id,
            "user_id": resolved_user_id,
            "date": sleep_date.isoformat(),
            "score": sleep_resp.score,
            "efficiency": sleep_resp.efficiency,
            "duration_minutes": duration_minutes,
            "phases": phases_dict,
            "start_time": start_time.isoformat().replace("+00:00", "Z"),
            "end_time": end_time.isoformat().replace("+00:00", "Z"),
        }
        # ---------------------------------------------------------------
        # Sleep Telemetry — DB Storage (port 8000, health_system backend)
        # ---------------------------------------------------------------
        # This endpoint persists sleep session data to the PostgreSQL DB
        # via health_system backend on port 8000.
        #
        # AI-based sleep stage inference is handled separately by
        # SleepAIClient (simulator_core/sleep_ai_client.py) which targets
        # healthguard-model-api on port 8001.
        #
        # Dual-endpoint design is intentional:
        #   - Port 8001 → AI inference (sleep stage classification)
        #   - Port 8000 → DB storage  (sleep session persistence)
        # ---------------------------------------------------------------
        endpoint = f"{self._health_backend_url}/mobile/telemetry/sleep"
        try:
            req = Request(
                endpoint,
                data=_json.dumps(payload).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=5) as resp:
                code = int(resp.getcode() or 200)
            self._publish_device_log(
                sim_device_id,
                level="INFO",
                message=f"Sleep push OK: HTTP {code} | date={sleep_date.isoformat()} | duration={duration_minutes}min",
                timestamp=_utc_now_iso(),
            )
        except Exception as exc:
            self._publish_device_log(
                sim_device_id,
                level="ERROR",
                message=f"Sleep push failed: {exc}",
                timestamp=_utc_now_iso(),
            )

    def _sleep_session_exists(
        self,
        *,
        db_device_id: int,
        user_id: int,
        target_date: date,
    ) -> bool:
        try:
            with session_scope() as db:
                result = db.execute(
                    text(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM sleep_sessions
                            WHERE user_id = :user_id
                              AND device_id = :device_id
                              AND sleep_date = CAST(:sleep_date AS DATE)
                        )
                        """
                    ),
                    {
                        "user_id": user_id,
                        "device_id": db_device_id,
                        "sleep_date": target_date.isoformat(),
                    },
                ).scalar()
        except Exception:
            return False
        return bool(result)

    @staticmethod
    def _coerce_phase_minutes_dict(phases_raw: Any) -> dict[str, int]:
        if isinstance(phases_raw, str):
            try:
                phases_data = _json.loads(phases_raw)
            except ValueError:
                phases_data = {}
        elif isinstance(phases_raw, dict):
            phases_data = phases_raw
        else:
            phases_data = {}

        normalized: dict[str, int] = {}
        for stage in ("deep", "light", "rem", "awake"):
            try:
                value = int(round(float(phases_data.get(stage, 0) or 0)))
            except (TypeError, ValueError):
                value = 0
            normalized[stage] = max(0, value)
        return normalized

    @staticmethod
    def _coerce_datetime_value(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        return None

    @staticmethod
    def _datetime_to_iso(value: datetime | None) -> str:
        if value is None:
            return ""
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def sleep_db_history(self, device_id: str, days: int = 30) -> list[DbSleepHistoryRow]:
        with self._lock:
            device = self._require_device(device_id)
            bound_db_device_id = device.bound_db_device_id

        if bound_db_device_id is None:
            return []

        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)
        try:
            with session_scope() as db:
                rows = db.execute(
                    text(
                        """
                        SELECT
                            sleep_date,
                            start_time,
                            end_time,
                            sleep_score,
                            phases,
                            wake_count
                        FROM sleep_sessions
                        WHERE device_id = :device_id
                          AND sleep_date >= CAST(:cutoff_date AS DATE)
                        ORDER BY sleep_date DESC
                        LIMIT 90
                        """
                    ),
                    {
                        "device_id": bound_db_device_id,
                        "cutoff_date": cutoff_date.isoformat(),
                    },
                ).fetchall()
        except Exception:
            return []

        records: list[DbSleepHistoryRow] = []
        for row in rows:
            phases = self._coerce_phase_minutes_dict(getattr(row, "phases", None))
            fallback_duration = sum(phases.values())
            start_time = self._coerce_datetime_value(getattr(row, "start_time", None))
            end_time = self._coerce_datetime_value(getattr(row, "end_time", None))
            duration_minutes = fallback_duration
            if start_time is not None and end_time is not None:
                duration_minutes = max(0, int(round((end_time - start_time).total_seconds() / 60)))
            if duration_minutes <= 0:
                duration_minutes = fallback_duration

            awake_minutes = max(0, phases.get("awake", 0))
            asleep_minutes = max(0, duration_minutes - awake_minutes)
            efficiency = round((asleep_minutes / duration_minutes) * 100, 1) if duration_minutes > 0 else 0.0

            try:
                wake_count = int(getattr(row, "wake_count", 0) or 0)
            except (TypeError, ValueError):
                wake_count = 0
            if wake_count <= 0 and awake_minutes > 0:
                wake_count = max(1, awake_minutes // 30)

            sleep_date = _coerce_date(getattr(row, "sleep_date", None))
            if sleep_date is None and start_time is not None:
                sleep_date = start_time.date()
            if sleep_date is None:
                sleep_date = datetime.now(timezone.utc).date()

            try:
                score = int(getattr(row, "sleep_score", 0) or 0)
            except (TypeError, ValueError):
                score = 0

            records.append(
                DbSleepHistoryRow(
                    date=sleep_date.isoformat(),
                    score=score,
                    efficiency=efficiency,
                    durationMinutes=duration_minutes,
                    wakeCount=wake_count,
                    phases=phases,
                    startTime=self._datetime_to_iso(start_time),
                    endTime=self._datetime_to_iso(end_time),
                )
            )

        return records

    @staticmethod
    def _compute_sleep_score_from_summary(summary: dict[str, Any]) -> int:
        efficiency_ratio = SimulatorRuntime._safe_float(summary.get("sleep_efficiency"), 0.0)
        if efficiency_ratio is None:
            efficiency_ratio = 0.0
        if efficiency_ratio > 1:
            efficiency_ratio /= 100
        efficiency_ratio = max(0.0, min(1.0, efficiency_ratio))
        stage_props = summary.get("stage_proportions") or {}
        deep_ratio = SimulatorRuntime._safe_float(stage_props.get("deep"), 0.0)
        if deep_ratio is None:
            deep_ratio = 0.0
        if deep_ratio > 1:
            deep_ratio /= 100
        deep_ratio = max(0.0, min(1.0, deep_ratio))
        wake_count = int(summary.get("wake_count") or 0)
        return max(0, min(100, round(25 + efficiency_ratio * 55 + deep_ratio * 20 - min(wake_count, 8) * 2.5)))

    def _build_sleep_ai_record(
        self,
        *,
        scenario_id: str,
        summary: dict[str, Any],
        phases_dict: dict[str, int],
        duration_minutes: int,
        sleep_date: date,
        start_time: datetime,
        end_time: datetime,
        user_id: int,
        persona_config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        scenario_defaults: dict[str, dict[str, float | int | str]] = {
            "good_sleep_night": {
                "sleep_latency_minutes": 12.0,
                "step_count_day": 7600.0,
                "caffeine_mg": 80.0,
                "alcohol_units": 0.0,
                "medication_flag": 0.0,
                "jetlag_hours": 0.0,
                "timezone": "Asia/Bangkok",
                "bedtime_consistency_std_min": 18.0,
                "stress_score": 27.0,
                "activity_before_bed_min": 20.0,
                "screen_time_before_bed_min": 35.0,
                "insomnia_flag": 0.0,
                "apnea_risk_score": 14.0,
                "nap_duration_minutes": 0.0,
                "device_model": "VSmartwatch Simulator",
            },
            "fragmented_sleep": {
                "sleep_latency_minutes": 22.0,
                "step_count_day": 5600.0,
                "caffeine_mg": 120.0,
                "alcohol_units": 0.5,
                "medication_flag": 0.0,
                "jetlag_hours": 0.0,
                "timezone": "Asia/Bangkok",
                "bedtime_consistency_std_min": 42.0,
                "stress_score": 54.0,
                "activity_before_bed_min": 12.0,
                "screen_time_before_bed_min": 62.0,
                "insomnia_flag": 1.0,
                "apnea_risk_score": 30.0,
                "nap_duration_minutes": 18.0,
                "device_model": "VSmartwatch Simulator",
            },
            "sleep_apnea_mild": {
                "sleep_latency_minutes": 18.0,
                "step_count_day": 5100.0,
                "caffeine_mg": 100.0,
                "alcohol_units": 0.5,
                "medication_flag": 0.0,
                "jetlag_hours": 0.0,
                "timezone": "Asia/Bangkok",
                "bedtime_consistency_std_min": 34.0,
                "stress_score": 60.0,
                "activity_before_bed_min": 15.0,
                "screen_time_before_bed_min": 50.0,
                "insomnia_flag": 0.0,
                "apnea_risk_score": 64.0,
                "nap_duration_minutes": 12.0,
                "device_model": "VSmartwatch Simulator",
            },
            "sleep_apnea_severe": {
                "sleep_latency_minutes": 20.0,
                "step_count_day": 4200.0,
                "caffeine_mg": 90.0,
                "alcohol_units": 0.0,
                "medication_flag": 0.0,
                "jetlag_hours": 0.0,
                "timezone": "Asia/Bangkok",
                "bedtime_consistency_std_min": 45.0,
                "stress_score": 68.0,
                "activity_before_bed_min": 5.0,
                "screen_time_before_bed_min": 40.0,
                "insomnia_flag": 0.0,
                "apnea_risk_score": 92.0,
                "nap_duration_minutes": 24.0,
                "device_model": "VSmartwatch Simulator",
            },
        }
        defaults = scenario_defaults.get(scenario_id, scenario_defaults["fragmented_sleep"])
        persona = dict(persona_config or {})
        enriched = enrich_sleep_record(scenario_id, summary, persona)
        total_minutes = max(1, int(duration_minutes))
        awake_minutes = max(0, int(phases_dict.get("awake", 0)))
        asleep_minutes = max(1, total_minutes - awake_minutes)

        sleep_efficiency = self._safe_float(summary.get("sleep_efficiency"), None)
        if sleep_efficiency is None:
            sleep_efficiency_pct = round((asleep_minutes / total_minutes) * 100.0, 1)
        else:
            sleep_efficiency_pct = round(sleep_efficiency * 100.0 if sleep_efficiency <= 1 else sleep_efficiency, 1)

        def _pct(stage: str) -> float:
            return round((max(0, float(phases_dict.get(stage, 0))) / total_minutes) * 100.0, 1)

        def _float_value(key: str, default: float) -> float:
            raw = persona.get(key, defaults.get(key, default))
            value = self._safe_float(raw, default)
            return float(default if value is None else value)

        def _int_value(key: str, default: int) -> int:
            raw = persona.get(key, defaults.get(key, default))
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default

        gender = _normalize_gender(persona.get("gender")) or "female"
        timezone_name = str(persona.get("timezone") or defaults["timezone"])
        device_model = str(persona.get("device_model") or defaults["device_model"])
        wake_count = int(summary.get("wake_count") or 0)

        return {
            "user_id": str(user_id),
            "date_recorded": sleep_date.isoformat(),
            "sleep_start_timestamp": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "sleep_end_timestamp": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_minutes": float(total_minutes),
            "sleep_latency_minutes": _float_value("sleep_latency_minutes", 15.0),
            "wake_after_sleep_onset_minutes": float(awake_minutes),
            "sleep_efficiency_pct": sleep_efficiency_pct,
            "sleep_stage_deep_pct": _pct("deep"),
            "sleep_stage_light_pct": _pct("light"),
            "sleep_stage_rem_pct": _pct("rem"),
            "sleep_stage_awake_pct": _pct("awake"),
            **enriched,
            "step_count_day": _float_value("step_count_day", 6000.0),
            "caffeine_mg": _float_value("caffeine_mg", 80.0),
            "alcohol_units": _float_value("alcohol_units", 0.0),
            "medication_flag": _float_value("medication_flag", 0.0),
            "jetlag_hours": _float_value("jetlag_hours", 0.0),
            "timezone": timezone_name,
            "age": float(_int_value("age", 35)),
            "gender": gender,
            "weight_kg": _float_value("weight_kg", 70.0),
            "height_cm": _float_value("height_cm", 170.0),
            "device_model": device_model,
            "bedtime_consistency_std_min": _float_value("bedtime_consistency_std_min", 25.0),
            "stress_score": _float_value("stress_score", 40.0),
            "activity_before_bed_min": _float_value("activity_before_bed_min", 15.0),
            "screen_time_before_bed_min": _float_value("screen_time_before_bed_min", 45.0),
            "insomnia_flag": _float_value("insomnia_flag", 0.0),
            "apnea_risk_score": _float_value("apnea_risk_score", 20.0),
            "nap_duration_minutes": _float_value("nap_duration_minutes", 0.0),
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "wake_count": wake_count,
            "scenario_id": scenario_id,
        }

    def _compute_sleep_score_with_ai(self, sleep_ai_record: dict) -> int:
        client = getattr(self, "_sleep_ai_client", None)
        if client is not None:
            result = client.predict(sleep_ai_record)
            predicted = self._safe_float((result or {}).get("predicted_sleep_score"), None) if isinstance(result, dict) else None
            if predicted is not None:
                score = max(0, min(100, int(round(predicted))))
                self._last_sleep_score_source = "ai"
                logger.info("Sleep AI score: %s", score)
                return score

        fallback_summary = {
            "sleep_efficiency": (self._safe_float(sleep_ai_record.get("sleep_efficiency_pct"), 0.0) or 0.0) / 100.0,
            "stage_proportions": {
                "deep": (self._safe_float(sleep_ai_record.get("sleep_stage_deep_pct"), 0.0) or 0.0) / 100.0,
            },
            "wake_count": int(sleep_ai_record.get("wake_count") or 0),
        }
        fallback_score = self._compute_sleep_score_from_summary(fallback_summary)
        self._last_sleep_score_source = "heuristic"
        logger.warning("Sleep AI unavailable — using heuristic fallback score: %s", fallback_score)
        return fallback_score

    def _post_sleep_payload(self, *, payload: dict[str, Any], device_id: str) -> tuple[bool, int]:
        # ---------------------------------------------------------------
        # Sleep Telemetry — DB Storage (port 8000, health_system backend)
        # ---------------------------------------------------------------
        # This endpoint persists sleep session data to the PostgreSQL DB
        # via health_system backend on port 8000.
        #
        # AI-based sleep stage inference is handled separately by
        # SleepAIClient (simulator_core/sleep_ai_client.py) which targets
        # healthguard-model-api on port 8001.
        #
        # Dual-endpoint design is intentional:
        #   - Port 8001 → AI inference (sleep stage classification)
        #   - Port 8000 → DB storage  (sleep session persistence)
        # ---------------------------------------------------------------
        endpoint = f"{self._health_backend_url}/mobile/telemetry/sleep"
        req = Request(
            endpoint,
            data=_json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=5) as resp:
            code = int(resp.getcode() or 200)
            raw_body = resp.read().decode("utf-8", "replace").strip()
        if raw_body:
            try:
                body = _json.loads(raw_body)
            except ValueError:
                body = None
            if isinstance(body, dict):
                errors = body.get("errors")
                if isinstance(errors, list) and errors:
                    raise RuntimeError(f"Backend sleep ingest errors: {'; '.join(str(item) for item in errors)}")
                ingested = body.get("ingested")
                if ingested is not None:
                    try:
                        if int(ingested) <= 0:
                            raise RuntimeError("Backend sleep ingest reported 0 rows written")
                    except (TypeError, ValueError):
                        raise RuntimeError(f"Backend sleep ingest returned invalid ingested value: {ingested!r}")
        return 200 <= code < 300, code

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

    def list_devices(self) -> list[SimulatedDevice]:
        with self._lock:
            return [
                device.to_schema(current_scenario_id=self.device_scenarios.get(device.id))
                for device in self.devices.values()
            ]

    def create_device(self, request: CreateDeviceRequest) -> SimulatedDevice:
        with self._lock:
            device_id = uuid4().hex
            serial = f"SIM-{device_id[:8].upper()}"
            mqtt_client = f"sim-client-{device_id[:8]}"
            device = DeviceRecord(
                id=device_id,
                name=request.name,
                serial_number=serial,
                mqtt_client_id=mqtt_client,
                device_type=request.type,
                persona_config=request.persona_config.model_dump(),
                data_binding=request.data_binding.model_dump() if request.data_binding else None,
            )
            self.devices[device_id] = device
            self.device_scenarios[device_id] = "normal_rest"
            return device.to_schema(current_scenario_id=self.device_scenarios.get(device_id))

    def delete_device(self, device_id: str) -> None:
        with self._lock:
            self.devices.pop(device_id, None)
            self.device_scenarios.pop(device_id, None)
            self.risk_snapshots.pop(device_id, None)
            self.risk_history.pop(device_id, None)
            self._tick_buffer = [payload for payload in self._tick_buffer if payload.get("device_id") != device_id]
            self._refresh_pending_sync_flags()
            for session in self.sessions.values():
                if device_id in session.device_ids:
                    session.device_ids = [item for item in session.device_ids if item != device_id]
            self._rebuild_db_device_active_cache_locked()
            self._record_event(
                device_id=device_id,
                event_type="device_deleted",
                severity="offline",
                message="Device removed from simulator runtime",
            )

    def bind_device(self, sim_device_id: str, db_device_id: int) -> DeviceRecord:
        with self._lock:
            device = self._require_device(sim_device_id)
            device.bound_db_device_id = db_device_id
            device.bind_status = "bound"
            if device.state in {"draft", "provisioned", "bindable", "bound"}:
                device.state = "bound"
            self._rebuild_db_device_active_cache_locked()
            return device

    def unbind_device(self, sim_device_id: str) -> DeviceRecord:
        with self._lock:
            device = self._require_device(sim_device_id)
            device.bound_db_device_id = None
            device.bind_status = "unbound"
            if device.state == "bound":
                device.state = "bindable"
            self._tick_buffer = [payload for payload in self._tick_buffer if payload.get("device_id") != sim_device_id]
            self._refresh_pending_sync_flags()
            self._rebuild_db_device_active_cache_locked()
            return device

    # ===========================================================================
    # Admin Methods — Device Management via Backend DB
    # ===========================================================================

    def admin_list_db_devices(self) -> list[dict[str, Any]]:
        """Load toàn bộ devices từ backend DB."""
        return self.admin_client.list_devices()

    def admin_find_user(self, email: str) -> dict[str, Any] | None:
        """Tìm user theo email. Dùng trước khi bind."""
        return self.admin_client.find_user_by_email(email)

    def admin_create_db_device(
        self,
        device_name: str,
        device_type: str = "smartwatch",
        serial_number: str | None = None,
        user_email: str | None = None,
    ) -> dict[str, Any]:
        """
        Tạo device mới trong backend DB.
        Auto-gen serial_number và mqtt_client_id nếu không truyền.
        """
        suffix = str(int(time.time()))[-6:]
        safe_name = "".join(ch if ch.isalnum() else "-" for ch in device_name.lower()).strip("-") or "device"
        auto_mqtt = f"sim-{safe_name}-{suffix}"
        auto_serial = serial_number or f"SIM-{auto_mqtt.upper()[:12]}"
        return self.admin_client.create_device(
            device_name=device_name,
            device_type=device_type,
            serial_number=auto_serial,
            mqtt_client_id=auto_mqtt,
            user_email=user_email,
        )

    def admin_assign_db_device(self, device_id: int, user_email: str) -> dict[str, Any]:
        """Bind device (đã có trong DB) cho user bằng email."""
        return self.admin_client.assign_device(device_id, user_email)

    def admin_activate_db_device(self, device_id: int) -> dict[str, Any]:
        """
        Kích hoạt device trong DB (is_active=True, single-active rule).
        Tự động tạo SimDevice + Session cho device này nếu chưa có.
        """
        result = self.admin_client.activate_device(device_id)
        self._ensure_sim_session_for_db_device(device_id, result)
        return result

    def admin_deactivate_db_device(self, device_id: int) -> dict[str, Any]:
        """Tắt device. Dừng session simulator đang chạy."""
        result = self.admin_client.deactivate_device(device_id)
        self._stop_sim_session_for_db_device(device_id)
        return result

    def admin_delete_db_device(self, device_id: int) -> None:
        """Xóa device khỏi DB (soft delete). Dừng session nếu đang chạy."""
        self._stop_sim_session_for_db_device(device_id)
        self.admin_client.delete_device(device_id)

    # ── Admin Helpers ────────────────────────────────────────────────────────────

    def _find_sim_id_for_db_device(self, db_device_id: int) -> str | None:
        """Tìm sim_device_id đang map với db_device_id."""
        for sim_id, device in self.devices.items():
            if device.bound_db_device_id == db_device_id:
                return sim_id
        return None

    def _find_running_session_for_sim_device(self, sim_id: str) -> SessionRecord | None:
        """Tìm session đang running có chứa sim_id."""
        for record in self.sessions.values():
            if sim_id in record.device_ids and record.status == "running":
                return record
        return None

    def _rebuild_db_device_active_cache_locked(self) -> None:
        active_db_device_ids: dict[int, bool] = {}
        for record in self.sessions.values():
            if record.status != "running":
                continue
            for sim_id in record.device_ids:
                device = self.devices.get(sim_id)
                if device is None or device.bound_db_device_id is None:
                    continue
                active_db_device_ids[device.bound_db_device_id] = True
        self._db_device_active_cache = active_db_device_ids

    def list_running_db_device_ids(self) -> set[int]:
        with self._lock:
            return set(self._db_device_active_cache)

    def is_db_device_sim_running(self, db_device_id: int) -> bool:
        """
        Returns True nếu có SimDevice bound với db_device_id này
        VÀ đang có session running push vitals.
        Thread-safe — dùng self._lock.
        Không gọi DB — chỉ đọc in-memory state.
        """
        with self._lock:
            return self._db_device_active_cache.get(db_device_id, False)

    def _ensure_sim_session_for_db_device(self, db_device_id: int, device_info: dict[str, Any]) -> None:
        """
        Khi DB device được activate:
        1. Stop các running sessions của các DB devices KHÁC cùng user.
           Lý do: DB đã apply single-active rule trong phạm vi user hiện tại,
           nên runtime chỉ được stop session của những device cùng user đó.
        2. Tìm hoặc tạo SimDevice với bound_db_device_id = db_device_id.
        3. Start session mới nếu chưa có session running.
        """
        same_user_other_db_device_ids: set[int] = set()
        user_id_raw = device_info.get("user_id")
        try:
            user_id = int(user_id_raw) if user_id_raw is not None else None
        except (TypeError, ValueError):
            user_id = None

        if user_id is not None:
            with session_scope() as db:
                same_user_devices = SimAdminService.list_all_devices(db, user_id=user_id)
            same_user_other_db_device_ids = {
                int(device["id"])
                for device in same_user_devices
                if int(device["id"]) != db_device_id
            }

        persona = _build_db_device_persona(device_info, db_device_id)

        session_id_to_start: str | None = None
        with self._lock:
            # ── Step 1: Stop các running sessions của device KHÁC cùng user ──────
            # Chỉ stop những SimDevices đang bound với DB devices khác cùng user.
            # Không đụng đến session của user khác đang chạy trong cùng process.
            for sim_id_other, dev_record in list(self.devices.items()):
                bound_db_device_id = dev_record.bound_db_device_id
                if bound_db_device_id is None or bound_db_device_id not in same_user_other_db_device_ids:
                    continue
                running = self._find_running_session_for_sim_device(sim_id_other)
                if running is not None:
                    self.stop_session(running.id)

            # ── Step 2: Tìm hoặc tạo SimDevice ───────────────────────────────────
            sim_id = self._find_sim_id_for_db_device(db_device_id)
            if sim_id is None:
                request = CreateDeviceRequest(
                    name=str(device_info.get("device_name") or f"DBDevice-{db_device_id}"),
                    type=str(device_info.get("device_type") or "smartwatch"),
                    persona_config=persona,
                )
                sim_device_schema = self.create_device(request)
                sim_id = sim_device_schema.id
                sim_record = self.bind_device(sim_id, db_device_id)
            else:
                sim_record = self._require_device(sim_id)
                if sim_record.bound_db_device_id != db_device_id:
                    sim_record = self.bind_device(sim_id, db_device_id)

            sim_record.persona_config = dict(persona)

            # ── Step 3: Start session nếu chưa có ────────────────────────────────
            if self._find_running_session_for_sim_device(sim_id) is None:
                session = self.create_session([sim_id], speed=5)
                session_id_to_start = session.get("id")
                if session_id_to_start is None:
                    raise RuntimeError(f"Khong the tao session cho db_device_id={db_device_id}")
        if session_id_to_start is not None:
            self.start_session(session_id_to_start)

    def _stop_sim_session_for_db_device(self, db_device_id: int) -> None:
        """Dừng session simulator đang chạy cho db_device_id."""
        with self._lock:
            sim_id = self._find_sim_id_for_db_device(db_device_id)
            if sim_id is None:
                return
            session_ids = [
                record.id
                for record in self.sessions.values()
                if sim_id in record.device_ids and record.status == "running"
            ]
            for session_id in session_ids:
                self.stop_session(session_id)

    def recover_active_sessions(self) -> int:
        """Re-create simulator sessions for all DB devices marked active.

        Called at startup to restore in-memory sessions lost on server restart.
        Returns the number of sessions successfully recovered.
        """
        recovered = 0
        try:
            with session_scope() as db:
                active_devices = SimAdminService.list_active_devices(db)
            for device_info in active_devices:
                db_device_id = int(device_info["id"])
                try:
                    self._ensure_sim_session_for_db_device(db_device_id, device_info)
                    recovered += 1
                    logger.info(
                        "Auto-recovered session for DB device %d (%s)",
                        db_device_id,
                        device_info.get("device_name", "unknown"),
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to recover session for DB device %d: %s",
                        db_device_id,
                        exc,
                        exc_info=True,
                    )
        except Exception as exc:
            logger.warning("Auto-recovery DB query failed: %s", exc, exc_info=True)
        return recovered

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": session.id,
                    "deviceIds": list(session.device_ids),
                    "speed": session.speed,
                    "status": session.status,
                    "createdAt": session.created_at,
                    "lastTickAt": session.last_tick_at,
                }
                for session in self.sessions.values()
            ]

    def create_session(self, device_ids: list[str], speed: int) -> dict[str, Any]:
        with self._lock:
            missing = [device_id for device_id in device_ids if device_id not in self.devices]
            if missing:
                raise KeyError(f"Unknown device ids: {', '.join(missing)}")
            contexts = []
            source_modes: dict[str, str] = {}
            for device_id in device_ids:
                device = self.devices[device_id]
                config = dict(device.persona_config)
                raw_binding = device.data_binding or None
                sim_binding: SimDataBinding | None = None
                source_mode = "synthetic"
                if raw_binding:
                    subject_id = str(raw_binding.get("subject_id") or "")
                    dataset = str(raw_binding.get("dataset") or "")
                    source_mode = str(raw_binding.get("source_mode") or "synthetic")
                    sim_binding = SimDataBinding(
                        subject_id=subject_id,
                        dataset=dataset,
                        source_mode=source_mode,
                        loop=bool(raw_binding.get("loop", True)),
                        speed_factor=float(raw_binding.get("speed_factor", 1.0)),
                    )
                    if source_mode == "replay":
                        timeline = self.registry.get_vitals_timeline(subject_id, dataset)
                        if not timeline:
                            raise KeyError(
                                f"subject_id={subject_id} dataset={dataset} not found in artifact registry"
                            )
                        get_case_demographics = getattr(self.registry, "get_case_demographics", None)
                        if callable(get_case_demographics):
                            demographics = get_case_demographics(subject_id, dataset)
                            if demographics:
                                config.update(demographics)
                                device.persona_config = dict(config)
                source_modes[device_id] = source_mode
                contexts.append(
                    build_device(
                        device_id,
                        age=int(config.get("age", 35)),
                        weight_kg=float(config.get("weight_kg", 70.0)),
                        height_cm=float(config.get("height_cm", 170.0)),
                        gender=str(config.get("gender")) if config.get("gender") is not None else None,
                        seed=int(config.get("seed", 7)),
                        data_binding=sim_binding,
                    )
                )
            session_id = uuid4().hex
            simulator = SimulatorSession(self.registry, contexts)
            record = SessionRecord(
                id=session_id,
                device_ids=list(device_ids),
                speed=speed,
                simulator=simulator,
                source_modes=source_modes,
            )
            self.sessions[session_id] = record
            return {
                "id": record.id,
                "deviceIds": list(record.device_ids),
                "speed": record.speed,
                "status": record.status,
                "createdAt": record.created_at,
                "lastTickAt": record.last_tick_at,
            }

    def start_session(self, session_id: str) -> None:
        effects = SessionSideEffects()
        with self._lock:
            record = self._require_session(session_id)
            record.simulator.start()
            record.status = "running"
            for device_id in record.device_ids:
                if device_id in self.devices:
                    self.devices[device_id].state = "streaming"
                    self.devices[device_id].is_online = True
            self._rebuild_db_device_active_cache_locked()
            self._record_event(
                device_id=record.device_ids[0] if record.device_ids else "system",
                event_type="session_started",
                severity="normal",
                message=f"Session {record.id} started",
            )
            effects = self._tick_session_locked(record, force=True)
        self._run_session_side_effects(effects)

    def stop_session(self, session_id: str) -> None:
        with self._lock:
            record = self._require_session(session_id)
            record.simulator.stop()
            record.status = "stopped"
            for device_id in record.device_ids:
                if device_id in self.devices:
                    self.devices[device_id].state = "bound" if self.devices[device_id].bound_db_device_id is not None else "bindable"
                    self.devices[device_id].is_online = False
            self._rebuild_db_device_active_cache_locked()
            self._record_event(
                device_id=record.device_ids[0] if record.device_ids else "system",
                event_type="session_stopped",
                severity="warning",
                message=f"Session {record.id} stopped",
            )

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
        with self._lock:
            selected = self.event_history[-max(1, limit) :]
            return [event.to_schema() for event in reversed(selected)]

    def dashboard_summary(self) -> DashboardSummary:
        with self._lock:
            total = len(self.devices)
            active = len([device for device in self.devices.values() if device.state == "streaming"])
            alerts = len(
                [
                    event
                    for event in self.event_history
                    if event.severity in {"warning", "critical"}
                    and (datetime.now(timezone.utc).timestamp() - datetime.fromisoformat(event.timestamp).timestamp()) <= 3600
                ]
            )
            latencies = [
                session.last_publish_latency_ms
                for session in self.sessions.values()
                if session.last_publish_count > 0 and session.last_publish_latency_ms is not None
            ]
            avg_latency = int(round(sum(latencies) / len(latencies))) if latencies else 0
            return DashboardSummary(
                totalDevices=total,
                activeDevices=active,
                alertsLastHour=alerts,
                avgLatencyMs=avg_latency,
            )

    def health_payload(self) -> dict[str, str]:
        with self._lock:
            api_status = "running"
            mqtt_status = "connected"
            if not self.sessions:
                mqtt_status = "idle"
        backend_status = "connected" if self._backend_healthy() else "down"
        db_status = "healthy" if self._local_database_healthy() else "down"
        return {
            "status": api_status,
            "api": api_status,
            "backend": backend_status,
            "mqtt": mqtt_status,
            "db": db_status,
            "version": "simulator-api-0.3.0",
        }

    def _build_sleep_session_locked(self, device_id: str) -> SleepSessionResponse:
        self._require_device(device_id)
        if self.registry.has_sleep_sessions():
            raw = self.registry.sample_sleep_session()
            return self._real_sleep_session_from_registry(device_id=device_id, raw=raw)
        return self._fallback_sleep_session(device_id=device_id)

    @staticmethod
    def _apply_sleep_summary_override(
        base_summary: dict[str, Any],
        stats_override: dict[str, Any] | None,
    ) -> dict[str, Any]:
        summary = dict(base_summary or {})
        stage_proportions = dict(summary.get("stage_proportions") or {})
        if stats_override is None:
            summary["stage_proportions"] = stage_proportions
            return summary

        for key, value in stats_override.items():
            if key == "stage_proportions" and isinstance(value, dict):
                stage_proportions.update(value)
                continue
            if key == "total_sleep_s_override":
                summary["total_sleep_s"] = int(value)
                continue
            if key == "spo2_min_override":
                continue
            summary[key] = value

        summary["stage_proportions"] = stage_proportions
        return summary

    @staticmethod
    def _normalize_stage_proportions(stage_proportions: dict[str, Any] | None) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for stage in ("awake", "light", "deep", "rem"):
            value = SimulatorRuntime._safe_float((stage_proportions or {}).get(stage), 0.0) or 0.0
            if value > 1:
                value /= 100.0
            normalized[stage] = max(0.0, value)

        total = sum(normalized.values())
        if normalized["awake"] == 0.0 and 0.0 < total < 1.0:
            normalized["awake"] = max(0.0, 1.0 - total)
            total = sum(normalized.values())

        if total <= 0:
            return {"awake": 0.10, "light": 0.55, "deep": 0.15, "rem": 0.20}
        if abs(total - 1.0) > 0.0001:
            normalized = {stage: value / total for stage, value in normalized.items()}
        return normalized

    @staticmethod
    def _split_minutes(total_minutes: int, parts: int) -> list[int]:
        if parts <= 0:
            return []
        base = max(0, total_minutes) // parts
        remainder = max(0, total_minutes) % parts
        return [base + (1 if idx < remainder else 0) for idx in range(parts)]

    def _build_scenario_phase_segments(
        self,
        *,
        raw: dict[str, Any],
        summary: dict[str, Any],
        phases_pattern_override: list[str] | None,
    ) -> list[SleepStageSegment]:
        total_sleep_s = int(summary.get("total_sleep_s") or 0)
        total_duration_minutes = max(1, int(round(total_sleep_s / 60))) if total_sleep_s > 0 else 360
        stage_proportions = self._normalize_stage_proportions(summary.get("stage_proportions"))
        ordered_stages = ["awake", "light", "deep", "rem"]
        stage_minutes: dict[str, int] = {}
        remaining_minutes = total_duration_minutes
        for stage in ordered_stages[:-1]:
            minutes = int(round(stage_proportions.get(stage, 0.0) * total_duration_minutes))
            minutes = max(0, min(remaining_minutes, minutes))
            stage_minutes[stage] = minutes
            remaining_minutes -= minutes
        stage_minutes[ordered_stages[-1]] = max(0, remaining_minutes)

        pattern = [stage for stage in (phases_pattern_override or ordered_stages) if stage_minutes.get(stage, 0) > 0]
        if not pattern:
            pattern = [stage for stage in ordered_stages if stage_minutes.get(stage, 0) > 0]
        if not pattern:
            pattern = ["light"]
            stage_minutes["light"] = total_duration_minutes

        occurrences = {stage: pattern.count(stage) for stage in set(pattern)}
        split_map: dict[str, list[int]] = {
            stage: self._split_minutes(stage_minutes.get(stage, 0), count)
            for stage, count in occurrences.items()
        }
        split_index = {stage: 0 for stage in occurrences}

        recording_start = str(raw.get("recording_start") or _utc_now_iso())
        try:
            current = datetime.fromisoformat(recording_start.replace("Z", "+00:00"))
        except ValueError:
            current = datetime.now(timezone.utc).replace(hour=22, minute=0, second=0, microsecond=0)

        segments: list[SleepStageSegment] = []
        for stage in pattern:
            minutes_list = split_map.get(stage) or []
            idx = split_index.get(stage, 0)
            if idx >= len(minutes_list):
                continue
            minutes = minutes_list[idx]
            split_index[stage] = idx + 1
            if minutes <= 0:
                continue
            start = current
            end = current + timedelta(minutes=minutes)
            segments.append(
                SleepStageSegment(
                    stage=stage,  # type: ignore[arg-type]
                    start=start.isoformat().replace("+00:00", "Z"),
                    end=end.isoformat().replace("+00:00", "Z"),
                )
            )
            current = end
        return segments

    def _select_session_for_scenario(self, scenario_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        profile = SLEEP_SCENARIO_PROFILES.get(scenario_id, SLEEP_SCENARIO_PROFILES["good_sleep_night"])
        pool = list(getattr(self.registry, "_sleep_sessions", []) or [])
        if not pool:
            return {}, {
                "scenario_id": scenario_id,
                "summary": self._apply_sleep_summary_override({}, profile.get("stats_override")),
                "use_summary_override": profile.get("stats_override") is not None,
                "disorder_tags": list(profile.get("disorder_tags", [])),
                "spo2_min_override": (profile.get("stats_override") or {}).get("spo2_min_override"),
                "phases_pattern_override": profile.get("phases_pattern_override"),
                "description": str(profile.get("description") or ""),
            }

        filter_fn = profile.get("filter")
        filtered = pool
        if callable(filter_fn):
            filtered = []
            for session in pool:
                try:
                    if filter_fn(session):
                        filtered.append(session)
                except Exception:
                    continue
            if not filtered:
                filtered = pool

        import random as _random

        raw = _random.choice(filtered)
        summary = self._apply_sleep_summary_override(raw.get("summary") or {}, profile.get("stats_override"))
        return raw, {
            "scenario_id": scenario_id,
            "summary": summary,
            "use_summary_override": profile.get("stats_override") is not None,
            "disorder_tags": list(profile.get("disorder_tags", [])),
            "spo2_min_override": (profile.get("stats_override") or {}).get("spo2_min_override"),
            "phases_pattern_override": profile.get("phases_pattern_override"),
            "description": str(profile.get("description") or ""),
        }

    def _build_sleep_session_for_scenario_locked(
        self,
        device_id: str,
        scenario_id: str,
    ) -> SleepSessionResponse:
        self._require_device(device_id)
        if not self.registry.has_sleep_sessions():
            return self._fallback_sleep_session(device_id=device_id)

        raw, effective = self._select_session_for_scenario(scenario_id)
        return self._real_sleep_session_from_registry(
            device_id=device_id,
            raw=raw,
            summary_override=effective.get("summary") if effective.get("use_summary_override") else None,
            phases_pattern_override=effective.get("phases_pattern_override"),
            disorder_tags=effective.get("disorder_tags"),
            min_spo2_override=effective.get("spo2_min_override"),
            scenario_id=scenario_id,
            description=effective.get("description"),
        )

    def sleep_session(self, device_id: str) -> SleepSessionResponse:
        with self._lock:
            return self._build_sleep_session_locked(device_id)

    def push_sleep_session(self, device_id: str) -> SleepSessionResponse:
        with self._lock:
            result = self._build_sleep_session_locked(device_id)
        self._push_sleep_to_backend(sim_device_id=device_id, sleep_resp=result)
        return result

    def push_sleep_session_for_date(
        self,
        device_id: str,
        target_date: date,
        scenario_id: str = "good_sleep_night",
    ) -> dict[str, Any]:
        with self._lock:
            self._require_device(device_id)
            device = self.devices.get(device_id)
            bound_db_device_id = device.bound_db_device_id if device is not None else None
            has_registry_sessions = self.registry.has_sleep_sessions()
            if has_registry_sessions:
                raw, effective = self._select_session_for_scenario(scenario_id)
            else:
                raw, effective = {}, {
                    "summary": {},
                    "disorder_tags": [],
                    "spo2_min_override": None,
                    "phases_pattern_override": None,
                    "use_summary_override": False,
                    "description": "",
                }

        if bound_db_device_id is None:
            return {
                "success": False,
                "target_date": target_date.isoformat(),
                "scenario_id": scenario_id,
                "duration_minutes": 0,
                "sleep_score": 0,
                "disorder_tags": [],
                "was_overwritten": False,
                "message": "Device not bound",
            }
        user_id = self._resolve_bound_device_user_id(bound_db_device_id)
        if user_id is None:
            return {
                "success": False,
                "target_date": target_date.isoformat(),
                "scenario_id": scenario_id,
                "duration_minutes": 0,
                "sleep_score": 0,
                "disorder_tags": [],
                "was_overwritten": False,
                "message": f"No owner found for db_device_id={bound_db_device_id}",
            }

        if has_registry_sessions:
            summary = dict(effective.get("summary") or raw.get("summary") or {})
            phases = (
                self._build_scenario_phase_segments(
                    raw=raw,
                    summary=summary,
                    phases_pattern_override=effective.get("phases_pattern_override"),
                )
                if effective.get("use_summary_override") or effective.get("phases_pattern_override") is not None
                else self._sleep_stage_segments_from_raw(raw)
            )
            fallback_duration_minutes = int(summary.get("total_sleep_s") or 0) // 60 or 360
            phases_dict, duration_minutes = self._phase_minutes_from_segments(
                phases,
                fallback_duration_minutes=fallback_duration_minutes,
            )
            sleep_efficiency = self._safe_float(summary.get("sleep_efficiency"), 0.85) or 0.85
            efficiency_pct = round(sleep_efficiency * 100 if sleep_efficiency <= 1 else sleep_efficiency, 1)
            disorder_tags = list(effective.get("disorder_tags") or [])
        else:
            fallback = self._fallback_sleep_session(device_id=device_id)
            phases_dict, duration_minutes = self._phase_minutes_from_segments(
                fallback.phases,
                fallback_duration_minutes=fallback.durationMinutes,
            )
            sleep_score = int(fallback.score)
            efficiency_pct = float(fallback.efficiency)
            disorder_tags = []

        was_overwritten = self._sleep_session_exists(
            db_device_id=bound_db_device_id,
            user_id=user_id,
            target_date=target_date,
        )
        sleep_date, start_time, end_time = self._compute_sleep_window_for_date(target_date, duration_minutes)
        persona_config = dict(device.persona_config or {}) if device is not None else {}
        sleep_ai_record: dict[str, Any] | None = None
        if has_registry_sessions:
            sleep_ai_record = self._build_sleep_ai_record(
                scenario_id=scenario_id,
                summary=summary,
                phases_dict=phases_dict,
                duration_minutes=duration_minutes,
                sleep_date=sleep_date,
                start_time=start_time,
                end_time=end_time,
                user_id=user_id,
                persona_config=persona_config,
            )
            sleep_score = self._compute_sleep_score_with_ai(sleep_ai_record)
        score_source = getattr(self, "_last_sleep_score_source", "heuristic")

        payload = {
            "db_device_id": bound_db_device_id,
            "user_id": user_id,
            "date": sleep_date.isoformat(),
            "score": sleep_score,
            "efficiency": efficiency_pct,
            "duration_minutes": duration_minutes,
            "phases": phases_dict,
            "start_time": start_time.isoformat().replace("+00:00", "Z"),
            "end_time": end_time.isoformat().replace("+00:00", "Z"),
            "heart_rate_mean_bpm": (sleep_ai_record or {}).get("heart_rate_mean_bpm"),
            "heart_rate_min_bpm": (sleep_ai_record or {}).get("heart_rate_min_bpm"),
            "heart_rate_max_bpm": (sleep_ai_record or {}).get("heart_rate_max_bpm"),
            "hrv_rmssd_ms": (sleep_ai_record or {}).get("hrv_rmssd_ms"),
            "respiration_rate_bpm": (sleep_ai_record or {}).get("respiration_rate_bpm"),
            "spo2_mean_pct": (sleep_ai_record or {}).get("spo2_mean_pct"),
            "spo2_min_pct": (sleep_ai_record or {}).get("spo2_min_pct"),
            "movement_count": (sleep_ai_record or {}).get("movement_count"),
            "snore_events": (sleep_ai_record or {}).get("snore_events"),
        }

        try:
            ok, status_code = self._post_sleep_payload(
                payload=payload,
                device_id=device_id,
            )
            self._publish_device_log(
                device_id,
                level="INFO",
                message=(
                    f"Sleep backfill push OK: HTTP {status_code} | date={target_date.isoformat()} "
                    f"| duration={duration_minutes}min | scenario={scenario_id} | score_source={score_source}"
                ),
                timestamp=_utc_now_iso(),
            )
            return {
                "success": ok,
                "target_date": target_date.isoformat(),
                "scenario_id": scenario_id,
                "duration_minutes": duration_minutes,
                "sleep_score": sleep_score,
                "disorder_tags": disorder_tags,
                "was_overwritten": was_overwritten,
                "message": "Updated" if was_overwritten else "Created",
            }
        except Exception as exc:
            self._publish_device_log(
                device_id,
                level="ERROR",
                message=(
                    f"Sleep backfill push failed: {exc} | date={target_date.isoformat()} "
                    f"| scenario={scenario_id}"
                ),
                timestamp=_utc_now_iso(),
            )
            return {
                "success": False,
                "target_date": target_date.isoformat(),
                "scenario_id": scenario_id,
                "duration_minutes": duration_minutes,
                "sleep_score": sleep_score,
                "disorder_tags": disorder_tags,
                "was_overwritten": was_overwritten,
                "message": f"Failed: {type(exc).__name__}: {exc}",
            }

    @staticmethod
    def _resolve_bound_device_user_id(db_device_id: int) -> int | None:
        try:
            with session_scope() as db:
                value = db.execute(
                    text(
                        """
                        SELECT user_id
                        FROM devices
                        WHERE id = :device_id
                          AND deleted_at IS NULL
                        LIMIT 1
                        """
                    ),
                    {"device_id": db_device_id},
                ).scalar()
        except Exception:
            return None
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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

        # ── ACTIVE MODE: use orchestrator's force_health_prediction ──
        if (
            self._pre_model_trigger_active
            and self._trigger_orchestrator is not None
        ):
            try:
                vitals_snap = self._trigger_orchestrator._extract_vitals_snapshot(
                    self._get_latest_vitals_dict(request.device_id),
                )
                persona = self._get_trigger_persona(request.device_id)
                actions = self._trigger_orchestrator.force_health_prediction(
                    device_id=request.device_id,
                    vitals=vitals_snap,
                    persona=persona,
                )
                severity = "normal"
                message = "Trigger orchestrator health prediction completed"
                metadata: dict[str, str] = {
                    "action_count": str(len(actions)),
                    "source": "trigger_orchestrator",
                }
                for action in actions:
                    if action.action_type == "alert":
                        self._record_event(
                            device_id=request.device_id,
                            event_type="risk_prediction_alert",
                            severity=action.severity,
                            message=action.message,
                            metadata=action.metadata,
                        )
            except Exception as exc:
                logger.warning(
                    "Trigger force_health_prediction failed for %s: %s — falling back to legacy",
                    request.device_id, exc,
                )
                severity = "warning"
                message = f"Trigger prediction failed, legacy fallback: {exc}"
                metadata = {"error": str(exc)}
            with self._lock:
                self._record_event(
                    device_id=request.device_id,
                    event_type="risk_inference_triggered",
                    severity=severity,
                    message=message,
                    metadata=metadata,
                )
            return

        # ── LEGACY MODE: call backend risk inference ──
        status_code = self._trigger_risk_inference(request.device_id)
        metadata_legacy: dict[str, str] = {}
        if status_code is not None:
            metadata_legacy["http_status"] = str(status_code)

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
                metadata=metadata_legacy,
            )

    def latest_vitals(self, device_id: str) -> VitalsSample:
        with self._lock:
            latest_match: tuple[datetime, SessionRecord, dict[str, Any]] | None = None
            for record in self.sessions.values():
                for payload in reversed(record.last_tick_outputs):
                    if payload.get("device_id") == device_id:
                        emitted_at_raw = str(payload.get("emitted_at") or "")
                        try:
                            emitted_at_dt = datetime.fromisoformat(emitted_at_raw)
                        except ValueError:
                            emitted_at_dt = datetime.min.replace(tzinfo=timezone.utc)
                        if latest_match is None or emitted_at_dt >= latest_match[0]:
                            latest_match = (emitted_at_dt, record, payload)
                        break
            if latest_match is None:
                raise KeyError(f"No vitals found for device: {device_id}")

            _, record, payload = latest_match
            raw_vitals = payload.get("vitals") or {}
            payload_state = payload.get("state") or {}
            source_mode = str(record.source_modes.get(device_id, "synthetic") or "synthetic").strip().lower()
            has_bp = (
                raw_vitals.get("blood_pressure_sys") is not None
                and raw_vitals.get("blood_pressure_dia") is not None
            )
            bp_observation_age_sec, bp_is_stale = self._compute_bp_staleness(device_id, has_bp=has_bp)
            sample = self._to_vitals(
                raw_vitals,
                stale=record.status != "running",
                emitted_at=str(payload.get("emitted_at") or ""),
                activity_state=str(payload_state.get("activity_state") or "unknown"),
                is_sleeping=_is_sleeping_state(payload_state.get("activity_state")),
                source_mode=source_mode,
                device_id=device_id,
                bp_observation_age_sec=bp_observation_age_sec,
                bp_is_stale=bp_is_stale,
            )
            activity_state = str(payload_state.get("activity_state") or "").strip().lower()
            fall_variant = str(payload_state.get("fall_variant") or "").strip().lower()
            if activity_state == "fall" and fall_variant != "fall_brief":
                return sample.model_copy(update={"severity": "critical"})
            return sample

    def _compute_bp_staleness(self, device_id: str, has_bp: bool) -> tuple[float | None, bool | None]:
        """Track replay NIBP freshness using the latest observed blood pressure sample."""
        now = monotonic()
        if has_bp:
            self._bp_last_observed[device_id] = now
        last = self._bp_last_observed.get(device_id)
        if last is None:
            return None, None
        age = round(now - last, 1)
        return age, age > 300.0

    def _get_latest_vitals_dict(self, device_id: str) -> dict[str, Any]:
        """Return the raw vitals dict for *device_id* from the latest tick output."""
        with self._lock:
            for record in self.sessions.values():
                for payload in reversed(record.last_tick_outputs):
                    if payload.get("device_id") == device_id:
                        return payload.get("vitals") or {}
        return {}

    def _verification_is_stale_locked(self, record: SessionRecord) -> bool:
        last_tick_at = self._coerce_datetime_value(record.last_tick_at)
        if last_tick_at is None:
            return False
        stale_after_seconds = max(float(self._push_interval) * 2.0, 10.0)
        age_seconds = (datetime.now(timezone.utc) - last_tick_at).total_seconds()
        return age_seconds > stale_after_seconds

    def _verification_status_locked(self, record: SessionRecord) -> str:
        if record.last_publish_count > 0:
            if not record.last_publish_ok:
                return "FAILED"
            if record.status == "running" and self._verification_is_stale_locked(record):
                return "DELAYED"
            return "PASS"

        if record.status != "running":
            return "PENDING"
        if not record.last_tick_outputs:
            return "PENDING"
        if self._verification_is_stale_locked(record):
            return "DELAYED"
        return "PENDING"

    def verification(self, session_id: str) -> VerificationResult:
        with self._lock:
            record = self._require_session(session_id)
            device_id = record.device_ids[0] if record.device_ids else "unknown"
            status = self._verification_status_locked(record)
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
        if session_id not in self.sessions:
            raise KeyError(f"Session not found: {session_id}")
        return self.sessions[session_id]

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
                self._advance_sleep_phase_if_due(device_id)
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
            is_sleeping = _is_sleeping_state(state.get("activity_state"))

            # ── ACTIVE MODE: delegate to trigger orchestrator ──
            if self._pre_model_trigger_active and self._trigger_orchestrator is not None:
                db_thresholds: dict[str, float] | None = None
                try:
                    db_thresholds = self._trigger_orchestrator._settings.get_vitals_thresholds(
                        is_sleeping=is_sleeping,
                    )
                except Exception:
                    pass  # Fall back to hard-coded if DB unavailable
                vitals_sample = self._to_vitals(
                    vitals_payload,
                    stale=False,
                    emitted_at=emitted_at,
                    activity_state=str(state.get("activity_state") or "unknown"),
                    is_sleeping=is_sleeping,
                    source_mode=str(vitals_payload.get("source_mode") or record.source_modes.get(str(device_id), "synthetic")),
                    device_id=str(device_id),
                    thresholds_override=db_thresholds,
                )
                try:
                    trigger_actions: list[TriggerActionItem] = self._trigger_orchestrator.evaluate_tick(
                        device_id=str(device_id),
                        vitals=vitals_payload,
                        motion=payload.get("motion"),
                        state=state,
                        persona=self._get_trigger_persona(str(device_id)),
                    )
                    for action in trigger_actions:
                        if action.action_type == "alert":
                            effects.pending_alerts.append(
                                PendingAlertCall(
                                    sim_device_id=str(device_id),
                                    event_type=action.metadata.get("event_type", "vitals_out_of_range"),
                                    severity=action.severity,
                                    metadata={
                                        "source": action.source or "trigger_orchestrator",
                                        "timestamp": emitted_at,
                                        "message": action.message,
                                        "scenario_id": self.device_scenarios.get(str(device_id), "normal_rest"),
                                        **{k: v for k, v in action.metadata.items() if k != "event_type"},
                                    },
                                )
                            )
                except Exception as exc:
                    logger.warning("Trigger orchestrator evaluate_tick failed for %s: %s", device_id, exc)
                    # Fall back to severity-based alert from _to_vitals
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
                                    "scenario_id": self.device_scenarios.get(str(device_id), "normal_rest"),
                                },
                            )
                        )
                continue

            # ── LEGACY MODE: hard-coded thresholds ──
            vitals_sample = self._to_vitals(
                vitals_payload,
                stale=False,
                emitted_at=emitted_at,
                activity_state=str(state.get("activity_state") or "unknown"),
                is_sleeping=is_sleeping,
                source_mode=str(vitals_payload.get("source_mode") or record.source_modes.get(str(device_id), "synthetic")),
                device_id=str(device_id),
            )
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

        # ── SHADOW MODE: evaluate new trigger engine (does NOT affect behavior) ──
        if self._trigger_orchestrator is not None and not self._pre_model_trigger_active:
            for payload in outputs:
                device_id = str(payload.get("device_id") or "")
                state = payload.get("state") or {}
                vitals_payload = payload.get("vitals") or {}
                try:
                    shadow_actions = self._trigger_orchestrator.evaluate_tick(
                        device_id=device_id,
                        vitals=vitals_payload,
                        motion=payload.get("motion"),
                        state=state,
                        persona=self._get_trigger_persona(device_id),
                    )
                    self._log_shadow_comparison(device_id, shadow_actions, effects)
                except Exception:
                    pass  # Shadow mode NEVER affects main flow

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
        pending_ids = {
            str(payload.get("device_id"))
            for payload in self._tick_buffer
            if payload.get("device_id") is not None and payload.get("db_device_id") is not None
        }
        for device_id, device in self.devices.items():
            device.has_pending_sync = device_id in pending_ids

    @staticmethod
    def _scenario_state_hint(scenario_id: str) -> str:
        if scenario_id in {"hypoxia_critical", "high_risk_cardiac", "fall_no_response"}:
            return "critical"
        if scenario_id in {"tachycardia_warning", "hypertension_moderate", "fragmented_sleep", "medium_risk_general", "fall_false_alarm"}:
            return "warning"
        if scenario_id == "fall_high_confidence":
            return "fall_countdown"
        if scenario_id in {"normal_rest", "good_sleep_night"}:
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
        thresholds_override: dict[str, float] | None = None,
    ) -> VitalsSample:
        heart_rate = SimulatorRuntime._safe_float(vitals.get("heart_rate"), 72.0)
        spo2_val   = SimulatorRuntime._safe_float(vitals.get("spo2"), 98.0)
        bp_sys_val = SimulatorRuntime._safe_float(vitals.get("blood_pressure_sys"), 120.0)
        bp_dia_val = SimulatorRuntime._safe_float(vitals.get("blood_pressure_dia"), 80.0)
        raw_temp = vitals.get("temperature")
        raw_rr = vitals.get("respiratory_rate")
        if raw_rr is None:
            raw_rr = vitals.get("respiration_rate")
        replay_mode = source_mode == "replay"
        provenance: dict[str, str] | None = None
        if replay_mode:
            provenance = {
                "heartRate": "measured" if vitals.get("heart_rate") is not None else "unknown",
                "spo2": "measured" if vitals.get("spo2") is not None else "unknown",
                "bloodPressureSys": "measured" if vitals.get("blood_pressure_sys") is not None else "unknown",
                "bloodPressureDia": "measured" if vitals.get("blood_pressure_dia") is not None else "unknown",
                "temperature": "unknown",
                "respiratoryRate": "measured" if raw_rr is not None else "unknown",
                "hrv": "unknown",
            }
        temperature = SimulatorRuntime._safe_float(raw_temp, 36.7)
        respiratory_rate = (
            SimulatorRuntime._safe_float(raw_rr, None)
            if replay_mode and raw_rr is None
            else SimulatorRuntime._safe_float(raw_rr, 15.0)
        )
        blood_pressure_sys = (
            None
            if replay_mode and bp_is_stale is True
            else SimulatorRuntime._safe_float(vitals.get("blood_pressure_sys"), 120.0)
        )
        blood_pressure_dia = (
            None
            if replay_mode and bp_is_stale is True
            else SimulatorRuntime._safe_float(vitals.get("blood_pressure_dia"), 80.0)
        )
        # Use DB-driven thresholds when provided, fall back to hard-coded.
        if thresholds_override is not None:
            thresholds = thresholds_override
        else:
            thresholds = SLEEP_THRESHOLDS if is_sleeping else DAYTIME_THRESHOLDS
        critical_rr = (
            respiratory_rate is not None
            and (
                respiratory_rate < thresholds["rr_critical_low"]
                or respiratory_rate > thresholds["rr_critical_high"]
            )
        )
        low_sys_critical = blood_pressure_sys is not None and blood_pressure_sys < 80.0
        # Multi-signal severity with context-aware thresholds for waking vs sleeping.
        severity = "normal"
        if (
            heart_rate >= thresholds["hr_critical_high"]
            or heart_rate < thresholds["hr_critical_low"]
            or spo2_val < thresholds["spo2_critical"]
            or low_sys_critical
            or bp_sys_val >= thresholds["bp_sys_critical"]
            or bp_dia_val >= thresholds["bp_dia_critical"]
            or critical_rr
        ):
            severity = "critical"
        elif (
            heart_rate >= thresholds["hr_warning_high"]
            or heart_rate < thresholds["hr_warning_low"]
            or spo2_val < thresholds["spo2_warning"]
            or bp_sys_val >= thresholds["bp_sys_warning"]
            or bp_dia_val >= thresholds["bp_dia_warning"]
        ):
            severity = "warning"
        activity_map: dict[str, str] = {
            "resting": "resting",
            "walking": "walking",
            "running": "running",
            "fall": "falling",
            "recovery": "recovery",
            "sleeping": "sleeping",
            "standing": "resting",
        }
        label = activity_map.get(str(activity_state or "unknown").strip().lower(), "unknown")
        generator_label = str(vitals.get("activity_label") or "").strip().lower()
        if generator_label in {"sleeping", "resting", "walking", "running", "falling", "recovery", "unknown"}:
            label = generator_label
        return VitalsSample(
            timestamp=emitted_at or vitals.get("timestamp") or _utc_now_iso(),
            heartRate=heart_rate,
            spo2=spo2_val,
            temperature=temperature,
            bloodPressureSys=blood_pressure_sys,
            bloodPressureDia=blood_pressure_dia,
            respiratoryRate=respiratory_rate,
            hrv=None,
            signalQuality=None,
            motionArtifact=False,
            isStale=stale,
            severity=severity,  # type: ignore[arg-type]
            activityLabel=label,  # type: ignore[arg-type]
            motionTag=label,  # type: ignore[arg-type]
            fieldProvenance=provenance,
            bpObservationAgeSec=bp_observation_age_sec,
            bpIsStale=bp_is_stale,
            sourceMode=source_mode if source_mode != "synthetic" else None,
        )

    @staticmethod
    def _safe_float(value: Any, default: float | None) -> float | None:
        try:
            cast = float(value)
        except (TypeError, ValueError):
            return default
        if math.isnan(cast) or math.isinf(cast):
            return default
        return cast

    def _require_device(self, device_id: str) -> DeviceRecord:
        if device_id not in self.devices:
            raise KeyError(f"Device not found: {device_id}")
        return self.devices[device_id]

    @staticmethod
    def _build_sleep_segments(
        anchor_date: datetime.date,
        start_hour: int = 22,
        start_minute: int = 0,
    ) -> list[SleepStageSegment]:
        import random as _random

        if start_hour == 22 and start_minute == 0:
            offset = _random.randint(0, 90)
            start_hour = 22 + (offset // 60)
            start_minute = offset % 60

        base = datetime(anchor_date.year, anchor_date.month, anchor_date.day, start_hour, start_minute, tzinfo=timezone.utc)
        pattern: list[tuple[str, int]] = [
            ("light", 35),
            ("deep", 60),
            ("rem", 25),
            ("light", 45),
            ("awake", 10),
            ("deep", 55),
            ("rem", 25),
            ("light", 45),
            ("awake", 7),
            ("rem", 28),
            ("light", 75),
        ]
        segments: list[SleepStageSegment] = []
        current = base
        for stage, duration in pattern:
            start = current
            end = current + timedelta(minutes=duration)
            segments.append(SleepStageSegment(stage=stage, start=start.isoformat(), end=end.isoformat()))  # type: ignore[arg-type]
            current = end
        return segments

    @staticmethod
    def _segment_minutes(start_iso: str, end_iso: str) -> int:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
        delta = end - start
        return int(max(0, delta.total_seconds() // 60))

    @staticmethod
    def _build_sleep_history(device_id: str, anchor_date: datetime.date) -> list[SleepHistoryRow]:
        seed = int(device_id[:8], 16)
        rows: list[SleepHistoryRow] = []
        for offset in range(6, -1, -1):
            date_value = (anchor_date - timedelta(days=offset)).isoformat()
            score = 78 + ((seed + offset * 3) % 18)
            efficiency = round(87.0 + ((seed >> (offset % 6)) % 10) * 0.9, 1)
            duration_minutes = 380 + ((seed + offset * 11) % 61)
            avg_hr = float(55 + ((seed + offset) % 9))
            min_spo2 = float(93 + ((seed + offset * 2) % 5))
            rows.append(
                SleepHistoryRow(
                    date=date_value,
                    score=score,
                    efficiency=efficiency,
                    durationMinutes=duration_minutes,
                    avgHeartRate=avg_hr,
                    minSpo2=min_spo2,
                )
            )
        return rows

    def _fallback_sleep_session(self, device_id: str) -> SleepSessionResponse:
        today = datetime.now(timezone.utc).date()
        phases = self._build_sleep_segments(today)
        history = self._build_sleep_history(device_id=device_id, anchor_date=today)
        duration_minutes = sum(self._segment_minutes(segment.start, segment.end) for segment in phases)
        return SleepSessionResponse(
            deviceId=device_id,
            date=today.isoformat(),
            realismMode="fallback",
            score=84,
            efficiency=92.6,
            durationMinutes=duration_minutes,
            avgHeartRate=58.0,
            minSpo2=95.0,
            phases=phases,
            history=history,
            banner="Sleep Realism Mode: Fallback pattern (Phase 5A). Tai Sleep-EDF de nang cap.",
        )

    def _real_sleep_session_from_registry(
        self,
        *,
        device_id: str,
        raw: dict[str, Any],
        summary_override: dict[str, Any] | None = None,
        phases_pattern_override: list[str] | None = None,
        disorder_tags: list[str] | None = None,
        min_spo2_override: float | None = None,
        scenario_id: str | None = None,
        description: str | None = None,
    ) -> SleepSessionResponse:
        summary = dict(summary_override or raw.get("summary") or {})
        phases = (
            self._build_scenario_phase_segments(
                raw=raw,
                summary=summary,
                phases_pattern_override=phases_pattern_override,
            )
            if summary_override is not None or phases_pattern_override is not None
            else self._sleep_stage_segments_from_raw(raw)
        )
        recording_start = str(raw.get("recording_start") or _utc_now_iso())
        date_value = recording_start.split("T")[0]
        efficiency_raw = self._safe_float(summary.get("sleep_efficiency"), 0.0)
        efficiency = round(efficiency_raw * 100, 1) if efficiency_raw <= 1 else round(efficiency_raw, 1)
        total_sleep_s = int(summary.get("total_sleep_s") or 0)
        duration_minutes = max(1, int(round(total_sleep_s / 60)))
        wake_count = int(summary.get("wake_count") or 0)
        stage_proportions = summary.get("stage_proportions") or {}
        deep_ratio = self._safe_float(stage_proportions.get("deep"), 0.0)
        avg_heart_rate = round(max(48.0, min(78.0, 62.0 - deep_ratio * 9.0 + wake_count * 0.4)), 1)
        min_spo2 = (
            round(float(min_spo2_override), 1)
            if min_spo2_override is not None
            else round(max(90.0, min(99.0, 96.0 - wake_count * 0.25)), 1)
        )
        history = self._sleep_history_from_registry()
        effective_raw = dict(raw)
        effective_raw["summary"] = summary
        score = self._calc_sleep_score(effective_raw)
        banner = "Sleep Realism Mode: Real Sleep-EDF session."
        if scenario_id is not None:
            tag_suffix = ", ".join(disorder_tags or [])
            banner = f"Sleep Realism Mode: Scenario {scenario_id}."
            if description:
                banner = f"{banner} {description}"
            if tag_suffix:
                banner = f"{banner} Tags: {tag_suffix}."

        return SleepSessionResponse(
            deviceId=device_id,
            date=date_value,
            realismMode="real",
            score=score,
            efficiency=efficiency,
            durationMinutes=duration_minutes,
            avgHeartRate=avg_heart_rate,
            minSpo2=min_spo2,
            phases=phases,
            history=history,
            banner=banner,
        )

    def _sleep_stage_segments_from_raw(self, raw: dict[str, Any]) -> list[SleepStageSegment]:
        phases_raw_obj = raw.get("phases")
        if phases_raw_obj is None:
            phases_raw: list[Any] = []
        elif isinstance(phases_raw_obj, list):
            phases_raw = phases_raw_obj
        elif isinstance(phases_raw_obj, tuple):
            phases_raw = list(phases_raw_obj)
        elif hasattr(phases_raw_obj, "tolist"):
            converted = phases_raw_obj.tolist()
            phases_raw = converted if isinstance(converted, list) else [converted]
        else:
            phases_raw = [phases_raw_obj]
        segments: list[SleepStageSegment] = []
        for item in phases_raw:
            if not isinstance(item, dict):
                continue
            stage = str(item.get("stage") or "")
            start = item.get("start")
            end = item.get("end")
            if stage not in {"deep", "light", "rem", "awake"}:
                continue
            if not start or not end:
                continue
            segments.append(SleepStageSegment(stage=stage, start=str(start), end=str(end)))  # type: ignore[arg-type]
        return segments

    def _sleep_history_from_registry(self, limit: int = 7) -> list[SleepHistoryRow]:
        if not self.registry.has_sleep_sessions():
            return []

        all_sessions = list(getattr(self.registry, "_sleep_sessions", []) or [])
        if not all_sessions:
            return []

        import hashlib as _hashlib
        import random as _random

        sample_size = min(max(1, limit * 2), len(all_sessions))
        sampled = _random.sample(all_sessions, sample_size)

        seen_dates: set[str] = set()
        rows: list[SleepHistoryRow] = []
        today = datetime.now(timezone.utc).date()
        for raw in sampled:
            summary = raw.get("summary") or {}
            session_hash = int(_hashlib.md5(str(raw).encode("utf-8")).hexdigest()[:8], 16)
            date_value = (today - timedelta(days=(session_hash % 30) + 1)).isoformat()
            if date_value in seen_dates:
                continue
            seen_dates.add(date_value)
            efficiency_raw = self._safe_float(summary.get("sleep_efficiency"), 0.0)
            efficiency = round(efficiency_raw * 100, 1) if efficiency_raw <= 1 else round(efficiency_raw, 1)
            total_sleep_s = int(summary.get("total_sleep_s") or 0)
            duration_minutes = max(1, int(round(total_sleep_s / 60)))
            stage_proportions = summary.get("stage_proportions") or {}
            deep_ratio = self._safe_float(stage_proportions.get("deep"), 0.0)
            wake_count = int(summary.get("wake_count") or 0)
            rows.append(
                SleepHistoryRow(
                    date=date_value,
                    score=self._calc_sleep_score(raw),
                    efficiency=efficiency,
                    durationMinutes=duration_minutes,
                    avgHeartRate=round(max(48.0, min(78.0, 62.0 - deep_ratio * 9.0 + wake_count * 0.4)), 1),
                    minSpo2=round(max(90.0, min(99.0, 96.0 - wake_count * 0.25)), 1),
                )
            )
            if len(rows) >= limit:
                break
        rows.sort(key=lambda item: item.date)
        return rows[-limit:]

    def _calc_sleep_score(self, raw: dict[str, Any]) -> int:
        summary = raw.get("summary") or {}
        efficiency_ratio = self._safe_float(summary.get("sleep_efficiency"), 0.0)
        if efficiency_ratio > 1:
            efficiency_ratio /= 100
        efficiency_ratio = max(0.0, min(1.0, efficiency_ratio))
        stage_props = summary.get("stage_proportions") or {}
        deep_ratio = self._safe_float(stage_props.get("deep"), 0.0)
        if deep_ratio > 1:
            deep_ratio /= 100
        deep_ratio = max(0.0, min(1.0, deep_ratio))
        wake_count = int(summary.get("wake_count") or 0)
        wake_penalty = min(max(wake_count, 0), 8) * 2.5
        score = 25 + efficiency_ratio * 55 + deep_ratio * 20 - wake_penalty
        return max(0, min(100, round(score)))

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
            RiskContribution(feature="sleep_efficiency", value="92.6%", weight=-0.04, direction="down"),
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
        event = EventRecord(
            id=uuid4().hex,
            timestamp=_utc_now_iso(),
            device_id=device_id,
            event_type=event_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
        )
        self.event_history.append(event)
        if len(self.event_history) > 2000:
            self.event_history[:] = self.event_history[-2000:]


_runtime_singleton: SimulatorRuntime | None = None


def get_runtime() -> SimulatorRuntime:
    global _runtime_singleton
    if _runtime_singleton is None:
        _runtime_singleton = SimulatorRuntime()
    _runtime_singleton.start_background_tick()
    return _runtime_singleton


def reset_runtime_for_tests() -> None:
    global _runtime_singleton
    if _runtime_singleton is not None:
        _runtime_singleton.shutdown()
    _runtime_singleton = SimulatorRuntime()
