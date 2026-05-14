from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from api_server.middleware.auth import require_admin_key

from api_server.dependencies import SimulatorRuntime, get_runtime
from api_server.schemas import (
    CreateSessionRequest,
    FallState,
    MotionLatest,
    SessionInfo,
)

router = APIRouter(dependencies=[Depends(require_admin_key)], tags=["sessions"])


@router.get("/sessions", response_model=list[SessionInfo])
def list_sessions(runtime: SimulatorRuntime = Depends(get_runtime)) -> list[SessionInfo]:
    return [SessionInfo(**item) for item in runtime.list_sessions()]


@router.post("/sessions", response_model=SessionInfo, status_code=status.HTTP_201_CREATED)
def create_session(
    request: CreateSessionRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> SessionInfo:
    try:
        data = runtime.create_session(request.device_ids, int(request.speed))
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return SessionInfo(**data)


@router.post("/sessions/{session_id}/start", status_code=status.HTTP_204_NO_CONTENT)
def start_session(session_id: str, runtime: SimulatorRuntime = Depends(get_runtime)) -> Response:
    try:
        runtime.start_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop_session(session_id: str, runtime: SimulatorRuntime = Depends(get_runtime)) -> Response:
    try:
        runtime.stop_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Module C — Sessions / Fall Lab evidence surface.
# ---------------------------------------------------------------------------


@router.get("/sessions/{session_id}/motion/latest", response_model=MotionLatest)
def latest_motion(
    session_id: str,
    device_id: str = Query(..., alias="deviceId"),
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> MotionLatest:
    """Return the most recent motion window emitted for `deviceId`.

    Used by the Sessions page motion preview — replaces the previous
    `pseudoMetric()` synthetic preview with real dataset arrays.
    """
    try:
        return runtime.motion_latest(session_id, device_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/sessions/{session_id}/fall-state", response_model=FallState)
def fall_state(
    session_id: str,
    device_id: str = Query(..., alias="deviceId"),
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> FallState:
    """Return the operator-visible fall pipeline state for `deviceId`.

    Drives the Sessions page Fall Lab countdown bar — replaces the
    FE-only `setInterval` with a BE-derived `countdownRemainingSec`.
    """
    try:
        return runtime.fall_state(session_id, device_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

