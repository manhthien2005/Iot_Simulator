from __future__ import annotations

from fastapi import APIRouter, Depends

from Iot_Simulator.api_server.dependencies import SimulatorRuntime, get_runtime
from Iot_Simulator.api_server.schemas import DashboardSummary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(runtime: SimulatorRuntime = Depends(get_runtime)) -> DashboardSummary:
    return runtime.dashboard_summary()

