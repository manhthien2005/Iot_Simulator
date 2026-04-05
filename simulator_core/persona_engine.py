from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from time import monotonic
from typing import ClassVar


@dataclass
class Persona:
    age: int = 70
    weight_kg: float = 65.0
    height_cm: float = 165.0
    gender: str | None = None
    seed: int = 7


@dataclass
class DeviceState:
    activity_state: str = "resting"
    fall_variant: str | None = None
    stress_state: str | None = None
    sleep_phase: str | None = None
    battery_level: int = 100
    is_online: bool = True


# LOW #2: Activity-dependent battery drain multipliers
_BATTERY_DRAIN_FACTORS: dict[str, float] = {
    "sleeping": 0.5,
    "resting": 0.8,
    "walking": 1.5,
    "running": 1.5,
    "standing": 1.0,
    "fall": 1.2,
    "recovery": 1.0,
}


@dataclass
class PersonaEngine:
    FALL_DURATION_TICKS: ClassVar[int] = 10
    RECOVERY_DURATION_TICKS: ClassVar[int] = 20
    persona: Persona
    state: DeviceState = field(default_factory=DeviceState)

    def __post_init__(self) -> None:
        self._rng = Random(self.persona.seed)
        self._ticks = 0
        self._ticks_in_state = 0
        self._state_started_at = monotonic()
        self._drain_accumulator: float = 0.0

    def tick(self) -> DeviceState:
        self._ticks += 1
        if self.state.battery_level > 0 and self._ticks % 60 == 0:
            # LOW #2: drain rate depends on activity state
            factor = _BATTERY_DRAIN_FACTORS.get(self.state.activity_state, 1.0)
            self._drain_accumulator += factor
            if self._drain_accumulator >= 1.0:
                drain = int(self._drain_accumulator)
                self.state.battery_level = max(0, self.state.battery_level - drain)
                self._drain_accumulator -= drain

        self._ticks_in_state += 1
        if self.state.activity_state == "fall" and self._ticks_in_state >= self.FALL_DURATION_TICKS:
            self.transition_to("recovery")
        elif self.state.activity_state == "recovery" and self._ticks_in_state >= self.RECOVERY_DURATION_TICKS:
            self.transition_to("standing")

        return self.state

    def transition_to(self, activity_state: str, stress_state: str | None = None) -> DeviceState:
        self.state.activity_state = activity_state
        self.state.stress_state = stress_state
        if activity_state != "fall":
            self.state.fall_variant = None
        self._state_started_at = monotonic()
        self._ticks_in_state = 0
        return self.state

    # Removed dead code: set_activity, current_activity_label, time_in_state, is_fall_event

    def inject_event(self, event_type: str, variant: str | None = None) -> DeviceState:
        if event_type == "fall_detected":
            self.transition_to("fall")
            self.state.fall_variant = variant or "fall_generic"
        elif event_type == "sleep_start":
            self.transition_to("sleeping")
            self.state.sleep_phase = variant or "light"
        elif event_type == "sleep_end":
            self.transition_to("resting")
            self.state.sleep_phase = None
        elif event_type == "sleep_phase_change":
            if self.state.activity_state == "sleeping":
                self.state.sleep_phase = variant or "light"
        elif event_type == "low_battery":
            self.state.battery_level = min(self.state.battery_level, 15)
        elif event_type == "device_offline":
            self.state.is_online = False
        elif event_type == "device_online":
            self.state.is_online = True
        elif event_type == "stress":
            self.state.stress_state = "stress"
        elif event_type == "neutral":
            self.state.stress_state = "neutral"
        return self.state

