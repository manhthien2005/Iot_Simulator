"""VitalsService — extracted from SimulatorRuntime (Task 3.3).

Owns vitals retrieval, construction, BP-staleness tracking,
and the multi-signal severity classification logic.

Thread-safety: ``latest_vitals`` acquires ``self._lock`` (the *same*
``threading.RLock`` instance shared with ``SimulatorRuntime``).
"""

from __future__ import annotations

from threading import RLock
from time import monotonic
from typing import TYPE_CHECKING, Any

from api_server.schemas import VitalsSample
from api_server.utils import _utc_now_iso, _safe_float, _is_sleeping_state

if TYPE_CHECKING:
    from api_server.models import DeviceRecord, SessionRecord


# ── Threshold constants ──────────────────────────────────────────────────

DAYTIME_THRESHOLDS: dict[str, float] = {
    "hr_critical_low": 41.0,
    "hr_critical_high": 131.0,
    "hr_warning_low": 55.0,
    "hr_warning_high": 110.0,
    "spo2_critical": 90.0,
    "spo2_warning": 94.0,
    "rr_critical_low": 9.0,
    "rr_critical_high": 25.0,
    "bp_sys_critical": 180.0,
    "bp_sys_critical_low": 90.0,
    "bp_dia_critical": 120.0,
    "bp_sys_warning": 140.0,
    "bp_dia_warning": 90.0,
}


SLEEP_THRESHOLDS: dict[str, float] = {
    "hr_critical_low": 38.0,
    "hr_critical_high": 100.0,
    "hr_warning_low": 42.0,
    "hr_warning_high": 90.0,
    "spo2_critical": 85.0,
    "spo2_warning": 90.0,
    "rr_critical_low": 6.0,
    "rr_critical_high": 25.0,
    "bp_sys_critical": 180.0,
    "bp_dia_critical": 120.0,
    "bp_sys_warning": 160.0,
    "bp_dia_warning": 100.0,
    "osa_alert_spo2_threshold": 88.0,
    "nocturnal_tachy_hr": 120.0,
    "apnea_rr_threshold": 6.0,
}


