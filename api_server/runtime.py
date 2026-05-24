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
from api_server.services.risk_service import (
    RiskService,
    _build_risk_history,
    _risk_level_from_score,
    _severity_from_risk_level,
)
from api_server.services.verification_service import VerificationService
from api_server.services.fall_service import FallService, _normalise_imu_window_response, _coerce_float_list
from api_server.services.dashboard_service import DashboardService
from api_server.services.publish_service import PublishService
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
from simulator_core.tick_pipeline import (
    apply_scenario_overrides as _apply_scenario_overrides_fn,
    annotate_scenario_replay as _annotate_scenario_replay_fn,
    scenario_state_hint as _scenario_state_hint_fn,
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


def _safe_int(value: Any) -> int | None:
    cast = _safe_float(value, None)
    return int(round(cast)) if cast is not None else None



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
        # Mutable single-element lists so DashboardService / PublishService can
        # share them by reference without taking ownership.
        self._dashboard_cache_ts_ref: list[float] = [0.0]
        # HIGH #1 fix: pre-computed alert counter so dashboard_summary()
        # does not need to iterate event_history under lock.
        self._alert_count_1h: int = 0
        self._alert_count_1h_ref: list[int] = [0]
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
        self._last_push_time_ref: list[float] = [0.0]
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
            sleep_scenario_phases=SLEEP_SCENARIO_PHASES,
            sleep_scenario_profiles=SLEEP_SCENARIO_PROFILES,
        )

        self.risk_service = RiskService(
            devices=self.devices,
            risk_snapshots=self.risk_snapshots,
            risk_history=self.risk_history,
            event_history=self.event_history,
            lock=self._lock,
            vitals_service=self.vitals_service,
            record_event_fn=self._record_event,
        )

        self.verification_service = VerificationService(
            devices=self.devices,
            sessions=self.sessions,
            device_scenarios=self.device_scenarios,
            risk_snapshots=self.risk_snapshots,
            event_history=self.event_history,
            lock=self._lock,
            health_backend_url=self._health_backend_url,
            trigger_orchestrator=self._trigger_orchestrator,
            push_interval=self._push_interval,
            alert_timestamps_1h=self._alert_timestamps_1h,
        )

        self.fall_service = FallService(
            devices=self.devices,
            sessions=self.sessions,
            device_scenarios=self.device_scenarios,
            event_history=self.event_history,
            lock=self._lock,
            fall_predictions=self._fall_predictions,
            fall_motion_refs=self._fall_motion_refs,
            fall_countdown_policies=self._fall_countdown_policies,
            fall_pre_trigger_results=self._fall_pre_trigger_results,
            health_backend_url=self._health_backend_url,
            mobile_telemetry_client=self._mobile_telemetry_client,
            fall_pre_trigger=getattr(self, '_fall_pre_trigger', None),
            settings_provider=getattr(self, '_settings_provider', None),
            http_sender_fn=self._http_sender,
            publish_device_log_fn=self._publish_device_log,
            record_event_fn=self._record_event,
            run_session_side_effects_fn=self._run_session_side_effects,
            publish_flow_event_fn=self.publish_flow_event,
            tick_session_locked_fn=self._tick_session_locked,
            require_session_fn=self._require_session,
            internal_secret=os.environ.get("INTERNAL_SERVICE_SECRET"),
        )

        # ── DashboardService (Task 3.6) ──────────────────────────────────
        self.dashboard_service = DashboardService(
            devices=self.devices,
            sessions=self.sessions,
            event_history=self.event_history,
            alert_count_1h_ref=self._alert_count_1h_ref,
            alert_timestamps_1h=self._alert_timestamps_1h,
            health_state=self._health_state,
            admin_client=self.admin_client,
            trigger_orchestrator=self._trigger_orchestrator,
            dashboard_cache_ref=self._dashboard_cache_ref,
            dashboard_cache_ts_ref=self._dashboard_cache_ts_ref,
            lock=self._lock,
            health_backend_url=self._health_backend_url,
            sleep_ai_client=self._sleep_ai_client,
            compute_pre_trigger_block_fn=self._compute_pre_trigger_block,
            compute_telemetry_block_fn=self._compute_telemetry_block,
            measure_database_health_fn=self._measure_database_health,
        )

        # ── PublishService (Task 3.7) ────────────────────────────────────
        self.publish_service = PublishService(
            sessions=self.sessions,
            devices=self.devices,
            device_buffers=self._device_buffers,
            device_in_flight=self._device_in_flight,
            lock=self._lock,
            health_backend_url=self._health_backend_url,
            push_interval=self._push_interval,
            last_push_time_ref=self._last_push_time_ref,
            http_sender_fn=self._http_sender,
            publish_flow_event_fn=self.publish_flow_event,
            push_alert_fn=self._push_alert_to_backend,
            logs=self.logs,
        )
        self.publish_service.set_refresh_fn(self._refresh_pending_sync_flags)

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
        self.publish_service.update_device_heartbeat(db_device_id, battery_level)

    def _publish_vitals_http(
        self, pending_publish: PendingDevicePublish
    ) -> tuple[int, set[int], str | None]:
        return self.publish_service.publish_vitals_http(pending_publish)

    def _execute_pending_tick_publish(
        self, pending_publishes: list[PendingDevicePublish] | None
    ) -> None:
        self.publish_service.execute_pending_tick_publish(pending_publishes)

    def _execute_single_device_publish(
        self,
        pending_publish: PendingDevicePublish,
    ) -> None:
        self.publish_service.execute_single_device_publish(pending_publish)

    @staticmethod
    def _refresh_session_publish_aggregate_locked(session: SessionRecord) -> None:
        PublishService.refresh_session_publish_aggregate_locked(session)

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
        self.dashboard_service.probe_backend_cached()

    def _probe_model_api_cached(self) -> None:
        """Refresh ``_health_state.model_api_probe`` via ``SleepAIClient``."""
        self.dashboard_service.probe_model_api_cached()

    def _run_session_side_effects(self, effects: SessionSideEffects) -> None:
        self.publish_service.run_session_side_effects(effects)


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
                self.devices[device_id].state = _scenario_state_hint_fn(scenario_id)
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
        return self.fall_service._has_recent_fall_event_locked(device_id, seconds=seconds)

    @staticmethod
    def _resolve_fall_variant_policy(
        fe_variant: str | None,
    ) -> tuple[_FallVariantPolicy, str]:
        return FallService._resolve_fall_variant_policy(fe_variant)

    def _call_fall_ai_locked(
        self,
        motion: dict[str, Any] | None,
        device_id: str,
        fe_variant: str,
    ) -> AIPrediction:
        return self.fall_service._call_fall_ai_locked(motion, device_id, fe_variant)

    def _build_motion_window_ref(
        self,
        payload: dict[str, Any] | None,
        fe_variant: str,
    ) -> MotionWindowRef | None:
        return self.fall_service._build_motion_window_ref(payload, fe_variant)

    def _compute_pre_trigger_evidence(
        self,
        motion: dict[str, Any] | None,
    ) -> PreTriggerEvidence | None:
        return self.fall_service._compute_pre_trigger_evidence(motion)

    def _override_severity_from_verdict(
        self,
        policy: _FallVariantPolicy,
        verdict: AIPrediction,
    ) -> str:
        return self.fall_service._override_severity_from_verdict(policy, verdict)

    def inject_event(self, device_id: str, event_type: str, variant: str | None) -> None:
        return self.fall_service.inject_event(device_id, event_type, variant)

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
        return self.dashboard_service.dashboard_summary()

    # ── Health payload v2 (Phase 0.6) ────────────────────────────────────
    # Returns a structured payload for the new dashboard hero plus the
    # legacy flat keys consumed by ``HealthStatusPanel`` until Module A
    # retires them.  See plans/iot-sim-ux-refactor-backlog-75c8a6.md §4.

    _SIMULATOR_VERSION = "simulator-api-0.4.0"

    def _compute_pre_trigger_block(self) -> dict[str, Any]:
        return self.verification_service._compute_pre_trigger_block()

    def _compute_telemetry_block(self) -> dict[str, int]:
        return self.verification_service._compute_telemetry_block()

    def health_payload(self) -> dict[str, Any]:
        """Return the v2 health payload merged with legacy flat keys.

        Delegates to :class:`DashboardService` which owns probe state and
        payload construction.
        """
        return self.dashboard_service.health_payload()


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
        return self.risk_service.risk_score(device_id)

    def inject_risk_score(self, request: RiskInjectRequest) -> None:
        return self.risk_service.inject_risk_score(request)

    # ADR-020 Phase 7 S7: ``trigger_risk_calculation`` disposed alongside
    # ``_trigger_risk_inference``. The router endpoint
    # ``POST /api/v1/sim/analytics/risk/trigger`` was removed in the same
    # slice. Callers should rely on the BE auto-trigger that fires after
    # ``/telemetry/ingest`` (cooldown ``RISK_COOLDOWN_SECONDS``, default 60s).

    def latest_vitals(self, device_id: str) -> VitalsSample:
        return self.vitals_service.latest_vitals(device_id)

    # ── Module C — Sessions / Fall Lab evidence surface ──────────────────

    def motion_latest(self, session_id: str, device_id: str) -> MotionLatest:
        return self.fall_service.motion_latest(session_id, device_id)

    def fall_state(self, session_id: str, device_id: str) -> FallState:
        return self.fall_service.fall_state(session_id, device_id)

    @staticmethod
    def _latest_motion_payload_locked(
        record: SessionRecord, device_id: str
    ) -> dict[str, Any] | None:
        return FallService._latest_motion_payload_locked(record, device_id)

    @staticmethod
    def _iso_age_seconds(iso_ts: str) -> float:
        return FallService._iso_age_seconds(iso_ts)

    @staticmethod
    def _fall_state_locked(
        *,
        device_state: str,
        last_fall_event: EventRecord | None,
        last_cancel_event: EventRecord | None,
        countdown_remaining: int,
    ) -> FallStateValue:
        return FallService._fall_state_locked(
            device_state=device_state,
            last_fall_event=last_fall_event,
            last_cancel_event=last_cancel_event,
            countdown_remaining=countdown_remaining,
        )

    def verification(self, session_id: str) -> VerificationResult:
        return self.verification_service.verification(session_id)

    def _require_session(self, session_id: str) -> SessionRecord:
        return self.session_service._require_session(session_id)

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
        return self.fall_service._auto_resolve_fall_countdowns_locked(record)

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
                _annotate_scenario_replay_fn(payload, scenario_id)
            else:
                _apply_scenario_overrides_fn(payload, scenario_id)
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
        self, *, now: float, force: bool
    ) -> list[PendingDevicePublish]:
        return self.publish_service.publish_tick_buffer_locked(now=now, force=force)

    def _refresh_pending_sync_flags(self) -> None:
        self.device_service._refresh_pending_sync_flags()

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

