from __future__ import annotations

import os as _os
import time as _time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from Iot_Simulator.api_server.db import get_db
    from Iot_Simulator.api_server.dependencies import SimulatorRuntime, get_runtime
    from Iot_Simulator.api_server.middleware.auth import require_admin_key
    from Iot_Simulator.api_server.schemas import (
        AdminAssignUserRequest,
        AdminBatchActivateItem,
        AdminDeviceActionResponse,
        AdminDeviceAssignResponse,
        AdminDeviceResponse,
        AdminUserProfileResponse,
        AdminUserResponse,
        BatchActivateRequest,
        AdminCreateDeviceSimRequest,
        BindDeviceRequest,
        BindDeviceResponse,
        CreateDeviceRequest,
        LinkedCaregiverItem,
        LinkedCaregiversResponse,
        SimulatedDevice,
    )
    from Iot_Simulator.api_server.sim_admin_service import SimAdminService
except ModuleNotFoundError:
    from api_server.db import get_db
    from api_server.dependencies import SimulatorRuntime, get_runtime
    from api_server.middleware.auth import require_admin_key
    from api_server.schemas import (
        AdminAssignUserRequest,
        AdminBatchActivateItem,
        AdminDeviceActionResponse,
        AdminDeviceAssignResponse,
        AdminDeviceResponse,
        AdminUserProfileResponse,
        AdminUserResponse,
        BatchActivateRequest,
        AdminCreateDeviceSimRequest,
        BindDeviceRequest,
        BindDeviceResponse,
        CreateDeviceRequest,
        LinkedCaregiverItem,
        LinkedCaregiversResponse,
        SimulatedDevice,
    )
    from api_server.sim_admin_service import SimAdminService

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


@_admin_router.get("/admin/db-devices", response_model=list[AdminDeviceResponse])
def list_db_devices(
    runtime: SimulatorRuntime = Depends(get_runtime),
    db: Session = Depends(get_db),
) -> list[AdminDeviceResponse]:
    """Load all devices from production DB, enriched with sim runtime status."""
    devices = SimAdminService.list_admin_devices(db)
    running_db_device_ids = runtime.device_service.list_running_db_device_ids()
    for device in devices:
        device["is_sim_running"] = int(device["id"]) in running_db_device_ids
    return [AdminDeviceResponse.model_validate(d) for d in devices]


