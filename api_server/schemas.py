from __future__ import annotations

from datetime import date as Date, datetime as DateTime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


DeviceStateValue = Literal[
    "draft",
    "provisioned",
    "bindable",
    "bound",
    "streaming",
    "warning",
    "critical",
    "fall_countdown",
    "sos_active",
    "offline",
    "retired",
]
DeviceTypeValue = Literal["smartwatch", "fitness_band", "medical_device"]
BindStatusValue = Literal["unbound", "bindable", "bound"]
SeverityValue = Literal["normal", "warning", "critical", "invalid"]
VerificationStatusValue = Literal["PASS", "DELAYED", "FAILED", "PENDING"]
AlertSeverityValue = Literal["normal", "warning", "critical", "offline"]
RiskLevelValue = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
SleepStageValue = Literal["deep", "light", "rem", "awake"]
ActivityLabelValue = Literal[
    "resting",
    "walking",
    "running",
    "falling",
    "recovery",
    "sleeping",
    "unknown",
]


class PersonaConfig(BaseModel):
    age: int = 70
    weight_kg: float = 65.0
    height_cm: float = 165.0
    gender: str | None = None
    seed: int = 7


class DataBindingConfig(BaseModel):
    dataset: str
    subject_id: str
    source_mode: Literal["synthetic", "replay"] = "synthetic"
    loop: bool = True
    speed_factor: float = 1.0


class SimulatedDevice(BaseModel):
    id: str
    name: str
    serialNumber: str
    mqttClientId: str
    deviceType: DeviceTypeValue
    batteryLevel: int
    isOnline: bool
    bindStatus: BindStatusValue
    lastSeenAt: str | None
    hasPendingSync: bool
    state: DeviceStateValue
    boundDbDeviceId: int | None = None
    currentScenarioId: str | None = None
    personaConfig: PersonaConfig | None = None
    dataBinding: DataBindingConfig | None = None


class CreateDeviceRequest(BaseModel):
    name: str
    type: DeviceTypeValue = Field(default="smartwatch")
    persona_config: PersonaConfig = Field(default_factory=PersonaConfig)
    data_binding: DataBindingConfig | None = None


class BindDeviceRequest(BaseModel):
    db_device_id: int


class BindDeviceResponse(BaseModel):
    sim_device_id: str
    db_device_id: int | None = None
    status: str


class SessionInfo(BaseModel):
    id: str
    deviceIds: list[str]
    speed: int
    status: Literal["idle", "running", "stopped"]
    createdAt: str
    lastTickAt: str | None


class CreateSessionRequest(BaseModel):
    device_ids: list[str]
    speed: int = Field(default=5, ge=1, le=300)


class VitalsSample(BaseModel):
    timestamp: str
    heartRate: float
    spo2: float
    temperature: float | None = None
    bloodPressureSys: float | None = None
    bloodPressureDia: float | None = None
    respiratoryRate: float | None = None
    hrv: float | None = None
    signalQuality: float | None = None
    motionArtifact: bool | None = None
    isStale: bool
    severity: SeverityValue
    activityLabel: ActivityLabelValue = "unknown"
    motionTag: ActivityLabelValue = "unknown"
    fieldProvenance: dict[str, str] | None = None
    bpObservationAgeSec: float | None = None
    bpIsStale: bool | None = None
    sourceMode: Literal["synthetic", "replay", "assisted"] | None = None


class InjectEventRequest(BaseModel):
    device_id: str
    event_type: str
    variant: str | None = None


PipelineStageStatusValue = Literal["ok", "pending", "failed", "skipped"]
PipelineStageKeyValue = Literal[
    "device_registered",
    "session_started",
    "telemetry_generated",
    "telemetry_published",
    "risk_evaluated",
    "alert_dispatched",
]


class PipelineStage(BaseModel):
    """One step of the device → publish → downstream evidence trail.

    The frontend renders an ordered strip of these so an operator can
    see exactly where a session is in the pipeline (or where it broke).
    `at` is populated only for stages that have produced an artifact —
    e.g. `telemetry_published.at` mirrors the most recent successful
    publish timestamp.
    """

    key: PipelineStageKeyValue
    label: str
    status: PipelineStageStatusValue
    detail: str | None = None
    at: str | None = None


class VerificationResult(BaseModel):
    deviceId: str
    vitalsReceived: bool
    alertReceived: bool
    riskScoreReceived: bool
    latencyMs: int
    status: VerificationStatusValue
    lastCheckedAt: str
    # Module E additions ----------------------------------------------------
    stages: list[PipelineStage] = Field(default_factory=list)
    failureReason: str | None = None
    lastGoodPublishAt: str | None = None
    lastPublishAttemptAt: str | None = None
    publishAckCount: int = 0
    publishAttemptCount: int = 0


