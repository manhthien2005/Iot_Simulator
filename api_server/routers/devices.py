from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from Iot_Simulator.api_server.dependencies import SimulatorRuntime, get_runtime
from Iot_Simulator.api_server.schemas import BindDeviceRequest, BindDeviceResponse, CreateDeviceRequest, SimulatedDevice

router = APIRouter(tags=["devices"])


@router.get("/devices", response_model=list[SimulatedDevice])
def list_devices(runtime: SimulatorRuntime = Depends(get_runtime)) -> list[SimulatedDevice]:
    return runtime.list_devices()


@router.post("/devices", response_model=SimulatedDevice, status_code=status.HTTP_201_CREATED)
def create_device(
    request: CreateDeviceRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> SimulatedDevice:
    return runtime.create_device(request)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: str, runtime: SimulatorRuntime = Depends(get_runtime)) -> Response:
    runtime.delete_device(device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/devices/{device_id}/bind", response_model=BindDeviceResponse)
def bind_device(
    device_id: str,
    payload: BindDeviceRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> BindDeviceResponse:
    try:
        device = runtime.bind_device(device_id, payload.db_device_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BindDeviceResponse(sim_device_id=device.id, db_device_id=device.bound_db_device_id, status="bound")


@router.delete("/devices/{device_id}/bind", response_model=BindDeviceResponse)
def unbind_device(device_id: str, runtime: SimulatorRuntime = Depends(get_runtime)) -> BindDeviceResponse:
    try:
        device = runtime.unbind_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BindDeviceResponse(sim_device_id=device.id, db_device_id=device.bound_db_device_id, status="unbound")
