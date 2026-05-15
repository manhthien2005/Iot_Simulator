from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from api_server.middleware.auth import require_admin_key

from api_server.dependencies import SimulatorRuntime, get_runtime
from api_server.schemas import (
    DbSleepHistoryRow,
    RiskInjectRequest,
    RiskScoreResponse,
    SleepSessionResponse,
)

router = APIRouter(dependencies=[Depends(require_admin_key)], tags=["analytics"])


@router.get("/analytics/sleep", response_model=SleepSessionResponse)
def get_sleep_session(
    device_id: str = Query(..., alias="deviceId"),
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> SleepSessionResponse:
    try:
        return runtime.sleep_session(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/analytics/sleep/history", response_model=list[DbSleepHistoryRow])
def get_sleep_history(
    device_id: str = Query(..., alias="deviceId"),
    days: int = Query(default=30, ge=1, le=90),
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> list[DbSleepHistoryRow]:
    try:
        return runtime.sleep_db_history(device_id=device_id, days=days)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/analytics/sleep/{device_id}/push", response_model=SleepSessionResponse)
def push_sleep_session(
    device_id: str,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> SleepSessionResponse:
    try:
        return runtime.push_sleep_session(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/analytics/risk", response_model=RiskScoreResponse)
def get_risk_score(
    device_id: str = Query(..., alias="deviceId"),
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> RiskScoreResponse:
    try:
        return runtime.risk_score(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/events/risk-inject", status_code=status.HTTP_204_NO_CONTENT)
def inject_risk(
    request: RiskInjectRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> Response:
    try:
        runtime.inject_risk_score(request)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ADR-020 Phase 7 S7: ``POST /analytics/risk/trigger`` disposed. The mobile
# BE auto-calls ``calculate_device_risk`` after every successful
# ``/telemetry/ingest`` (cooldown ``RISK_COOLDOWN_SECONDS``, default 60s)
# so an explicit on-demand trigger from the simulator is no longer needed.
# The runtime helpers ``trigger_risk_calculation`` + ``_trigger_risk_inference``
# were removed in the same slice.
