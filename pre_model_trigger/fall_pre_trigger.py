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
import re
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

# P1-13: regex for extracting "<metric> <op> <value>" tokens out of
# rule-config conditions. Tolerates surrounding whitespace, optional
# trailing units (``g``, ``°``, ``s``), and connectors like ``and``.
_THRESHOLD_RE = re.compile(
    r"(?P<metric>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?P<op>>=|<=|>|<|==)\s*"
    r"(?P<value>-?\d+(?:\.\d+)?)"
)


def _extract_threshold(condition: str, metric: str) -> float | None:
    """Pull the numeric threshold for ``metric`` out of ``condition``.

    Returns ``None`` if the metric token is absent — caller should keep
    the built-in default. Robust to formatting drift in the JSON config
    (no-space ops, trailing units, multi-clause ``and`` expressions).
    """
    for match in _THRESHOLD_RE.finditer(condition or ""):
        if match.group("metric") == metric:
            try:
                return float(match.group("value"))
            except (TypeError, ValueError):
                return None
    return None


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

        # Parse hard triggers — P1-13: regex-based extraction.
        for trigger in stage1.get("hard_trigger_if_any", []):
            cond = trigger.get("condition", "")
            val = _extract_threshold(cond, "accel_mag_peak_g")
            if val is not None:
                self._hard_accel_g = val

        # Parse soft triggers — P1-13: regex-based extraction handles
        # multi-clause conditions like
        # ``"accel_mag_peak_g >= 2.5 AND posture_change_angle_deg >= 45"``.
        for trigger in stage1.get("soft_trigger_if_any", []):
            cond = trigger.get("condition", "")
            gyro_val = _extract_threshold(cond, "gyro_mag_peak_dps")
            if gyro_val is not None:
                self._gyro_dps = gyro_val
            posture_val = _extract_threshold(cond, "posture_change_angle_deg")
            if posture_val is not None:
                self._soft_posture_deg = posture_val
            low_motion_val = _extract_threshold(
                cond, "post_impact_low_motion_duration_s"
            )
            if low_motion_val is not None:
                self._soft_low_motion_s = low_motion_val
            soft_accel_val = _extract_threshold(cond, "accel_mag_peak_g")
            if soft_accel_val is not None and soft_accel_val < self._hard_accel_g:
                # Only treat it as the SOFT threshold when distinct from
                # hard. Avoids overwriting if the same condition string
                # was reused for both severity buckets.
                self._soft_accel_g = soft_accel_val

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


    def evaluate_with_evidence(self, motion: dict[str, Any] | None) -> dict[str, Any]:
        """Evaluate motion + return structured evidence for the Fall Lab UI.

        Companion to :meth:`evaluate` that returns the actual numeric
        signals + reason codes the operator sees in the AI Pipeline strip
        (Section B), instead of just the abstract ``TriggerActionItem``
        list the orchestrator routes on.

        Output shape mirrors ``api_server.schemas.PreTriggerEvidence``:

        ::

            {
                "fired": bool,
                "triggerType": "hard" | "soft" | "none",
                "reasonCodes": list[str],
                "accelPeakG": float | None,
                "postureAngleDeg": float | None,
                "lowMotionSec": float | None,
                "gyroPeakDps": float | None,
            }

        We re-implement the matching logic here (rather than running
        :meth:`evaluate` and post-parsing the metadata strings) so the
        numeric values flow through unrounded — and so a future change
        to the public ``evaluate`` API does not silently change the
        evidence shape consumed by the FE.
        """
        if not motion:
            return {
                "fired": False, "triggerType": "none", "reasonCodes": [],
                "accelPeakG": None, "postureAngleDeg": None,
                "lowMotionSec": None, "gyroPeakDps": None,
            }

        accel = motion.get("accel") or {}
        gyro = motion.get("gyro") or {}
        accel_mag = _compute_accel_magnitude(accel)
        gyro_mag = _compute_gyro_magnitude(gyro)
        posture_angle = _safe_float(motion.get("posture_change_angle_deg"))
        low_motion_dur = _safe_float(motion.get("post_impact_low_motion_duration_s"))
        accel_peak = _safe_float(motion.get("accel_mag_peak_g")) or accel_mag
        gyro_peak = _safe_float(motion.get("gyro_mag_peak_dps")) or gyro_mag

        # Hard trigger: high impact peak (mirrors :meth:`evaluate` line 197).
        if accel_peak is not None and accel_peak >= self._hard_accel_g:
            return {
                "fired": True,
                "triggerType": "hard",
                "reasonCodes": ["IMPACT_PEAK_3G"],
                "accelPeakG": float(accel_peak),
                "postureAngleDeg": float(posture_angle) if posture_angle is not None else None,
                "lowMotionSec": float(low_motion_dur) if low_motion_dur is not None else None,
                "gyroPeakDps": float(gyro_peak) if gyro_peak is not None else None,
            }

        # Soft trigger: impact + posture change.
        if (
            accel_peak is not None
            and accel_peak >= self._soft_accel_g
            and posture_angle is not None
            and posture_angle >= self._soft_posture_deg
        ):
            return {
                "fired": True,
                "triggerType": "soft",
                "reasonCodes": ["IMPACT_PLUS_POSTURE_CHANGE"],
                "accelPeakG": float(accel_peak),
                "postureAngleDeg": float(posture_angle),
                "lowMotionSec": float(low_motion_dur) if low_motion_dur is not None else None,
                "gyroPeakDps": float(gyro_peak) if gyro_peak is not None else None,
            }

        # Soft trigger: impact + post-impact low motion.
        if (
            accel_peak is not None
            and accel_peak >= self._soft_accel_g
            and low_motion_dur is not None
            and low_motion_dur >= self._soft_low_motion_s
        ):
            return {
                "fired": True,
                "triggerType": "soft",
                "reasonCodes": ["IMPACT_PLUS_LOW_MOTION"],
                "accelPeakG": float(accel_peak),
                "postureAngleDeg": float(posture_angle) if posture_angle is not None else None,
                "lowMotionSec": float(low_motion_dur),
                "gyroPeakDps": float(gyro_peak) if gyro_peak is not None else None,
            }

        # Soft trigger: gyro + posture change.
        if (
            gyro_peak is not None
            and gyro_peak >= self._gyro_dps
            and posture_angle is not None
            and posture_angle >= self._soft_posture_deg
        ):
            return {
                "fired": True,
                "triggerType": "soft",
                "reasonCodes": ["GYRO_PLUS_POSTURE_CHANGE"],
                "accelPeakG": float(accel_peak) if accel_peak is not None else None,
                "postureAngleDeg": float(posture_angle),
                "lowMotionSec": float(low_motion_dur) if low_motion_dur is not None else None,
                "gyroPeakDps": float(gyro_peak),
            }

        # No trigger fired — return all observed values for diagnostics.
        return {
            "fired": False,
            "triggerType": "none",
            "reasonCodes": [],
            "accelPeakG": float(accel_peak) if accel_peak is not None else None,
            "postureAngleDeg": float(posture_angle) if posture_angle is not None else None,
            "lowMotionSec": float(low_motion_dur) if low_motion_dur is not None else None,
            "gyroPeakDps": float(gyro_peak) if gyro_peak is not None else None,
        }


__all__ = ["FallPreTrigger"]
