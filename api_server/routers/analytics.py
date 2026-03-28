from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from Iot_Simulator.api_server.dependencies import SimulatorRuntime, get_runtime
from Iot_Simulator.api_server.schemas import (
    RiskInjectRequest,
    RiskScoreResponse,
    RiskTriggerRequest,
    SleepSessionResponse,
)

router = APIRouter(tags=["analytics"])


@router.get("/analytics/sleep", response_model=SleepSessionResponse)
def get_sleep_session(
    device_id: str = Query(..., alias="deviceId"),
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> SleepSessionResponse:
    try:
        return runtime.sleep_session(device_id)
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


@router.post("/analytics/risk/trigger", status_code=status.HTTP_204_NO_CONTENT)
def trigger_risk(
    request: RiskTriggerRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> Response:
    try:
        runtime.trigger_risk_calculation(request)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
