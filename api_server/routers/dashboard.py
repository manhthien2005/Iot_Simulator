from __future__ import annotations

from fastapi import APIRouter, Depends
from api_server.middleware.auth import require_admin_key

from api_server.dependencies import SimulatorRuntime, get_runtime
from api_server.schemas import DashboardSummary

router = APIRouter(dependencies=[Depends(require_admin_key)], tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(runtime: SimulatorRuntime = Depends(get_runtime)) -> DashboardSummary:
    return runtime.dashboard_summary()

