"""VerificationService — extracted from SimulatorRuntime.

Owns the full pipeline verification trail: stages, status, staleness check,
and the two payload-block helpers (_compute_pre_trigger_block,
_compute_telemetry_block) that are called from verification paths.

Thread-safety: every public method acquires ``self._lock`` (the same
``threading.RLock`` instance shared with ``SimulatorRuntime``).
"""

from __future__ import annotations

import collections
import os
import time
from datetime import datetime, timezone
from threading import RLock
from typing import TYPE_CHECKING, Any

_PRE_MODEL_TRIGGER_ENABLED: bool = os.environ.get(
    "PRE_MODEL_TRIGGER_ENABLED", ""
).lower() in ("1", "true", "yes")

from api_server.schemas import (
    PipelineStage,
    PipelineStageStatusValue,
    VerificationResult,
)
from api_server.utils import _utc_now_iso

if TYPE_CHECKING:
    from api_server.models import DeviceRecord, SessionRecord


class VerificationService:
    """Verification pipeline trail — stages, status, staleness helpers."""

    def __init__(
        self,
        *,
        devices: "dict[str, DeviceRecord]",
        sessions: "dict[str, SessionRecord]",
        device_scenarios: dict[str, str],
        risk_snapshots: dict[str, Any],
        event_history: Any,
        lock: RLock,
        health_backend_url: str,
        trigger_orchestrator: Any | None,
        push_interval: int,
        alert_timestamps_1h: "collections.deque[float]",
    ) -> None:
        # Shared mutable state — same object references as SimulatorRuntime
        self.devices = devices
        self.sessions = sessions
        self.device_scenarios = device_scenarios
        self.risk_snapshots = risk_snapshots
        self.event_history = event_history
        self._lock = lock
        self._health_backend_url = health_backend_url
        self._trigger_orchestrator = trigger_orchestrator
        self._push_interval = push_interval
        self._alert_timestamps_1h = alert_timestamps_1h

    # ------------------------------------------------------------------
    # Public endpoint
    # ------------------------------------------------------------------

    def verification(self, session_id: str) -> VerificationResult:
        with self._lock:
            record = self._require_session(session_id)
            device_id = record.device_ids[0] if record.device_ids else "unknown"
            status = self._verification_status_locked(record)
            risk_received = device_id in self.risk_snapshots
            stages = self._verification_stages_locked(record, device_id, risk_received)
            failure_reason = self._verification_failure_reason_locked(record, stages)
            return VerificationResult(
                deviceId=device_id,
                vitalsReceived=bool(record.last_tick_outputs),
                alertReceived=record.alert_received,
                riskScoreReceived=risk_received,
                latencyMs=record.last_publish_latency_ms or 0,
                status=status,  # type: ignore[arg-type]
                lastCheckedAt=_utc_now_iso(),
                stages=stages,
                failureReason=failure_reason,
                lastGoodPublishAt=record.last_publish_ok_at,
                lastPublishAttemptAt=record.last_publish_attempt_at,
                publishAckCount=record.publish_ack_count_total,
                publishAttemptCount=record.publish_attempt_count,
            )

    # ------------------------------------------------------------------
    # Core verification logic (private)
    # ------------------------------------------------------------------

    def _verification_stages_locked(
        self,
        record: "SessionRecord",
        device_id: str,
        risk_received: bool,
    ) -> list[PipelineStage]:
        """Build the ordered evidence trail for `record`.

        Stages are emitted in pipeline order so the FE strip renders
        device → session → telemetry → publish → risk → alert.  Each
        stage is one of `ok` / `pending` / `failed` / `skipped` so the
        operator can see exactly where the trail broke.
        """
        device_known = device_id in self.devices
        stages: list[PipelineStage] = []

        # 1. Device registered in simulator runtime.
        stages.append(
            PipelineStage(
                key="device_registered",
                label="Thiết bị đã đăng ký",
                status="ok" if device_known else "failed",
                detail=(
                    None
                    if device_known
                    else "Thiết bị không có trong simulator runtime — kiểm tra Devices."
                ),
            )
        )

        # 2. Session running.
        if record.status == "running":
            session_status: PipelineStageStatusValue = "ok"
            session_detail: str | None = None
        elif record.status == "stopped":
            session_status = "failed"
            session_detail = "Phiên đã dừng — bắt đầu lại để tiếp tục thu thập bằng chứng."
        else:
            session_status = "pending"
            session_detail = "Phiên chưa chạy."
        stages.append(
            PipelineStage(
                key="session_started",
                label="Phiên đang chạy",
                status=session_status,
                detail=session_detail,
                at=record.last_tick_at if record.status == "running" else None,
            )
        )

        # 3. Telemetry generated locally.
        has_outputs = bool(record.last_tick_outputs)
        is_stale = self._verification_is_stale_locked(record)
        if has_outputs and not is_stale:
            telemetry_status: PipelineStageStatusValue = "ok"
            telemetry_detail: str | None = None
        elif has_outputs and is_stale:
            telemetry_status = "failed"
            telemetry_detail = "Tick chưa cập nhật — simulator có thể bị treo."
        else:
            telemetry_status = "pending"
            telemetry_detail = "Chưa có tick nào tạo dữ liệu vitals."
        stages.append(
            PipelineStage(
                key="telemetry_generated",
                label="Sinh hiệu đã tạo",
                status=telemetry_status,
                detail=telemetry_detail,
                at=record.last_tick_at,
            )
        )

        # 4. Telemetry successfully published downstream.
        if record.publish_attempt_count == 0:
            publish_status: PipelineStageStatusValue = "pending"
            publish_detail: str | None = "Chưa publish lần nào."
        elif record.last_publish_ok:
            publish_status = "ok"
            publish_detail = (
                f"{record.last_publish_ack_count}/{record.last_publish_count} message ack thành công."
            )
        else:
            publish_status = "failed"
            publish_detail = record.last_publish_error or "Publish gần nhất thất bại."
        stages.append(
            PipelineStage(
                key="telemetry_published",
                label="Đã publish",
                status=publish_status,
                detail=publish_detail,
                at=record.last_publish_ok_at,
            )
        )

        # 5. Risk evaluated for the focal device.
        stages.append(
            PipelineStage(
                key="risk_evaluated",
                label="Đã tính rủi ro",
                status="ok" if risk_received else "pending",
                detail=(
                    None
                    if risk_received
                    else "Chưa có snapshot rủi ro — chờ tick kế tiếp hoặc trigger từ Diagnostics."
                ),
            )
        )

        # 6. Alert dispatched (only meaningful when an alert is expected).
        if record.alert_received:
            alert_stage = PipelineStage(
                key="alert_dispatched",
                label="Cảnh báo đã gửi",
                status="ok",
                detail="Đã ghi nhận cảnh báo cho phiên này.",
            )
        else:
            alert_stage = PipelineStage(
                key="alert_dispatched",
                label="Cảnh báo đã gửi",
                status="skipped",
                detail="Phiên hiện tại chưa có sự kiện cần cảnh báo.",
            )
        stages.append(alert_stage)

        return stages

    @staticmethod
    def _verification_failure_reason_locked(
        record: "SessionRecord",
        stages: list[PipelineStage],
    ) -> str | None:
        """Return the first user-readable failure reason, if any."""
        for stage in stages:
            if stage.status == "failed":
                return stage.detail or f"Stage {stage.key} thất bại."
        if record.last_publish_error and record.publish_attempt_count > 0 and not record.last_publish_ok:
            return record.last_publish_error
        return None

    def _require_session(self, session_id: str) -> "SessionRecord":
        if session_id not in self.sessions:
            raise KeyError(f"Session not found: {session_id}")
        return self.sessions[session_id]

    def _verification_is_stale_locked(self, record: "SessionRecord") -> bool:
        if not record.last_tick_at:
            return False
        try:
            last_tick_at = datetime.fromisoformat(record.last_tick_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        stale_after_seconds = max(float(self._push_interval) * 2.0, 10.0)
        age_seconds = (datetime.now(timezone.utc) - last_tick_at).total_seconds()
        return age_seconds > stale_after_seconds

    def _verification_status_locked(self, record: "SessionRecord") -> str:
        if record.last_publish_count > 0:
            if not record.last_publish_ok:
                return "FAILED"
            if record.status == "running" and self._verification_is_stale_locked(record):
                return "DELAYED"
            return "PASS"

        if record.status != "running":
            return "PENDING"
        if not record.last_tick_outputs:
            return "PENDING"
        if self._verification_is_stale_locked(record):
            return "DELAYED"
        return "PENDING"

    # ------------------------------------------------------------------
    # Payload block helpers (called from health_payload and verification)
    # ------------------------------------------------------------------

    def _compute_pre_trigger_block(self) -> dict[str, Any]:
        """Derive ``preTrigger`` block (mode + threshold source)."""
        if not _PRE_MODEL_TRIGGER_ENABLED:
            mode = "off"
        elif self._trigger_orchestrator is None:
            # Flag says ON but wiring failed: treat as off so the UI does not
            # claim shadow/active capability we cannot actually exercise.
            mode = "off"
        else:
            mode = "shadow"  # active mode disposed S7 (ADR-020)

        threshold_source = "unavailable"
        enable_model_calls = False
        if self._trigger_orchestrator is not None:
            enable_model_calls = False  # active mode disposed S7 (ADR-020)
            try:
                provider = self._trigger_orchestrator._settings
                day = provider.get_vitals_thresholds(is_sleeping=False)
                threshold_source = "db" if day else "fallback"
            except Exception:
                threshold_source = "unavailable"
        else:
            threshold_source = "fallback"

        return {
            "mode": mode,
            "enableModelCalls": enable_model_calls,
            "thresholdSource": threshold_source,
        }

    def _compute_telemetry_block(self) -> dict[str, int]:
        """Counts derived from runtime state for the v2 telemetry block."""
        with self._lock:
            devices_simulated = len(self.devices)
            sessions_running = sum(
                1 for session in self.sessions.values() if session.status == "running"
            )
            now_ts = time.time()
            cutoff = now_ts - 3600
            while self._alert_timestamps_1h and self._alert_timestamps_1h[0] < cutoff:
                self._alert_timestamps_1h.popleft()
            alerts_last_hour = len(self._alert_timestamps_1h)
            latencies = [
                session.last_publish_latency_ms
                for session in self.sessions.values()
                if session.last_publish_count > 0 and session.last_publish_latency_ms is not None
            ]
            avg_latency = int(round(sum(latencies) / len(latencies))) if latencies else 0
        return {
            "devicesSimulated": devices_simulated,
            "sessionsRunning": sessions_running,
            "alertsLastHour": alerts_last_hour,
            "avgPublishLatencyMs": avg_latency,
        }
