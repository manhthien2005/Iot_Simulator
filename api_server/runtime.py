"""SimulatorRuntime — core orchestration facade.

Extracted from api_server/dependencies.py. All heavy business logic lives here;
dependencies.py is now a thin DI wiring + re-export shim.
"""
from __future__ import annotations

import asyncio
import collections
import json as _json
import logging
import math
import os
import random as _random
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Lock, RLock, Thread
from time import monotonic
from typing import Any
from urllib.request import Request, urlopen
from uuid import uuid4

import httpx
from sqlalchemy import text

from api_server.config import load_sleep_scenarios
from api_server.backend_admin_client import BackendAdminClient
from api_server.db import session_scope
from api_server.runtime_state import HealthRuntimeState
from api_server.runtime_persistence import (
    RUNTIME_PATH,
    PersistenceState,
    RuntimeConfigValues,
    load_runtime_config,
    save_runtime_config,
    reset_runtime_config,
)
from api_server.utils import _utc_now_iso, _safe_float, _coerce_date, _normalize_gender, _is_sleeping_state
from api_server.schemas import (
    AIPrediction,
    AITopFeature,
    AlertEvent,
    CountdownPolicy,
    CreateDeviceRequest,
    DataBindingConfig,
    DashboardSummary,
    DbSleepHistoryRow,
    FallEventEntry,
    FallState,
    FallStateValue,
    MotionLatest,
    MotionWindowRef,
    PipelineStage,
    PipelineStageStatusValue,
    PreTriggerEvidence,
    RiskContribution,
    RiskHistoryPoint,
    RiskInjectRequest,
    RiskScoreResponse,
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
from pre_model_trigger import (
    FallPreTrigger,
    HealthGuardAPIClient,
    PersonaProfile,
    ResponseHandler,
    RuleEngine,
    SystemSettingsProvider,
    TriggerOrchestrator,
    VitalsHistoryBuffer,
)
from simulator_core.dataset_registry import DatasetRegistry
# ADR-019 Phase 7 S9: FallAIClient no longer used by the runtime -
# motion_window_to_samples + FALL_VARIANT_CONTEXT shape the IMU payload.
from simulator_core.fall_ai_client import (
    FALL_VARIANT_CONTEXT,
    FALL_VARIANT_DEFAULT_CONTEXT,
    motion_window_to_samples as _motion_window_to_samples,
)
from pre_model_trigger.mobile_telemetry_client import MobileTelemetryClient
from pre_model_trigger.sleep_dispatch import SleepRiskDispatcher
from simulator_core.session import DataBinding as SimDataBinding, SimulatorSession, build_device
from simulator_core.sleep_ai_client import SleepAIClient
from simulator_core.sleep_vitals_enricher import enrich_sleep_record
from transport import HttpPublisher, MqttPublisher, TransportRouter

# Extracted modules - import instead of defining locally
from api_server.fall_policy import (
    FallVariantPolicy,
    FALL_VARIANT_POLICIES,
    FALL_VARIANT_DEFAULT_POLICY,
    FALL_VARIANT_TO_PERSONA,
)
from api_server.log_hub import LogHub
from api_server.models import (
    DeviceRecord,
    DevicePublishStatus,
    SessionRecord,
    SessionSideEffects,
    PendingDevicePublish,
    PendingHeartbeatUpdate,
    PendingAlertCall,
    PreparedAlertPush,
    EventRecord,
    RiskSnapshot,
)

# Aliases to preserve internal names used throughout SimulatorRuntime
_FallVariantPolicy = FallVariantPolicy
_FALL_VARIANT_POLICIES = FALL_VARIANT_POLICIES
_FALL_VARIANT_DEFAULT_POLICY = FALL_VARIANT_DEFAULT_POLICY
_FALL_VARIANT_TO_PERSONA = FALL_VARIANT_TO_PERSONA


logger = logging.getLogger(__name__)

_PRE_MODEL_TRIGGER_ENABLED: bool = os.environ.get(
    "PRE_MODEL_TRIGGER_ENABLED", ""
).lower() in ("1", "true", "yes")


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


def _safe_float_db(value: Any) -> float | None:
    return _safe_float(value, None)


# ADR-019 Phase 7 S9: BE compact response -> simulator AIPrediction.
# Replaces the model-api raw normaliser (``normalise_verdict``) for the
# fall path. The compact response carries fewer fields than the
# model-api response (no SHAP top_features, no Vietnamese explanation
# string, no separate confidence) so we synthesise a generic Vietnamese
# explanation from probability + band. The richer XAI surface can be
# restored later by widening the BE response shape (out of S9 scope).

_BAND_TO_RISK_BAND: dict[str, str] = {
    "critical": "critical",
    "critical_fall": "critical",
    "warning": "warning",
    "possible_fall": "warning",
    "likely_fall": "warning",
    "normal": "normal",
    "unknown": "normal",
}

_BAND_TO_LABEL: dict[str, str] = {
    "critical": "critical_fall",
    "critical_fall": "critical_fall",
    "warning": "likely_fall",
    "likely_fall": "likely_fall",
    "possible_fall": "possible_fall",
    "normal": "normal",
    "unknown": "normal",
}


def _normalise_imu_window_response(
    response: dict[str, Any] | None,
    *,
    predicted_at: str,
) -> "AIPrediction":
    """Project ``ImuWindowResponse`` into the simulator's :class:`AIPrediction`.

    Returns an offline-shaped prediction when the response is missing
    or the backend reported ``status="model_unavailable"`` so the FE
    always has a deterministic envelope to render.
    """
    if not isinstance(response, dict):
        return AIPrediction(
            label="normal",
            probability=0.0,
            confidence=0.0,
            riskBand="normal",
            requiresAttention=False,
            highPriorityAlert=False,
            explanationSummary=(
                "Mobile BE không trả phản hồi — đang dùng ngưỡng pre-trigger."
            ),
            topFeatures=[],
            predictedAt=predicted_at,
            modelStatus="offline",
            failureReason="transport_error",
        )

    status = str(response.get("status") or "").strip().lower()
    if status != "ok":
        return AIPrediction(
            label="normal",
            probability=0.0,
            confidence=0.0,
            riskBand="normal",
            requiresAttention=False,
            highPriorityAlert=False,
            explanationSummary=(
                "AI model offline — đang dùng ngưỡng pre-trigger để quyết định cảnh báo."
            ),
            topFeatures=[],
            predictedAt=predicted_at,
            modelStatus="offline",
            failureReason=(
                "model_unavailable" if status == "model_unavailable" else "validation_422"
            ),
        )

    probability = _safe_float(response.get("fall_probability"), 0.0) or 0.0
    probability = max(0.0, min(1.0, probability))
    band_raw = str(response.get("prediction_band") or "unknown").strip().lower()
    risk_band = _BAND_TO_RISK_BAND.get(band_raw, "normal")
    label = _BAND_TO_LABEL.get(band_raw, "normal")
    requires_attention = bool(response.get("requires_attention"))
    predicted_fall = bool(response.get("predicted_fall"))
    # ``highPriorityAlert`` keeps the same semantics as the legacy
    # model-api flag: critical band + high probability.
    high_priority_alert = (risk_band == "critical") and (probability >= 0.8 or predicted_fall)

    # P0-4 (2026-05-18): propagate BE-side IDs so a follow-up
    # /telemetry/alert can dedup against the existing FallEvent row
    # instead of inserting a duplicate.
    raw_fall_event_id = response.get("fall_event_id")
    fall_event_id: int | None = None
    if isinstance(raw_fall_event_id, int):
        fall_event_id = raw_fall_event_id
    elif isinstance(raw_fall_event_id, str) and raw_fall_event_id.strip().isdigit():
        fall_event_id = int(raw_fall_event_id.strip())

    raw_request_id = response.get("model_request_id")
    model_request_id: str | None = None
    if isinstance(raw_request_id, str) and raw_request_id.strip():
        model_request_id = raw_request_id.strip()

    explanation = _build_synthetic_fall_explanation(
        risk_band=risk_band,
        probability=probability,
        predicted_fall=predicted_fall,
        model_request_id=model_request_id,
    )
    return AIPrediction(
        label=label,  # type: ignore[arg-type]
        probability=probability,
        # No separate confidence channel from the BE compact response —
        # mirror probability so downstream metadata (S2 confidence
        # bridge) stays meaningful.
        confidence=probability,
        riskBand=risk_band,  # type: ignore[arg-type]
        requiresAttention=requires_attention,
        highPriorityAlert=high_priority_alert,
        explanationSummary=explanation,
        topFeatures=[],
        predictedAt=predicted_at,
        modelStatus="ok",
        fallEventId=fall_event_id,
        modelRequestId=model_request_id,
    )


_BAND_PHRASE_VI: dict[str, str] = {
    "critical": "té ngã nghiêm trọng",
    "warning": "khả năng té ngã",
    "normal": "không có dấu hiệu té ngã",
}


def _build_synthetic_fall_explanation(
    *,
    risk_band: str,
    probability: float,
    predicted_fall: bool,
    model_request_id: Any,
) -> str:
    """Compose a short Vietnamese sentence from the BE compact response.

    Replaces the model-api SHAP-driven Vietnamese sentence with a
    deterministic synthesis so the operator UI keeps a useful caption
    even though the rich XAI fields are not on the BE response shape.
    """
    phrase = _BAND_PHRASE_VI.get(risk_band, _BAND_PHRASE_VI["normal"])
    pct = int(round(probability * 100))
    base = f"AI đánh giá: {phrase} (xác suất {pct}%)."
    if predicted_fall and risk_band != "critical":
        base += " Mức xác suất chưa đủ cao để escalate SOS."
    request_id = str(model_request_id or "").strip()
    if request_id:
        base += f" Trace: {request_id[:8]}…"
    return base


def _safe_int(value: Any) -> int | None:
    cast = _safe_float(value, None)
    return int(round(cast)) if cast is not None else None


def _coerce_float_list(value: Any) -> list[float]:
    """Best-effort conversion of *value* to a ``list[float]``.

    Designed for the motion arrays emitted by ``MotionGenerator``: numpy
    arrays, plain lists, tuples — anything iterable.  Non-numeric entries
    are skipped silently so a partial dataset row does not crash the
    response (we'd rather return what we can than 500 the operator).
    """
    if value is None:
        return []
    try:
        iterator = iter(value)  # type: ignore[arg-type]
    except TypeError:
        cast = _safe_float(value, None)
        return [cast] if cast is not None else []
    out: list[float] = []
    for item in iterator:
        cast = _safe_float(item, None)
        if cast is not None:
            out.append(cast)
    return out


# Sleep scenario data loaded from external YAML config (see api_server/config/sleep_scenarios.yaml)
SLEEP_SCENARIO_PHASES, SLEEP_SCENARIO_PROFILES = load_sleep_scenarios()

# MEDIUM #8: Threshold constants centralised in vitals_service.py
# Import them here for backward compatibility.
from api_server.services.vitals_service import DAYTIME_THRESHOLDS, SLEEP_THRESHOLDS




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
        self._health_state = HealthRuntimeState()
        self._runtime_persistence: PersistenceState = load_runtime_config()
        self._sync_runtime_env_from_persistence()
        self._sleep_ai_client = SleepAIClient()
        self._last_sleep_score_source = "heuristic"
        self._init_health_probes()
        self._init_core_state()
        self._init_transport()
        self._init_pre_trigger()
        self._init_services()

    # ── Private init helpers ─────────────────────────────────────────────

    def _init_health_probes(self) -> None:
        """Check Sleep AI availability and update health probe state."""
        try:
            if self._sleep_ai_client.check_availability():
                logger.info("Sleep AI model available at http://localhost:8001")
                with self._health_state.lock:
                    self._health_state.model_api_probe.state = "ready"
                    self._health_state.model_api_probe.checked_at = _utc_now_iso()
            else:
                logger.warning("Sleep AI model not available — heuristic fallback active")
                with self._health_state.lock:
                    self._health_state.model_api_probe.state = "unavailable"
                    self._health_state.model_api_probe.checked_at = _utc_now_iso()
        except Exception:
            logger.warning("Sleep AI availability check failed", exc_info=True)

    def _init_core_state(self) -> None:
        """Initialise all per-device and per-session in-memory dictionaries."""
        # ── Fall AI dispatcher (Module FA — Fall Lab redesign, S9 rewire) ──
        # ADR-019 Phase 7 S9: per-device caches surfaced via
        # ``/sessions/{id}/fall-state``. The :class:`MobileTelemetryClient`
        # itself is wired below — after ``_health_backend_url`` has been
        # resolved — because its constructor needs the backend base URL.
        self._fall_predictions: dict[str, AIPrediction] = {}
        self._fall_motion_refs: dict[str, MotionWindowRef] = {}
        self._fall_countdown_policies: dict[str, CountdownPolicy] = {}
        # Phase 2 — pre-trigger evidence captured at inject_event time so
        # the FE Fall Lab pipeline strip (Section B stage 2) shows BE truth
        # instead of FE-derived peak-vs-threshold guesses.
        self._fall_pre_trigger_results: dict[str, PreTriggerEvidence] = {}
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
        # ADR-024 Phase 7 S14: flow event channel for the sequence diagram.
        # Keyed by session_id; each subscriber holds an asyncio.Queue that
        # the WS handler drains.  Threading.Lock (not asyncio.Lock) because
        # subscribe/unsubscribe may be called from the async WS task while
        # publish_flow_event is called from the sync tick thread.
        self._flow_subscribers: dict[str, list[asyncio.Queue]] = {}
        self._flow_lock = Lock()
        # ``push_interval`` now sourced from the persistence layer; the env
        # var is kept in sync for downstream readers (Module F.1).
        self._push_interval = max(1, int(self._runtime_persistence.values.push_interval_seconds))
        # Per-device buffer + in-flight flag (fix bug "dữ liệu đi cùng qua 1
        # API"). Mỗi device có buffer riêng và flag in-flight riêng → 1
        # device fail/retry không kéo cả fleet đứng cùng lúc.
        self._device_buffers: dict[str, list[dict[str, Any]]] = {}
        self._last_push_time = 0.0
        self._device_in_flight: set[str] = set()

    def _init_transport(self) -> None:
        """Wire backend URLs, admin/mobile clients, and transport router."""
        self._health_backend_url = self._resolve_backend_base_url()
        self.backend_base_url = self._health_backend_url
        self.admin_client = BackendAdminClient(self._health_backend_url)
        # ADR-019 Phase 7 S9: dispatch IMU windows through the mobile BE
        # (``POST /api/v1/mobile/telemetry/imu-window``) instead of the
        # model-api directly. Wired here — after ``_health_backend_url``
        # is resolved — so the constructor can build the correct base
        # URL. The compact ``ImuWindowResponse`` is normalised back into
        # :class:`AIPrediction` by :func:`_normalise_imu_window_response`
        # so the operator UI keeps the same envelope as the legacy
        # ``FallAIClient`` path.
        self._mobile_telemetry_client = MobileTelemetryClient(
            base_url=self._health_backend_url,
            http_sender=self._http_sender_with_body,
            internal_secret=os.environ.get("INTERNAL_SERVICE_SECRET") or None,
        )
        logger.info(
            "Mobile telemetry client wired (fall window path -> %s/api/v1/mobile/telemetry/imu-window)",
            self._health_backend_url,
        )
        # ADR-019 Phase 7 S10: route sleep-risk prediction through the
        # mobile BE (``POST /api/v1/mobile/telemetry/sleep-risk``) instead
        # of calling ``SleepAIClient.predict`` directly against model-api.
        # The dispatcher wraps ``MobileTelemetryClient.submit_sleep_record``
        # with payload validation + structured logging. ``SleepAIClient``
        # is retained for the dashboard availability probe only
        # (model-api uptime indicator) — its disposal is tracked at S18.
        self._sleep_risk_dispatcher = SleepRiskDispatcher(self._mobile_telemetry_client)
        logger.info(
            "Sleep risk dispatcher wired (sleep-risk path -> %s/api/v1/mobile/telemetry/sleep-risk)",
            self._health_backend_url,
        )
        mqtt = MqttPublisher(topic_prefix="devices/sim", client=lambda topic, payload: True)
        http = HttpPublisher(
            endpoint=self._telemetry_ingest_endpoint(self._health_backend_url),
            sender=self._http_sender,
            headers={"X-Internal-Service": "iot-simulator"},
        )
        self.transport_router = TransportRouter(mqtt, http)

    def _init_pre_trigger(self) -> None:
        """Wire TriggerOrchestrator pipeline and auxiliary per-device trackers."""
        # ── Pre-model TriggerOrchestrator wiring (Phase 0.3) ─────────────
        # See plans/iot-sim-ux-refactor-backlog-75c8a6.md §4.5 task 0.3.
        # The orchestrator is what `routers/settings.py` reaches into for DB
        # thresholds; previously it was None which forced the settings
        # endpoint into its except branch and reported `threshold_source =
        # "fallback"` permanently.  We construct the full pipeline here so
        # downstream consumers (settings, health, future tick evaluations)
        # can rely on a single instance.
        self._trigger_orchestrator: TriggerOrchestrator | None = None
        try:
            _settings_provider = SystemSettingsProvider()
            _rule_engine = RuleEngine(settings_provider=_settings_provider)
            _fall_pre_trigger = FallPreTrigger(settings_provider=_settings_provider)
            # Phase 2 — keep refs on self so inject_event can capture
            # PreTriggerEvidence on the same motion window the AI sees,
            # without spinning up a fresh FallPreTrigger per call.
            self._settings_provider = _settings_provider
            self._fall_pre_trigger = _fall_pre_trigger
            _api_client = HealthGuardAPIClient(
                base_url=self._health_backend_url,
                http_sender=self._http_sender,
                internal_secret=os.environ.get("INTERNAL_SERVICE_SECRET") or None,
            )
            _vitals_buffer = VitalsHistoryBuffer(max_size=60)
            self._trigger_orchestrator = TriggerOrchestrator(
                settings_provider=_settings_provider,
                rule_engine=_rule_engine,
                fall_pre_trigger=_fall_pre_trigger,
                api_client=_api_client,
                response_handler=ResponseHandler,
                vitals_buffer=_vitals_buffer,
                enable_model_calls=False,
            )
            logger.info(
                "TriggerOrchestrator wired (pre_trigger_enabled=%s)",
                _PRE_MODEL_TRIGGER_ENABLED,
            )
        except Exception:
            logger.warning(
                "TriggerOrchestrator initialisation failed — settings will report threshold_source=fallback",
                exc_info=True,
            )
            self._trigger_orchestrator = None
        self._bp_last_observed: dict[str, float] = {}
        self._last_alert_pushes: dict[tuple[str, str, str], float] = {}
        self._alert_pushes_in_flight: set[tuple[str, str, str]] = set()
        self._sleep_phase_tracker: dict[str, tuple[int, float]] = {}
        self._db_device_active_cache: dict[int, bool] = {}
        # ``background_tick_interval`` sourced from the persistence layer
        # (Module F.1); env var stays in sync via ``_sync_runtime_env_*``.
        self._background_tick_interval = max(
            0.1, float(self._runtime_persistence.values.tick_interval_seconds)
        )
        self._background_tick_stop = Event()
        self._background_tick_thread: Thread | None = None

    def _init_services(self) -> None:
        """Instantiate all domain service objects (Task 3.x service layer)."""
        # ── Service layer (Task 3.1) ─────────────────────────────────────
        self._dashboard_cache_ref: list = [None]
        self.device_service = DeviceService(
            devices=self.devices,
            sessions=self.sessions,
            device_scenarios=self.device_scenarios,
            risk_snapshots=self.risk_snapshots,
            risk_history=self.risk_history,
            tick_buffer=self._device_buffers,
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
            internal_secret=os.environ.get("INTERNAL_SERVICE_SECRET") or None,
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
            sleep_risk_dispatcher=self._sleep_risk_dispatcher,
            sleep_phase_tracker=self._sleep_phase_tracker,
            health_backend_url=self._health_backend_url,
            http_sender=self._http_sender,
            publish_device_log_fn=self._publish_device_log,
            require_device_fn=self.device_service._require_device,
            internal_secret=os.getenv("INTERNAL_SERVICE_SECRET"),
            # MEDIUM #9: pass pre-loaded scenario data to avoid double load
            sleep_scenario_phases=SLEEP_SCENARIO_PHASES,
            sleep_scenario_profiles=SLEEP_SCENARIO_PROFILES,
        )

    # ── Runtime persistence helpers (Module F.1 / F.2) ───────────────────

    def _sync_runtime_env_from_persistence(self) -> None:
        """Mirror the persisted ``sleep_speed_factor`` into ``os.environ``.

        Module H cleanup: ``SIM_TICK_INTERVAL_SECONDS`` and
        ``SIM_PUSH_INTERVAL_SECONDS`` mirrors were dead — no consumer in
        ``api_server/`` reads them; live values are read directly from
        ``self._background_tick_interval`` / ``self._push_interval``.
        Only ``sleep_service`` still reads ``SIM_SLEEP_SPEED_FACTOR`` from
        env (it has no ``SimulatorRuntime`` handle), so that mirror stays
        until a follow-up wires sleep_service to the runtime directly.
        """
        values = self._runtime_persistence.values
        os.environ["SIM_SLEEP_SPEED_FACTOR"] = str(values.sleep_speed_factor)

    def apply_and_persist_runtime_config(
        self,
        *,
        tick_interval_seconds: float | None = None,
        push_interval_seconds: int | None = None,
        sleep_speed_factor: float | None = None,
    ) -> PersistenceState:
        """Apply *partial* updates to the runtime config and flush to disk.

        Used by ``PUT /api/v1/sim/settings/runtime``.  Returns the new
        :class:`PersistenceState` so the router can echo it back to the FE
        (the persistence indicator copy reads from ``last_saved_at``).

        Atomicity: live runtime fields and the env mirror are only updated
        *after* :func:`save_runtime_config` returns successfully, so a disk
        failure leaves the running simulator's state intact.
        """
        with self._runtime_persistence.lock:
            current = self._runtime_persistence.values
            new_values = RuntimeConfigValues(
                tick_interval_seconds=(
                    float(tick_interval_seconds)
                    if tick_interval_seconds is not None
                    else current.tick_interval_seconds
                ),
                push_interval_seconds=(
                    int(push_interval_seconds)
                    if push_interval_seconds is not None
                    else current.push_interval_seconds
                ),
                sleep_speed_factor=(
                    float(sleep_speed_factor)
                    if sleep_speed_factor is not None
                    else current.sleep_speed_factor
                ),
            )

            saved_at = save_runtime_config(new_values)

            # Apply to live runtime + env *after* the disk write succeeds.
            self._background_tick_interval = max(0.1, new_values.tick_interval_seconds)
            self._push_interval = max(1, new_values.push_interval_seconds)
            self._runtime_persistence.values = new_values
            self._runtime_persistence.source = "file"
            self._runtime_persistence.path = RUNTIME_PATH
            self._runtime_persistence.last_saved_at = saved_at
            self._runtime_persistence.last_error = None
            self._sync_runtime_env_from_persistence()

        return self._runtime_persistence

    def restore_runtime_defaults(self) -> PersistenceState:
        """Delete ``runtime.json`` and reload the defaults.

        Backs the "Khôi phục mặc định" button in Settings (Module F.5).
        Idempotent — safe to call when the file is already absent.
        """
        with self._runtime_persistence.lock:
            new_state = reset_runtime_config()
            self._background_tick_interval = max(0.1, new_state.values.tick_interval_seconds)
            self._push_interval = max(1, new_state.values.push_interval_seconds)
            self._runtime_persistence.values = new_state.values
            self._runtime_persistence.source = new_state.source
            self._runtime_persistence.path = new_state.path
            self._runtime_persistence.last_saved_at = new_state.last_saved_at
            self._runtime_persistence.last_error = new_state.last_error
            self._sync_runtime_env_from_persistence()
        return self._runtime_persistence

    def runtime_persistence_snapshot(self) -> PersistenceState:
        """Return the current persistence state for the settings endpoint."""
        return self._runtime_persistence

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
        # FastAPI Uvicorn local listens at /api/v1/mobile/... without /api
        # In production behind proxy, base_url should include the /api (e.g. http://domain/api/v1)
        return f"{base_url.rstrip('/')}/api/v1/mobile/telemetry/ingest"

    @staticmethod
    def _telemetry_alert_endpoint(base_url: str) -> str:
        # Mirrors the ingest endpoint path strategy: direct local calls hit /api/v1/mobile/...
        return f"{base_url.rstrip('/')}/api/v1/mobile/telemetry/alert"

    # ADR-020 Phase 7 S7: ``_risk_calculate_endpoint`` + ``_trigger_risk_inference``
    # disposed. The BE now auto-calls ``calculate_device_risk`` after every
    # successful ``/telemetry/ingest`` (cooldown ``RISK_COOLDOWN_SECONDS``,
    # default 60s) so the simulator never has to request a re-evaluation.
    # Removing the helper drops a stale duplication of the BE risk policy.

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

    @staticmethod
    def _http_sender_with_body(
        endpoint: str,
        payload: str,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
    ) -> tuple[int, str]:
        """ADR-019 Phase 7 S9: body-aware POST for :class:`MobileTelemetryClient`.

        Matches the ``HttpSenderWithBodyFn`` contract — returns
        ``(status_code, body_text)``. Status ``< 0`` signals a
        transport-level failure (connection refused / DNS / timeout) so
        the caller can branch without parsing exception types.
        """
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        try:
            response = httpx.post(
                endpoint,
                content=payload.encode("utf-8"),
                headers=request_headers,
                timeout=timeout,
            )
            return response.status_code, response.text
        except httpx.HTTPStatusError as exc:
            return exc.response.status_code, exc.response.text
        except httpx.HTTPError as exc:
            logger.warning(
                "Body-aware POST %s transport failure: %s",
                endpoint,
                exc,
            )
            return -1, ""

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

    # ── ADR-024 Phase 7 S14: Flow event WebSocket channel ────────────────

    def subscribe_flow_events(self, session_id: str) -> asyncio.Queue:
        """Register a new subscriber queue for *session_id* and return it."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._flow_lock:
            self._flow_subscribers.setdefault(session_id, []).append(queue)
        return queue

    def unsubscribe_flow_events(self, session_id: str, queue: asyncio.Queue) -> None:
        """Remove *queue* from the subscriber list for *session_id*."""
        with self._flow_lock:
            subs = self._flow_subscribers.get(session_id, [])
            self._flow_subscribers[session_id] = [q for q in subs if q is not queue]

    def publish_flow_event(self, session_id: str, event: dict) -> None:
        """Emit a flow event to all active subscribers for *session_id*.

        Called synchronously from tick/alert handlers.  Subscribers that
        are slow consumers have their queue silently dropped when full
        (maxsize=100 ≈ 500 s buffer at peak 5/s) — flow events are
        best-effort diagnostic data, not critical path.
        """
        event.setdefault("ts", _utc_now_iso())
        event.setdefault("session_id", session_id)
        with self._flow_lock:
            queues = list(self._flow_subscribers.get(session_id, []))
        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.debug(
                    "Flow event queue full for session=%s step=%s — dropping",
                    session_id, event.get("step"),
                )

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
        # ADR-024 S14: emit alert_push flow event for all running sessions.
        for sid, s in self.sessions.items():
            if s.status == "running":
                self.publish_flow_event(sid, {
                    "step": "alert_push",
                    "device_id": sim_device_id,
                    "status": "running",
                    "payload": {"event_type": event_type, "severity": severity},
                })

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

    def _publish_vitals_http(
        self, pending_publish: PendingDevicePublish
    ) -> tuple[int, set[int], str | None]:
        """ADR-020 S6 — push vitals batch over HTTP to the mobile BE.

        Returns ``(ack_count, synced_device_ids, error_detail)``:

        * ``ack_count`` mirrors ``response.ingested`` so the existing
          ``publish_ok`` / ``last_publish_ack_count`` tracking semantics
          stay intact (publish_ok = ack==count).
        * ``synced_device_ids`` is ``response.risk_evaluated_devices``
          so the dashboard can surface which devices the BE
          auto-trigger fanned out for (OQ5 visibility).
        * ``error_detail`` is a short tag suitable for the dashboard
          error column on the non-2xx / exception path.

        Payload matches the S5 ``VitalIngestRequest`` schema
        (``extra="forbid"`` rejects unknown keys), so only the 9
        canonical vital fields are forwarded — motion + metadata stay
        sim-local.
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

    def _execute_pending_tick_publish(
        self, pending_publishes: list[PendingDevicePublish] | None
    ) -> None:
        if not pending_publishes:
            return
        for pending_publish in pending_publishes:
            self._execute_single_device_publish(pending_publish)

    def _execute_single_device_publish(
        self,
        pending_publish: PendingDevicePublish,
    ) -> None:
        """Publish 1 device's buffer via HTTP; isolate state update per device."""
        device_id = pending_publish.device_id
        publish_started = monotonic()
        message_count = len(pending_publish.messages)

        ack_count, synced_device_ids, publish_error_detail = (
            self._publish_vitals_http(pending_publish)
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
            for session in self.sessions.values():
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
                self._refresh_session_publish_aggregate_locked(session)
            if publish_ok:
                buffer = self._device_buffers.get(device_id)
                if buffer is not None:
                    del buffer[: pending_publish.clear_count]
                self._last_push_time = monotonic()
                self._refresh_pending_sync_flags()

        # ADR-024 S14: emit vitals_ingest flow event for every running session
        # that owns this device (per-device granularity).
        running_session_ids = [
            sid
            for sid, s in self.sessions.items()
            if s.status == "running" and device_id in s.device_ids
        ]
        for sid in running_session_ids:
            self.publish_flow_event(
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

    @staticmethod
    def _refresh_session_publish_aggregate_locked(session: SessionRecord) -> None:
        """Recompute flat ``last_publish_*`` from per-device map.

        Backward-compat: dashboard, health-check, evidence center vẫn đọc
        các field flat này. Aggregate semantic:
        - ``last_publish_ok`` = AND của mọi device có status (vẫn yêu cầu
          tất cả device ack thành công để session "khoẻ").
        - ``ack_count`` / ``count`` / ``ack_count_total`` / ``attempt_count``
          = tổng cộng dồn từ map.
        - ``latency_ms`` = max của các device (worst-case observability).
        - ``last_error`` / ``last_attempt_at`` / ``last_ok_at`` = giá trị
          mới nhất theo timestamp.
        """
        statuses = list(session.device_publish_status.values())
        if not statuses:
            return
        session.last_publish_ack_count = sum(s.ack_count for s in statuses)
        session.last_publish_count = sum(s.message_count for s in statuses)
        session.publish_ack_count_total = sum(
            s.ack_count_total for s in statuses
        )
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

    @staticmethod
    def _local_database_healthy() -> bool:
        try:
            with session_scope() as db:
                db.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def _measure_database_health(self) -> tuple[bool, int | None]:
        """Probe the local DB once and return (healthy, latency_ms)."""
        start = monotonic()
        ok = self._local_database_healthy()
        latency_ms = int((monotonic() - start) * 1000)
        return ok, latency_ms

    def _backend_healthy(self) -> bool:
        endpoint = f"{self._health_backend_url.rstrip('/')}/api/v1/mobile/health"
        try:
            with urlopen(Request(endpoint, method="GET"), timeout=3.0) as response:
                return int(response.getcode() or 0) == 200
        except Exception:
            return False

    # ── Health probes with TTL caching (Phase 0.4) ───────────────────────
    # Both probes share the same TTL window so the dashboard hero can poll
    # ``/api/v1/sim/health`` aggressively without hammering upstream services.
    _HEALTH_PROBE_TTL_SECONDS = 5.0
    _HEALTH_BACKEND_SLOW_LATENCY_MS = 1500

    # ── Module C: SOS countdown ─────────────────────────────────────────
    # Window between a `fall_detected` event and the auto-`fall_no_response`
    # escalation. The frontend reads ``countdownTotalSec`` from the
    # ``/sessions/{id}/fall-state`` response so the UI never invents its
    # own timer.
    _SOS_COUNTDOWN_SECONDS = 30

    def _probe_backend_cached(self) -> None:
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

    def _probe_model_api_cached(self) -> None:
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

    def _run_session_side_effects(self, effects: SessionSideEffects) -> None:
        self._execute_pending_tick_publish(effects.pending_publishes)

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

    # ADR-020 Phase 7 S7: ``_trigger_risk_inference`` disposed. With the
    # HTTP vitals path active (S6) and the BE auto-trigger live at
    # ``/telemetry/ingest`` (S5 — ``calculate_device_risk`` with 60s
    # cooldown), the simulator no longer requests risk re-evaluation. The
    # legacy public surface ``trigger_risk_calculation`` + the router
    # endpoint ``/analytics/risk/trigger`` were also removed in S7.

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

    def recover_active_sessions(self) -> int:
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
            "normal_walking",
        }
        _WAKING_SCENARIOS = {
            "normal_rest",
            "normal_walking",
            "tachycardia_warning",
            "hypoxia_critical",
            "hypertension_moderate",
            "high_risk_cardiac",
            "medium_risk_general",
        }
        effects = SessionSideEffects()
        _FALL_EVENT_MAP = {
            "fall_high_confidence": "fall_1",
            "fall_no_response":     "fall_no_response",
            "fall_false_alarm":     "fall_brief",
        }
        _fall_variant_to_dispatch: str | None = None
        with self._lock:
            self._require_device(device_id)
            if scenario_id not in known:
                raise KeyError(f"Unknown scenario id: {scenario_id}")
            self.device_scenarios[device_id] = scenario_id
            # Fall scenarios: record the variant to dispatch AFTER the lock so
            # SimulatorRuntime.inject_event (full path: fall AI + FCM fanout)
            # runs instead of the bare InMemorySimulator.inject_event which only
            # transitions PersonaEngine state without calling _call_fall_ai_locked.
            if scenario_id in _FALL_EVENT_MAP:
                _fall_variant_to_dispatch = _FALL_EVENT_MAP[scenario_id]
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
            if scenario_id == "normal_walking":
                for _sr in self.sessions.values():
                    if _sr.status != "running" or device_id not in _sr.device_ids:
                        continue
                    for _device in _sr.simulator.devices:
                        if _device.device_id == device_id:
                            _device.engine.transition_to("walking")
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
        # Fall AI dispatch (must run outside the lock — inject_event acquires its own lock
        # and executes the full pipeline: tick → _call_fall_ai_locked → FCM fanout).
        if _fall_variant_to_dispatch is not None:
            self.inject_event(device_id, "fall_detected", _fall_variant_to_dispatch)

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

    # ------------------------------------------------------------------
    # Fall variant policy resolution + AI verdict (Module FA)
    # ------------------------------------------------------------------

    def _has_recent_fall_event_locked(
        self, device_id: str, *, seconds: float = 5.0
    ) -> bool:
        """Return True if a ``fall_detected`` event fired for this device recently.

        Used by the tick loop to dedupe its "fall via dataset annotation"
        recording against the canonical ``inject_event`` recording. The
        check walks ``event_history`` from newest to oldest and stops as
        soon as it finds an event older than ``seconds`` for the target
        device — bounded latency under the operating maxlen=2000 deque.
        """
        for event in reversed(self.event_history):
            if event.device_id != device_id:
                continue
            if event.event_type != "fall_detected":
                continue
            if self._iso_age_seconds(event.timestamp) <= seconds:
                return True
            return False
        return False

    @staticmethod
    def _resolve_fall_variant_policy(
        fe_variant: str | None,
    ) -> tuple[_FallVariantPolicy, str]:
        """Return ``(policy, persona_variant)`` for an operator-supplied variant.

        Falls back to ``confirmed`` policy + ``fall_1`` persona for any
        unknown variant string so legacy callers keep working.  The
        persona variant is what the PersonaEngine + signal generator key
        off for vitals/motion deltas; the FE-facing variant is what
        appears in events + recent_fall_events.
        """
        key = (fe_variant or "confirmed").strip().lower()
        policy = _FALL_VARIANT_POLICIES.get(key, _FALL_VARIANT_DEFAULT_POLICY)
        persona = _FALL_VARIANT_TO_PERSONA.get(key, "fall_1")
        return policy, persona

    def _call_fall_ai_locked(
        self,
        motion: dict[str, Any] | None,
        device_id: str,
        fe_variant: str,
    ) -> AIPrediction:
        """Post the most recent IMU window to the mobile BE for fall inference.

        ADR-019 Phase 7 S9: the simulator used to call the model-api
        directly via :class:`FallAIClient`. It now dispatches through
        :class:`MobileTelemetryClient` so the backend can persist the
        raw window (``imu_windows``), the fall event (``fall_events``),
        auto-trigger risk, and fan FCM out — same trust boundary as a
        production smartwatch -> phone -> BE -> model-api path.

        Returns an ``AIPrediction`` even on failure so the FE always has
        a deterministic shape: ``modelStatus`` distinguishes ``ok`` from
        ``offline`` from ``no_window`` from ``skipped`` (no bound DB
        device). No exception escapes.
        """
        predicted_at = _utc_now_iso()
        sample_count = 0
        if isinstance(motion, dict):
            # NOTE: motion arrays may be numpy ndarrays so `arr or []`
            # raises "truth value ambiguous".  Coerce via explicit None
            # checks + len() — same pattern as fall_ai_client._coerce.
            ax = motion.get("accel_x")
            ay = motion.get("accel_y")
            az = motion.get("accel_z")
            sample_count = min(
                len(ax) if ax is not None else 0,
                len(ay) if ay is not None else 0,
                len(az) if az is not None else 0,
            )
        if sample_count < 50:
            return AIPrediction(
                label="normal",
                probability=0.0,
                confidence=0.0,
                riskBand="normal",
                requiresAttention=False,
                highPriorityAlert=False,
                explanationSummary=(
                    f"Không đủ mẫu chuyển động để đánh giá (có {sample_count}, cần 50). "
                    "Hệ thống đang dùng pre-trigger fallback."
                ),
                topFeatures=[],
                predictedAt=predicted_at,
                modelStatus="no_window",
            )

        # Resolve the backend device PK — the BE rejects ``/imu-window``
        # without it because the persistence path needs a ``devices.id``
        # to attach the row to. Unbound simulator devices skip the call
        # entirely and surface ``modelStatus=skipped``.
        device = self.devices.get(device_id)
        bound_db_device_id = device.bound_db_device_id if device is not None else None
        if bound_db_device_id is None:
            return AIPrediction(
                label="normal",
                probability=0.0,
                confidence=0.0,
                riskBand="normal",
                requiresAttention=False,
                highPriorityAlert=False,
                explanationSummary=(
                    "Thiết bị mô phỏng chưa bind backend — bỏ qua dispatch IMU window."
                ),
                topFeatures=[],
                predictedAt=predicted_at,
                modelStatus="skipped",
                failureReason="device_unbound",
            )

        fall_context = FALL_VARIANT_CONTEXT.get(fe_variant, FALL_VARIANT_DEFAULT_CONTEXT)
        samples = _motion_window_to_samples(motion, fall_context=fall_context)
        if len(samples) < 50:
            return AIPrediction(
                label="normal",
                probability=0.0,
                confidence=0.0,
                riskBand="normal",
                requiresAttention=False,
                highPriorityAlert=False,
                explanationSummary=(
                    "Không đủ mẫu sau khi chuyển đổi window — pre-trigger fallback."
                ),
                topFeatures=[],
                predictedAt=predicted_at,
                modelStatus="no_window",
                failureReason="insufficient_samples",
            )

        logger.info(
            "submit_imu_window → device=%s db_device=%s samples=%d url=%s",
            device_id,
            bound_db_device_id,
            len(samples),
            getattr(self._mobile_telemetry_client, "_base_url", "?"),
        )
        try:
            response = self._mobile_telemetry_client.submit_imu_window(
                device_id=device_id,
                db_device_id=int(bound_db_device_id),
                window_data=samples,
            )
        except Exception:  # pragma: no cover — defensive
            logger.warning(
                "Mobile telemetry IMU window submit raised unexpectedly",
                exc_info=True,
            )
            response = None
        logger.info(
            "submit_imu_window ← response=%s",
            None if response is None else {k: v for k, v in response.items() if k in ("status", "fall_event_id", "fall_probability")},
        )

        return _normalise_imu_window_response(
            response,
            predicted_at=predicted_at,
        )

    def _build_motion_window_ref(
        self,
        payload: dict[str, Any] | None,
        fe_variant: str,
    ) -> MotionWindowRef | None:
        """Capture a ref to the motion window the AI was called on."""
        if not payload:
            return None
        motion = payload.get("motion") or {}
        # NOTE: numpy arrays — see _call_fall_ai_locked for context.
        ax = motion.get("accel_x")
        ay = motion.get("accel_y")
        az = motion.get("accel_z")
        sample_count = min(
            len(ax) if ax is not None else 0,
            len(ay) if ay is not None else 0,
            len(az) if az is not None else 0,
        )
        if sample_count == 0:
            return None
        return MotionWindowRef(
            emittedAt=str(payload.get("emitted_at") or _utc_now_iso()),
            sampleCount=sample_count,
            sampleRate=_safe_float(motion.get("sample_rate"), None),
            fallVariant=fe_variant or None,
        )

    def _compute_pre_trigger_evidence(
        self,
        motion: dict[str, Any] | None,
    ) -> PreTriggerEvidence | None:
        """Run pre-trigger evaluation against the inject-time motion window.

        Phase 2 wiring — exposes the BE's hard/soft trigger reasoning
        to the FE Fall Lab pipeline strip (Section B stage 2).  We
        adapt the column-array motion shape from MotionGenerator into
        the per-sample dict that :class:`FallPreTrigger` consumes by
        reading the most recent sample's accel/gyro values, plus the
        precomputed peak / posture / low-motion fields the persona
        engine attaches to the window metadata.

        Returns ``None`` only when the runtime has no FallPreTrigger
        configured (pre-trigger disabled at startup).  In that case the
        FE strip falls back to its FE-derived peak-vs-threshold view.
        """
        if not motion:
            return None
        # Late import to avoid circular Iot_Simulator -> pre_model_trigger
        # at module load time.  The instance is created at __init__ time
        # via the TriggerOrchestrator wiring; if startup failed we have
        # no pre-trigger to query and return None so the FE strip falls
        # back to its FE-derived peak-vs-threshold view.
        pre_trigger = getattr(self, "_fall_pre_trigger", None)
        if pre_trigger is None:
            return None

        # Build the per-sample dict the evaluator expects.  Use the LAST
        # sample (impact tail) for accel/gyro instantaneous values and
        # forward the window-level peak/posture/low-motion metadata
        # MotionGenerator already attaches.
        # NOTE: motion arrays are numpy ndarrays from MotionGenerator's
        # parquet pipeline so we MUST avoid `arr or []` and `not arr`
        # which both raise `ValueError: truth value of an array is
        # ambiguous`.  Mirrors the same pattern in
        # ``simulator_core.fall_ai_client.motion_window_to_samples``.
        def _coerce(value: Any) -> list[Any]:
            if value is None:
                return []
            try:
                return list(value)
            except TypeError:
                return []

        ax_arr = _coerce(motion.get("accel_x"))
        ay_arr = _coerce(motion.get("accel_y"))
        az_arr = _coerce(motion.get("accel_z"))
        gx_arr = _coerce(motion.get("gyro_x"))
        gy_arr = _coerce(motion.get("gyro_y"))
        gz_arr = _coerce(motion.get("gyro_z"))

        def _last(arr: Any) -> float | None:
            try:
                length = len(arr)
            except TypeError:
                return None
            if length == 0:
                return None
            try:
                return float(arr[length - 1])
            except (TypeError, ValueError):
                return None

        # Phase 3 fix — derive window-level peaks ourselves so the
        # evaluator does not fall back to the LAST-sample magnitude.
        # Accel raw values are in m/s²; convert to g to match the
        # 3.0g / 2.5g thresholds on `FallPreTrigger`.  Gyro is already
        # in dps so passes through unchanged.
        #
        # Without this fix, when the source motion window does not carry
        # an `accel_mag_peak_g` metadata key, the evaluator computed
        # sqrt(x²+y²+z²) of the LAST sample (~22 m/s² typical) and
        # compared to 3.0g — falsely tripping the HARD trigger for every
        # variant.
        _G_TO_MS2 = 9.80665

        def _peak_g_from_arrays(ax: list[Any], ay: list[Any], az: list[Any]) -> float | None:
            n = min(len(ax), len(ay), len(az))
            if n == 0:
                return None
            peak_ms2 = 0.0
            for i in range(n):
                try:
                    x = float(ax[i]); y = float(ay[i]); z = float(az[i])
                except (TypeError, ValueError):
                    continue
                mag = math.sqrt(x * x + y * y + z * z)
                if mag > peak_ms2:
                    peak_ms2 = mag
            return peak_ms2 / _G_TO_MS2 if peak_ms2 > 0 else 0.0

        def _peak_dps_from_arrays(gx: list[Any], gy: list[Any], gz: list[Any]) -> float | None:
            n = min(len(gx), len(gy), len(gz))
            if n == 0:
                return None
            peak = 0.0
            for i in range(n):
                try:
                    x = float(gx[i]); y = float(gy[i]); z = float(gz[i])
                except (TypeError, ValueError):
                    continue
                mag = math.sqrt(x * x + y * y + z * z)
                if mag > peak:
                    peak = mag
            return peak

        # Prefer metadata when present (some parquet windows already carry
        # the correctly-scaled peak), else compute from arrays.
        accel_peak_g = motion.get("accel_mag_peak_g")
        if accel_peak_g is None:
            accel_peak_g = _peak_g_from_arrays(ax_arr, ay_arr, az_arr)
        gyro_peak_dps = motion.get("gyro_mag_peak_dps")
        if gyro_peak_dps is None:
            gyro_peak_dps = _peak_dps_from_arrays(gx_arr, gy_arr, gz_arr)

        sample = {
            "accel": {
                "x": _last(ax_arr) or 0.0,
                "y": _last(ay_arr) or 0.0,
                "z": _last(az_arr) or 0.0,
            },
            "gyro": {
                "x": _last(gx_arr) or 0.0,
                "y": _last(gy_arr) or 0.0,
                "z": _last(gz_arr) or 0.0,
            },
            "accel_mag_peak_g": accel_peak_g,
            "gyro_mag_peak_dps": gyro_peak_dps,
            "posture_change_angle_deg": motion.get("posture_change_angle_deg"),
            "post_impact_low_motion_duration_s": motion.get(
                "post_impact_low_motion_duration_s"
            ),
        }
        evidence_dict = pre_trigger.evaluate_with_evidence(sample)
        return PreTriggerEvidence(**evidence_dict)

    def _override_severity_from_verdict(
        self,
        policy: _FallVariantPolicy,
        verdict: AIPrediction,
    ) -> str:
        """Decide alert severity from policy default + AI verdict band.

        AI "critical" always escalates; AI "normal" downgrades a
        ``warning`` policy default to "warning" still (don't suppress
        alerts entirely without operator decision); ``critical`` policy
        defaults stay critical regardless of AI band so the worst-case
        path (``fall_no_response``) is preserved.
        """
        if policy.default_severity == "critical":
            return "critical"
        if verdict.riskBand == "critical":
            return "critical"
        if verdict.riskBand == "warning":
            return "warning"
        return policy.default_severity

    def inject_event(self, device_id: str, event_type: str, variant: str | None) -> None:
        effects = SessionSideEffects()
        with self._lock:
            for record in self.sessions.values():
                if device_id not in record.device_ids:
                    continue

                # ---- Module FA — fall_detected ordering ------------------------
                # The tick loop has its own "if activity_state==fall: record"
                # branch (it's the canonical recorder for replay-mode falls
                # where activity arrives from the dataset).  To avoid
                # duplicating the event for operator-injected falls we have
                # to record the canonical event *before* ticking, so the
                # tick loop's `_has_recent_fall_event_locked` dedupe sees
                # it and skips.  AI verdict metadata is then merged into
                # that same event via in-place mutation after the tick +
                # AI call complete.
                #
                # For non-fall events the original pre-tick inject + post-
                # tick record order is preserved.
                policy: _FallVariantPolicy | None = None
                persona_variant: str | None = None
                canonical_fall_event: EventRecord | None = None

                if event_type == "fall_detected":
                    policy, persona_variant = self._resolve_fall_variant_policy(variant)
                    record.simulator.inject_event(device_id, event_type, persona_variant)
                    record.alert_received = True
                    # Pre-record with provisional severity (policy default).
                    # We mutate severity + metadata after AI verdict below.
                    self._record_event(
                        device_id=device_id,
                        event_type="fall_detected",
                        severity=policy.default_severity,
                        message="Injected event fall_detected",
                        metadata={
                            "variant": variant or "",
                            "persona_variant": persona_variant or "",
                            "source": "inject_event",
                        },
                    )
                    canonical_fall_event = self.event_history[-1]
                elif event_type == "sos_cancel":
                    # Module C: runtime-only event — PersonaEngine has no
                    # concept of it, so we handle the FSM transition here.
                    if device_id in self.devices and self.devices[device_id].state in {
                        "fall_countdown",
                        "sos_active",
                    }:
                        self.devices[device_id].state = "streaming"
                    for sim_device in record.simulator.devices:
                        if sim_device.device_id == device_id:
                            if sim_device.engine.state.activity_state == "fall":
                                sim_device.engine.transition_to("recovery")
                            break
                    # Drop any stale AI verdict + countdown policy now that
                    # the operator dismissed the SOS — keeps the FE clean.
                    self._fall_predictions.pop(device_id, None)
                    self._fall_motion_refs.pop(device_id, None)
                    self._fall_countdown_policies.pop(device_id, None)
                    self._fall_pre_trigger_results.pop(device_id, None)
                else:
                    record.simulator.inject_event(device_id, event_type, variant)

                if event_type == "device_offline" and device_id in self.devices:
                    self.devices[device_id].state = "offline"
                    self.devices[device_id].is_online = False
                if event_type == "device_online" and device_id in self.devices:
                    self.devices[device_id].state = "streaming"
                    self.devices[device_id].is_online = True

                # ---- Tick to generate motion (and vitals) for this event ----
                if record.status == "running":
                    effects.extend(self._tick_session_locked(record, force=True))

                # ---- AI verdict + variant policy application (fall only) ----
                ai_verdict: AIPrediction | None = None
                motion_ref: MotionWindowRef | None = None
                pre_trigger_evidence: PreTriggerEvidence | None = None
                severity = "warning"
                if event_type == "fall_detected" and policy is not None:
                    payload = self._latest_motion_payload_locked(record, device_id)
                    motion = (payload or {}).get("motion") or {}
                    # Phase 2 — capture pre-trigger evidence on the same
                    # motion window the AI sees, so the FE Fall Lab
                    # pipeline strip (Section B stage 2) renders BE truth.
                    pre_trigger_evidence = self._compute_pre_trigger_evidence(motion)
                    if pre_trigger_evidence is not None:
                        self._fall_pre_trigger_results[device_id] = pre_trigger_evidence
                    ai_verdict = self._call_fall_ai_locked(
                        motion, device_id, variant or ""
                    )
                    motion_ref = self._build_motion_window_ref(payload, variant or "")
                    self._fall_predictions[device_id] = ai_verdict
                    if motion_ref is not None:
                        self._fall_motion_refs[device_id] = motion_ref
                    self._fall_countdown_policies[device_id] = CountdownPolicy(
                        totalSec=int(policy.countdown_sec),
                        autoResolve=bool(policy.auto_resolve),
                        allowsCancel=bool(policy.allows_cancel),
                    )
                    if device_id in self.devices:
                        self.devices[device_id].state = policy.device_state_on_inject  # type: ignore[assignment]
                    severity = self._override_severity_from_verdict(policy, ai_verdict)
                    # Mutate the canonical event we pre-recorded with the
                    # final severity + AI metadata so the FE / Recent Events
                    # feed shows a single coherent record.
                    if canonical_fall_event is not None:
                        canonical_fall_event.severity = severity
                        canonical_fall_event.metadata["ai_label"] = ai_verdict.label
                        canonical_fall_event.metadata["ai_probability"] = (
                            f"{ai_verdict.probability:.4f}"
                        )
                        canonical_fall_event.metadata["ai_band"] = ai_verdict.riskBand
                        canonical_fall_event.metadata["ai_status"] = (
                            ai_verdict.modelStatus
                        )
                    # ADR-024 S14: emit imu_predict flow event.
                    self.publish_flow_event(record.id, {
                        "step": "imu_predict",
                        "device_id": device_id,
                        "status": "done" if ai_verdict.modelStatus == "ok" else "error",
                        "payload": {
                            "label": ai_verdict.label,
                            "confidence": round(ai_verdict.confidence, 3),
                            "model_status": ai_verdict.modelStatus,
                        },
                    })

                # ---- Non-fall event recording (single source of truth) ----
                if event_type != "fall_detected":
                    severity = "warning"
                    if event_type == "sos_cancel":
                        severity = "normal"
                    elif event_type == "device_offline":
                        severity = "offline"
                    elif event_type == "device_online":
                        severity = "normal"
                    self._record_event(
                        device_id=device_id,
                        event_type=event_type,
                        severity=severity,
                        message=(
                            "Operator cancelled SOS countdown"
                            if event_type == "sos_cancel"
                            else f"Injected event {event_type}"
                        ),
                        metadata={"variant": variant or ""},
                    )

                # ---- Backend alert webhook (conditional on policy + AI) ----
                if event_type == "fall_detected" and policy is not None:
                    should_push = policy.push_alert
                    if ai_verdict is not None and ai_verdict.highPriorityAlert:
                        # AI escalation overrides a non-pushing policy.
                        should_push = True
                    if should_push:
                        # Confidence bridge (Module FA-2 fix): the BE's
                        # `_pick_float(metadata, "confidence")` gate keys
                        # off this single field.  We send
                        # ``max(ai_probability, simulated_confidence)``
                        # so:
                        #   - The AI verdict is honoured when it's high
                        #     enough to clear the BE threshold (0.7),
                        #   - Each variant has a deterministic floor so
                        #     test scenarios reach the right BE branch
                        #     (soft-alert / SOS / SOS-no-cancel)
                        #     regardless of the model's mood that day.
                        ai_prob = (
                            float(ai_verdict.probability) if ai_verdict else 0.0
                        )
                        confidence_value = max(
                            ai_prob, float(policy.simulated_confidence)
                        )
                        effects.pending_alerts.append(
                            PendingAlertCall(
                                sim_device_id=device_id,
                                event_type="fall_detected",
                                severity=severity,
                                metadata={
                                    "variant": variant or "",
                                    "persona_variant": persona_variant or "",
                                    "source": "inject_event",
                                    "timestamp": _utc_now_iso(),
                                    "ai_label": ai_verdict.label if ai_verdict else "unknown",
                                    "ai_probability": (
                                        f"{ai_verdict.probability:.4f}" if ai_verdict else "0.0"
                                    ),
                                    "ai_band": ai_verdict.riskBand if ai_verdict else "normal",
                                    # The canonical field the BE reads.
                                    "confidence": f"{confidence_value:.4f}",
                                    "simulated_confidence": (
                                        f"{policy.simulated_confidence:.4f}"
                                    ),
                                    # P0-4: forward BE-side IDs so /telemetry/alert
                                    # dedups against the row /imu-window already
                                    # persisted instead of inserting a duplicate.
                                    **(
                                        {"fall_event_id": str(ai_verdict.fallEventId)}
                                        if ai_verdict and ai_verdict.fallEventId is not None
                                        else {}
                                    ),
                                    **(
                                        {"model_request_id": ai_verdict.modelRequestId}
                                        if ai_verdict and ai_verdict.modelRequestId
                                        else {}
                                    ),
                                },
                            )
                        )
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

    # ── Health payload v2 (Phase 0.6) ────────────────────────────────────
    # Returns a structured payload for the new dashboard hero plus the
    # legacy flat keys consumed by ``HealthStatusPanel`` until Module A
    # retires them.  See plans/iot-sim-ux-refactor-backlog-75c8a6.md §4.

    _SIMULATOR_VERSION = "simulator-api-0.4.0"

    def _compute_pre_trigger_block(self) -> dict[str, Any]:
        """Derive ``preTrigger`` block (mode + threshold source)."""
        if not _PRE_MODEL_TRIGGER_ENABLED:
            mode = "off"
        elif self._trigger_orchestrator is None:
            # Flag says ON but wiring failed: treat as off so the UI does not
            # claim shadow/active capability we cannot actually exercise.
            mode = "off"
        else:
            mode = "shadow"  # active mode disposed S7 (ADR-020)

        threshold_source = "unavailable"
        enable_model_calls = False
        if self._trigger_orchestrator is not None:
            enable_model_calls = False  # active mode disposed S7 (ADR-020)
            try:
                provider = self._trigger_orchestrator._settings
                day = provider.get_vitals_thresholds(is_sleeping=False)
                threshold_source = "db" if day else "fallback"
            except Exception:
                threshold_source = "unavailable"
        else:
            threshold_source = "fallback"

        return {
            "mode": mode,
            "enableModelCalls": enable_model_calls,
            "thresholdSource": threshold_source,
        }

    def _compute_telemetry_block(self) -> dict[str, int]:
        """Counts derived from runtime state for the v2 telemetry block."""
        with self._lock:
            devices_simulated = len(self.devices)
            sessions_running = sum(
                1 for session in self.sessions.values() if session.status == "running"
            )
            now_ts = time.time()
            cutoff = now_ts - 3600
            while self._alert_timestamps_1h and self._alert_timestamps_1h[0] < cutoff:
                self._alert_timestamps_1h.popleft()
            alerts_last_hour = len(self._alert_timestamps_1h)
            latencies = [
                session.last_publish_latency_ms
                for session in self.sessions.values()
                if session.last_publish_count > 0 and session.last_publish_latency_ms is not None
            ]
            avg_latency = int(round(sum(latencies) / len(latencies))) if latencies else 0
        return {
            "devicesSimulated": devices_simulated,
            "sessionsRunning": sessions_running,
            "alertsLastHour": alerts_last_hour,
            "avgPublishLatencyMs": avg_latency,
        }

    def health_payload(self) -> dict[str, Any]:
        """Return the v2 health payload merged with legacy flat keys.

        v2 callers (Module A dashboard hero) read the nested blocks; legacy
        callers (current ``HealthStatusPanel``) keep using the flat keys for
        one release cycle before they are removed.
        """
        # Refresh probes (TTL-gated, so cheap when called often).
        self._probe_backend_cached()
        self._probe_model_api_cached()
        db_ok, db_latency_ms = self._measure_database_health()

        with self._lock:
            session_count = len(self.sessions)
            running_sessions = sum(
                1 for session in self.sessions.values() if session.status == "running"
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
        if pre_trigger_block["mode"] == "off" and _PRE_MODEL_TRIGGER_ENABLED and self._trigger_orchestrator is None:
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
        # NOTE: the legacy key was previously named "backend" (a flat string
        # like "connected"/"down") which collided with the v2 "backend" field
        # (HealthBackendBlock dict) when the dicts were merged — causing a
        # ResponseValidationError on the /api/v1/sim/health endpoint.  Renamed
        # to "backendStatus" to avoid the collision.
        legacy_keys: dict[str, Any] = {
            "status": runtime_state if runtime_state != "idle" else "running",
            "api": "running",
            "backendStatus": "connected" if backend_state == "connected" else "down",
            "mqtt": mqtt_status,
            "db": "healthy" if db_ok else "down",
            "version": self._SIMULATOR_VERSION,
        }

        return {**v2_payload, **legacy_keys}


    def sleep_session(self, device_id: str) -> SleepSessionResponse:
        return self.sleep_service.sleep_session(device_id)

    def push_sleep_session(self, device_id: str) -> SleepSessionResponse:
        result = self.sleep_service.push_sleep_session(device_id)
        # ADR-024 S14: emit sleep_predict flow event for all running sessions.
        for sid, s in self.sessions.items():
            if s.status == "running":
                self.publish_flow_event(sid, {
                    "step": "sleep_predict",
                    "device_id": device_id,
                    "status": "done",
                    "payload": {"score": getattr(result, "score", None)},
                })
        return result

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

    # ADR-020 Phase 7 S7: ``trigger_risk_calculation`` disposed alongside
    # ``_trigger_risk_inference``. The router endpoint
    # ``POST /api/v1/sim/analytics/risk/trigger`` was removed in the same
    # slice. Callers should rely on the BE auto-trigger that fires after
    # ``/telemetry/ingest`` (cooldown ``RISK_COOLDOWN_SECONDS``, default 60s).

    def latest_vitals(self, device_id: str) -> VitalsSample:
        return self.vitals_service.latest_vitals(device_id)

    # ── Module C — Sessions / Fall Lab evidence surface ──────────────────

    def motion_latest(self, session_id: str, device_id: str) -> MotionLatest:
        """Return the most recent motion window emitted for `device_id`.

        We pull straight from `record.last_tick_outputs` so the FE can
        render the same arrays the dataset registry produced — no
        synthetic preview, no client-side fabrication.
        """
        with self._lock:
            record = self._require_session(session_id)
            if device_id not in record.device_ids:
                raise KeyError(f"Device {device_id} not in session {session_id}")
            payload = self._latest_motion_payload_locked(record, device_id)
            state = (payload or {}).get("state") or {}
            motion = (payload or {}).get("motion") or {}
            return MotionLatest(
                deviceId=device_id,
                sessionId=session_id,
                emittedAt=str((payload or {}).get("emitted_at") or _utc_now_iso()),
                activityState=str(state.get("activity_state") or "unknown"),
                fallVariant=(str(state.get("fall_variant")) if state.get("fall_variant") else None),
                sampleRate=_safe_float(motion.get("sample_rate"), None),
                accelX=_coerce_float_list(motion.get("accel_x")),
                accelY=_coerce_float_list(motion.get("accel_y")),
                accelZ=_coerce_float_list(motion.get("accel_z")),
                accelMag=_coerce_float_list(motion.get("accel_mag")),
                gyroX=_coerce_float_list(motion.get("gyro_x")),
                gyroY=_coerce_float_list(motion.get("gyro_y")),
                gyroZ=_coerce_float_list(motion.get("gyro_z")),
            )

    def fall_state(self, session_id: str, device_id: str) -> FallState:
        """Operator-visible fall pipeline state derived from runtime truth.

        Sources:
          * `device.state` — canonical FSM (`fall_countdown` / `sos_active`).
          * Most recent `fall_detected` event in `event_history`.
          * `record.last_tick_outputs[i].state.{activity_state,fall_variant}`.
        """
        with self._lock:
            record = self._require_session(session_id)
            if device_id not in record.device_ids:
                raise KeyError(f"Device {device_id} not in session {session_id}")
            device = self.devices.get(device_id)
            tick_state = (
                (self._latest_motion_payload_locked(record, device_id) or {}).get("state") or {}
            )
            recent_fall_events = [
                event
                for event in reversed(self.event_history)
                if event.device_id == device_id
                and event.event_type in {"fall_detected", "sos_cancel", "fall_no_response"}
            ][:5]
            last_fall_event = next(
                (event for event in recent_fall_events if event.event_type == "fall_detected"),
                None,
            )
            last_cancel_event = next(
                (event for event in recent_fall_events if event.event_type == "sos_cancel"),
                None,
            )

            # Module FA: countdown total is now variant-aware.  Falls back
            # to the legacy 30s constant when no policy was cached (e.g.
            # legacy event injected before the runtime started caching).
            cached_policy = self._fall_countdown_policies.get(device_id)
            countdown_total = (
                cached_policy.totalSec if cached_policy else int(self._SOS_COUNTDOWN_SECONDS)
            )
            countdown_remaining = 0
            countdown_started_at: str | None = None
            sos_active = False
            if device is not None and device.state in {"fall_countdown", "sos_active"} and last_fall_event:
                countdown_started_at = last_fall_event.timestamp
                # If the operator already cancelled after this fall event,
                # the countdown is logically zero even if the FSM hasn't
                # advanced yet (it will on the next tick).
                cancelled_after_fall = (
                    last_cancel_event is not None
                    and last_cancel_event.timestamp >= last_fall_event.timestamp
                )
                if not cancelled_after_fall:
                    elapsed = self._iso_age_seconds(last_fall_event.timestamp)
                    countdown_remaining = max(
                        0, int(round(countdown_total - elapsed))
                    )
                    sos_active = device.state == "sos_active" or countdown_remaining > 0

            fall_state_value = self._fall_state_locked(
                device_state=(device.state if device else "streaming"),
                last_fall_event=last_fall_event,
                last_cancel_event=last_cancel_event,
                countdown_remaining=countdown_remaining,
            )

            return FallState(
                deviceId=device_id,
                sessionId=session_id,
                deviceState=(device.state if device else "streaming"),  # type: ignore[arg-type]
                activityState=str(tick_state.get("activity_state") or "unknown"),
                fallVariant=(str(tick_state.get("fall_variant")) if tick_state.get("fall_variant") else None),
                fallState=fall_state_value,  # type: ignore[arg-type]
                lastFallEventAt=last_fall_event.timestamp if last_fall_event else None,
                countdownStartedAt=countdown_started_at,
                countdownRemainingSec=countdown_remaining,
                countdownTotalSec=int(countdown_total),
                sosActive=sos_active,
                recentFallEvents=[
                    FallEventEntry(
                        id=event.id,
                        timestamp=event.timestamp,
                        eventType=event.event_type,
                        severity=event.severity,  # type: ignore[arg-type]
                        variant=event.metadata.get("variant") or None,
                    )
                    for event in recent_fall_events
                ],
                aiPrediction=self._fall_predictions.get(device_id),
                motionWindowRef=self._fall_motion_refs.get(device_id),
                countdownPolicy=cached_policy,
                preTriggerResult=self._fall_pre_trigger_results.get(device_id),
            )

    @staticmethod
    def _latest_motion_payload_locked(
        record: SessionRecord, device_id: str
    ) -> dict[str, Any] | None:
        """Return the most recent tick payload for `device_id`, if any."""
        for payload in reversed(record.last_tick_outputs):
            if payload.get("device_id") == device_id:
                return payload
        return None

    @staticmethod
    def _iso_age_seconds(iso_ts: str) -> float:
        """Seconds between now (UTC) and `iso_ts` — robust to ``Z`` suffix."""
        try:
            ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        return (datetime.now(timezone.utc) - ts).total_seconds()

    @staticmethod
    def _fall_state_locked(
        *,
        device_state: str,
        last_fall_event: EventRecord | None,
        last_cancel_event: EventRecord | None,
        countdown_remaining: int,
    ) -> FallStateValue:
        """Reduce runtime signals into the FE-friendly fall lifecycle.

        ``idle``           — no recent fall events.
        ``fall_detected``  — fall event recorded but FSM has cleared (e.g.
                             a brief or false-alarm variant that didn't
                             escalate).
        ``fall_countdown`` — FSM is in `fall_countdown` and the SOS
                             window has not elapsed.
        ``sos_active``     — FSM is in `sos_active` (operator did not
                             respond and the device escalated).
        ``fall_resolved``  — operator pressed "Tôi ổn" after a fall event.
        """
        if last_cancel_event is not None and (
            last_fall_event is None or last_cancel_event.timestamp >= last_fall_event.timestamp
        ):
            return "fall_resolved"
        if device_state == "sos_active":
            return "sos_active"
        if device_state == "fall_countdown" and countdown_remaining > 0:
            return "fall_countdown"
        if last_fall_event is not None:
            return "fall_detected"
        return "idle"

    def verification(self, session_id: str) -> VerificationResult:
        with self._lock:
            record = self._require_session(session_id)
            device_id = record.device_ids[0] if record.device_ids else "unknown"
            status = self._verification_status_locked(record)
            risk_received = device_id in self.risk_snapshots
            stages = self._verification_stages_locked(record, device_id, risk_received)
            failure_reason = self._verification_failure_reason_locked(record, stages)
            return VerificationResult(
                deviceId=device_id,
                vitalsReceived=bool(record.last_tick_outputs),
                alertReceived=record.alert_received,
                riskScoreReceived=risk_received,
                latencyMs=record.last_publish_latency_ms or 0,
                status=status,  # type: ignore[arg-type]
                lastCheckedAt=_utc_now_iso(),
                stages=stages,
                failureReason=failure_reason,
                lastGoodPublishAt=record.last_publish_ok_at,
                lastPublishAttemptAt=record.last_publish_attempt_at,
                publishAckCount=record.publish_ack_count_total,
                publishAttemptCount=record.publish_attempt_count,
            )

    def _verification_stages_locked(
        self,
        record: SessionRecord,
        device_id: str,
        risk_received: bool,
    ) -> list[PipelineStage]:
        """Build the ordered evidence trail for `record`.

        Stages are emitted in pipeline order so the FE strip renders
        device → session → telemetry → publish → risk → alert.  Each
        stage is one of `ok` / `pending` / `failed` / `skipped` so the
        operator can see exactly where the trail broke.
        """
        device_known = device_id in self.devices
        stages: list[PipelineStage] = []

        # 1. Device registered in simulator runtime.
        stages.append(
            PipelineStage(
                key="device_registered",
                label="Thiết bị đã đăng ký",
                status="ok" if device_known else "failed",
                detail=(
                    None
                    if device_known
                    else "Thiết bị không có trong simulator runtime — kiểm tra Devices."
                ),
            )
        )

        # 2. Session running.
        if record.status == "running":
            session_status: PipelineStageStatusValue = "ok"
            session_detail: str | None = None
        elif record.status == "stopped":
            session_status = "failed"
            session_detail = "Phiên đã dừng — bắt đầu lại để tiếp tục thu thập bằng chứng."
        else:
            session_status = "pending"
            session_detail = "Phiên chưa chạy."
        stages.append(
            PipelineStage(
                key="session_started",
                label="Phiên đang chạy",
                status=session_status,
                detail=session_detail,
                at=record.last_tick_at if record.status == "running" else None,
            )
        )

        # 3. Telemetry generated locally.
        has_outputs = bool(record.last_tick_outputs)
        is_stale = self._verification_is_stale_locked(record)
        if has_outputs and not is_stale:
            telemetry_status: PipelineStageStatusValue = "ok"
            telemetry_detail: str | None = None
        elif has_outputs and is_stale:
            telemetry_status = "failed"
            telemetry_detail = "Tick chưa cập nhật — simulator có thể bị treo."
        else:
            telemetry_status = "pending"
            telemetry_detail = "Chưa có tick nào tạo dữ liệu vitals."
        stages.append(
            PipelineStage(
                key="telemetry_generated",
                label="Sinh hiệu đã tạo",
                status=telemetry_status,
                detail=telemetry_detail,
                at=record.last_tick_at,
            )
        )

        # 4. Telemetry successfully published downstream.
        if record.publish_attempt_count == 0:
            publish_status: PipelineStageStatusValue = "pending"
            publish_detail: str | None = "Chưa publish lần nào."
        elif record.last_publish_ok:
            publish_status = "ok"
            publish_detail = (
                f"{record.last_publish_ack_count}/{record.last_publish_count} message ack thành công."
            )
        else:
            publish_status = "failed"
            publish_detail = record.last_publish_error or "Publish gần nhất thất bại."
        stages.append(
            PipelineStage(
                key="telemetry_published",
                label="Đã publish",
                status=publish_status,
                detail=publish_detail,
                at=record.last_publish_ok_at,
            )
        )

        # 5. Risk evaluated for the focal device.
        stages.append(
            PipelineStage(
                key="risk_evaluated",
                label="Đã tính rủi ro",
                status="ok" if risk_received else "pending",
                detail=(
                    None
                    if risk_received
                    else "Chưa có snapshot rủi ro — chờ tick kế tiếp hoặc trigger từ Diagnostics."
                ),
            )
        )

        # 6. Alert dispatched (only meaningful when an alert is expected).
        if record.alert_received:
            alert_stage = PipelineStage(
                key="alert_dispatched",
                label="Cảnh báo đã gửi",
                status="ok",
                detail="Đã ghi nhận cảnh báo cho phiên này.",
            )
        else:
            alert_stage = PipelineStage(
                key="alert_dispatched",
                label="Cảnh báo đã gửi",
                status="skipped",
                detail="Phiên hiện tại chưa có sự kiện cần cảnh báo.",
            )
        stages.append(alert_stage)

        return stages

    @staticmethod
    def _verification_failure_reason_locked(
        record: SessionRecord,
        stages: list[PipelineStage],
    ) -> str | None:
        """Return the first user-readable failure reason, if any."""
        for stage in stages:
            if stage.status == "failed":
                return stage.detail or f"Stage {stage.key} thất bại."
        if record.last_publish_error and record.publish_attempt_count > 0 and not record.last_publish_ok:
            return record.last_publish_error
        return None

    def _require_session(self, session_id: str) -> SessionRecord:
        return self.session_service._require_session(session_id)

    def _verification_is_stale_locked(self, record: SessionRecord) -> bool:
        if not record.last_tick_at:
            return False
        try:
            last_tick_at = datetime.fromisoformat(record.last_tick_at.replace("Z", "+00:00"))
        except ValueError:
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

    def _build_trigger_persona(self, device_id: str) -> "PersonaProfile":
        """Build a PersonaProfile from the device's stored persona_config."""
        device = self.devices.get(str(device_id))
        pcfg = (device.persona_config if device is not None else None) or {}
        return PersonaProfile(
            age=int(pcfg.get("age", 35)),
            gender=str(pcfg.get("gender", "unknown")),
            weight_kg=float(pcfg.get("weight_kg", 70.0)),
            height_cm=float(pcfg.get("height_cm", 170.0)),
            medical_conditions=list(pcfg.get("medical_conditions") or []),
        )

    def _auto_resolve_fall_countdowns_locked(self, record: SessionRecord) -> None:
        """Module FA: clear ``fall_countdown`` devices whose policy auto-resolves.

        ``fall_brief`` is the canonical case: a 10s countdown that ends
        without operator intervention.  We synthesise a ``sos_cancel``
        event so the recent-events feed + FE banner show the resolution
        consistently with the operator-driven cancel path.
        """
        for device_id in list(record.device_ids):
            policy = self._fall_countdown_policies.get(device_id)
            if policy is None or not policy.autoResolve:
                continue
            device = self.devices.get(device_id)
            if device is None or device.state not in {"fall_countdown", "sos_active"}:
                continue
            # Find the most recent fall_detected to compute elapsed time.
            last_fall_event = next(
                (
                    event
                    for event in reversed(self.event_history)
                    if event.device_id == device_id and event.event_type == "fall_detected"
                ),
                None,
            )
            if last_fall_event is None:
                continue
            elapsed = self._iso_age_seconds(last_fall_event.timestamp)
            if elapsed < float(policy.totalSec):
                continue
            # Auto-resolve: revert FSM + persona + emit a synthetic cancel.
            device.state = "streaming"
            for sim_device in record.simulator.devices:
                if sim_device.device_id == device_id:
                    if sim_device.engine.state.activity_state == "fall":
                        sim_device.engine.transition_to("recovery")
                    break
            self._record_event(
                device_id=device_id,
                event_type="sos_cancel",
                severity="normal",
                message="Auto-resolved short fall (variant policy)",
                metadata={"variant": "auto_resolve", "source": "tick_auto_resolve"},
            )
            # Drop AI verdict + policy so the FE doesn't keep rendering the
            # countdown card after auto-resolve.
            self._fall_predictions.pop(device_id, None)
            self._fall_motion_refs.pop(device_id, None)
            self._fall_countdown_policies.pop(device_id, None)
            self._fall_pre_trigger_results.pop(device_id, None)

    def _tick_session_locked(self, record: SessionRecord, force: bool) -> SessionSideEffects:
        effects = SessionSideEffects()
        if record.status != "running":
            return effects
        target_interval = float(max(record.speed, 1))
        now = monotonic()
        if not force and now - record.last_tick_monotonic < target_interval:
            return effects
        self._auto_resolve_fall_countdowns_locked(record)
        outputs = record.simulator.tick()
        self._enrich_and_buffer_outputs(outputs, record)
        self._refresh_pending_sync_flags()
        effects.pending_publishes = self._publish_tick_buffer_locked(now=now, force=force)
        self._process_tick_outputs(outputs, record, effects)
        if _PRE_MODEL_TRIGGER_ENABLED and self._trigger_orchestrator is not None:
            self._run_shadow_orchestrator(outputs)
        record.last_tick_monotonic = now
        record.last_tick_outputs = outputs
        record.last_tick_at = _utc_now_iso()
        return effects

    def _enrich_and_buffer_outputs(
        self, outputs: list[dict], record: SessionRecord
    ) -> None:
        """Attach persona/db metadata, apply scenario overrides, advance sleep phase,
        and push bound-device payloads into ``_device_buffers``."""
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
        if buffered_messages:
            for payload in buffered_messages:
                device_id = str(payload.get("device_id") or "")
                if not device_id:
                    continue
                self._device_buffers.setdefault(device_id, []).append(payload)

    def _process_tick_outputs(
        self,
        outputs: list[dict],
        record: SessionRecord,
        effects: SessionSideEffects,
    ) -> None:
        """Update device state, emit log entries, and evaluate alerts for each payload."""
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
                # Module FA fix: dedupe with `inject_event` recording.
                # The tick loop is still the canonical trigger for
                # replay-mode falls (where activity_state arrives from a
                # dataset annotation, not an operator click).  But for
                # operator-injected falls, ``inject_event`` already
                # recorded the canonical event with AI verdict metadata
                # attached — recording here too produced duplicate
                # "Recent events" entries (QA-reported bug).
                #
                # We dedupe by checking whether a fall_detected was
                # recorded for this device in the past 60 seconds.  The
                # window must be longer than the persona engine's
                # ``FALL_DURATION_TICKS`` window (10 ticks × default 5 s
                # tick = 50 s) so the tick loop doesn't fire one event
                # per tick while the same fall episode is still
                # propagating through the persona state machine.  Using
                # 5 s caused exactly the duplicate-event QA bug because
                # the tick interval matched the dedupe window, so each
                # tick observed a 5.0-s-old prior event and treated it
                # as outside the dedupe window (boundary fail).
                if not self._has_recent_fall_event_locked(
                    device_id=str(device_id), seconds=60.0
                ):
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

    def _run_shadow_orchestrator(self, outputs: list[dict]) -> None:
        """Shadow orchestrator evaluation (Fix R2/R5).

        Runs only when PRE_MODEL_TRIGGER_ENABLED=1 and the orchestrator was
        successfully wired at startup.  Results are logged only (shadow mode):
        they do NOT modify ``effects.pending_alerts`` so the existing alert
        flow is untouched. ADR-020 Phase 7 S7 disposed the active R3 wire;
        the BE auto-calls ``calculate_device_risk`` after every ingest.
        """
        for payload in outputs:
            _orch_device_id = str(payload.get("device_id") or "")
            if _orch_device_id not in self.devices:
                continue
            try:
                _orch_actions = self._trigger_orchestrator.evaluate_tick(
                    device_id=_orch_device_id,
                    vitals=payload.get("vitals") or {},
                    motion=payload.get("motion"),
                    state=payload.get("state") or {},
                    persona=self._build_trigger_persona(_orch_device_id),
                )
                if _orch_actions:
                    logger.debug(
                        "Orchestrator [shadow] device=%s actions=%s",
                        _orch_device_id,
                        [(a.action_type, a.severity) for a in _orch_actions],
                    )
            except Exception:
                logger.exception(
                    "Orchestrator evaluation failed for device %s (non-fatal)",
                    _orch_device_id,
                )

    def _publish_tick_buffer_locked(
        self, now: float, force: bool
    ) -> list[PendingDevicePublish]:
        """Build per-device publish units (fix bug "dữ liệu đi cùng qua 1 API").

        Mỗi device có buffer riêng → 1 device đang in-flight không block
        device khác. Trả empty list nếu chưa tới window hoặc không có
        buffered message nào eligible.
        """
        if not force and now - self._last_push_time < float(self._push_interval):
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
        if scenario_id in {"normal_rest", "normal_walking", "good_sleep_night", "elderly_normal"}:
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
            # WHO/AHA: moderate walking adult. HR 80-100, BP slightly elevated, SpO2 normal.
            "normal_walking": (88.0, 5.0, 97.0, 0.5, 37.1, 0.15, 126.0, 82.0, 6.0, 4.0, 18.0),
            # AASM elderly normal: less deep sleep, HR 55-65, mild BP elevation (age-adjusted).
            "elderly_normal": (60.0, 4.0, 96.0, 0.8, 36.4, 0.15, 118.0, 75.0, 5.0, 3.5, 14.0),
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

