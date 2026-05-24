"""Device-level domain dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api_server.schemas import DataBindingConfig, SimulatedDevice


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

    def to_schema(self, current_scenario_id: str | None = None) -> "SimulatedDevice":
        from api_server.schemas import DataBindingConfig, SimulatedDevice  # noqa: PLC0415
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
class DevicePublishStatus:
    """Per-device publish bookkeeping (fix bug all-or-nothing ack)."""

    ok: bool = False
    ack_count: int = 0
    message_count: int = 0
    latency_ms: int | None = None
    attempt_at: str | None = None
    last_ok_at: str | None = None
    error: str | None = None
    attempt_count: int = 0
    ack_count_total: int = 0
