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


class VerificationResult(BaseModel):
    deviceId: str
    vitalsReceived: bool
    alertReceived: bool
    riskScoreReceived: bool
    latencyMs: int
    status: VerificationStatusValue
    lastCheckedAt: str


class LogEntry(BaseModel):
    level: Literal["INFO", "WARN", "ERROR"]
    session_id: str
    device_id: str
    message: str
    ts: str


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


class RiskTriggerRequest(BaseModel):
    device_id: str


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


class FeatureFlags(BaseModel):
    use_db_thresholds: bool = False
    pre_model_trigger_enabled: bool = False


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
