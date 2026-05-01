from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from typing import Literal

from api_server.dependencies import SimulatorRuntime, get_runtime
from api_server.schemas import (
    ApplyScenarioRequest,
    BackfillSleepRequest,
    BackfillSleepResponse,
    PushSleepDateRequest,
    PushSleepDateResponse,
    RiskInjectRequest,
)

_logger = logging.getLogger(__name__)

router = APIRouter(tags=["scenarios"])


# ---------------------------------------------------------------------------
# Module B — Scenario manifest contract.
#
# `KeySignal` describes one observable change a scenario produces.  The FE
# renders these as chips so an operator can pick the right scenario without
# reading prose.  `direction` is optional ("up"/"down"/"flat"); `target`
# holds the FSM key the signal lands on (vitals key, sleep_phase, etc.).
# `followUp` declares any side-effects the scenario triggers when applied
# — the FE no longer has to maintain a parallel `if (scenarioId === ...)`
# chain to know that `hypoxia_critical` injects a HIGH risk score.
# ---------------------------------------------------------------------------


KeySignalDirection = Literal["up", "down", "flat"]
ScenarioSeverity = Literal["normal", "warning", "critical"]
ScenarioFollowUpKind = Literal["fall_event", "risk_inject", "sleep_phase", "wake"]


class KeySignal(BaseModel):
    label: str
    direction: KeySignalDirection | None = None
    target: str | None = None
    severity: ScenarioSeverity = "normal"


class ScenarioFollowUp(BaseModel):
    kind: ScenarioFollowUpKind
    detail: str


class ScenarioOption(BaseModel):
    id: str
    name: str
    category: Literal["vitals", "fall", "sleep", "risk"]
    description: str
    expectedOutcome: str
    severity: ScenarioSeverity = "normal"
    keySignals: list[KeySignal] = Field(default_factory=list)
    followUp: list[ScenarioFollowUp] = Field(default_factory=list)


