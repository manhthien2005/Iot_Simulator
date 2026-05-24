"""TickPipeline — stateless simulation tick processing pipeline.

Does NOT import api_server/. AlertEvaluator injected via constructor.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from time import monotonic
from typing import Any

from simulator_core.alert_evaluator import AlertEvaluator, AlertSignal


@dataclass
class SleepPhaseSignal:
    device_id: str


@dataclass
class TickPipelineResult:
    enriched_outputs: list[dict[str, Any]]
    bufferable: list[dict[str, Any]]
    alert_signals: list[AlertSignal]
    sleep_phase_signals: list[SleepPhaseSignal]


class TickPipeline:
    """Stateless pipeline: raw tick outputs → TickPipelineResult.

    Stages:
    1. Scenario enrichment (synthetic override or replay annotation)
    2. Alert evaluation (pure threshold check)
    3. Sleep phase signal detection
    """

    def __init__(self, alert_evaluator: AlertEvaluator) -> None:
        self._alert_evaluator = alert_evaluator

    def process(
        self,
        raw_outputs: list[dict[str, Any]],
        *,
        device_map: dict[str, Any],
        scenario_map: dict[str, str],
        source_modes: dict[str, str],
    ) -> TickPipelineResult:
        enriched: list[dict[str, Any]] = []
        bufferable: list[dict[str, Any]] = []
        alert_signals: list[AlertSignal] = []
        sleep_signals: list[SleepPhaseSignal] = []

        for payload in raw_outputs:
            device_id = str(payload.get("device_id") or "")
            scenario_id = scenario_map.get(device_id, "normal_rest")
            source_mode = str(source_modes.get(device_id, "synthetic") or "synthetic").strip().lower()

            if source_mode == "replay":
                annotate_scenario_replay(payload, scenario_id)
            else:
                apply_scenario_overrides(payload, scenario_id)

            enriched.append(payload)

            # Only bound devices (db_device_id present) go to buffer
            device = device_map.get(device_id)
            if device is not None and getattr(device, "bound_db_device_id", None) is not None:
                payload["db_device_id"] = device.bound_db_device_id
                bufferable.append(payload)

            # Alert evaluation
            vitals = payload.get("vitals") or {}
            state = payload.get("state") or {}
            activity_state = str(state.get("activity_state") or "")
            is_sleeping = activity_state == "sleeping"

            signals = self._alert_evaluator.evaluate(
                vitals,
                device_id=device_id,
                scenario_id=scenario_id,
                is_sleeping=is_sleeping,
                activity_state=activity_state,
            )
            alert_signals.extend(signals)

            # Sleep phase signal
            if is_sleeping:
                sleep_signals.append(SleepPhaseSignal(device_id=device_id))

        return TickPipelineResult(
            enriched_outputs=enriched,
            bufferable=bufferable,
            alert_signals=alert_signals,
            sleep_phase_signals=sleep_signals,
        )


# ── Scenario enrichment helpers (moved from SimulatorRuntime) ─────────────

def scenario_state_hint(scenario_id: str) -> str:
    if scenario_id in {"hypoxia_critical", "high_risk_cardiac", "fall_no_response", "sleep_apnea_severe"}:
        return "critical"
    if scenario_id in {
        "tachycardia_warning", "hypertension_moderate", "fragmented_sleep",
        "medium_risk_general", "fall_false_alarm",
        "sleep_apnea_mild", "insomnia_pattern",
    }:
        return "warning"
    if scenario_id == "fall_high_confidence":
        return "fall_countdown"
    return "streaming"


def annotate_scenario_replay(payload: dict[str, Any], scenario_id: str) -> None:
    """Replay mode: annotate context without rewriting real vitals."""
    annotation = payload.get("scenario_annotation")
    if not isinstance(annotation, dict):
        annotation = {}
        payload["scenario_annotation"] = annotation
    annotation["scenario_id"] = scenario_id
    annotation["overlay_blocked"] = True
    annotation["state_hint"] = scenario_state_hint(scenario_id)
    if scenario_id.startswith("fall_"):
        annotation["event_hint"] = "fall_detected"


def apply_scenario_overrides(payload: dict[str, Any], scenario_id: str) -> None:
    """Synthetic mode: rewrite vitals to match scenario profile + persona adjustments."""
    vitals = payload.get("vitals") or {}
    emitted_at = str(payload.get("emitted_at") or datetime.utcnow().isoformat())
    try:
        phase = datetime.fromisoformat(emitted_at).timestamp()
    except ValueError:
        phase = monotonic()

    device_id_str = str(payload.get("device_id") or "")
    device_offset = float(hash(device_id_str) % 97)

    def wave(scale: float, shift: float = 0.0) -> float:
        return (math.sin((phase + shift + device_offset) / 9.0) * scale
                + math.cos((phase + shift + device_offset) / 13.0) * (scale * 0.4))

    def clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    profiles: dict[str, tuple[float, ...]] = {
        "normal_rest":           (65.0, 4.0, 97.5, 0.7, 36.6, 0.15, 115.0, 75.0, 5.0, 3.5, 15.0),
        "tachycardia_warning":   (108.0, 7.0, 96.0, 0.8, 37.1, 0.20, 130.0, 84.0, 6.5, 4.5, 20.0),
        "hypoxia_critical":      (118.0, 10.0, 88.0, 1.5, 37.5, 0.25, 148.0, 94.0, 9.0, 6.0, 26.0),
        "hypertension_moderate": (80.0, 5.5, 96.5, 0.7, 37.0, 0.18, 138.0, 100.0, 8.0, 5.5, 16.0),
        "good_sleep_night":      (55.0, 3.0, 96.5, 1.0, 36.3, 0.15, 105.0, 65.0, 4.0, 3.0, 13.0),
        "fragmented_sleep":      (76.0, 7.0, 93.0, 1.5, 36.8, 0.22, 126.0, 82.0, 7.5, 5.0, 17.0),
        "high_risk_cardiac":     (128.0, 12.0, 91.0, 1.8, 38.0, 0.30, 165.0, 104.0, 12.0, 8.0, 24.0),
        "medium_risk_general":   (94.0, 7.0, 94.5, 1.0, 37.3, 0.22, 142.0, 90.0, 8.5, 5.5, 18.0),
        "normal_walking":        (88.0, 5.0, 97.0, 0.5, 37.1, 0.15, 126.0, 82.0, 6.0, 4.0, 18.0),
        "elderly_normal":        (60.0, 4.0, 96.0, 0.8, 36.4, 0.15, 118.0, 75.0, 5.0, 3.5, 14.0),
    }
    (hr_base, hr_amp, spo2_base, spo2_amp, temp_base, temp_amp,
     bp_sys_base, bp_dia_base, bp_sys_amp, bp_dia_amp, rr_base) = profiles.get(
        scenario_id, profiles["normal_rest"]
    )

    heart_rate = clamp(hr_base + wave(hr_amp, 0.0), 40, 190)
    spo2 = clamp(spo2_base + wave(spo2_amp, 3.0), 78, 100)
    temperature = clamp(temp_base + wave(temp_amp, 7.0), 34.5, 41.5)
    blood_pressure_sys = clamp(bp_sys_base + wave(bp_sys_amp, 11.0), 85, 225)
    blood_pressure_dia = clamp(bp_dia_base + wave(bp_dia_amp, 15.0), 50, 140)
    respiratory_rate = clamp(rr_base + wave(1.5, 5.0), 4.0, 35.0)

    _fall_activity = str((payload.get("state") or {}).get("activity_state") or "")
    _fall_variant  = str((payload.get("state") or {}).get("fall_variant") or "fall_generic")

    if _fall_activity == "fall":
        if _fall_variant == "fall_no_response":
            heart_rate         = clamp(heart_rate - 10.0, 40, 220)
            spo2               = clamp(spo2 - 14.0, 78, 100)
            blood_pressure_sys = clamp(blood_pressure_sys - 22.0, 85, 225)
            blood_pressure_dia = clamp(blood_pressure_dia - 12.0, 50, 140)
            respiratory_rate   = clamp(respiratory_rate - 8.0, 4, 35)
        elif _fall_variant == "fall_brief":
            heart_rate         = clamp(heart_rate + 15.0, 40, 220)
            spo2               = clamp(spo2 - 2.0, 78, 100)
            blood_pressure_sys = clamp(blood_pressure_sys + 8.0, 85, 225)
        else:
            heart_rate         = clamp(heart_rate + 32.0, 40, 220)
            spo2               = clamp(spo2 - 6.0, 78, 100)
            blood_pressure_sys = clamp(blood_pressure_sys + 22.0, 85, 225)
    elif _fall_activity == "recovery":
        heart_rate         = clamp(heart_rate + 15.0, 40, 220)
        spo2               = clamp(spo2 - 3.0, 78, 100)
        blood_pressure_sys = clamp(blood_pressure_sys + 10.0, 85, 225)

    _stress = str((payload.get("state") or {}).get("stress_state") or "")
    if _stress == "stress":
        heart_rate         = clamp(heart_rate + 12.0, 40, 220)
        blood_pressure_sys = clamp(blood_pressure_sys + 10.0, 85, 225)
        blood_pressure_dia = clamp(blood_pressure_dia + 7.0, 50, 140)

    _pcfg = payload.get("persona_config") or {}
    _age  = float(_pcfg.get("age", 70.0))
    _wkg  = float(_pcfg.get("weight_kg", 65.0))
    _hm   = float(_pcfg.get("height_cm", 165.0)) / 100.0
    _bmi  = max(10.0, min(70.0, _wkg / (_hm ** 2) if _hm > 0 else 22.0))

    _hr_age   = max(0.0, (_age - 40.0)) * 0.25
    _spo2_age = -(max(0.0, _age - 50.0) * 0.03)
    _sys_age  = max(0.0, (_age - 30.0)) * 0.6
    _dia_age  = (min(_age, 55.0) - 30.0) * 0.3 - max(0.0, _age - 55.0) * 0.2
    _tmp_age  = -(max(0.0, _age - 40.0) * 0.01)
    _rr_age   = max(0.0, (_age - 50.0) * 0.1)

    if _bmi > 25.0:
        _ex = _bmi - 25.0
        _hr_bmi, _sys_bmi, _dia_bmi = _ex * 0.5, _ex * 1.0, _ex * 0.6
        _spo2_bmi, _tmp_bmi = -(_ex * 0.08), _ex * 0.015
    elif _bmi < 18.5:
        _df = 18.5 - _bmi
        _hr_bmi, _sys_bmi, _dia_bmi = _df * 0.4, -(_df * 0.7), -(_df * 0.4)
        _spo2_bmi, _tmp_bmi = 0.0, -(_df * 0.01)
    else:
        _hr_bmi = _sys_bmi = _dia_bmi = _spo2_bmi = _tmp_bmi = 0.0

    heart_rate         = clamp(heart_rate + _hr_age + _hr_bmi,           40, 220)
    spo2               = clamp(spo2 + _spo2_age + _spo2_bmi,             78, 100)
    temperature        = clamp(temperature + _tmp_age + _tmp_bmi,        34.5, 41.5)
    blood_pressure_sys = clamp(blood_pressure_sys + _sys_age + _sys_bmi, 85, 225)
    blood_pressure_dia = clamp(blood_pressure_dia + _dia_age + _dia_bmi, 50, 140)
    respiratory_rate   = clamp(respiratory_rate + _rr_age,               4, 35)

    if spo2 < 95.0:
        respiratory_rate = clamp(respiratory_rate + (95.0 - spo2) * 0.5, 4, 35)

    if temperature > 37.5:
        heart_rate = clamp(heart_rate + (temperature - 37.5) * 10.0, 40, 220)

    vitals["heart_rate"]         = round(heart_rate, 2)
    vitals["spo2"]               = round(spo2, 2)
    vitals["temperature"]        = round(temperature, 2)
    vitals["blood_pressure_sys"] = round(blood_pressure_sys, 2)
    vitals["blood_pressure_dia"] = round(blood_pressure_dia, 2)
    vitals["respiratory_rate"]   = round(respiratory_rate, 1)
    payload["vitals"] = vitals
