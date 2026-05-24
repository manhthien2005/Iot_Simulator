"""Session-level domain dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import TYPE_CHECKING, Any

from api_server.models.device import DevicePublishStatus
from api_server.utils import _utc_now_iso

if TYPE_CHECKING:
    from simulator_core.session import SimulatorSession


@dataclass
class PendingDevicePublish:
    """Per-device publish unit.

    Mỗi device được đóng gói riêng → 1 device fail không kéo cả batch.
    """

    device_id: str
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
    pending_publishes: list[PendingDevicePublish] = field(default_factory=list)
    pending_heartbeats: list[PendingHeartbeatUpdate] = field(default_factory=list)
    pending_alerts: list[PendingAlertCall] = field(default_factory=list)

    def extend(self, other: "SessionSideEffects") -> None:
        self.pending_publishes.extend(other.pending_publishes)
        self.pending_heartbeats.extend(other.pending_heartbeats)
        self.pending_alerts.extend(other.pending_alerts)


@dataclass
class SessionRecord:
    id: str
    device_ids: list[str]
    speed: int
    simulator: "SimulatorSession"
    status: str = "idle"
    created_at: str = field(default_factory=_utc_now_iso)
    last_tick_at: str | None = None
    last_tick_outputs: list[dict[str, Any]] = field(default_factory=list)
    last_publish_ok: bool = False
    last_publish_ack_count: int = 0
    last_publish_count: int = 0
    last_publish_latency_ms: int | None = None
    last_publish_attempt_at: str | None = None
    last_publish_ok_at: str | None = None
    last_publish_error: str | None = None
    publish_attempt_count: int = 0
    publish_ack_count_total: int = 0
    device_publish_status: dict[str, DevicePublishStatus] = field(default_factory=dict)
    alert_received: bool = False
    last_tick_monotonic: float = field(default_factory=monotonic)
    source_modes: dict[str, str] = field(default_factory=dict)
