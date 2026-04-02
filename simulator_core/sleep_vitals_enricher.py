"""Heuristic sleep vitals enrichment for scenario-based sleep summaries."""

from __future__ import annotations

import math
import random
from typing import Any

ScenarioProfile = dict[str, Any]


SLEEP_VITALS_PROFILES: dict[str, ScenarioProfile] = {
    "good_sleep_night": {
        "hr_mean": (59.0, 3.0, 45.0, 80.0),
        "hr_min_delta": (7.0, 2.0, 4.0, 15.0),
        "hr_max_delta": (12.0, 3.0, 8.0, 20.0),
        "hrv_rmssd_ms": (57.0, 8.0, 35.0, 80.0),
        "respiration_rate_bpm": (13.0, 0.8, 10.0, 18.0),
        "spo2_mean_pct": (98.0, 0.5, 94.0, 100.0),
        "spo2_dip": (1.5, 0.5, 0.5, 4.0),
        "movement_factor": 2.0,
        "snore_range": (0, 2),
        "ambient_noise_db": (30.0, 2.0, 22.0, 38.0),
        "room_temperature_c": (22.5, 0.5, 20.0, 25.0),
        "room_humidity_pct": (50.0, 4.0, 40.0, 60.0),
    },
    "fragmented_sleep": {
        "hr_mean": (70.0, 4.0, 52.0, 90.0),
        "hr_min_delta": (5.0, 1.5, 3.0, 10.0),
        "hr_max_delta": (16.0, 3.5, 10.0, 26.0),
        "hrv_rmssd_ms": (27.0, 6.0, 14.0, 45.0),
        "respiration_rate_bpm": (15.5, 1.2, 11.0, 20.0),
        "spo2_mean_pct": (95.5, 0.8, 92.0, 99.0),
        "spo2_dip": (2.5, 0.8, 1.0, 5.0),
        "movement_factor": 4.5,
        "snore_range": (4, 15),
        "ambient_noise_db": (34.0, 3.0, 26.0, 45.0),
        "room_temperature_c": (23.0, 0.7, 20.0, 26.0),
        "room_humidity_pct": (52.0, 5.0, 40.0, 65.0),
    },
    "sleep_apnea_mild": {
        "hr_mean": (73.0, 5.0, 55.0, 98.0),
        "hr_min_delta": (4.0, 1.5, 2.0, 8.0),
        "hr_max_delta": (18.0, 4.0, 10.0, 28.0),
        "hrv_rmssd_ms": (20.0, 4.0, 10.0, 32.0),
        "respiration_rate_bpm": (10.5, 1.5, 7.0, 17.0),
        "spo2_mean_pct": (94.5, 1.0, 89.0, 97.0),
        "spo2_dip": (4.5, 1.0, 2.0, 8.0),
        "movement_factor": 6.5,
        "snore_range": (18, 40),
        "ambient_noise_db": (36.0, 3.0, 28.0, 48.0),
        "room_temperature_c": (22.8, 0.7, 20.0, 26.0),
        "room_humidity_pct": (53.0, 5.0, 40.0, 68.0),
    },
    "sleep_apnea_severe": {
        "hr_mean": (78.0, 6.0, 60.0, 110.0),
        "hr_min_delta": (3.0, 1.2, 1.0, 6.0),
        "hr_max_delta": (22.0, 4.0, 12.0, 34.0),
        "hrv_rmssd_ms": (10.0, 3.0, 4.0, 25.0),
        "respiration_rate_bpm": (8.5, 2.0, 6.0, 16.0),
        "spo2_mean_pct": (90.5, 1.5, 84.0, 93.0),
        "spo2_dip": (7.0, 2.0, 4.0, 15.0),
        "movement_factor": 9.0,
        "snore_range": (50, 80),
        "ambient_noise_db": (39.0, 3.5, 30.0, 52.0),
        "room_temperature_c": (23.2, 0.8, 20.0, 27.0),
        "room_humidity_pct": (55.0, 6.0, 40.0, 70.0),
    },
}


def _gauss_clamp(mean: float, std: float, lo: float, hi: float) -> float:
    """Return a Gaussian sample clamped to the given range."""
    sample = random.gauss(mean, std)
    if math.isnan(sample) or math.isinf(sample):
        sample = mean
    return max(lo, min(hi, sample))


def _get_profile(scenario_id: str | None) -> ScenarioProfile:
    return SLEEP_VITALS_PROFILES.get(str(scenario_id or "").strip(), SLEEP_VITALS_PROFILES["fragmented_sleep"])


def _coerce_wake_count(summary: dict[str, Any] | None) -> int:
    value = (summary or {}).get("wake_count", 0)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _persona_env_value(persona_config: dict[str, Any] | None, key: str) -> Any:
    if not persona_config:
        return None
    if key in persona_config:
        return persona_config[key]
    sleep_env = persona_config.get("sleep_environment")
    if isinstance(sleep_env, dict):
        return sleep_env.get(key)
    environment = persona_config.get("environment")
    if isinstance(environment, dict):
        return environment.get(key)
    return None


def _resolve_env_metric(persona_config: dict[str, Any] | None, key: str, profile_range: tuple[float, float, float, float]) -> float:
    configured = _persona_env_value(persona_config, key)
    _, _, lo, hi = profile_range
    if configured is not None:
        try:
            return round(max(lo, min(hi, float(configured))), 1)
        except (TypeError, ValueError):
            pass
    return round(_gauss_clamp(*profile_range), 1)


def enrich_sleep_record(
    scenario_id: str,
    summary: dict[str, Any] | None,
    persona_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate the missing sleep vitals for a scenario-specific summary."""
    profile = _get_profile(scenario_id)
    wake_count = _coerce_wake_count(summary)

    heart_rate_mean = round(_gauss_clamp(*profile["hr_mean"]), 1)
    heart_rate_min_bpm = round(max(30.0, heart_rate_mean - _gauss_clamp(*profile["hr_min_delta"])), 1)
    heart_rate_max_bpm = round(max(heart_rate_mean, heart_rate_mean + _gauss_clamp(*profile["hr_max_delta"])), 1)

    spo2_mean_pct = round(_gauss_clamp(*profile["spo2_mean_pct"]), 1)
    spo2_min_pct = round(max(70.0, spo2_mean_pct - _gauss_clamp(*profile["spo2_dip"])), 1)

    movement_noise = random.gauss(0.0, 5.0)
    movement_count = max(5, int(wake_count * float(profile["movement_factor"]) + movement_noise))

    snore_lo, snore_hi = profile["snore_range"]

    return {
        "heart_rate_mean_bpm": heart_rate_mean,
        "heart_rate_min_bpm": heart_rate_min_bpm,
        "heart_rate_max_bpm": heart_rate_max_bpm,
        "hrv_rmssd_ms": round(_gauss_clamp(*profile["hrv_rmssd_ms"]), 1),
        "respiration_rate_bpm": round(_gauss_clamp(*profile["respiration_rate_bpm"]), 1),
        "spo2_mean_pct": spo2_mean_pct,
        "spo2_min_pct": spo2_min_pct,
        "movement_count": movement_count,
        "snore_events": random.randint(snore_lo, snore_hi),
        "ambient_noise_db": _resolve_env_metric(persona_config, "ambient_noise_db", profile["ambient_noise_db"]),
        "room_temperature_c": _resolve_env_metric(persona_config, "room_temperature_c", profile["room_temperature_c"]),
        "room_humidity_pct": _resolve_env_metric(persona_config, "room_humidity_pct", profile["room_humidity_pct"]),
    }