class LogEntry(BaseModel):
    level: Literal["INFO", "WARN", "ERROR"]
    session_id: str
    device_id: str
    message: str
    ts: str


# ---------------------------------------------------------------------------
# Module C — Sessions / Fall Lab. Motion + fall-state evidence contract.
#
# `MotionLatest` mirrors the most recent `motion` block emitted by the
# simulator's `MotionGenerator`; arrays are short (~100 samples) and the
# full vector is sent so the FE can render a sparkline without faking it.
#
# `FallState` is derived: `deviceState` is the canonical FSM state from
# `SimulatedDevice.state`, `lastFallEventAt` is the timestamp of the most
# recent `fall_detected` event, and `countdownRemainingSec` is computed
# from that timestamp + the SOS countdown window.  No FE-only state.
# ---------------------------------------------------------------------------


class MotionLatest(BaseModel):
    """Most recent motion window emitted for `deviceId` in `sessionId`.

    The arrays are kept verbatim from the dataset registry so the frontend
    can render the same trace the dataset produced (no synthetic fallback).
    `accelMag` is the precomputed magnitude that the fall pipeline uses.
    """

    deviceId: str
    sessionId: str
    emittedAt: str
    activityState: str
    fallVariant: str | None = None
    sampleRate: float | None = None
    accelX: list[float] = Field(default_factory=list)
    accelY: list[float] = Field(default_factory=list)
    accelZ: list[float] = Field(default_factory=list)
    accelMag: list[float] = Field(default_factory=list)
    gyroX: list[float] = Field(default_factory=list)
    gyroY: list[float] = Field(default_factory=list)
    gyroZ: list[float] = Field(default_factory=list)


FallStateValue = Literal[
    "idle",
    "fall_detected",
    "fall_countdown",
    "sos_active",
    "fall_resolved",
]


class FallEventEntry(BaseModel):
    """Lightweight fall-event reference for the operator panel."""

    id: str
    timestamp: str
    eventType: str
    severity: AlertSeverityValue
    variant: str | None = None


# ---------------------------------------------------------------------------
# AI verdict surface (Module FA — Fall Lab redesign)
#
# These types project the model-api `/api/v1/fall/predict` response into a
# shape the FE consumes directly.  Centralising the projection in
# `simulator_core.fall_ai_client.normalise_verdict()` keeps the runtime
# free of model-specific field plumbing.
# ---------------------------------------------------------------------------


AIPredictionLabel = Literal["normal", "possible_fall", "likely_fall", "critical_fall"]
AIPredictionBand = Literal["normal", "warning", "critical"]


class AITopFeature(BaseModel):
    """One SHAP top-feature contribution with a Vietnamese explanation."""

    featureName: str
    contribution: float
    vietnameseExplanation: str
    severity: Literal["normal", "warning", "critical"] = "normal"


class AIPrediction(BaseModel):
    """AI fall verdict for the most recent inject_event call."""

    label: AIPredictionLabel
    probability: float
    confidence: float
    riskBand: AIPredictionBand
    requiresAttention: bool = False
    highPriorityAlert: bool = False
    explanationSummary: str | None = None
    topFeatures: list[AITopFeature] = Field(default_factory=list)
    predictedAt: str
    modelStatus: Literal["ok", "offline", "no_window", "skipped"] = "ok"


class MotionWindowRef(BaseModel):
    """Reference to the motion window the AI verdict was computed on.

    Lets the FE align the sparkline + AI verdict to the same data the
    model classified, instead of the live-streaming tick payload (which
    moves on by the time the verdict comes back).
    """

    emittedAt: str
    sampleCount: int
    sampleRate: float | None = None
    fallVariant: str | None = None


class CountdownPolicy(BaseModel):
    """Variant-specific SOS countdown policy.

    The same FallState shape is returned for every variant; only the
    *policy* differs (false_fall has 0s + no countdown; fall_brief auto-
    resolves at 10s; confirmed/no_response use the standard 30s).
    """

    totalSec: int
    autoResolve: bool = False
    allowsCancel: bool = True