BUILT_IN_SCENARIOS: list[ScenarioOption] = [
    # ── Vitals ─────────────────────────────────────────────────────────
    ScenarioOption(
        id="normal_rest",
        name="Nghỉ ngơi bình thường",
        category="vitals",
        description="Trạng thái nghỉ khỏe mạnh, nhịp tim 60-80 bpm và SpO2 98-99%.",
        expectedOutcome="Sinh hiệu duy trì ổn định ở mức bình thường.",
        severity="normal",
        keySignals=[
            KeySignal(label="HR 60-80 bpm", direction="flat", target="heart_rate"),
            KeySignal(label="SpO2 98-99%", direction="flat", target="spo2"),
            KeySignal(label="Activity: resting", target="activity_state"),
        ],
    ),
    ScenarioOption(
        id="tachycardia_warning",
        name="Cảnh báo nhịp tim nhanh",
        category="vitals",
        description="Nhịp tim tăng cao kéo dài theo mô phỏng trạng thái căng thẳng.",
        expectedOutcome="Vùng cảnh báo nhịp tim được kích hoạt và mức rủi ro tăng.",
        severity="warning",
        keySignals=[
            KeySignal(label="HR ↑ (110-140 bpm)", direction="up", target="heart_rate", severity="warning"),
            KeySignal(label="Stress state: stress", target="stress_state", severity="warning"),
        ],
    ),
    ScenarioOption(
        id="hypoxia_critical",
        name="Giảm oxy máu nguy cấp",
        category="vitals",
        description="Xu hướng SpO2 giảm xuống dưới ngưỡng an toàn.",
        expectedOutcome="Sinh cảnh báo mức nguy cấp và ghi nhận vào dòng thời gian sự kiện.",
        severity="critical",
        keySignals=[
            KeySignal(label="SpO2 ↓ (<90%)", direction="down", target="spo2", severity="critical"),
            KeySignal(label="Risk: general HIGH", target="risk_level", severity="critical"),
        ],
        followUp=[
            ScenarioFollowUp(
                kind="risk_inject",
                detail="general / HIGH @ score 0.78",
            ),
        ],
    ),
    ScenarioOption(
        id="hypertension_moderate",
        name="Tăng huyết áp",
        category="vitals",
        description="Huyết áp tăng vượt nền cơ bản với mức kéo dài trung bình.",
        expectedOutcome="Trạng thái cảnh báo xuất hiện kèm chỉ số huyết áp tâm thu tăng.",
        severity="warning",
        keySignals=[
            KeySignal(label="BP_sys ↑ (140-160)", direction="up", target="blood_pressure_sys", severity="warning"),
        ],
    ),
    ScenarioOption(
        id="normal_walking",
        name="Đi bộ bình thường",
        category="vitals",
        description="Người cao tuổi đang đi bộ nhẹ nhàng. HR 80-100 bpm (bình thường khi hoạt động), SpO2 ổn định.",
        expectedOutcome="Sinh hiệu tăng nhẹ nhưng trong giới hạn bình thường — hệ thống không phát cảnh báo.",
        severity="normal",
        keySignals=[
            KeySignal(label="HR 80-100 bpm (đi bộ)", direction="up", target="heart_rate"),
            KeySignal(label="SpO2 97%", direction="flat", target="spo2"),
            KeySignal(label="Activity: walking", target="activity_state"),
        ],
    ),
    # ── Fall ───────────────────────────────────────────────────────────
    ScenarioOption(
        id="fall_high_confidence",
        name="Té ngã (độ tin cậy cao)",
        category="fall",
        description="Tín hiệu té ngã rõ ràng, có va chạm và bất động sau đó.",
        expectedOutcome="Sự kiện té ngã được phát hiện và luồng đếm ngược được kích hoạt.",
        severity="critical",
        keySignals=[
            KeySignal(label="Fall variant: fall_1", target="fall_variant", severity="critical"),
            KeySignal(label="Activity: fall → recovery", target="activity_state", severity="critical"),
            KeySignal(label="Device → fall_countdown", target="device.state", severity="critical"),
        ],
        followUp=[
            ScenarioFollowUp(
                kind="fall_event",
                detail="fall_detected variant=fall_1 (BE auto-injects)",
            ),
        ],
    ),
    ScenarioOption(
        id="fall_false_alarm",
        name="Té ngã giả",
        category="fall",
        description="Chuyển động đột ngột giống té ngã nhưng hồi phục nhanh.",
        expectedOutcome="Không duy trì trạng thái nguy cấp sau khi hồi phục.",
        severity="warning",
        keySignals=[
            KeySignal(label="Fall variant: fall_brief", target="fall_variant", severity="warning"),
            KeySignal(label="Activity: fall → recovery (nhanh)", target="activity_state"),
        ],
        followUp=[
            ScenarioFollowUp(
                kind="fall_event",
                detail="fall_detected variant=fall_brief (BE auto-injects)",
            ),
        ],
    ),
    ScenarioOption(
        id="fall_no_response",
        name="Té ngã - Không phản hồi",
        category="fall",
        description="Xảy ra té ngã nhưng không có phản hồi phục hồi trong thời gian đếm ngược.",
        expectedOutcome="Luồng leo thang cảnh báo tiếp tục và mục xác minh hiển thị đường đi cảnh báo.",
        severity="critical",
        keySignals=[
            KeySignal(label="Fall variant: fall_no_response", target="fall_variant", severity="critical"),
            KeySignal(label="Device → sos_active sau countdown", target="device.state", severity="critical"),
        ],
        followUp=[
            ScenarioFollowUp(
                kind="fall_event",
                detail="fall_detected variant=fall_no_response (BE auto-injects)",
            ),
        ],
    ),
    # ── Sleep ──────────────────────────────────────────────────────────
    ScenarioOption(
        id="good_sleep_night",
        name="Đêm ngủ tốt",
        category="sleep",
        description=(
            "Chu kỳ NREM+REM theo chuẩn AASM: Light(35') → Deep(60') → REM(25') "
            "lặp lại 2-3 chu kỳ. Tổng ~410 phút, Deep ≥28%, REM ≥19%, "
            "Awake <5%. Nhịp tim giảm xuống 40-55 bpm khi ngủ sâu, "
            "SpO2 duy trì 95-99%, hô hấp 11-14 lần/phút."
        ),
        expectedOutcome=(
            "Điểm giấc ngủ ≥85, hiệu suất ≥85%, sinh hiệu giảm chuẩn AASM. "
            "activityLabel = 'sleeping', heart_rate ≈ 47-55 bpm lúc Deep sleep."
        ),
        severity="normal",
        keySignals=[
            KeySignal(label="Sleep phases: Light → Deep → REM", target="sleep_phase"),
            KeySignal(label="HR ↓ (40-55 bpm Deep)", direction="down", target="heart_rate"),
            KeySignal(label="Hiệu suất ≥85%", target="sleep.efficiency"),
        ],
        followUp=[
            ScenarioFollowUp(
                kind="sleep_phase",
                detail="sleep_start variant=light (BE auto-injects)",
            ),
        ],
    ),
    ScenarioOption(
        id="fragmented_sleep",
        name="Ngủ phân mảnh",
        category="sleep",
        description=(
            "Nhiều micro-arousal xen kẽ: Light → Awake → Light → Awake → REM "
            "lặp lại không đều. Tổng ~220 phút, Awake >20%, Deep <10% (~7%), "
            "REM <15%. Mô phỏng rối loạn giấc ngủ (insomnia-like pattern)."
        ),
        expectedOutcome=(
            "Điểm giấc ngủ <70, hiệu suất ~72%, wake_count cao ≥4. "
            "Nhịp tim dao động bất thường khi chuyển phase. "
            "Phù hợp test AI risk scoring với sleep quality thấp."
        ),
        severity="warning",
        keySignals=[
            KeySignal(label="Sleep phases: nhiều micro-arousal", target="sleep_phase", severity="warning"),
            KeySignal(label="Hiệu suất ~72%", target="sleep.efficiency", severity="warning"),
            KeySignal(label="wake_count ≥4", direction="up", target="sleep.wake_count", severity="warning"),
        ],
        followUp=[
            ScenarioFollowUp(
                kind="sleep_phase",
                detail="sleep_start variant=light (BE auto-injects)",
            ),
        ],
    ),
    ScenarioOption(
        id="elderly_normal",
        name="Giấc ngủ người cao tuổi",
        category="sleep",
        description=(
            "Pattern giấc ngủ người cao tuổi: nhiều light sleep hơn, deep sleep giảm (~11%), "
            "REM ~19%. Bình thường theo tuổi tác."
        ),
        expectedOutcome=(
            "Sleep score 70-80 (bình thường cho người già). HR 55-65 bpm. "
            "Chu kỳ light → deep → REM → light lặp lại."
        ),
        severity="normal",
        keySignals=[
            KeySignal(label="Sleep phases: nhiều light, ít deep", target="sleep_phase"),
            KeySignal(label="HR ↓ (55-65 bpm)", direction="down", target="heart_rate"),
            KeySignal(label="Deep ~11% (age-normal)", target="sleep.efficiency"),
        ],
        followUp=[
            ScenarioFollowUp(
                kind="sleep_phase",
                detail="sleep_start variant=light (BE auto-injects)",
            ),
        ],
    ),
    # ── Risk ───────────────────────────────────────────────────────────
    ScenarioOption(
        id="high_risk_cardiac",
        name="Rủi ro tim mạch cao",
        category="risk",
        description="Tiêm hồ sơ rủi ro tim mạch với mức đóng góp nguy cơ cao.",
        expectedOutcome="API rủi ro trả về hồ sơ mức CAO/NGUY KỊCH nhanh chóng.",
        severity="critical",
        keySignals=[
            KeySignal(label="Risk: cardiac CRITICAL", target="risk_level", severity="critical"),
            KeySignal(label="Score 0.90", direction="up", target="risk.score", severity="critical"),
        ],
        followUp=[
            ScenarioFollowUp(
                kind="risk_inject",
                detail="cardiac / CRITICAL @ score 0.90",
            ),
        ],
    ),
    ScenarioOption(
        id="medium_risk_general",
        name="Rủi ro trung bình",
        category="risk",
        description="Hồ sơ rủi ro tổng quát với các chỉ báo cảnh báo mức vừa.",
        expectedOutcome="Kết quả rủi ro ổn định quanh mức TRUNG BÌNH.",
        severity="warning",
        keySignals=[
            KeySignal(label="Risk: general MEDIUM", target="risk_level", severity="warning"),
            KeySignal(label="Score 0.58", target="risk.score", severity="warning"),
        ],
        followUp=[
            ScenarioFollowUp(
                kind="risk_inject",
                detail="general / MEDIUM @ score 0.58",
            ),
        ],
    ),
]


