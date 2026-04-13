from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from api_server.dependencies import SimulatorRuntime, get_runtime
from api_server.schemas import CreateSessionRequest, SessionInfo

router = APIRouter(tags=["sessions"])


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

