"""HTTP client for the local Fall Detection AI inference API.

This client targets **port 8001** (``healthguard-model-api``) for AI-based
fall detection: posting a 50+ sample IMU window and receiving a
probability + risk-band + SHAP explanation.

Mirrors :mod:`simulator_core.sleep_ai_client` design (stdlib-only, simple
circuit breaker) so the operational surface is uniform across the two AI
families the simulator integrates with.

Architecture context
--------------------
- Port 8001 → AI inference (this client)    : POST /api/v1/fall/predict
- Port 8000 → HealthGuard backend (alerts) : POST /api/v1/mobile/telemetry/alert

The fall AI verdict is consumed by ``api_server.dependencies.SimulatorRuntime``
during :meth:`SimulatorRuntime.inject_event` so the UI can render an AI
verdict the moment the operator triggers a fall variant — instead of
deferring everything to the backend rule engine.

Input payload contract (must match ``healthguard-model-api`` spec):
  {
    "device_id": str,
    "sampling_rate": int,       # default 50
    "window_size":   int,       # default 50
    "data": [SensorSample, ...] # length >= 50
  }
SensorSample = {
    "timestamp": int,
    "accel": {"x", "y", "z"},
    "gyro":  {"x", "y", "z"},
    "orientation": {"pitch", "roll", "yaw"},
    "environment": {"floor_vibration", "room_occupancy", "pressure_mat"}
}
Response contract (relevant subset):
  {
    "results": [{
      "device_id": str,
      "predicted_fall_probability": float,
      "predicted_fall": bool,
      "risk_level": "normal" | "warning" | "critical",
      "requires_attention": bool,
      "high_priority_alert": bool,
      "prediction": {
        "prediction_label": "normal" | "possible_fall" | "likely_fall" | "critical_fall",
        "prediction_score": float,
        "confidence": float
      },
      "top_features": [{"name": str, "contribution": float, "reason": str}, ...],
      "explanation": {"summary": str, "tags": [str]}
    }],
    "total": int
  }
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-variant context — controls whether environment signals are injected.
#
# Real falls (high-confidence / no-response) should have floor_vibration=1.0
# and pressure_mat=1.0 from the impact sample onwards — mirroring the binary
# pattern in training data (fall_detection.csv).
#
# False alarm (fall_brief) simulates a sudden jerk with quick recovery:
# the person does NOT hit the floor so env stays 0.0, which correctly keeps
# the model probability low (~20-35%).
# ---------------------------------------------------------------------------

FALL_VARIANT_CONTEXT: dict[str, dict] = {
    # Numeric internal variants (legacy fall scenarios)
    "fall_1":           {"inject_environment": True},
    "fall_2":           {"inject_environment": True},
    "fall_3":           {"inject_environment": True},
    "fall_4":           {"inject_environment": True},
    "fall_5":           {"inject_environment": True},
    "fall_6":           {"inject_environment": True},
    "fall_7":           {"inject_environment": True},
    "fall_8":           {"inject_environment": True},
    # FE-injectable variants (Module FA Fall Lab redesign)
    # P0-3 (2026-05-18): added so the simulator runtime injects environment
    # signals (or NOT, for false-alarm cases) consistent with each variant's
    # clinical intent. Previously these variants fell through to the default
    # fallback ``{"inject_environment": True}`` which made even ``false_fall``
    # / ``slip_recovery`` smell like a real impact, biasing the AI toward a
    # false positive.
    "false_fall":       {"inject_environment": False},
    "slip_recovery":    {"inject_environment": False},
    "fall_brief":       {"inject_environment": False},
    "fall_from_bed":    {"inject_environment": True},
    "confirmed":        {"inject_environment": True},
    "fall_no_response": {"inject_environment": True},
}

#: P0-3: fail-safe default for unknown variants. We previously defaulted to
#: ``inject_environment=True`` which caused unknown variants to look like
#: real falls; defaulting to ``False`` keeps unknown injects honest — if the
#: window genuinely had floor contact the accelerometer signal speaks for
#: itself, no need to fabricate environment cues.
FALL_VARIANT_DEFAULT_CONTEXT: dict = {"inject_environment": False}

#: How many samples the model-api requires. Mirrors
#: ``healthguard-model-api/app/config.py::fall_min_sequence_samples``.
MIN_WINDOW_SAMPLES: int = 50

#: Default IMU sample rate the simulator emits at.
DEFAULT_SAMPLING_RATE_HZ: int = 50


# ---------------------------------------------------------------------------
# Helpers — array-form motion window  →  SensorSample list
# ---------------------------------------------------------------------------


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _derive_orientation(ax: float, ay: float, az: float) -> tuple[float, float, float]:
    """Approximate ``(pitch, roll, yaw)`` in DEGREES from the gravity vector.

    The simulator's IMU has no magnetometer so yaw stays at ``0.0``.
    Pitch / roll come from the accelerometer's apparent gravity direction.

    P0-2 (2026-05-18): the values returned MUST be in degrees because the
    model-api ``OrientationData`` schema declares ``pitch/roll: ge=-180,
    le=180`` and the training distribution was extracted with degree-scale
    features. ``math.atan2`` returns radians (~-π..π) which validate
    successfully against the schema bound (3.14 < 180) but compress the
    feature scale ~57x, biasing ``orientation_dispersion`` toward zero
    and dragging fall probabilities down systematically.
    """
    pitch_rad = math.atan2(-ax, math.sqrt(ay * ay + az * az))
    roll_rad = math.atan2(ay, az)
    return math.degrees(pitch_rad), math.degrees(roll_rad), 0.0


def _derive_env_from_accel_peak(
    accel_x: list[Any],
    accel_y: list[Any],
    accel_z: list[Any],
    n: int,
) -> list[tuple[float, float]]:
    """Return per-sample (floor_vibration, pressure_mat) derived from accel peak.

    Mirrors the binary pattern in training data (fall_detection.csv):
    - Samples BEFORE peak index : (0.0, 0.0) — pre-fall, no floor contact
    - Samples FROM peak onwards : (1.0, 1.0) — impact + post-fall on floor

    This gives realistic statistical means for the 50-sample window:
    ``floor_vibration_mean ≈ 0.6–0.7``, matching what the model expects.
    """
    mags = [
        math.sqrt(
            _safe_float(accel_x[i]) ** 2
            + _safe_float(accel_y[i]) ** 2
            + _safe_float(accel_z[i]) ** 2
        )
        for i in range(n)
    ]
    peak_idx = mags.index(max(mags)) if mags else 0
    return [
        (1.0, 1.0) if i >= peak_idx else (0.0, 0.0)
        for i in range(n)
    ]


def motion_window_to_samples(
    motion: dict[str, Any] | None,
    *,
    sampling_rate_hz: int = DEFAULT_SAMPLING_RATE_HZ,
    fall_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Convert a simulator ``motion`` window (column-arrays) → model API samples.

    The simulator's :class:`simulator_core.generators.MotionGenerator`
    returns the column-array shape (``accel_x: [N], accel_y: [N], …``)
    extracted from the parquet windows. The model API instead expects a
    list of per-timestep dicts with nested ``accel/gyro/orientation/
    environment`` blocks (one per sample). This helper performs that
    transformation in a single pass.

    ``fall_context`` controls environment-signal injection:
    - ``{"inject_environment": True}``  → derive floor_vibration / pressure_mat
      from the accel-peak index (mirrors training-data binary pattern).
    - ``{"inject_environment": False}`` → keep 0.0 (false-alarm scenario).
    - ``None``                           → keep 0.0 (backwards-compatible default).

    Returns an empty list when motion is ``None`` or has no usable arrays;
    callers must check ``len(samples) >= MIN_WINDOW_SAMPLES`` before
    submitting to the AI.
    """
    if not motion:
        return []
    # NOTE: motion arrays may be numpy ndarrays (from MotionGenerator's
    # parquet-backed pipeline) so we MUST avoid `arr or []` and `not arr`
    # which both trigger ``ValueError: truth value of an array is
    # ambiguous`` on numpy arrays.  Use explicit None checks + len().
    def _coerce(value: Any) -> list[Any]:
        if value is None:
            return []
        try:
            return list(value)
        except TypeError:
            return []

    accel_x = _coerce(motion.get("accel_x"))
    accel_y = _coerce(motion.get("accel_y"))
    accel_z = _coerce(motion.get("accel_z"))
    gyro_x = _coerce(motion.get("gyro_x"))
    gyro_y = _coerce(motion.get("gyro_y"))
    gyro_z = _coerce(motion.get("gyro_z"))
    if len(accel_x) == 0 or len(accel_y) == 0 or len(accel_z) == 0:
        return []
    n = min(len(accel_x), len(accel_y), len(accel_z))
    if len(gyro_x) > 0 and len(gyro_y) > 0 and len(gyro_z) > 0:
        n = min(n, len(gyro_x), len(gyro_y), len(gyro_z))
    if n == 0:
        return []
    interval_ms = round(1000 / max(sampling_rate_hz, 1))

    inject_env = bool((fall_context or {}).get("inject_environment", False))
    env_values: list[tuple[float, float]] = (
        _derive_env_from_accel_peak(accel_x, accel_y, accel_z, n)
        if inject_env
        else [(0.0, 0.0)] * n
    )

    samples: list[dict[str, Any]] = []
    for i in range(n):
        ax = _safe_float(accel_x[i])
        ay = _safe_float(accel_y[i])
        az = _safe_float(accel_z[i])
        gx = _safe_float(gyro_x[i]) if i < len(gyro_x) else 0.0
        gy = _safe_float(gyro_y[i]) if i < len(gyro_y) else 0.0
        gz = _safe_float(gyro_z[i]) if i < len(gyro_z) else 0.0
        pitch, roll, yaw = _derive_orientation(ax, ay, az)
        floor_vib, pressure = env_values[i]
        samples.append(
            {
                "timestamp": i * interval_ms,
                "accel": {"x": ax, "y": ay, "z": az},
                "gyro": {"x": gx, "y": gy, "z": gz},
                "orientation": {"pitch": pitch, "roll": roll, "yaw": yaw},
                "environment": {
                    "floor_vibration": floor_vib,
                    "room_occupancy": 0.0,
                    "pressure_mat": pressure,
                },
            }
        )
    return samples


__all__ = [
    "DEFAULT_SAMPLING_RATE_HZ",
    "FALL_VARIANT_CONTEXT",
    "FALL_VARIANT_DEFAULT_CONTEXT",
    "MIN_WINDOW_SAMPLES",
    "motion_window_to_samples",
]
