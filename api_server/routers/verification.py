from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api_server.dependencies import SimulatorRuntime, get_runtime
from api_server.schemas import VerificationResult

router = APIRouter(tags=["verification"])


@router.get("/verification/latest", response_model=VerificationResult)
def latest_verification(
    session_id: str = Query(..., alias="sessionId"),
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> VerificationResult:
    try:
        return runtime.verification(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

