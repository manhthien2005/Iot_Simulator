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
    battery_level: int = 100
    is_online: bool = True


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

    def tick(self) -> DeviceState:
        self._ticks += 1
        if self.state.battery_level > 0 and self._ticks % 60 == 0:
            self.state.battery_level -= 1

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

    def set_activity(self, activity_state: str, stress_state: str | None = None) -> DeviceState:
        return self.transition_to(activity_state, stress_state)

    def inject_event(self, event_type: str, variant: str | None = None) -> DeviceState:
        if event_type == "fall_detected":
            self.transition_to("fall")
            self.state.fall_variant = variant or "fall_generic"
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

    def current_activity_label(self) -> str:
        return self.state.activity_state

    def time_in_state(self) -> float:
        return monotonic() - self._state_started_at

    def is_fall_event(self) -> bool:
        return self.state.activity_state == "fall"