@_admin_router.post("/admin/db-devices", response_model=AdminDeviceResponse, status_code=status.HTTP_201_CREATED)
def create_db_device(
    payload: AdminCreateDeviceSimRequest,
    db: Session = Depends(get_db),
) -> AdminDeviceResponse:
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
    auto_serial = payload.serial_number or f"SIM-{safe_name.upper()[:8]}-{suffix}"

    try:
        raw = SimAdminService.create_device(
            db,
            device_name=payload.device_name,
            device_type=payload.device_type,
            serial_number=auto_serial,
            mqtt_client_id=auto_mqtt,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AdminDeviceResponse.model_validate(raw)


@_admin_router.post("/admin/db-devices/{device_id}/assign", response_model=AdminDeviceAssignResponse)
def assign_db_device(
    device_id: int,
    payload: AdminAssignUserRequest,
    db: Session = Depends(get_db),
) -> AdminDeviceAssignResponse:
    """Assign an existing device to a user by email."""
    user = SimAdminService.find_user_by_email(payload.user_email, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User not found: {payload.user_email}")
    if not user.get("is_active"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User {payload.user_email} is inactive")

    result = SimAdminService.assign_device(device_id, int(user["id"]), db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")
    return AdminDeviceAssignResponse.model_validate(
        {**result, "user_email": user["email"], "message": f"Assigned to {user['email']}"}
    )


@_admin_router.post("/admin/db-devices/{device_id}/activate", response_model=AdminDeviceActionResponse)
def activate_db_device(
    device_id: int,
    runtime: SimulatorRuntime = Depends(get_runtime),
    db: Session = Depends(get_db),
) -> AdminDeviceActionResponse:
    """Activate a DB device and start its simulator session."""
    try:
        result = SimAdminService.activate_device(device_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")

    runtime.device_service._ensure_sim_session_for_db_device(device_id, result)
    return AdminDeviceActionResponse.model_validate({**result, "message": "Device activated"})


@_admin_router.post("/admin/db-devices/batch-activate", response_model=list[AdminBatchActivateItem])
def batch_activate_db_devices(
    payload: BatchActivateRequest,
    runtime: SimulatorRuntime = Depends(get_runtime),
    db: Session = Depends(get_db),
) -> list[AdminBatchActivateItem]:
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
    return [AdminBatchActivateItem.model_validate(r) for r in results]


@_admin_router.post("/admin/db-devices/{device_id}/deactivate", response_model=AdminDeviceActionResponse)
def deactivate_db_device(
    device_id: int,
    runtime: SimulatorRuntime = Depends(get_runtime),
    db: Session = Depends(get_db),
) -> AdminDeviceActionResponse:
    """Deactivate a DB device and stop its simulator session."""
    result = SimAdminService.deactivate_device(device_id, db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Device {device_id} not found")

    runtime.device_service._stop_sim_session_for_db_device(device_id)
    return AdminDeviceActionResponse.model_validate({**result, "message": "Device deactivated"})


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


@_admin_router.get("/admin/users/search", response_model=AdminUserResponse)
def search_user(email: str, db: Session = Depends(get_db)) -> AdminUserResponse:
    """Find a user by email directly from the production DB."""
    user = SimAdminService.find_user_by_email(email, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User not found: {email}")
    return AdminUserResponse.model_validate(user)


@_admin_router.get("/admin/users/{user_id}/profile", response_model=AdminUserProfileResponse)
def get_user_profile(user_id: int, db: Session = Depends(get_db)) -> AdminUserProfileResponse:
    """Return a user's full profile (demographics + medical info + emergency contacts).

    Consumed by the simulator-web Session page profile card.  Returns 404
    when the user is missing or soft-deleted.
    """
    profile = SimAdminService.get_user_profile(user_id, db)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
    return AdminUserProfileResponse.model_validate(profile)


@_admin_router.get("/admin/users/{user_id}/caregivers", response_model=LinkedCaregiversResponse)
def get_user_caregivers(user_id: int, db: Session = Depends(get_db)) -> LinkedCaregiversResponse:
    """Return accepted caregivers linked to *user_id* with FCM token status.

    ADR-024 Phase 7 S16 — consumed by simulator-web LinkedCaregiverPanel.
    """
    rows = db.execute(
        text("""
            SELECT
                u.id              AS user_id,
                u.full_name,
                u.email,
                u.avatar_url,
                ur.relationship_type,
                ur.primary_relationship_label AS relationship_label,
                EXISTS(
                    SELECT 1 FROM user_push_tokens pt
                    WHERE pt.user_id = u.id AND pt.is_active = true
                ) AS has_active_fcm_token
            FROM users u
            JOIN user_relationships ur ON ur.caregiver_id = u.id
            WHERE ur.patient_id    = :patient_id
              AND ur.status        = 'accepted'
              AND ur.deleted_at    IS NULL
              AND u.deleted_at     IS NULL
            ORDER BY ur.is_primary DESC, u.full_name
        """),
        {"patient_id": user_id},
    ).mappings().all()

    caregivers = [LinkedCaregiverItem(**dict(row)) for row in rows]
    return LinkedCaregiversResponse(patient_id=user_id, caregivers=caregivers)


# ---------------------------------------------------------------------------
# Phase 1 Personalization proxy
# ---------------------------------------------------------------------------
# Sim web cần xem trạng thái cá nhân hóa của user để demo viên đối chiếu
# input (sim sinh) vs output (backend personalization). Endpoint này KHÔNG
# tự tính — chỉ proxy sang health_system FastAPI ở
# ``HEALTH_SYSTEM_BASE_URL`` (default http://127.0.0.1:8002). Trả 502 nếu
# backend không reachable, 404 nếu user không có data.

_HEALTH_SYSTEM_BASE_URL = _os.environ.get(
    "HEALTH_SYSTEM_BASE_URL", "http://127.0.0.1:8002"
).rstrip("/")


@_admin_router.get("/admin/users/{user_id}/personalization")
def get_user_personalization(user_id: int) -> dict:
    """Read-only proxy to health_system personalization snapshot.

    Sim web hiển thị baseline + adaptive thresholds + NEWS2-Lite + trend
    slopes để đối chiếu input vs output cá nhân hóa.

    Phase 1 minimal: tải latest detail report của user, extract field
    ``personalization``. Ổn định cho demo (3 user Bảo/Mai/Phúc đã seed).
    """
    upstream = (
        f"{_HEALTH_SYSTEM_BASE_URL}/api/v1/mobile/analysis/risk-reports?limit=1"
    )
    headers = {"X-Target-Profile-Id": str(user_id)}
    try:
        with httpx.Client(timeout=5.0) as client:
            list_resp = client.get(upstream, headers=headers)
        if list_resp.status_code == 404:
            raise HTTPException(status_code=404, detail="No risk report yet for user")
        if list_resp.status_code >= 500:
            raise HTTPException(
                status_code=502,
                detail=f"health_system upstream {list_resp.status_code}",
            )
        items = list_resp.json() if list_resp.status_code == 200 else []
        if not isinstance(items, list) or not items:
            raise HTTPException(status_code=404, detail="No risk report yet for user")
        report_id = items[0].get("id")
        if report_id is None:
            raise HTTPException(status_code=404, detail="Latest report has no id")

        detail_url = (
            f"{_HEALTH_SYSTEM_BASE_URL}/api/v1/mobile/analysis/risk-reports/"
            f"{report_id}"
        )
        with httpx.Client(timeout=5.0) as client:
            detail_resp = client.get(detail_url, headers=headers)
        if detail_resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"health_system detail {detail_resp.status_code}",
            )
        detail_json = detail_resp.json()
        personalization = detail_json.get("personalization")
        if personalization is None:
            return {
                "enabled": False,
                "baseline_status": "disabled",
                "baselines": {},
                "adaptive_thresholds": {},
                "news2_lite": None,
                "trend_slopes": {},
                "hard_floor_violations": [],
                "personal_context_message": None,
            }
        return personalization
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"health_system unreachable: {exc}",
        ) from exc


# Merge admin sub-router into main router so all routes are exposed together
router.include_router(_admin_router)
