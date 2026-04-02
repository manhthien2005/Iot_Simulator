from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .dataset_registry import DatasetRegistry
from .generators import MotionGenerator, VitalsGenerator
from .persona_engine import Persona, PersonaEngine


@dataclass
class DataBinding:
    subject_id: str
    dataset: str
    source_mode: str = "synthetic"
    loop: bool = True
    speed_factor: float = 1.0


@dataclass
class ReplayCursor:
    binding: DataBinding
    _index: int = 0

    def advance(self) -> int:
        index = self._index
        self._index += 1
        return index

    def reset(self) -> None:
        self._index = 0


@dataclass
class DeviceContext:
    device_id: str
    engine: PersonaEngine
    data_binding: DataBinding | None = None
    _replay_cursor: ReplayCursor | None = field(default=None, init=False, repr=False)

    @property
    def replay_cursor(self) -> ReplayCursor:
        binding = self.data_binding
        if binding is None or binding.source_mode != "replay":
            raise RuntimeError(f"Replay cursor requested for non-replay device: {self.device_id}")
        if self._replay_cursor is None or self._replay_cursor.binding is not binding:
            self._replay_cursor = ReplayCursor(binding=binding)
        return self._replay_cursor


class SimulatorSession:
    def __init__(self, registry: DatasetRegistry, devices: list[DeviceContext]) -> None:
        self.registry = registry
        self.devices = devices
        self.vitals_generator = VitalsGenerator(registry)
        self.motion_generator = MotionGenerator(registry)
        self.is_running = False

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False

    def tick(self) -> list[dict[str, Any]]:
        if not self.is_running:
            raise RuntimeError("Session is not running")

        outputs: list[dict[str, Any]] = []
        for device in self.devices:
            state = device.engine.tick()
            vitals = self.vitals_generator.generate_tick(
                state,
                device.engine.persona,
                device_context=device,
            )
            motion = self.motion_generator.generate(state)
            outputs.append(
                {
                    "device_id": device.device_id,
                    "emitted_at": datetime.now(timezone.utc).isoformat(),
                    "state": {
                        "activity_state": state.activity_state,
                        "fall_variant": state.fall_variant,
                        "stress_state": state.stress_state,
                        "battery_level": state.battery_level,
                        "is_online": state.is_online,
                    },
                    "vitals": vitals,
                    "motion": motion,
                }
            )
        return outputs

    def inject_event(self, device_id: str, event_type: str, variant: str | None = None) -> None:
        for device in self.devices:
            if device.device_id == device_id:
                device.engine.inject_event(event_type, variant)
                return
        raise KeyError(f"Device not found in session: {device_id}")


def build_device(
    device_id: str,
    *,
    age: int = 35,
    weight_kg: float = 70.0,
    height_cm: float = 170.0,
    gender: str | None = None,
    seed: int = 7,
    data_binding: DataBinding | None = None,
) -> DeviceContext:
    persona = Persona(
        age=age,
        weight_kg=weight_kg,
        height_cm=height_cm,
        gender=gender,
        seed=seed,
    )
    return DeviceContext(
        device_id=device_id,
        engine=PersonaEngine(persona),
        data_binding=data_binding,
    )
