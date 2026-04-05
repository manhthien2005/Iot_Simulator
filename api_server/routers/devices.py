from __future__ import annotations

import time as _time

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from Iot_Simulator.api_server.db import get_db
from Iot_Simulator.api_server.dependencies import SimulatorRuntime, get_runtime
from Iot_Simulator.api_server.middleware.auth import require_admin_key
from Iot_Simulator.api_server.schemas import (
    AdminAssignUserRequest,
    BatchActivateRequest,
    AdminCreateDeviceSimRequest,
    BindDeviceRequest,
    BindDeviceResponse,
    CreateDeviceRequest,
    SimulatedDevice,
)
from Iot_Simulator.api_server.sim_admin_service import SimAdminService

router = APIRouter(tags=["devices"])

# Sub-router for admin endpoints — protected by API-key auth
_admin_router = APIRouter(
    tags=["admin-devices"],
    dependencies=[Depends(require_admin_key)],
)


@router.get("/devices", response_model=list[SimulatedDevice])
def list_devices(runtime: SimulatorRuntime = Depends(get_runtime)) -> list[SimulatedDevice]:
    return runtime.device_service.list_devices()


@router.post("/devices", response_model=SimulatedDevice, status_code=status.HTTP_201_CREATED)
def create_device(
    request: CreateDeviceRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> SimulatedDevice:
    return runtime.device_service.create_device(request)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: str, runtime: SimulatorRuntime = Depends(get_runtime)) -> Response:
    runtime.device_service.delete_device(device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/devices/{device_id}/bind", response_model=BindDeviceResponse)
def bind_device(
    device_id: str,
    payload: BindDeviceRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> BindDeviceResponse:
    try:
        device = runtime.device_service.bind_device(device_id, payload.db_device_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BindDeviceResponse(sim_device_id=device.id, db_device_id=device.bound_db_device_id, status="bound")


@router.delete("/devices/{device_id}/bind", response_model=BindDeviceResponse)
def unbind_device(device_id: str, runtime: SimulatorRuntime = Depends(get_runtime)) -> BindDeviceResponse:
    try:
        device = runtime.device_service.unbind_device(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return BindDeviceResponse(sim_device_id=device.id, db_device_id=device.bound_db_device_id, status="unbound")


@_admin_router.get("/admin/db-devices")
def list_db_devices(
    runtime: SimulatorRuntime = Depends(get_runtime),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Load all devices from production DB, enriched with sim runtime status."""
    devices = SimAdminService.list_admin_devices(db)
    running_db_device_ids = runtime.device_service.list_running_db_device_ids()
    for device in devices:
        device["is_sim_running"] = int(device["id"]) in running_db_device_ids
    return devices


@_admin_router.post("/admin/db-devices", status_code=status.HTTP_201_CREATED)
def create_db_device(
    payload: AdminCreateDeviceSimRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Create a new device directly in the production DB."""
    user_id = None
    if payload.user_email:
        user = SimAdminService.find_user_by_email(payload.user_email, db)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User not found: {payload.user_email}")
        if not user.get("is_active"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User {payload.user_email} is inactive")
        user_id = int(user["id"])

    suffix = str(int(_time.time()))[-6:]
    safe_name = "".join(ch if ch.isalnum() else "-" for ch in payload.device_name.lower()).strip("-") or "device"
    auto_mqtt = f"sim-{safe_name}-{suffix}"
    auto_serial = payload.serial_number or f"SIM-{auto_mqtt.upper()[:12]}"

    try:
        return SimAdminService.create_device(
            db,
            device_name=payload.device_name,
            device_type=payload.device_type,
            serial_number=auto_serial,
            mqtt_client_id=auto_mqtt,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@_admin_router.post("/admin/db-devices/{device_id}/assign")
def assign_db_device(
    device_id: int,
    payload: AdminAssignUserRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Assign an existing device to a user by email."""
    user = SimAdminService.find_user_by_email(payload.user_email, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User not found: {payload.user_email}")
    if not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User {payload.user_email} is inactive")

    result = SimAdminService.assign_device(device_id, int(user["id"]), db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")
    return {**result, "user_email": user["email"], "message": f"Assigned to {user['email']}"}


@_admin_router.post("/admin/db-devices/{device_id}/activate")
def activate_db_device(
    device_id: int,
    runtime: SimulatorRuntime = Depends(get_runtime),
    db: Session = Depends(get_db),
) -> dict:
    """Activate a DB device and start its simulator session."""
    try:
        result = SimAdminService.activate_device(device_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")

    runtime.device_service._ensure_sim_session_for_db_device(device_id, result)
    return {**result, "message": "Device activated"}


@_admin_router.post("/admin/db-devices/batch-activate")
def batch_activate_db_devices(
    payload: BatchActivateRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
    db: Session = Depends(get_db),
) -> list[dict]:
    results: list[dict] = []
    for device_id in payload.device_ids:
        try:
            result = SimAdminService.activate_device(device_id, db)
            if result is None:
                results.append({"id": device_id, "status": "not_found"})
                continue
            runtime.device_service._ensure_sim_session_for_db_device(device_id, result)
            results.append({**result, "status": "activated"})
        except ValueError as exc:
            results.append({"id": device_id, "status": "error", "detail": str(exc)})
        except Exception as exc:
            results.append({"id": device_id, "status": "error", "detail": str(exc)})
    return results


@_admin_router.post("/admin/db-devices/{device_id}/deactivate")
def deactivate_db_device(
    device_id: int,
    runtime: SimulatorRuntime = Depends(get_runtime),
    db: Session = Depends(get_db),
) -> dict:
    """Deactivate a DB device and stop its simulator session."""
    result = SimAdminService.deactivate_device(device_id, db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")

    runtime.device_service._stop_sim_session_for_db_device(device_id)
    return {**result, "message": "Device deactivated"}


@_admin_router.delete("/admin/db-devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_db_device(
    device_id: int,
    runtime: SimulatorRuntime = Depends(get_runtime),
    db: Session = Depends(get_db),
) -> Response:
    """Soft-delete a DB device and stop its simulator session."""
    runtime.device_service._stop_sim_session_for_db_device(device_id)
    deleted = SimAdminService.delete_device(device_id, db)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@_admin_router.get("/admin/users/search")
def search_user(email: str, db: Session = Depends(get_db)) -> dict:
    """Find a user by email directly from the production DB."""
    user = SimAdminService.find_user_by_email(email, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User not found: {email}")
    return user


# Merge admin sub-router into main router so all routes are exposed together
router.include_router(_admin_router)