class FallState(BaseModel):
    """Operator-visible fall pipeline state for one focal device.

    All fields are derived from existing runtime state — no extra storage.
    The frontend uses `countdownRemainingSec` to render an evidence-driven
    countdown bar instead of a FE-only `setInterval`.

    The Module-FA redesign added `aiPrediction`, `motionWindowRef`, and
    `countdownPolicy`; all three are nullable so legacy clients that only
    poll for the FSM-level fields continue to work without changes.
    """

    deviceId: str
    sessionId: str
    deviceState: DeviceStateValue
    activityState: str
    fallVariant: str | None = None
    fallState: FallStateValue
    lastFallEventAt: str | None = None
    countdownStartedAt: str | None = None
    countdownRemainingSec: int = 0
    countdownTotalSec: int = 0
    sosActive: bool = False
    recentFallEvents: list[FallEventEntry] = Field(default_factory=list)
    aiPrediction: AIPrediction | None = None
    motionWindowRef: MotionWindowRef | None = None
    countdownPolicy: CountdownPolicy | None = None


class AlertEvent(BaseModel):
    id: str
    timestamp: str
    deviceId: str
    eventType: str
    severity: AlertSeverityValue
    message: str
    metadata: dict[str, str] = Field(default_factory=dict)


class DashboardSummary(BaseModel):
    totalDevices: int
    activeDevices: int
    alertsLastHour: int
    avgLatencyMs: int


class SleepStageSegment(BaseModel):
    stage: SleepStageValue
    start: str
    end: str


class SleepHistoryRow(BaseModel):
    date: str
    score: int
    efficiency: float
    durationMinutes: int
    avgHeartRate: float
    minSpo2: float


class DbSleepHistoryRow(BaseModel):
    date: str
    score: int
    efficiency: float
    durationMinutes: int
    wakeCount: int
    phases: dict[str, int]
    startTime: str
    endTime: str


class SleepSessionResponse(BaseModel):
    deviceId: str
    date: str
    realismMode: Literal["fallback", "real", "edf"]
    score: int
    efficiency: float
    durationMinutes: int
    avgHeartRate: float
    minSpo2: float
    phases: list[SleepStageSegment]
    history: list[SleepHistoryRow]
    banner: str


class RiskContribution(BaseModel):
    feature: str
    value: str
    weight: float
    direction: Literal["up", "down", "flat"]


class RiskHistoryPoint(BaseModel):
    date: str
    score: float


class RiskScoreResponse(BaseModel):
    deviceId: str
    score: float
    riskLevel: RiskLevelValue
    model: str
    algorithm: str
    calculatedAt: str
    explanation: list[RiskContribution]
    history: list[RiskHistoryPoint]


class RiskInjectRequest(BaseModel):
    device_id: str
    risk_type: Literal["general", "stroke", "cardiac"] = "general"
    risk_level: RiskLevelValue
    score: float = Field(ge=0.0, le=1.0)


# ADR-020 Phase 7 S7: ``RiskTriggerRequest`` disposed alongside the
# ``POST /analytics/risk/trigger`` router endpoint. The mobile BE now
# auto-calls ``calculate_device_risk`` after every successful
# ``/telemetry/ingest`` so an explicit risk-trigger payload is unused.


class ApplyScenarioRequest(BaseModel):
    device_id: str
    scenario_id: str


class BackfillSleepRequest(BaseModel):
    """Request để bơm dữ liệu sleep lịch sử N ngày về trước."""

    device_id: str
    days_behind: int = Field(default=30, ge=1, le=90)
    scenario_id: str = Field(default="good_sleep_night")


class BackfillSleepResponse(BaseModel):
    """Kết quả sau khi backfill sleep data."""

    pushed: int
    skipped: int
    errors: list[str]
    total_days: int


class PushSleepDateRequest(BaseModel):
    device_id: str
    target_date: Date
    scenario_id: str = Field(default="good_sleep_night")


class PushSleepDateResponse(BaseModel):
    success: bool
    target_date: str
    scenario_id: str
    duration_minutes: int
    sleep_score: int
    disorder_tags: list[str]
    was_overwritten: bool
    message: str


class AdminCreateDeviceSimRequest(BaseModel):
    """Request body khi tạo device qua Simulator Admin UI."""

    device_name: str
    device_type: str = "smartwatch"
    serial_number: str | None = None
    user_email: str | None = None


class AdminAssignUserRequest(BaseModel):
    """Request body khi bind device cho user."""

    user_email: str


class BatchActivateRequest(BaseModel):
    device_ids: list[int]


class RuntimeConfig(BaseModel):
    tick_interval_seconds: float = Field(ge=0.1, le=60, description="Background tick interval")
    push_interval_seconds: int = Field(ge=1, le=300, description="Telemetry push interval")
    sleep_speed_factor: float = Field(ge=1, le=3600, description="Sleep phase speed-up factor")
    health_backend_url: str = Field(description="Health backend base URL (read-only)")


