from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api_server.dependencies import SimulatorRuntime, get_runtime
from api_server.schemas import AlertEvent, InjectEventRequest

router = APIRouter(tags=["events"])


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
@router.post("/events/inject", status_code=status.HTTP_204_NO_CONTENT)
def inject_event(
    request: InjectEventRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> Response:
    try:
        runtime.inject_event(request.device_id, request.event_type, request.variant)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/events/recent", response_model=list[AlertEvent])
def recent_events(
    limit: int = Query(default=10, ge=1, le=200),
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> list[AlertEvent]:
    return runtime.alert_service.recent_events(limit=limit)


@router.post("/events/fall", status_code=status.HTTP_204_NO_CONTENT)
def inject_fall_event(
    request: InjectEventRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> Response:
    try:
        runtime.inject_event(request.device_id, "fall_detected", request.variant or "confirmed")
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/events/device-status", status_code=status.HTTP_204_NO_CONTENT)
def inject_device_status(
    request: InjectEventRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> Response:
    try:
        runtime.inject_event(request.device_id, request.event_type, request.variant)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
