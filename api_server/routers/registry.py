from __future__ import annotations

from fastapi import APIRouter, Depends

from Iot_Simulator.api_server.dependencies import SimulatorRuntime, get_runtime

router = APIRouter(tags=["registry"])


@router.get("/registry/status")
def registry_status(runtime: SimulatorRuntime = Depends(get_runtime)) -> dict[str, object]:
    return runtime.registry.status()
