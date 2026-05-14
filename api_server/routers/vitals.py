from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from api_server.middleware.auth import require_admin_key

from api_server.dependencies import SimulatorRuntime, get_runtime
from api_server.schemas import VitalsSample

router = APIRouter(dependencies=[Depends(require_admin_key)], tags=["vitals"])


@router.get("/vitals/latest", response_model=VitalsSample)
def latest_vitals(
    device_id: str = Query(..., alias="deviceId"),
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> VitalsSample:
    try:
        return runtime.vitals_service.latest_vitals(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

