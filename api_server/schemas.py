from __future__ import annotations

from typing import Literal

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
