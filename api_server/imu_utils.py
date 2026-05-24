"""IMU window response utilities — normalise mobile BE responses to AIPrediction."""

from __future__ import annotations

from typing import Any

from api_server.schemas import AIPrediction
from api_server.utils import _safe_float


_BAND_TO_RISK_BAND: dict[str, str] = {
    "critical": "critical",
    "critical_fall": "critical",
    "warning": "warning",
    "possible_fall": "warning",
    "likely_fall": "warning",
    "normal": "normal",
    "unknown": "normal",
}

_BAND_TO_LABEL: dict[str, str] = {
    "critical": "critical_fall",
    "critical_fall": "critical_fall",
    "warning": "likely_fall",
    "likely_fall": "likely_fall",
    "possible_fall": "possible_fall",
    "normal": "normal",
    "unknown": "normal",
}

_BAND_PHRASE_VI: dict[str, str] = {
    "critical": "té ngã nghiêm trọng",
    "warning": "khả năng té ngã",
    "normal": "không có dấu hiệu té ngã",
}


def _build_synthetic_fall_explanation(
    *,
    risk_band: str,
    probability: float,
    predicted_fall: bool,
    model_request_id: Any,
) -> str:
    phrase = _BAND_PHRASE_VI.get(risk_band, _BAND_PHRASE_VI["normal"])
    pct = int(round(probability * 100))
    base = f"AI đánh giá: {phrase} (xác suất {pct}%)."
    if predicted_fall and risk_band != "critical":
        base += " Mức xác suất chưa đủ cao để escalate SOS."
    request_id = str(model_request_id or "").strip()
    if request_id:
        base += f" Trace: {request_id[:8]}…"
    return base


def _normalise_imu_window_response(
    response: dict[str, Any] | None,
    *,
    predicted_at: str,
) -> AIPrediction:
    """Project ImuWindowResponse into AIPrediction."""
    if not isinstance(response, dict):
        return AIPrediction(
            label="normal", probability=0.0, confidence=0.0, riskBand="normal",
            requiresAttention=False, highPriorityAlert=False,
            explanationSummary="Mobile BE không trả phản hồi — đang dùng ngưỡng pre-trigger.",
            topFeatures=[], predictedAt=predicted_at, modelStatus="offline",
            failureReason="transport_error",
        )

    status = str(response.get("status") or "").strip().lower()
    if status != "ok":
        return AIPrediction(
            label="normal", probability=0.0, confidence=0.0, riskBand="normal",
            requiresAttention=False, highPriorityAlert=False,
            explanationSummary="AI model offline — đang dùng ngưỡng pre-trigger để quyết định cảnh báo.",
            topFeatures=[], predictedAt=predicted_at, modelStatus="offline",
            failureReason="model_unavailable" if status == "model_unavailable" else "validation_422",
        )

    probability = max(0.0, min(1.0, _safe_float(response.get("fall_probability"), 0.0) or 0.0))
    band_raw = str(response.get("prediction_band") or "unknown").strip().lower()
    risk_band = _BAND_TO_RISK_BAND.get(band_raw, "normal")
    label = _BAND_TO_LABEL.get(band_raw, "normal")
    requires_attention = bool(response.get("requires_attention"))
    predicted_fall = bool(response.get("predicted_fall"))
    high_priority_alert = (risk_band == "critical") and (probability >= 0.8 or predicted_fall)

    raw_fall_event_id = response.get("fall_event_id")
    fall_event_id: int | None = (
        raw_fall_event_id if isinstance(raw_fall_event_id, int)
        else int(raw_fall_event_id.strip()) if isinstance(raw_fall_event_id, str) and raw_fall_event_id.strip().isdigit()
        else None
    )
    raw_request_id = response.get("model_request_id")
    model_request_id: str | None = (
        raw_request_id.strip() if isinstance(raw_request_id, str) and raw_request_id.strip() else None
    )

    explanation = _build_synthetic_fall_explanation(
        risk_band=risk_band, probability=probability,
        predicted_fall=predicted_fall, model_request_id=model_request_id,
    )
    return AIPrediction(
        label=label,  # type: ignore[arg-type]
        probability=probability, confidence=probability,
        riskBand=risk_band,  # type: ignore[arg-type]
        requiresAttention=requires_attention, highPriorityAlert=high_priority_alert,
        explanationSummary=explanation, topFeatures=[], predictedAt=predicted_at,
        modelStatus="ok", fallEventId=fall_event_id, modelRequestId=model_request_id,
    )


def _coerce_float_list(value: Any) -> list[float]:
    """Best-effort conversion of *value* to list[float]."""
    if value is None:
        return []
    try:
        iterator = iter(value)  # type: ignore[arg-type]
    except TypeError:
        cast = _safe_float(value, None)
        return [cast] if cast is not None else []
    out: list[float] = []
    for item in iterator:
        cast = _safe_float(item, None)
        if cast is not None:
            out.append(cast)
    return out
