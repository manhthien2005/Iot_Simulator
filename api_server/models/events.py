"""Event and risk snapshot dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api_server.schemas import AlertEvent, RiskContribution


@dataclass
class EventRecord:
    id: str
    timestamp: str
    device_id: str
    event_type: str
    severity: str
    message: str
    metadata: dict[str, str] = field(default_factory=dict)

    def to_schema(self) -> "AlertEvent":
        from api_server.schemas import AlertEvent  # noqa: PLC0415
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
    explanation: list["RiskContribution"]
    model: str = "healthguard-v1.2"
    algorithm: str = "ONNX RF+LGBM"
