from __future__ import annotations

from copy import deepcopy
import math
from math import isnan
from random import Random
from typing import Any

from .dataset_registry import DatasetRegistry
from .persona_engine import DeviceState, Persona


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


# ---------------------------------------------------------------------------
# Module FA Phase 3 — variant-aware motion source for FE fall variants.
#
# The dataset only carries internal `fall_1`..`fall_8` variants which all
# correspond to genuine high-impact falls (>3.5g peak).  The FE Fall Lab
# exposes 6 operator-facing variants where two of them (`false_fall`,
# `slip_recovery`) are *not* real falls and should NOT pull from the fall
# windows at all — otherwise pre-trigger fires HARD on every inject and
# the AI rightly classifies them as critical.
#
# This map drives `MotionGenerator.inject_fall(variant)`:
#
#   * `source_activity` — which activity bucket to pull a window from.
#     `"fall"` selects from the high-impact fall pool; anything else
#     (e.g. `"walking"`) yields a benign baseline window.
#   * `peak_g_range` — target accel-magnitude peak (in g) the window
#     should land at *after* scaling.  Picked to match
#     `FALL_VARIANT_CATALOGUE.expectedPeakG` on the FE so the evidence
#     checklist verifies cleanly.
#
# Matching numbers ensure pre-trigger fires HARD only for `confirmed`
# / `fall_no_response`, SOFT for `fall_brief` / `fall_from_bed`, and
# stays NONE for the two false-alarm variants.
# ---------------------------------------------------------------------------

_FE_VARIANT_MOTION_CONFIG: dict[str, dict[str, Any]] = {
    # peak_g_range — target accel-magnitude peak (g) the window is scaled to.
    # posture_deg_range — target posture_change_angle_deg metadata to inject.
    #   Only set when the soft-trigger evaluator should see it (≥45° for soft).
    # low_motion_s_range — target post_impact_low_motion_duration_s metadata.
    #   Only set when the soft trigger should also see low-motion ≥1.0s.
    "false_fall":       {"source_activity": "walking", "peak_g_range": (1.2, 1.8)},
    "slip_recovery":    {"source_activity": "walking", "peak_g_range": (1.5, 2.3)},
    "fall_brief":       {"source_activity": "fall",    "peak_g_range": (2.5, 2.95),
                         "posture_deg_range": (45, 55)},
    "fall_from_bed":    {"source_activity": "fall",    "peak_g_range": (2.6, 2.95),
                         "posture_deg_range": (50, 70),
                         "low_motion_s_range": (1.0, 1.8)},
    "confirmed":        {"source_activity": "fall",    "peak_g_range": (5.0, 7.0),
                         "posture_deg_range": (60, 85),
                         "low_motion_s_range": (1.5, 2.5)},
    "fall_no_response": {"source_activity": "fall",    "peak_g_range": (6.0, 9.0),
                         "posture_deg_range": (70, 90),
                         "low_motion_s_range": (2.0, 3.0)},
}