class RuntimeConfigUpdate(BaseModel):
    tick_interval_seconds: float | None = Field(default=None, ge=0.1, le=60)
    push_interval_seconds: int | None = Field(default=None, ge=1, le=300)
    sleep_speed_factor: float | None = Field(default=None, ge=1, le=3600)


TriggerModeValue = Literal["off", "shadow", "active"]
PersistenceSourceValue = Literal["file", "defaults"]


class FeatureFlags(BaseModel):
    """Feature-flag block exposed by ``/api/v1/sim/settings``.

    ``triggerMode`` is the canonical, server-derived view of how the pre-model
    trigger pipeline is running.  Module F requires the FE to consume it
    instead of guessing from booleans (plan §10.4 / 1.2 #2):

    * ``off``    — ``PRE_MODEL_TRIGGER_ENABLED`` is off (or the orchestrator
      failed to wire); no rule evaluation happens.
    * ``shadow`` — pipeline is on, ``enable_model_calls=False``: rules + fall
      detection run locally, but the simulator never calls the model API.
    * ``active`` — pipeline is on, ``enable_model_calls=True``: rules run
      and the simulator escalates to the model API when triggered.

    Legacy booleans ``use_db_thresholds`` and ``pre_model_trigger_enabled``
    are kept on the response for one release cycle so existing FE code keeps
    compiling.  Module F.6 retires them in favour of ``triggerMode`` +
    ``thresholdSource``.
    """

    use_db_thresholds: bool = False
    pre_model_trigger_enabled: bool = False
    trigger_mode: TriggerModeValue = "off"
    enable_model_calls: bool = False


class RuntimePersistenceBlock(BaseModel):
    """Where the live runtime config came from (Module F.1)."""

    source: PersistenceSourceValue = "defaults"
    path: str = ""
    last_saved_at: str | None = None
    last_error: str | None = None


class SimulatorSettingsResponse(BaseModel):
    runtime: RuntimeConfig
    daytime_thresholds: dict[str, float]
    sleep_thresholds: dict[str, float]
    rules_config: dict | None = None
    fall_config: dict | None = None
    feature_flags: FeatureFlags
    db_daytime_thresholds: dict[str, float] | None = None
    db_sleep_thresholds: dict[str, float] | None = None
    threshold_source: str = "fallback"
    persistence: RuntimePersistenceBlock = Field(default_factory=RuntimePersistenceBlock)


class RuntimeConfigSaveResponse(BaseModel):
    """Response shape for ``PUT /api/v1/sim/settings/runtime`` (Module F.2).

    Carries the live config plus the persistence echo so the FE can render
    "Đã lưu lúc HH:MM — vẫn áp dụng sau khi restart" right after the call
    completes, without waiting for the next ``/api/v1/sim/settings`` poll.
    """

    runtime: RuntimeConfig
    persistence: RuntimePersistenceBlock


# ---------------------------------------------------------------------------
# Admin device response models (typed replacements for raw ``dict`` returns)
# ---------------------------------------------------------------------------


class AdminDeviceResponse(BaseModel):
    """Typed response for a device row from the production DB."""

    model_config = {"from_attributes": True}

    id: int
    uuid: str | UUID | None = None
    user_id: int | None = None
    user_email: str | None = None
    user_full_name: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    date_of_birth: str | Date | None = None
    gender: str | None = None
    device_name: str | None = None
    device_type: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    serial_number: str | None = None
    mac_address: str | None = None
    mqtt_client_id: str | None = None
    is_active: bool = False
    battery_level: int | None = None
    signal_strength: int | None = None
    last_seen_at: str | DateTime | None = None
    last_sync_at: str | DateTime | None = None
    registered_at: str | DateTime | None = None
    updated_at: str | DateTime | None = None
    deleted_at: str | DateTime | None = None
    # enriched by the router layer
    is_sim_running: bool = False


class AdminDeviceActionResponse(AdminDeviceResponse):
    """Extended response returned by mutating admin actions (activate, assign, etc.)."""

    message: str | None = None


class AdminDeviceAssignResponse(AdminDeviceActionResponse):
    """Response for the assign endpoint — includes the assigned user's email."""

    user_email: str | None = None  # type: ignore[assignment]


