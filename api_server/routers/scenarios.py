from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from typing import Literal

from Iot_Simulator.api_server.dependencies import SimulatorRuntime, get_runtime
from Iot_Simulator.api_server.schemas import ApplyScenarioRequest

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
        description="Phân bổ ngủ nông/ngủ sâu/REM cân bằng với hiệu suất cao.",
        expectedOutcome="Điểm giấc ngủ duy trì tốt, số lần thức giấc thấp.",
    ),
    ScenarioOption(
        id="fragmented_sleep",
        name="Ngủ phân mảnh",
        category="sleep",
        description="Thức giấc nhiều lần và tỷ lệ ngủ sâu giảm.",
        expectedOutcome="Điểm giấc ngủ giảm và xu hướng lịch sử xấu đi.",
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