_G_TO_MS2: float = 9.80665


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
        return {
            "timestamp": baseline.get("timestamp"),
            "heart_rate": round(heart_rate, 2),
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
        return deepcopy(windows[self._rng.randrange(len(windows))])

    # Removed dead code: get_window_for_state (alias for generate, 0 callers)

    def inject_fall(self, variant: str) -> dict[str, Any] | None:
        """Return a motion window for the given fall variant.

        Module FA Phase 3 — adds variant-aware source selection.  FE
        variants in :data:`_FE_VARIANT_MOTION_CONFIG` pull from the
        configured `source_activity` bucket (e.g. `walking` for
        false-alarm variants) and get the accel arrays scaled into the
        target peak-g range so pre-trigger / AI verdict matches the
        operator's expectation.  Legacy `fall_1`..`fall_8` variants
        keep the original "highest-impact fall window" behaviour.
        """
        config = _FE_VARIANT_MOTION_CONFIG.get(variant)

        if config is None:
            # Legacy internal variant — preserve original behaviour.
            windows = self.registry.get_motion_windows(fall_variant=variant)
            if not windows:
                windows = self.registry.get_motion_windows(activity="fall")
            if not windows:
                event = self.registry.get_fall_event(variant)
                return {"event": event} if event else None
            return deepcopy(self._select_best_fall_window(windows))

        # FE variant — pick a baseline window from the configured source
        # activity and scale it to the target peak.
        source_activity = str(config["source_activity"])
        windows = self.registry.get_motion_windows(activity=source_activity)
        if not windows:
            # Fallback to any motion window so we never block the inject.
            windows = self.registry.get_motion_windows()
        if not windows:
            event = self.registry.get_fall_event(variant)
            return {"event": event} if event else None

        window = deepcopy(windows[self._rng.randrange(len(windows))])
        target_min, target_max = config["peak_g_range"]
        target_peak_g = self._rng.uniform(float(target_min), float(target_max))
        window = self._scale_window_to_peak_g(window, target_peak_g)
        # Phase 3 — inject posture / low-motion metadata so the BE
        # pre-trigger evaluator can fire the SOFT trigger paths
        # (IMPACT_PLUS_POSTURE_CHANGE / IMPACT_PLUS_LOW_MOTION) for the
        # warning-band variants.  Without this metadata the dataset
        # windows pulled from the `fall` activity bucket carry only the
        # accel/gyro arrays and pre-trigger sees `posture=None`,
        # `low_motion=None` -> only HARD can fire.
        posture_range = config.get("posture_deg_range")
        if posture_range is not None:
            window["posture_change_angle_deg"] = round(
                self._rng.uniform(float(posture_range[0]), float(posture_range[1])), 1
            )
        low_motion_range = config.get("low_motion_s_range")
        if low_motion_range is not None:
            window["post_impact_low_motion_duration_s"] = round(
                self._rng.uniform(float(low_motion_range[0]), float(low_motion_range[1])), 2
            )
        return window

    @staticmethod
    def _scale_window_to_peak_g(window: dict[str, Any], target_peak_g: float) -> dict[str, Any]:
        """Scale accel arrays so peak |a| equals ``target_peak_g`` g.

        Computes the current peak magnitude (m/s²) across the window
        accel components, derives a multiplicative factor, then applies
        it in-place to ``accel_x``/``accel_y``/``accel_z``.  Updates the
        ``accel_mag_peak_g`` metadata so downstream consumers
        (``_compute_pre_trigger_evidence``, ``_compute_accel_magnitude``)
        see the scaled value without re-deriving.

        Returns the same window dict (mutated) for caller convenience.
        Handles numpy arrays via the same coerce pattern used elsewhere.
        """
        ax = window.get("accel_x")
        ay = window.get("accel_y")
        az = window.get("accel_z")
        ax_list = list(ax) if ax is not None else []
        ay_list = list(ay) if ay is not None else []
        az_list = list(az) if az is not None else []
        n = min(len(ax_list), len(ay_list), len(az_list))
        if n == 0:
            return window
        peak_ms2 = 0.0
        for i in range(n):
            try:
                x = float(ax_list[i]); y = float(ay_list[i]); z = float(az_list[i])
            except (TypeError, ValueError):
                continue
            mag = math.sqrt(x * x + y * y + z * z)
            if mag > peak_ms2:
                peak_ms2 = mag
        if peak_ms2 <= 0:
            return window
        target_ms2 = float(target_peak_g) * _G_TO_MS2
        factor = target_ms2 / peak_ms2
        scaled_x = [float(ax_list[i]) * factor for i in range(n)]
        scaled_y = [float(ay_list[i]) * factor for i in range(n)]
        scaled_z = [float(az_list[i]) * factor for i in range(n)]
        window["accel_x"] = scaled_x
        window["accel_y"] = scaled_y
        window["accel_z"] = scaled_z
        # Persist scaled peak so pre-trigger evidence + AI client see the
        # correctly-scaled value without re-computing.
        window["accel_mag_peak_g"] = round(target_peak_g, 4)
        return window

    @staticmethod
    def _select_best_fall_window(windows: list[dict]) -> dict:
        """Return the window with the highest accel peak magnitude.

        Choosing the highest-impact window maximises the accel_peak_to_mean
        and accel_x_range features, which are strong positive SHAP contributors
        for fall detection. With env injection the model sees a full fall
        signature (large spike + floor contact) instead of low-amplitude drift.
        """
        def _peak_accel(window: dict) -> float:
            # Use explicit None checks — window arrays are numpy ndarrays from
            # the parquet pipeline; `arr or []` raises ValueError on ndarrays.
            ax_raw = window.get("accel_x")
            ay_raw = window.get("accel_y")
            az_raw = window.get("accel_z")
            ax = list(ax_raw) if ax_raw is not None else []
            ay = list(ay_raw) if ay_raw is not None else []
            az = list(az_raw) if az_raw is not None else []
            n = min(len(ax), len(ay), len(az))
            if n == 0:
                return 0.0
            return max(
                math.sqrt(float(ax[i]) ** 2 + float(ay[i]) ** 2 + float(az[i]) ** 2)
                for i in range(n)
            )
        return max(windows, key=_peak_accel)