class AdminBatchActivateItem(BaseModel):
    """Single item in a batch-activate response list."""

    model_config = {"from_attributes": True}

    id: int
    status: str
    detail: str | None = None
    # all AdminDeviceResponse fields are optional here (present only on success)
    uuid: str | None = None
    user_id: int | None = None
    user_email: str | None = None
    user_full_name: str | None = None
    device_name: str | None = None
    device_type: str | None = None
    is_active: bool | None = None
    message: str | None = None


class AdminUserResponse(BaseModel):
    """Typed response for user search."""

    model_config = {"from_attributes": True}

    id: int
    email: str
    full_name: str | None = None
    is_active: bool = True


class AdminEmergencyContact(BaseModel):
    """One row from `emergency_contacts` for a user."""

    model_config = {"from_attributes": True}

    id: int
    name: str
    phone: str
    relationship: str | None = None
    priority: int = 1


class AdminUserProfileResponse(BaseModel):
    """Full user profile consumed by the simulator-web Session page.

    Aggregates demographics + medical info from `users` and the list of
    `emergency_contacts` so the FE can render a single profile card without
    chaining multiple admin requests.  Array fields default to `[]` so the
    FE can render unconditionally.
    """

    model_config = {"from_attributes": True}

    # Identity
    id: int
    email: str
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None

    # Demographics
    date_of_birth: str | None = None  # ISO date string YYYY-MM-DD
    gender: str | None = None
    height_cm: int | None = None
    weight_kg: float | None = None

    # Medical
    blood_type: str | None = None
    medical_conditions: list[str] = []
    medications: list[str] = []
    allergies: list[str] = []

    # Emergency
    emergency_contacts: list[AdminEmergencyContact] = []


# ---------------------------------------------------------------------------
# Health payload v2 — single source of truth consumed by the dashboard hero,
# settings, and verification surfaces.  See Phase 0 of the UX refactor plan.
# ---------------------------------------------------------------------------


HealthRuntimeStateValue = Literal["running", "idle", "stopped", "degraded"]
HealthBackendStateValue = Literal["connected", "down", "slow", "unknown"]
HealthDatabaseStateValue = Literal["connected", "down"]
HealthModelApiStateValue = Literal["ready", "unavailable", "unknown"]
HealthPreTriggerModeValue = Literal["off", "shadow", "active"]
HealthThresholdSourceValue = Literal["db", "fallback", "unavailable"]
HealthScoreSourceValue = Literal["ai", "heuristic"]


class HealthRuntimeBlock(BaseModel):
    state: HealthRuntimeStateValue = "running"
    version: str = "simulator-api-0.4.0"
    uptimeSeconds: int = 0


class HealthDatabaseBlock(BaseModel):
    state: HealthDatabaseStateValue = "connected"
    lastCheckMs: int | None = None


class HealthBackendBlock(BaseModel):
    state: HealthBackendStateValue = "unknown"
    url: str = ""
    lastLatencyMs: int | None = None
    lastError: str | None = None


class HealthModelApiBlock(BaseModel):
    state: HealthModelApiStateValue = "unknown"
    url: str = "http://localhost:8001"
    lastCheckedAt: str | None = None
    lastScoreSource: HealthScoreSourceValue = "heuristic"
    lastError: str | None = None


class HealthPreTriggerBlock(BaseModel):
    mode: HealthPreTriggerModeValue = "off"
    enableModelCalls: bool = False
    thresholdSource: HealthThresholdSourceValue = "fallback"


class HealthTelemetryBlock(BaseModel):
    devicesSimulated: int = 0
    sessionsRunning: int = 0
    alertsLastHour: int = 0
    avgPublishLatencyMs: int = 0


class HealthPayloadV2(BaseModel):
    """Structured health payload returned by ``/api/v1/sim/health`` (v2).

    The legacy flat keys (``status``/``api``/``backend``/``mqtt``/``db``/``version``)
    are still emitted on the same response object during the deprecation window
    so existing consumers (``HealthStatusPanel`` etc.) keep working.
    """

    schemaVersion: Literal["2.0"] = "2.0"
    runtime: HealthRuntimeBlock = Field(default_factory=HealthRuntimeBlock)
    database: HealthDatabaseBlock = Field(default_factory=HealthDatabaseBlock)
    backend: HealthBackendBlock = Field(default_factory=HealthBackendBlock)
    modelApi: HealthModelApiBlock = Field(default_factory=HealthModelApiBlock)
    preTrigger: HealthPreTriggerBlock = Field(default_factory=HealthPreTriggerBlock)
    telemetry: HealthTelemetryBlock = Field(default_factory=HealthTelemetryBlock)
    degradedReasons: list[str] = Field(default_factory=list)
