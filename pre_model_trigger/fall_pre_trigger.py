"""Fall pre-trigger detector (Stage 1 of the fall pipeline).

Evaluates motion data against the hard/soft trigger thresholds defined
in ``fall/fall_pipeline_wrist_config.json`` to decide whether the full
fall-detection model should be invoked.

Architecture reference: plans/alert-threshold-architecture-plan.md §5.1
Config reference: pre_model_trigger/fall/fall_pipeline_wrist_config.json
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from pre_model_trigger.settings_provider import SystemSettingsProvider
from pre_model_trigger.types import TriggerActionItem

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "fall" / "fall_pipeline_wrist_config.json"

# Default thresholds (from config stage_1_pretrigger)
_DEFAULT_HARD_ACCEL_G = 3.0
_DEFAULT_SOFT_ACCEL_G = 2.5
_DEFAULT_SOFT_POSTURE_DEG = 45.0
_DEFAULT_SOFT_LOW_MOTION_S = 1.0
_DEFAULT_GYRO_DPS = 250.0


def _load_fall_config() -> dict[str, Any]:
    """Load and parse the fall pipeline JSON config."""
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load fall config: %s — using defaults", exc)
        return {}


def _safe_float(value: Any) -> float | None:
    """Coerce *value* to float or return ``None``."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_accel_magnitude(accel: dict[str, Any]) -> float | None:
    """Compute acceleration magnitude from x/y/z components."""
    x = _safe_float(accel.get("x"))
    y = _safe_float(accel.get("y"))
    z = _safe_float(accel.get("z"))
    if x is None or y is None or z is None:
        return None
    return math.sqrt(x * x + y * y + z * z)


def _compute_gyro_magnitude(gyro: dict[str, Any]) -> float | None:
    """Compute gyroscope magnitude from x/y/z components."""
    x = _safe_float(gyro.get("x"))
    y = _safe_float(gyro.get("y"))
    z = _safe_float(gyro.get("z"))
    if x is None or y is None or z is None:
        return None
    return math.sqrt(x * x + y * y + z * z)


