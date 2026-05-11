"""Vitals normalization for the pre-model rule engine.

Translates the simulator's native payload field names to the canonical
names expected by ``rules_config.json`` / ``RuleEngine``, computes
derived metrics (pulse_pressure, map_val), and validates data quality.

Fix #1  — field name mismatch (respiratory_rate→resp_rate, etc.)
Fix #2  — derived metrics pulse_pressure / map_val now computed here
Fix #3  — data quality validation enforced before rule evaluation
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Post-normalization field names required for rule evaluation.
_REQUIRED_FIELDS: tuple[str, ...] = (
    "heart_rate",
    "spo2",
    "body_temp",
    "sys_bp",
    "dia_bp",
    "resp_rate",
)

_MINIMUM_SIGNAL_QUALITY_SCORE: float = 0.7


def normalize_vitals_for_rules(vitals: dict[str, Any]) -> dict[str, Any]:
    """Map simulator payload field names to rule-engine canonical names.

    Simulator sends:  ``respiratory_rate``, ``temperature``,
    ``blood_pressure_sys``, ``blood_pressure_dia``, ``activity_label``.

    Rule engine expects: ``resp_rate``, ``body_temp``,
    ``sys_bp``, ``dia_bp``, ``activity_level``.

    Also computes ``pulse_pressure`` and ``map_val`` when BP data is present.

    Parameters
    ----------
    vitals:
        Raw vitals dict from simulator payload (``payload["vitals"]``).

    Returns
    -------
    dict
        Normalized vitals dict ready to be passed to ``RuleEngine.evaluate()``.
    """
    sys_bp_raw = vitals.get("blood_pressure_sys") if vitals.get("blood_pressure_sys") is not None \
        else vitals.get("sys_bp")
    dia_bp_raw = vitals.get("blood_pressure_dia") if vitals.get("blood_pressure_dia") is not None \
        else vitals.get("dia_bp")

    normalized: dict[str, Any] = {
        "heart_rate": vitals.get("heart_rate"),
        "spo2": vitals.get("spo2"),
        "hrv": vitals.get("hrv"),
        "body_temp": vitals.get("temperature") if vitals.get("temperature") is not None
                     else vitals.get("body_temp"),
        "sys_bp": sys_bp_raw,
        "dia_bp": dia_bp_raw,
        "resp_rate": vitals.get("respiratory_rate") if vitals.get("respiratory_rate") is not None
                     else vitals.get("resp_rate"),
        "activity_level": vitals.get("activity_label") or vitals.get("activity_level"),
        "signal_quality_score": vitals.get("signal_quality_score"),
        "sensor_error_flag": vitals.get("sensor_error_flag"),
        "spo2_source": vitals.get("spo2_source"),
        "rr_source": vitals.get("rr_source"),
        "stress_data_source": vitals.get("stress_data_source"),
        "scenario_id": vitals.get("scenario_id"),
        "timestamp": vitals.get("timestamp") or vitals.get("sim_time"),
    }

    try:
        if sys_bp_raw is not None and dia_bp_raw is not None:
            sys_f = float(sys_bp_raw)
            dia_f = float(dia_bp_raw)
            normalized["pulse_pressure"] = round(sys_f - dia_f, 2)
            normalized["map_val"] = round(dia_f + (sys_f - dia_f) / 3.0, 2)
    except (TypeError, ValueError):
        logger.warning(
            "Cannot compute derived BP metrics: sys=%s dia=%s",
            sys_bp_raw,
            dia_bp_raw,
        )

    return normalized


def validate_data_quality(
    vitals: dict[str, Any],
    *,
    minimum_signal_quality: float = _MINIMUM_SIGNAL_QUALITY_SCORE,
) -> tuple[bool, list[str]]:
    """Validate data quality of a normalized vitals snapshot.

    Checks:
    - All required fields are present and non-None.
    - Required fields are numeric.
    - ``signal_quality_score`` >= ``minimum_signal_quality`` (default 0.7).
    - ``sensor_error_flag`` is not ``True``.

    Parameters
    ----------
    vitals:
        Normalized vitals dict (output of :func:`normalize_vitals_for_rules`).
    minimum_signal_quality:
        Minimum acceptable signal quality score.

    Returns
    -------
    (is_valid, errors)
        ``is_valid`` is ``True`` when no quality issues found.
        ``errors`` lists each specific issue detected.
    """
    errors: list[str] = []

    for field in _REQUIRED_FIELDS:
        if vitals.get(field) is None:
            errors.append(f"missing_required_field:{field}")

    for field in _REQUIRED_FIELDS:
        value = vitals.get(field)
        if value is not None:
            try:
                float(value)
            except (TypeError, ValueError):
                errors.append(f"non_numeric_value:{field}")

    sq = vitals.get("signal_quality_score")
    if sq is not None:
        try:
            if float(sq) < minimum_signal_quality:
                errors.append("signal_quality_score_below_threshold")
        except (TypeError, ValueError):
            errors.append("non_numeric_value:signal_quality_score")

    if vitals.get("sensor_error_flag") is True:
        errors.append("sensor_error_flag")

    return len(errors) == 0, errors


__all__ = ["normalize_vitals_for_rules", "validate_data_quality"]
