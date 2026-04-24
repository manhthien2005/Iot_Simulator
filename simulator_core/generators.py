from __future__ import annotations

from copy import deepcopy
from math import isnan
from random import Random
from typing import Any

import numpy as np

from .dataset_registry import DatasetRegistry
from .persona_engine import DeviceState, Persona


def _to_scalar(value: Any, default: float = 0.0) -> float:
    """Safely convert *value* to a Python float.

    Handles plain numbers, 0-d numpy arrays, and multi-dimensional numpy
    arrays (takes the first element).  Returns *default* when *value* is
    ``None`` or conversion fails.
    """
    if value is None:
        return default
    try:
        if isinstance(value, np.ndarray):
            return float(value.flat[0]) if value.size > 0 else default
        return float(value)
    except (TypeError, ValueError):
        return default


SLEEP_PHASE_VITALS: dict[str, dict[str, float]] = {
    "light": {
        "hr_delta": -8.0,
        "rr_delta": -2.0,
        "temp_delta": -0.3,
    },
    "deep": {
        "hr_delta": -18.0,
        "rr_delta": -4.0,
        "temp_delta": -0.8,
    },
    "rem": {
        "hr_delta": -5.0,
        "rr_delta": -1.0,
        "temp_delta": -0.5,
    },
    "awake": {
        "hr_delta": 2.0,
        "rr_delta": 0.0,
        "temp_delta": 0.0,
    },
}


def _is_missing_numeric(value: Any) -> bool:
    return value is None or (isinstance(value, float) and isnan(value))


def _default_temperature(rng: Random) -> float:
    return round(36.7 + rng.uniform(-0.3, 0.3), 2)


class VitalsGenerator:
    def __init__(self, registry: DatasetRegistry, seed: int = 11) -> None:
        self.registry = registry
        self._rng = Random(seed)

    def generate(self, state: DeviceState, persona: Persona) -> dict[str, Any]:
        lookup_activity = state.activity_state if state.activity_state not in {"fall", "recovery"} else None
        baseline = self.registry.get_vitals_baseline(activity=lookup_activity)
        if baseline is None:
            baseline = self.registry.get_vitals_baseline()
        respiration_row = self._get_respiration_row(lookup_activity)
        respiration_rate = respiration_row.get("respiration_rate") if respiration_row else 16.0
        if _is_missing_numeric(respiration_rate):
            respiration_rate = 16.0
            rr_source = "mock"
        else:
            rr_source = f"real:{respiration_row.get('dataset')}" if respiration_row and respiration_row.get("dataset") else "real:BIDMC"
        respiration_rate = round(float(respiration_rate), 1)
        if baseline is None:
            return {
                "heart_rate": 72.0,
                "spo2": 98.0,
                "temperature": _default_temperature(self._rng),
                "blood_pressure_sys": 120.0,
                "blood_pressure_dia": 80.0,
                "respiratory_rate": respiration_rate,
                "activity_label": state.activity_state,
                "spo2_source": "mock",
                "rr_source": rr_source,
                "stress_data_source": "mock",
            }

        spo2 = baseline.get("spo2")
        blood_pressure_sys = baseline.get("blood_pressure_sys")
        blood_pressure_dia = baseline.get("blood_pressure_dia")
        baseline_dataset = baseline.get("dataset")
        if not _is_missing_numeric(spo2):
            spo2_source = f"real:{baseline_dataset}" if baseline_dataset else "mock"
        else:
            spo2_source = "mock"

        if _is_missing_numeric(spo2):
            vitaldb_row = self.registry.get_vitals_baseline(
                dataset="VitalDB",
                required_fields=("spo2", "blood_pressure_sys", "blood_pressure_dia"),
            )
            if vitaldb_row is not None:
                spo2 = vitaldb_row.get("spo2")
                blood_pressure_sys = vitaldb_row.get("blood_pressure_sys")
                blood_pressure_dia = vitaldb_row.get("blood_pressure_dia")
                if not _is_missing_numeric(spo2):
                    spo2_source = "real:VitalDB"

        stress_adjust = 0.0
        stress_data_source = "mock"
        if state.stress_state is not None:
            stress_sample = self.registry.get_stress_sample(state.stress_state)
            stress_reference = self.registry.get_stress_baseline_mean()
            if stress_sample is not None:
                reference_hr = stress_reference if stress_reference is not None else 72.0
                sample_hr = float(stress_sample.get("heart_rate") or reference_hr)
                stress_adjust = sample_hr - reference_hr
                stress_data_source = "real:WESAD"
            elif state.stress_state == "stress":
                stress_adjust = 8.0

        noise = self._rng.uniform(-1.5, 1.5)
        temperature = baseline.get("temperature")
        if _is_missing_numeric(temperature):
            temperature = _default_temperature(self._rng)
        else:
            temperature = round(float(temperature), 2)
        heart_rate = (baseline.get("heart_rate") or 72.0) + stress_adjust + noise
        # HRV (RMSSD ms) — inversely correlated with heart_rate
        # Typical range: 20-80ms for adults. Higher HR → lower HRV.
        hrv = max(10.0, round(120.0 - 0.8 * heart_rate + self._rng.uniform(-5.0, 5.0), 1))
        return {
            "timestamp": baseline.get("timestamp"),
            "heart_rate": round(heart_rate, 2),
            "hrv": hrv,
            "spo2": spo2,
            "temperature": temperature,
            "blood_pressure_sys": blood_pressure_sys,
            "blood_pressure_dia": blood_pressure_dia,
            "respiratory_rate": respiration_rate,
            "activity_label": state.activity_state,
            "dataset": baseline.get("dataset"),
            "spo2_source": spo2_source,
            "rr_source": rr_source,
            "stress_data_source": stress_data_source,
        }

    def generate_tick(
        self,
        state: DeviceState,
        persona: Persona,
        sim_time: float | None = None,
        device_context: Any | None = None,
    ) -> dict[str, Any]:
        binding = getattr(device_context, "data_binding", None)
        if binding is not None and binding.source_mode == "replay":
            return self._generate_replay(device_context, sim_time)
        payload = self.generate(state, persona)
        if state.activity_state == "sleeping":
            sleep_phase = state.sleep_phase or "light"
            deltas = SLEEP_PHASE_VITALS.get(sleep_phase, {})
            heart_rate = payload.get("heart_rate")
            if heart_rate is not None:
                payload["heart_rate"] = round(max(35.0, float(heart_rate) + deltas.get("hr_delta", 0.0)), 2)
            respiratory_rate = payload.get("respiratory_rate")
            if respiratory_rate is not None:
                payload["respiratory_rate"] = round(max(8.0, float(respiratory_rate) + deltas.get("rr_delta", 0.0)), 1)
            temperature = payload.get("temperature")
            if temperature is not None:
                payload["temperature"] = round(float(temperature) + deltas.get("temp_delta", 0.0), 2)
            payload["sleep_phase"] = sleep_phase
            payload["activity_label"] = "sleeping"
        if sim_time is not None:
            payload["sim_time"] = sim_time
        return payload

    def _get_respiration_row(self, activity: str | None) -> dict[str, Any] | None:
        getter = getattr(self.registry, "get_respiration_sample", None)
        if getter is None:
            return None
        row = getter(activity=activity) if activity is not None else getter()
        if row is None and activity is not None:
            row = getter()
        return row

    def _generate_replay(self, device_context: Any, sim_time: float | None = None) -> dict[str, Any]:
        binding = device_context.data_binding
        cursor = device_context.replay_cursor
        row = self.registry.get_vitals_sample_at(
            binding.subject_id,
            binding.dataset,
            cursor.advance(),
        )
        if row is None:
            payload: dict[str, Any] = {
                "heart_rate": None,
                "temperature": _default_temperature(self._rng),
                "source_mode": "replay",
                "error": "no_data",
            }
        else:
            payload = dict(row)
            if _is_missing_numeric(payload.get("temperature")):
                payload["temperature"] = _default_temperature(self._rng)
            payload["source_mode"] = "replay"
        if sim_time is not None:
            payload["sim_time"] = sim_time
        return payload


