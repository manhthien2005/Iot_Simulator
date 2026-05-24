"""RiskService — risk score computation, history, and explanation.

Extracted from SimulatorRuntime to reduce runtime.py size.
"""

from __future__ import annotations

import collections
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import TYPE_CHECKING, Any

from api_server.models import EventRecord, RiskSnapshot
from api_server.schemas import RiskContribution, RiskHistoryPoint, RiskScoreResponse, RiskInjectRequest
from api_server.utils import _utc_now_iso

if TYPE_CHECKING:
    from api_server.services.vitals_service import VitalsService
    from api_server.models import DeviceRecord


class RiskService:
    """Manages risk score calculation, injection, snapshot and history."""

    def __init__(
        self,
        *,
        devices: "dict[str, DeviceRecord]",
        risk_snapshots: dict[str, RiskSnapshot],
        risk_history: dict[str, list[RiskHistoryPoint]],
        event_history: collections.deque[EventRecord],
        lock: RLock,
        vitals_service: "VitalsService",
        record_event_fn: Any,
    ) -> None:
        self.devices = devices
        self.risk_snapshots = risk_snapshots
        self.risk_history = risk_history
        self.event_history = event_history
        self._lock = lock
        self._vitals_service = vitals_service
        self._record_event = record_event_fn

    def risk_score(self, device_id: str) -> RiskScoreResponse:
        with self._lock:
            if device_id not in self.devices:
                raise KeyError(f"Device {device_id} not found")
            snapshot = self.risk_snapshots.get(device_id)
            if snapshot is None:
                score = self._calculate_dynamic_risk(device_id)
                level = _risk_level_from_score(score)
                snapshot = self._upsert_risk_snapshot(
                    device_id=device_id,
                    score=score,
                    risk_level=level,
                    risk_type="general",
                    explanation=self._build_risk_explanation(device_id=device_id, score=score, risk_type="general"),
                    calculated_at=_utc_now_iso(),
                )
            history = self.risk_history.get(device_id)
            if not history:
                history = _build_risk_history(device_id, snapshot.score)
                self.risk_history[device_id] = history
            return RiskScoreResponse(
                deviceId=device_id,
                score=snapshot.score,
                riskLevel=snapshot.risk_level,  # type: ignore[arg-type]
                model=snapshot.model,
                algorithm=snapshot.algorithm,
                calculatedAt=snapshot.calculated_at,
                explanation=snapshot.explanation,
                history=history,
            )

    def inject_risk_score(self, request: RiskInjectRequest) -> None:
        with self._lock:
            if request.device_id not in self.devices:
                raise KeyError(f"Device {request.device_id} not found")
            score = max(0.0, min(1.0, round(float(request.score), 3)))
            explanation = self._build_risk_explanation(
                device_id=request.device_id,
                score=score,
                risk_type=request.risk_type,
            )
            self._upsert_risk_snapshot(
                device_id=request.device_id,
                score=score,
                risk_level=request.risk_level,
                risk_type=request.risk_type,
                explanation=explanation,
                calculated_at=_utc_now_iso(),
            )
            self._append_risk_history(request.device_id, score)
            self._record_event(
                device_id=request.device_id,
                event_type="risk_injected",
                severity=_severity_from_risk_level(request.risk_level),
                message=f"Risk injected ({request.risk_type})",
                metadata={"score": f"{score:.2f}", "risk_level": request.risk_level, "risk_type": request.risk_type},
            )

    def _upsert_risk_snapshot(
        self,
        *,
        device_id: str,
        score: float,
        risk_level: str,
        risk_type: str,
        explanation: list[RiskContribution],
        calculated_at: str,
    ) -> RiskSnapshot:
        snapshot = RiskSnapshot(
            device_id=device_id,
            score=round(score, 3),
            risk_level=risk_level,
            risk_type=risk_type,
            explanation=explanation,
            calculated_at=calculated_at,
        )
        self.risk_snapshots[device_id] = snapshot
        return snapshot

    def _append_risk_history(self, device_id: str, score: float) -> None:
        score = round(max(0.0, min(1.0, score)), 3)
        today = datetime.now(timezone.utc).date().isoformat()
        history = self.risk_history.get(device_id)
        if history is None:
            history = _build_risk_history(device_id, score)
        if history and history[-1].date == today:
            history[-1] = RiskHistoryPoint(date=today, score=score)
        else:
            history.append(RiskHistoryPoint(date=today, score=score))
        self.risk_history[device_id] = history[-30:]

    def _calculate_dynamic_risk(self, device_id: str) -> float:
        score = 0.18
        try:
            vitals = self._vitals_service.latest_vitals(device_id)
            score += max(0.0, (vitals.heartRate - 72.0) / 220.0)
            score += max(0.0, (96.0 - vitals.spo2) / 35.0)
            score += max(0.0, (vitals.bloodPressureSys - 125.0) / 220.0)
        except KeyError:
            pass

        device = self.devices[device_id]
        if device.battery_level < 20:
            score += 0.06
        if device.state in {"warning", "critical", "fall_countdown", "sos_active"}:
            score += 0.14

        now = datetime.now(timezone.utc)
        for event in reversed(self.event_history):
            if event.device_id != device_id:
                continue
            age = now - datetime.fromisoformat(event.timestamp)
            if age.total_seconds() > 3600:
                break
            if event.severity == "critical":
                score += 0.1
            elif event.severity == "warning":
                score += 0.05
        return round(max(0.0, min(1.0, score)), 3)

    def _build_risk_explanation(self, *, device_id: str, score: float, risk_type: str) -> list[RiskContribution]:
        try:
            vitals = self._vitals_service.latest_vitals(device_id)
            hr = f"{round(vitals.heartRate)} bpm"
            spo2 = f"{round(vitals.spo2)}%"
            bp_sys = f"{round(vitals.bloodPressureSys)} mmHg"
        except KeyError:
            hr = "72 bpm"
            spo2 = "98%"
            bp_sys = "120 mmHg"

        type_weight = {"general": 0.08, "stroke": 0.11, "cardiac": 0.13}.get(risk_type, 0.08)
        baseline_age = 65 if risk_type != "general" else 58

        return [
            RiskContribution(feature="heart_rate", value=hr, weight=0.18, direction="up"),
            RiskContribution(feature="spo2", value=spo2, weight=0.12, direction="up"),
            RiskContribution(feature="blood_pressure_sys", value=bp_sys, weight=0.1, direction="up"),
            RiskContribution(feature="risk_type_bias", value=risk_type, weight=type_weight, direction="up"),
            RiskContribution(feature="age", value=f"{baseline_age} years", weight=0.07, direction="up"),
            RiskContribution(feature="sleep_efficiency", value="~estimated", weight=-0.04, direction="down"),
            RiskContribution(feature="stability_guard", value=f"{score:.2f}", weight=0.03, direction="flat"),
        ]


# ── Pure functions (no instance state) ────────────────────────────────────

def _build_risk_history(device_id: str, baseline_score: float) -> list[RiskHistoryPoint]:
    seed = int(device_id[:8], 16)
    today = datetime.now(timezone.utc).date()
    history: list[RiskHistoryPoint] = []
    current = max(0.05, min(0.95, baseline_score))
    for offset in range(29, -1, -1):
        date_value = (today - timedelta(days=offset)).isoformat()
        drift = ((seed + offset * 17) % 11 - 5) / 200
        current = max(0.01, min(0.99, current + drift))
        history.append(RiskHistoryPoint(date=date_value, score=round(current, 3)))
    return history


def _risk_level_from_score(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.65:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


def _severity_from_risk_level(level: str) -> str:
    return {"LOW": "normal", "MEDIUM": "warning", "HIGH": "warning", "CRITICAL": "critical"}.get(
        level.upper(), "warning"
    )
