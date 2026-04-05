from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from pydantic import BaseModel
from typing import Literal

from Iot_Simulator.api_server.dependencies import SimulatorRuntime, get_runtime
from Iot_Simulator.api_server.schemas import (
    ApplyScenarioRequest,
    BackfillSleepRequest,
    BackfillSleepResponse,
    PushSleepDateRequest,
    PushSleepDateResponse,
)

_logger = logging.getLogger(__name__)

router = APIRouter(tags=["scenarios"])


class ScenarioOption(BaseModel):
    id: str
    name: str
    category: Literal["vitals", "fall", "sleep", "risk"]
    description: str
    expectedOutcome: str


BUILT_IN_SCENARIOS: list[ScenarioOption] = [
    # Vitals
    ScenarioOption(
        id="normal_rest",
        name="Nghỉ ngơi bình thường",
        category="vitals",
        description="Trạng thái nghỉ khỏe mạnh, nhịp tim 60-80 bpm và SpO2 98-99%.",
        expectedOutcome="Sinh hiệu duy trì ổn định ở mức bình thường.",
    ),
    ScenarioOption(
        id="tachycardia_warning",
        name="Cảnh báo nhịp tim nhanh",
        category="vitals",
        description="Nhịp tim tăng cao kéo dài theo mô phỏng trạng thái căng thẳng.",
        expectedOutcome="Vùng cảnh báo nhịp tim được kích hoạt và mức rủi ro tăng.",
    ),
    ScenarioOption(
        id="hypoxia_critical",
        name="Giảm oxy máu nguy cấp",
        category="vitals",
        description="Xu hướng SpO2 giảm xuống dưới ngưỡng an toàn.",
        expectedOutcome="Sinh cảnh báo mức nguy cấp và ghi nhận vào dòng thời gian sự kiện.",
    ),
    ScenarioOption(
        id="hypertension_moderate",
        name="Tăng huyết áp",
        category="vitals",
        description="Huyết áp tăng vượt nền cơ bản với mức kéo dài trung bình.",
        expectedOutcome="Trạng thái cảnh báo xuất hiện kèm chỉ số huyết áp tâm thu tăng.",
    ),
    # Fall
    ScenarioOption(
        id="fall_high_confidence",
        name="Té ngã (độ tin cậy cao)",
        category="fall",
        description="Tín hiệu té ngã rõ ràng, có va chạm và bất động sau đó.",
        expectedOutcome="Sự kiện té ngã được phát hiện và luồng đếm ngược được kích hoạt.",
    ),
    ScenarioOption(
        id="fall_false_alarm",
        name="Té ngã giả",
        category="fall",
        description="Chuyển động đột ngột giống té ngã nhưng hồi phục nhanh.",
        expectedOutcome="Không duy trì trạng thái nguy cấp sau khi hồi phục.",
    ),
    ScenarioOption(
        id="fall_no_response",
        name="Té ngã - Không phản hồi",
        category="fall",
        description="Xảy ra té ngã nhưng không có phản hồi phục hồi trong thời gian đếm ngược.",
        expectedOutcome="Luồng leo thang cảnh báo tiếp tục và mục xác minh hiển thị đường đi cảnh báo.",
    ),
    # Sleep
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
    ),
    # Risk
    ScenarioOption(
        id="high_risk_cardiac",
        name="Rủi ro tim mạch cao",
        category="risk",
        description="Tiêm hồ sơ rủi ro tim mạch với mức đóng góp nguy cơ cao.",
        expectedOutcome="API rủi ro trả về hồ sơ mức CAO/NGUY KỊCH nhanh chóng.",
    ),
    ScenarioOption(
        id="medium_risk_general",
        name="Rủi ro trung bình",
        category="risk",
        description="Hồ sơ rủi ro tổng quát với các chỉ báo cảnh báo mức vừa.",
        expectedOutcome="Kết quả rủi ro ổn định quanh mức TRUNG BÌNH.",
    ),
]


@router.get("/scenarios", response_model=list[ScenarioOption])
def list_scenarios() -> list[ScenarioOption]:
    return BUILT_IN_SCENARIOS


@router.post("/scenarios/apply", status_code=status.HTTP_204_NO_CONTENT)
def apply_scenario(
    request: ApplyScenarioRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> Response:
    try:
        runtime.set_device_scenario(request.device_id, request.scenario_id)
    except KeyError as exc:
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