class MotionGenerator:
    def __init__(self, registry: DatasetRegistry, seed: int = 13) -> None:
        self.registry = registry
        self._rng = Random(seed)
        # Orientation state — simple gyro integration (drift acceptable for sim)
        self._pitch: float = 0.0
        self._roll: float = 0.0
        self._yaw: float = 0.0

    def _integrate_orientation(self, window: dict[str, Any]) -> None:
        """Integrate gyro data into orientation and inject ``orientation`` key."""
        gyro = window.get("gyro")
        if isinstance(gyro, dict) and gyro:
            gyro_x = _to_scalar(gyro.get("x", 0.0))
            gyro_y = _to_scalar(gyro.get("y", 0.0))
            gyro_z = _to_scalar(gyro.get("z", 0.0))
        else:
            gyro_x = _to_scalar(window.get("gyro_x", 0.0))
            gyro_y = _to_scalar(window.get("gyro_y", 0.0))
            gyro_z = _to_scalar(window.get("gyro_z", 0.0))

        dt = 1.0  # ~1 second per tick
        self._pitch = max(-90.0, min(90.0, self._pitch + gyro_x * dt))
        self._roll = max(-90.0, min(90.0, self._roll + gyro_y * dt))
        self._yaw = ((self._yaw + gyro_z * dt + 180.0) % 360.0) - 180.0

        window["orientation"] = {
            "pitch": round(self._pitch, 2),
            "roll": round(self._roll, 2),
            "yaw": round(self._yaw, 2),
        }

    def generate(self, state: DeviceState) -> dict[str, Any] | None:
        activity = state.activity_state
        if activity == "recovery":
            activity = "standing"
        if activity == "fall":
            return self.inject_fall(state.fall_variant or "fall_1")

        windows = self.registry.get_motion_windows(activity=activity)
        if not windows:
            windows = self.registry.get_motion_windows()
        if not windows:
            return None
        window = deepcopy(windows[self._rng.randrange(len(windows))])
        self._integrate_orientation(window)
        return window

    def get_window_for_state(self, state: DeviceState) -> dict[str, Any] | None:
        return self.generate(state)

    def inject_fall(self, variant: str) -> dict[str, Any] | None:
        windows = self.registry.get_motion_windows(fall_variant=variant)
        if not windows:
            windows = self.registry.get_motion_windows(activity="fall")
        if not windows:
            event = self.registry.get_fall_event(variant)
            if event is None:
                return None
            result: dict[str, Any] = {"event": event}
            result["orientation"] = {
                "pitch": round(self._rng.uniform(-45.0, 45.0), 2),
                "roll": round(self._rng.uniform(-30.0, 30.0), 2),
                "yaw": round(self._yaw, 2),
            }
            return result
        window = deepcopy(windows[self._rng.randrange(len(windows))])
        # Fall events produce spike orientation values
        window["orientation"] = {
            "pitch": round(self._rng.uniform(-45.0, 45.0), 2),
            "roll": round(self._rng.uniform(-30.0, 30.0), 2),
            "yaw": round(self._yaw, 2),
        }
        return window