# Side-effect routing table for `apply_scenario` — keeps the runtime
# function pure of literal strings and lets new scenarios opt in by
# adding a row here.  Format: scenario_id -> RiskInjectRequest kwargs.
_SCENARIO_RISK_INJECTS: dict[str, dict[str, object]] = {
    "hypoxia_critical": {"risk_type": "general", "risk_level": "HIGH", "score": 0.78},
    "high_risk_cardiac": {"risk_type": "cardiac", "risk_level": "CRITICAL", "score": 0.90},
    "medium_risk_general": {"risk_type": "general", "risk_level": "MEDIUM", "score": 0.58},
}


@router.get("/scenarios", response_model=list[ScenarioOption])
def list_scenarios() -> list[ScenarioOption]:
    return BUILT_IN_SCENARIOS


@router.post("/scenarios/apply", status_code=status.HTTP_204_NO_CONTENT)
def apply_scenario(
    request: ApplyScenarioRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> Response:
    """Apply a scenario to a device — atomic, BE-driven side-effects.

    Module B.2: this endpoint is now the single source of truth for the
    apply pipeline.  Fall and sleep side-effects are already injected by
    `runtime.set_device_scenario()`; the risk-inject side-effects are
    looked up from `_SCENARIO_RISK_INJECTS` and dispatched here.  The FE
    no longer fires its own follow-on `events/fall` / `events/risk-inject`
    POSTs after a scenario apply.
    """
    try:
        runtime.set_device_scenario(request.device_id, request.scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    risk_payload = _SCENARIO_RISK_INJECTS.get(request.scenario_id)
    if risk_payload is not None:
        try:
            runtime.inject_risk_score(
                RiskInjectRequest(
                    device_id=request.device_id,
                    risk_type=risk_payload["risk_type"],  # type: ignore[arg-type]
                    risk_level=risk_payload["risk_level"],  # type: ignore[arg-type]
                    score=float(risk_payload["score"]),  # type: ignore[arg-type]
                ),
            )
        except KeyError as exc:
            # Device disappeared between the two calls — surface as 404
            # so the operator can retry rather than silently leaving the
            # scenario in a half-applied state.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _run_backfill(
    runtime: SimulatorRuntime,
    device_id: str,
    days_behind: int,
    scenario_id: str,
) -> None:
    """Execute backfill loop in background (CRITICAL #3 fix).

    This runs outside the HTTP request lifecycle so it can take as long
    as needed without hitting request timeouts.
    """
    today = datetime.now(timezone.utc).date()
    pushed = 0
    skipped = 0
    for offset in range(days_behind, 0, -1):
        target_date = today - timedelta(days=offset)
        try:
            result = runtime.push_sleep_session_for_date(
                device_id=device_id,
                target_date=target_date,
                scenario_id=scenario_id,
            )
            if result.get("success"):
                pushed += 1
            else:
                skipped += 1
        except Exception as exc:
            skipped += 1
            _logger.warning(
                "Backfill day %s failed: %s: %s",
                target_date, type(exc).__name__, exc,
            )
    _logger.info(
        "Backfill complete for device=%s days=%d pushed=%d skipped=%d",
        device_id, days_behind, pushed, skipped,
    )


@router.post("/scenarios/sleep/backfill", response_model=BackfillSleepResponse)
def backfill_sleep_history(
    request: BackfillSleepRequest,
    background_tasks: BackgroundTasks,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> BackfillSleepResponse:
    """
    Bơm dữ liệu giấc ngủ lịch sử N ngày về trước vào Backend DB.
    Mỗi ngày: sample_sleep_session() → override date → push lên Backend.
    Dùng để cung cấp đủ data lịch sử cho AI risk scoring.

    - days_behind: số ngày muốn backfill (1-90)
    - scenario_id: kịch bản giấc ngủ để truyền xuống runtime

    CRITICAL #3 fix: The heavy loop (up to 90 iterations of DB + AI + HTTP)
    now runs in a FastAPI BackgroundTask. The endpoint returns immediately
    with status ``pushed=0`` and ``total_days`` set, indicating processing
    has been accepted.
    """
    # Schedule the heavy work in the background
    background_tasks.add_task(
        _run_backfill,
        runtime,
        request.device_id,
        request.days_behind,
        request.scenario_id,
    )

    # Return immediately — the client receives a "processing" response
    return BackfillSleepResponse(
        pushed=0,
        skipped=0,
        errors=["Backfill accepted — processing in background"],
        total_days=request.days_behind,
    )


@router.post("/scenarios/sleep/push-date", response_model=PushSleepDateResponse)
def push_sleep_for_date(
    request: PushSleepDateRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> PushSleepDateResponse:
    today = datetime.now(timezone.utc).date()
    if request.target_date >= today:
        raise HTTPException(
            status_code=422,
            detail="Không thể push dữ liệu cho ngày hôm nay hoặc tương lai. Chọn ngày <= hôm qua.",
        )

    if (today - request.target_date).days > 365:
        raise HTTPException(
            status_code=422,
            detail="Không thể push dữ liệu cũ hơn 1 năm.",
        )

    try:
        result = runtime.push_sleep_session_for_date(
            device_id=request.device_id,
            target_date=request.target_date,
            scenario_id=request.scenario_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return PushSleepDateResponse(**result)
