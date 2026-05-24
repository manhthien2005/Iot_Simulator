"""Repository layer that wraps raw SQL queries for the ``devices`` table.

This module extracts the data-access concerns out of
:class:`~api_server.sim_admin_service.SimAdminService` and maps every row
to a typed Pydantic model (:class:`AdminDeviceResponse`) instead of
returning bare ``dict[str, Any]``.

Only the **most common** queries are wrapped here (list / create / delete).
The remaining queries stay in ``SimAdminService`` until a later phase.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from api_server.schemas import AdminDeviceResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL constants (extracted verbatim from SimAdminService)
# ---------------------------------------------------------------------------

_DEVICE_DETAIL_SQL = """
    SELECT
        d.id,
        d.uuid,
        d.user_id,
        u.email AS user_email,
        u.full_name AS user_full_name,
        u.height_cm,
        u.weight_kg,
        u.date_of_birth,
        u.gender,
        d.device_name,
        d.device_type,
        d.model,
        d.firmware_version,
        d.serial_number,
        d.mac_address,
        d.mqtt_client_id,
        d.is_active,
        d.battery_level,
        d.signal_strength,
        d.last_seen_at,
        d.last_sync_at,
        d.registered_at,
        d.updated_at,
        d.deleted_at
    FROM devices d
    LEFT JOIN users u ON u.id = d.user_id
    WHERE d.id = :device_id
      AND d.deleted_at IS NULL
    LIMIT 1
"""

_ADMIN_LIST_SQL = """
    SELECT
        d.id,
        d.uuid,
        d.user_id,
        u.email AS user_email,
        u.full_name AS user_full_name,
        u.height_cm,
        u.weight_kg,
        u.date_of_birth,
        u.gender,
        d.device_name,
        d.device_type,
        d.model,
        d.firmware_version,
        d.serial_number,
        d.mac_address,
        d.mqtt_client_id,
        d.is_active,
        d.battery_level,
        d.signal_strength,
        d.last_seen_at,
        d.last_sync_at,
        d.registered_at,
        d.updated_at,
        d.deleted_at
    FROM devices d
    LEFT JOIN users u ON u.id = d.user_id
    WHERE d.deleted_at IS NULL
    ORDER BY d.is_active DESC, d.registered_at DESC
    LIMIT 200
"""

# IS-008: dedicated SQL for active-only listing — single JOIN query, eliminates
# N+1 pattern in SimAdminService.list_active_devices.
_ADMIN_LIST_ACTIVE_SQL = """
    SELECT
        d.id,
        d.uuid,
        d.user_id,
        u.email AS user_email,
        u.full_name AS user_full_name,
        u.height_cm,
        u.weight_kg,
        u.date_of_birth,
        u.gender,
        d.device_name,
        d.device_type,
        d.model,
        d.firmware_version,
        d.serial_number,
        d.mac_address,
        d.mqtt_client_id,
        d.is_active,
        d.battery_level,
        d.signal_strength,
        d.last_seen_at,
        d.last_sync_at,
        d.registered_at,
        d.updated_at,
        d.deleted_at
    FROM devices d
    LEFT JOIN users u ON u.id = d.user_id
    WHERE d.deleted_at IS NULL
      AND d.is_active = TRUE
    ORDER BY d.registered_at DESC
    LIMIT 200
"""

_CREATE_DEVICE_SQL = """
    INSERT INTO devices (
        user_id,
        device_name,
        device_type,
        serial_number,
        mqtt_client_id,
        is_active,
        registered_at,
        updated_at
    )
    VALUES (
        :user_id,
        :device_name,
        :device_type,
        :serial_number,
        :mqtt_client_id,
        FALSE,
        NOW(),
        NOW()
    )
    RETURNING id
"""

_SOFT_DELETE_SQL = """
    UPDATE devices
    SET deleted_at = NOW(), is_active = FALSE, updated_at = NOW()
    WHERE id = :device_id
      AND deleted_at IS NULL
    RETURNING id
"""

_CHECK_DUPLICATE_SQL = """
    SELECT id
    FROM devices
    WHERE deleted_at IS NULL
      AND (
        (:serial_number IS NOT NULL AND serial_number = :serial_number)
        OR (:mqtt_client_id IS NOT NULL AND mqtt_client_id = :mqtt_client_id)
      )
    LIMIT 1
"""


class DeviceRepository:
    """Typed data-access layer for the ``devices`` table.

    All public methods return Pydantic models rather than raw dicts.
    The repository is stateless — pass a SQLAlchemy ``Session`` per call.
    """

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def fetch_device(device_id: int, db: Session) -> AdminDeviceResponse | None:
        """Load a single device by primary key, returning a typed model."""
        row = (
            db.execute(text(_DEVICE_DETAIL_SQL), {"device_id": device_id})
            .mappings()
            .first()
        )
        if row is None:
            return None
        return AdminDeviceResponse.model_validate(dict(row))

    @staticmethod
    def list_admin_devices(db: Session, *, active_only: bool = False) -> list[AdminDeviceResponse]:
        """Return non-deleted devices (up to 200), typed.

        Parameters
        ----------
        active_only:
            When True, filter ``is_active = TRUE`` (single-query, no N+1).
            Used by ``SimAdminService.list_active_devices`` (IS-008 fix).
        """
        sql = _ADMIN_LIST_ACTIVE_SQL if active_only else _ADMIN_LIST_SQL
        rows = db.execute(text(sql)).mappings().all()
        return [AdminDeviceResponse.model_validate(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    def create_device(
        db: Session,
        *,
        device_name: str,
        device_type: str = "smartwatch",
        serial_number: str | None = None,
        mqtt_client_id: str | None = None,
        user_id: int | None = None,
    ) -> AdminDeviceResponse:
        """Insert a device row and return the fully-loaded typed model.

        Raises :class:`ValueError` on duplicate identity or empty name.
        """
        normalized_name = device_name.strip()
        if not normalized_name:
            raise ValueError("device_name must not be empty")

        _norm_str = lambda v: (v.strip() or None) if v else None  # noqa: E731
        normalized_serial = _norm_str(serial_number)
        normalized_mqtt = _norm_str(mqtt_client_id)

        # Duplicate check
        if normalized_serial or normalized_mqtt:
            dup = (
                db.execute(
                    text(_CHECK_DUPLICATE_SQL),
                    {
                        "serial_number": normalized_serial,
                        "mqtt_client_id": normalized_mqtt,
                    },
                )
                .mappings()
                .first()
            )
            if dup is not None:
                raise ValueError(
                    "Device identity already exists (duplicate serial_number or mqtt_client_id)"
                )

        row = (
            db.execute(
                text(_CREATE_DEVICE_SQL),
                {
                    "user_id": user_id,
                    "device_name": normalized_name,
                    "device_type": device_type,
                    "serial_number": normalized_serial,
                    "mqtt_client_id": normalized_mqtt,
                },
            )
            .mappings()
            .first()
        )

        if row is None:
            db.rollback()
            raise ValueError("Failed to create device")

        db.commit()
        created = DeviceRepository.fetch_device(int(row["id"]), db)
        if created is None:
            raise ValueError("Failed to reload device after creation")
        return created

    @staticmethod
    def delete_device(device_id: int, db: Session) -> bool:
        """Soft-delete a device. Returns ``True`` if a row was affected."""
        row = (
            db.execute(text(_SOFT_DELETE_SQL), {"device_id": device_id})
            .mappings()
            .first()
        )
        if row is None:
            db.rollback()
            return False
        db.commit()
        return True