class VitalsService:
    """Retrieves and builds vitals samples with severity classification."""

    def __init__(
        self,
        *,
        sessions: dict[str, "SessionRecord"],
        bp_last_observed: dict[str, float],
        lock: RLock,
    ) -> None:
        self.sessions = sessions
        self._bp_last_observed = bp_last_observed
        self._lock = lock

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def latest_vitals(self, device_id: str) -> VitalsSample:
        with self._lock:
            for record in self.sessions.values():
                for payload in reversed(record.last_tick_outputs):
                    if payload.get("device_id") == device_id:
                        raw_vitals = payload.get("vitals") or {}
                        payload_state = payload.get("state") or {}
                        source_mode = str(record.source_modes.get(device_id, "synthetic") or "synthetic").strip().lower()
                        has_bp = (
                            raw_vitals.get("blood_pressure_sys") is not None
                            and raw_vitals.get("blood_pressure_dia") is not None
                        )
                        bp_observation_age_sec, bp_is_stale = self._compute_bp_staleness(device_id, has_bp=has_bp)
                        sample = self.to_vitals(
                            raw_vitals,
                            stale=record.status != "running",
                            emitted_at=str(payload.get("emitted_at") or ""),
                            activity_state=str(payload_state.get("activity_state") or "unknown"),
                            is_sleeping=_is_sleeping_state(payload_state.get("activity_state")),
                            source_mode=source_mode,
                            device_id=device_id,
                            bp_observation_age_sec=bp_observation_age_sec,
                            bp_is_stale=bp_is_stale,
                        )
                        activity_state = str(payload_state.get("activity_state") or "").strip().lower()
                        fall_variant = str(payload_state.get("fall_variant") or "").strip().lower()
                        if activity_state == "fall" and fall_variant != "fall_brief":
                            return sample.model_copy(update={"severity": "critical"})
                        return sample
            raise KeyError(f"No vitals found for device: {device_id}")

    # ------------------------------------------------------------------
    # BP staleness tracking
    # ------------------------------------------------------------------

    def _compute_bp_staleness(self, device_id: str, has_bp: bool) -> tuple[float | None, bool | None]:
        """Track replay NIBP freshness using the latest observed blood pressure sample."""
        now = monotonic()
        if has_bp:
            self._bp_last_observed[device_id] = now
        last = self._bp_last_observed.get(device_id)
        if last is None:
            return None, None
        age = round(now - last, 1)
        return age, age > 300.0

    # ------------------------------------------------------------------
    # Vitals construction + severity logic (static)
    # ------------------------------------------------------------------

    @staticmethod
    def to_vitals(
        vitals: dict[str, Any],
        stale: bool,
        emitted_at: str | None = None,
        activity_state: str = "unknown",
        is_sleeping: bool = False,
        source_mode: str = "synthetic",
        device_id: str = "",
        bp_observation_age_sec: float | None = None,
        bp_is_stale: bool | None = None,
    ) -> VitalsSample:
        heart_rate = _safe_float(vitals.get("heart_rate"), 72.0)
        spo2_val   = _safe_float(vitals.get("spo2"), 98.0)
        bp_sys_val = _safe_float(vitals.get("blood_pressure_sys"), 120.0)
        bp_dia_val = _safe_float(vitals.get("blood_pressure_dia"), 80.0)
        raw_temp = vitals.get("temperature")
        raw_rr = vitals.get("respiratory_rate")
        if raw_rr is None:
            raw_rr = vitals.get("respiration_rate")
        replay_mode = source_mode == "replay"
        provenance: dict[str, str] | None = None
        if replay_mode:
            provenance = {
                "heartRate": "measured" if vitals.get("heart_rate") is not None else "unknown",
                "spo2": "measured" if vitals.get("spo2") is not None else "unknown",
                "bloodPressureSys": "measured" if vitals.get("blood_pressure_sys") is not None else "unknown",
                "bloodPressureDia": "measured" if vitals.get("blood_pressure_dia") is not None else "unknown",
                "temperature": "unknown",
                "respiratoryRate": "measured" if raw_rr is not None else "unknown",
                "hrv": "unknown",
            }
        temperature = _safe_float(raw_temp, 36.7)
        respiratory_rate = (
            _safe_float(raw_rr, None)
            if replay_mode and raw_rr is None
            else _safe_float(raw_rr, 15.0)
        )
        blood_pressure_sys = (
            None
            if replay_mode and bp_is_stale is True
            else _safe_float(vitals.get("blood_pressure_sys"), 120.0)
        )
        blood_pressure_dia = (
            None
            if replay_mode and bp_is_stale is True
            else _safe_float(vitals.get("blood_pressure_dia"), 80.0)
        )
        thresholds = SLEEP_THRESHOLDS if is_sleeping else DAYTIME_THRESHOLDS
        critical_rr = (
            respiratory_rate is not None
            and (
                respiratory_rate < thresholds["rr_critical_low"]
                or respiratory_rate > thresholds["rr_critical_high"]
            )
        )
        low_sys_critical = blood_pressure_sys is not None and blood_pressure_sys < thresholds.get("bp_sys_critical_low", 80.0)
        # Multi-signal severity with context-aware thresholds for waking vs sleeping.
        severity = "normal"
        if (
            heart_rate >= thresholds["hr_critical_high"]
            or heart_rate < thresholds["hr_critical_low"]
            or spo2_val < thresholds["spo2_critical"]
            or low_sys_critical
            or bp_sys_val >= thresholds["bp_sys_critical"]
            or bp_dia_val >= thresholds["bp_dia_critical"]
            or critical_rr
        ):
            severity = "critical"
        elif (
            heart_rate >= thresholds["hr_warning_high"]
            or heart_rate < thresholds["hr_warning_low"]
            or spo2_val < thresholds["spo2_warning"]
            or bp_sys_val >= thresholds["bp_sys_warning"]
            or bp_dia_val >= thresholds["bp_dia_warning"]
        ):
            severity = "warning"
        activity_map: dict[str, str] = {
            "resting": "resting",
            "walking": "walking",
            "running": "running",
            "fall": "falling",
            "recovery": "recovery",
            "sleeping": "sleeping",
            "standing": "resting",
        }
        label = activity_map.get(str(activity_state or "unknown").strip().lower(), "unknown")
        generator_label = str(vitals.get("activity_label") or "").strip().lower()
        if generator_label in {"sleeping", "resting", "walking", "running", "falling", "recovery", "unknown"}:
            label = generator_label
        return VitalsSample(
            timestamp=emitted_at or vitals.get("timestamp") or _utc_now_iso(),
            heartRate=heart_rate,
            spo2=spo2_val,
            temperature=temperature,
            bloodPressureSys=blood_pressure_sys,
            bloodPressureDia=blood_pressure_dia,
            respiratoryRate=respiratory_rate,
            hrv=None,
            signalQuality=None,
            motionArtifact=False,
            isStale=stale,
            severity=severity,  # type: ignore[arg-type]
            activityLabel=label,  # type: ignore[arg-type]
            motionTag=label,  # type: ignore[arg-type]
            fieldProvenance=provenance,
            bpObservationAgeSec=bp_observation_age_sec,
            bpIsStale=bp_is_stale,
            sourceMode=source_mode if source_mode != "synthetic" else None,
        )
