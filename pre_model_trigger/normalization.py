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

# Post-normalization field names. Split into "critical" vs "soft" so a
# tick missing only soft fields (BP/temp/RR — many wearables omit these)
# does not silently suppress URGENT instant rules on the critical ones.
#
# P0-5 (2026-05-18): previously every required field was treated equally,
# which meant a HR=200 / SpO2=85 emergency was ignored just because the
# device did not report a respiratory rate that tick.
_CRITICAL_FIELDS: tuple[str, ...] = (
    "heart_rate",
    "spo2",
)
_SOFT_FIELDS: tuple[str, ...] = (
    "body_temp",
    "sys_bp",
    "dia_bp",
    "resp_rate",
)
# Backwards-compatible alias still used by external callers / tests.
_REQUIRED_FIELDS: tuple[str, ...] = _CRITICAL_FIELDS + _SOFT_FIELDS

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
    - Critical fields (heart_rate, spo2) MUST be present and non-None.
      Without at least one of them the tick is unsafe to evaluate.
    - Soft fields (body_temp, sys_bp, dia_bp, resp_rate) MAY be missing —
      :func:`available_metrics` reports the subset that survived for the
      orchestrator's per-metric rule gating.
    - Required-but-present fields must be numeric.
    - ``signal_quality_score`` >= ``minimum_signal_quality`` (default 0.7).
    - ``sensor_error_flag`` is not ``True``.

    P0-5 (2026-05-18): previously a single missing soft field (e.g.
    ``resp_rate``) suppressed the entire vitals rule pass, including
    URGENT instant rules on the critical fields that were present. The
    new contract treats only ``heart_rate`` + ``spo2`` as fatal because
    the canonical clinical-rules ingest at the BE
    (``/telemetry/ingest`` ``INSUFFICIENT_VITALS`` gate) already
    requires at least one of those two.

    Parameters
    ----------
    vitals:
        Normalized vitals dict (output of :func:`normalize_vitals_for_rules`).
    minimum_signal_quality:
        Minimum acceptable signal quality score.

    Returns
    -------
    (is_valid, errors)
        ``is_valid`` is ``True`` when no critical issues were found —
        soft-field absences are reported in :func:`available_metrics`
        rather than blocking evaluation here.
        ``errors`` lists each specific issue detected.
    """
    errors: list[str] = []

    # Hard gate — at least one critical field MUST be present.
    critical_present = [f for f in _CRITICAL_FIELDS if vitals.get(f) is not None]
    if not critical_present:
        for field in _CRITICAL_FIELDS:
            errors.append(f"missing_critical_field:{field}")

    # Soft-field absences logged but do not flip ``is_valid``. The
    # orchestrator decides per-metric whether to evaluate the rule.
    for field in _SOFT_FIELDS:
        if vitals.get(field) is None:
            errors.append(f"missing_soft_field:{field}")

    for field in _REQUIRED_FIELDS:
        value = vitals.get(field)
        if value is not None:
            try:
                float(value)
            except (TypeError, ValueError):
                errors.append(f"non_numeric_value:{field}")

    # Try both signal_quality and signal_quality_score (A2 alignment with
    # /telemetry/ingest VitalIngestVitals which uses signal_quality).
    sq = vitals.get("signal_quality_score")
    if sq is None:
        sq = vitals.get("signal_quality")
    if sq is not None:
        try:
            if float(sq) < minimum_signal_quality:
                errors.append("signal_quality_score_below_threshold")
        except (TypeError, ValueError):
            errors.append("non_numeric_value:signal_quality_score")

    if vitals.get("sensor_error_flag") is True:
        errors.append("sensor_error_flag")

    # Hard-fatal subset that should suppress evaluation entirely.
    fatal = [
        e
        for e in errors
        if e.startswith("missing_critical_field:")
        or e.startswith("non_numeric_value:")
        or e == "sensor_error_flag"
        or e == "signal_quality_score_below_threshold"
    ]
    return len(fatal) == 0, errors


def available_metrics(vitals: dict[str, Any]) -> set[str]:
    """Return the subset of ``_REQUIRED_FIELDS`` present + numeric.

    P0-5: the orchestrator uses this to gate which rule sections fire
    on a given tick — a missing ``resp_rate`` no longer suppresses
    URGENT heart_rate / spo2 rules.
    """
    out: set[str] = set()
    for field in _REQUIRED_FIELDS:
        value = vitals.get(field)
        if value is None:
            continue
        try:
            float(value)
        except (TypeError, ValueError):
            continue
        out.add(field)
    return out


__all__ = [
    "available_metrics",
    "normalize_vitals_for_rules",
    "validate_data_quality",
]
