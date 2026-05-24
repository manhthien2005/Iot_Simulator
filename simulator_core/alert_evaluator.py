"""AlertEvaluator — pure function threshold evaluation, no side effects.

Does NOT import api_server/. Thresholds injected via constructor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AlertSignal:
    event_type: str
    severity: str       # "normal" | "warning" | "critical"
    device_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AlertEvaluator:
    """Evaluate vitals against thresholds and return alert signals.

    Pure: no DB, no HTTP, no shared mutable state.
    Thresholds sourced from DAYTIME_THRESHOLDS or SLEEP_THRESHOLDS.
    """

    def __init__(self, thresholds: dict[str, float]) -> None:
        self._t = thresholds

    def evaluate(
        self,
        vitals: dict[str, Any],
        *,
        device_id: str,
        scenario_id: str,
        is_sleeping: bool,
        activity_state: str,
    ) -> list[AlertSignal]:
        """Return alert signals for abnormal vitals. Empty list = all normal.

        Falls are handled by inject_event separately — skip evaluation.
        """
        if activity_state == "falling":
            return []

        signals: list[AlertSignal] = []
        t = self._t

        hr = _safe_float(vitals.get("heart_rate"))
        if hr is not None:
            if hr < t.get("hr_critical_low", 0) or hr > t.get("hr_critical_high", float("inf")):
                signals.append(AlertSignal(
                    event_type="heart_rate_alert",
                    severity="critical",
                    device_id=device_id,
                    metadata={"value": hr, "scenario_id": scenario_id},
                ))
            elif hr < t.get("hr_warning_low", 0) or hr > t.get("hr_warning_high", float("inf")):
                signals.append(AlertSignal(
                    event_type="heart_rate_alert",
                    severity="warning",
                    device_id=device_id,
                    metadata={"value": hr, "scenario_id": scenario_id},
                ))

        spo2 = _safe_float(vitals.get("spo2"))
        if spo2 is not None:
            # Sleep apnea: check OSA threshold first if sleeping
            osa_threshold = t.get("osa_alert_spo2_threshold") if is_sleeping else None
            critical_threshold = osa_threshold if osa_threshold is not None else t.get("spo2_critical", 0)
            if spo2 < critical_threshold:
                signals.append(AlertSignal(
                    event_type="spo2_alert",
                    severity="critical",
                    device_id=device_id,
                    metadata={"value": spo2, "scenario_id": scenario_id, "sleeping": is_sleeping},
                ))
            elif spo2 < t.get("spo2_warning", 0):
                signals.append(AlertSignal(
                    event_type="spo2_alert",
                    severity="warning",
                    device_id=device_id,
                    metadata={"value": spo2, "scenario_id": scenario_id},
                ))

        rr = _safe_float(vitals.get("respiratory_rate"))
        if rr is not None:
            apnea_threshold = t.get("apnea_rr_threshold") if is_sleeping else None
            rr_crit_low = apnea_threshold if apnea_threshold is not None else t.get("rr_critical_low", 0)
            if rr < rr_crit_low or rr > t.get("rr_critical_high", float("inf")):
                signals.append(AlertSignal(
                    event_type="respiratory_rate_alert",
                    severity="critical",
                    device_id=device_id,
                    metadata={"value": rr, "scenario_id": scenario_id, "sleeping": is_sleeping},
                ))

        return signals


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