class FallPreTrigger:
    """Stage 1 fall pre-trigger evaluation.

    Checks motion sensor data against configurable thresholds to decide
    whether the full fall-detection model should run.  Produces
    ``TriggerActionItem`` entries when a fall pre-trigger fires.

    Parameters
    ----------
    settings_provider:
        Access to system settings (reserved for future threshold
        override from DB).

    Usage in ``dependencies.py``::

        fall_trigger = FallPreTrigger(settings_provider=settings_provider)
    """

    def __init__(self, *, settings_provider: SystemSettingsProvider) -> None:
        self._settings = settings_provider
        config = _load_fall_config()
        stage1 = config.get("stage_1_pretrigger", {})

        # Extract threshold values from config (fall back to defaults)
        self._hard_accel_g = _DEFAULT_HARD_ACCEL_G
        self._soft_accel_g = _DEFAULT_SOFT_ACCEL_G
        self._soft_posture_deg = _DEFAULT_SOFT_POSTURE_DEG
        self._soft_low_motion_s = _DEFAULT_SOFT_LOW_MOTION_S
        self._gyro_dps = _DEFAULT_GYRO_DPS

        # Parse hard triggers
        for trigger in stage1.get("hard_trigger_if_any", []):
            cond = trigger.get("condition", "")
            if "accel_mag_peak_g >= " in cond:
                val = _safe_float(cond.split(">= ")[-1].strip())
                if val is not None:
                    self._hard_accel_g = val

        # Parse soft triggers for threshold extraction
        for trigger in stage1.get("soft_trigger_if_any", []):
            cond = trigger.get("condition", "")
            if "gyro_mag_peak_dps >= " in cond:
                parts = cond.split("gyro_mag_peak_dps >= ")
                if len(parts) > 1:
                    val = _safe_float(parts[1].split()[0])
                    if val is not None:
                        self._gyro_dps = val

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, motion: dict[str, Any] | None) -> list[TriggerActionItem]:
        """Evaluate motion data for fall pre-trigger conditions.

        Parameters
        ----------
        motion:
            Motion sensor data from the current tick.  Expected keys:
            ``accel`` (with x/y/z), ``gyro`` (with x/y/z),
            ``posture_change_angle_deg``, ``post_impact_low_motion_duration_s``.

        Returns
        -------
        list[TriggerActionItem]
            Empty if no trigger fires; otherwise contains one or more
            fall-related actions.
        """
        if not motion:
            return []

        actions: list[TriggerActionItem] = []

        # Extract sensor values
        accel = motion.get("accel") or {}
        gyro = motion.get("gyro") or {}
        accel_mag = _compute_accel_magnitude(accel)
        gyro_mag = _compute_gyro_magnitude(gyro)
        posture_angle = _safe_float(motion.get("posture_change_angle_deg"))
        low_motion_dur = _safe_float(motion.get("post_impact_low_motion_duration_s"))

        # Also check for pre-computed peak values (from motion generator)
        accel_peak = _safe_float(motion.get("accel_mag_peak_g")) or accel_mag
        gyro_peak = _safe_float(motion.get("gyro_mag_peak_dps")) or gyro_mag

        # Hard trigger: high impact peak
        if accel_peak is not None and accel_peak >= self._hard_accel_g:
            actions.append(TriggerActionItem(
                action_type="alert",
                severity="URGENT",
                message=f"Fall pre-trigger (hard): accel peak {accel_peak:.1f}g >= {self._hard_accel_g}g",
                source="fall_pre_trigger",
                metadata={
                    "event_type": "fall_pre_trigger",
                    "trigger_type": "hard",
                    "accel_peak_g": str(round(accel_peak, 2)),
                },
                reason_codes=["IMPACT_PEAK_3G"],
            ))
            return actions  # Hard trigger is sufficient

        # Soft trigger: impact + posture change
        if (
            accel_peak is not None
            and accel_peak >= self._soft_accel_g
            and posture_angle is not None
            and posture_angle >= self._soft_posture_deg
        ):
            actions.append(TriggerActionItem(
                action_type="model_call",
                severity="SEND_TO_RISK_MODEL",
                message=(
                    f"Fall pre-trigger (soft): accel {accel_peak:.1f}g + "
                    f"posture change {posture_angle:.0f}°"
                ),
                source="fall_pre_trigger",
                metadata={
                    "event_type": "fall_pre_trigger",
                    "trigger_type": "soft",
                    "accel_peak_g": str(round(accel_peak, 2)),
                    "posture_angle_deg": str(round(posture_angle, 1)),
                },
                reason_codes=["IMPACT_PLUS_POSTURE_CHANGE"],
            ))
            return actions

        # Soft trigger: impact + post-impact low motion
        if (
            accel_peak is not None
            and accel_peak >= self._soft_accel_g
            and low_motion_dur is not None
            and low_motion_dur >= self._soft_low_motion_s
        ):
            actions.append(TriggerActionItem(
                action_type="model_call",
                severity="SEND_TO_RISK_MODEL",
                message=(
                    f"Fall pre-trigger (soft): accel {accel_peak:.1f}g + "
                    f"low motion {low_motion_dur:.1f}s"
                ),
                source="fall_pre_trigger",
                metadata={
                    "event_type": "fall_pre_trigger",
                    "trigger_type": "soft",
                    "accel_peak_g": str(round(accel_peak, 2)),
                    "low_motion_s": str(round(low_motion_dur, 2)),
                },
                reason_codes=["IMPACT_PLUS_LOW_MOTION"],
            ))
            return actions

        # Soft trigger: gyro + posture change
        if (
            gyro_peak is not None
            and gyro_peak >= self._gyro_dps
            and posture_angle is not None
            and posture_angle >= self._soft_posture_deg
        ):
            actions.append(TriggerActionItem(
                action_type="model_call",
                severity="SEND_TO_RISK_MODEL",
                message=(
                    f"Fall pre-trigger (soft): gyro {gyro_peak:.0f}dps + "
                    f"posture change {posture_angle:.0f}°"
                ),
                source="fall_pre_trigger",
                metadata={
                    "event_type": "fall_pre_trigger",
                    "trigger_type": "soft",
                    "gyro_peak_dps": str(round(gyro_peak, 1)),
                    "posture_angle_deg": str(round(posture_angle, 1)),
                },
                reason_codes=["GYRO_PLUS_POSTURE_CHANGE"],
            ))

        return actions


__all__ = ["FallPreTrigger"]
