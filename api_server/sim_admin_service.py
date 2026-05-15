from __future__ import annotations

import logging
import os
from threading import RLock
from time import monotonic
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from Iot_Simulator.api_server.repositories.device_repository import DeviceRepository
except ModuleNotFoundError:
    from api_server.repositories.device_repository import DeviceRepository

logger = logging.getLogger(__name__)


class SimAdminService:
    """Direct database operations for simulator admin device management."""

    _ADMIN_LIST_CACHE_TTL_SECONDS = max(
        float(os.environ.get("SIM_ADMIN_DB_DEVICE_CACHE_TTL_SECONDS", "30")),
        0.0,
    )
    _admin_list_cache_lock = RLock()
    _admin_list_cache_expires_at = 0.0
    _admin_list_cache_rows: tuple[dict[str, Any], ...] | None = None

    # HIGH #4 fix: removed duplicate _DEVICE_DETAIL_SQL — now delegates
    # to DeviceRepository.fetch_device() which owns the canonical SQL.
    # Removed dead code: _ADMIN_LIST_SQL (delegated to DeviceRepository),
    # _normalize_optional_string, _check_duplicate_identity

    @staticmethod
    def _copy_rows(rows: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    @classmethod
    def invalidate_admin_list_cache(cls) -> None:
        with cls._admin_list_cache_lock:
            cls._admin_list_cache_rows = None
            cls._admin_list_cache_expires_at = 0.0

    @staticmethod
    def _fetch_device(device_id: int, db: Session) -> dict[str, Any] | None:
        """HIGH #4 fix: delegate to DeviceRepository to eliminate SQL duplication."""
        typed = DeviceRepository.fetch_device(device_id, db)
        if typed is None:
            return None
        return typed.model_dump()

    @staticmethod
    def list_all_devices(db: Session, user_id: int | None = None) -> list[dict[str, Any]]:
        rows = db.execute(
            text(
                """
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
                  AND (:user_id IS NULL OR d.user_id = :user_id)
                ORDER BY d.is_active DESC, d.registered_at DESC
                LIMIT 200
                """
            ),
            {"user_id": user_id},
        ).mappings().all()

        return [dict(row) for row in rows]

    @classmethod
    def list_admin_devices(cls, db: Session) -> list[dict[str, Any]]:
        ttl_seconds = cls._ADMIN_LIST_CACHE_TTL_SECONDS
        if ttl_seconds > 0:
            now = monotonic()
            with cls._admin_list_cache_lock:
                if cls._admin_list_cache_rows is not None and now < cls._admin_list_cache_expires_at:
                    return cls._copy_rows(cls._admin_list_cache_rows)

        # Delegate to DeviceRepository for typed query execution
        typed_devices = DeviceRepository.list_admin_devices(db)
        devices = [d.model_dump() for d in typed_devices]

        if ttl_seconds > 0:
            with cls._admin_list_cache_lock:
                cls._admin_list_cache_rows = tuple(dict(row) for row in devices)
                cls._admin_list_cache_expires_at = monotonic() + ttl_seconds

        return devices

    @staticmethod
    def find_user_by_email(email: str, db: Session) -> dict[str, Any] | None:
        row = db.execute(
            text(
                """
                SELECT id, email, full_name, is_active
                FROM users
                WHERE lower(email) = :email
                  AND deleted_at IS NULL
                LIMIT 1
                """
            ),
            {"email": email.strip().lower()},
        ).mappings().first()
        return dict(row) if row is not None else None

    @staticmethod
    def get_user_profile(user_id: int, db: Session) -> dict[str, Any] | None:
        """Aggregate the full user profile for the simulator-web Session page.

        Joins `users` (demographics + medical info) with `emergency_contacts`
        in a single service call so the FE renders the profile card without
        chaining requests.  Returns ``None`` when the user is missing or
        soft-deleted.

        The shape matches ``AdminUserProfileResponse`` — array columns that
        are NULL in Postgres are coerced to empty lists, ``date_of_birth``
        is serialised to an ISO date string, and ``weight_kg`` is normalised
        to a Python ``float`` (the column is ``DECIMAL`` which SQLAlchemy
        returns as ``Decimal``).
        """
        user_row = db.execute(
            text(
                """
                SELECT id, email, full_name, phone, avatar_url,
                       date_of_birth, gender, height_cm, weight_kg,
                       blood_type, medical_conditions, medications, allergies
                FROM users
                WHERE id = :user_id
                  AND deleted_at IS NULL
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).mappings().first()

        if user_row is None:
            return None

        contact_rows = db.execute(
            text(
                """
                SELECT id, name, phone, relationship, priority
                FROM emergency_contacts
                WHERE user_id = :user_id
                ORDER BY priority ASC, id ASC
                """
            ),
            {"user_id": user_id},
        ).mappings().all()

        profile: dict[str, Any] = dict(user_row)

        # Normalise scalar types so Pydantic + JSON serialise cleanly.
        dob = profile.get("date_of_birth")
        if dob is not None:
            profile["date_of_birth"] = dob.isoformat() if hasattr(dob, "isoformat") else str(dob)
        weight = profile.get("weight_kg")
        if weight is not None:
            profile["weight_kg"] = float(weight)

        # Postgres TEXT[] columns return None when never written.  The FE
        # contract is "always an array, possibly empty" so coerce here.
        for array_field in ("medical_conditions", "medications", "allergies"):
            if profile.get(array_field) is None:
                profile[array_field] = []

        profile["emergency_contacts"] = [dict(row) for row in contact_rows]
        return profile

    @staticmethod
    def create_device(
        db: Session,
        *,
        device_name: str,
        device_type: str = "smartwatch",
        serial_number: str | None = None,
        mqtt_client_id: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        # Delegate to DeviceRepository (handles validation, dup-check, insert)
        typed = DeviceRepository.create_device(
            db,
            device_name=device_name,
            device_type=device_type,
            serial_number=serial_number,
            mqtt_client_id=mqtt_client_id,
            user_id=user_id,
        )
        SimAdminService.invalidate_admin_list_cache()
        return typed.model_dump()

    @staticmethod
    def assign_device(device_id: int, user_id: int, db: Session) -> dict[str, Any] | None:
        row = db.execute(
            text(
                """
                UPDATE devices
                SET user_id = :user_id, updated_at = NOW()
                WHERE id = :device_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"device_id": device_id, "user_id": user_id},
        ).mappings().first()

        if row is None:
            db.rollback()
            return None

        db.commit()
        SimAdminService.invalidate_admin_list_cache()
        return SimAdminService._fetch_device(device_id, db)

    @staticmethod
    def activate_device(device_id: int, db: Session) -> dict[str, Any] | None:
        target = db.execute(
            text(
                """
                SELECT user_id
                FROM devices
                WHERE id = :device_id
                  AND deleted_at IS NULL
                LIMIT 1
                """
            ),
            {"device_id": device_id},
        ).mappings().first()

        if target is None:
            return None

        user_id = target["user_id"]
        if user_id is None:
            # IS-009: rollback session before raise to avoid dirty state if caller
            # has prior pending mutations in same transaction scope.
            db.rollback()
            raise ValueError(f"Device {device_id} is not assigned to a user")

        db.execute(
            text(
                """
                UPDATE devices
                SET is_active = FALSE, updated_at = NOW()
                WHERE user_id = :user_id
                  AND id != :device_id
                  AND deleted_at IS NULL
                """
            ),
            {"user_id": user_id, "device_id": device_id},
        )

        row = db.execute(
            text(
                """
                UPDATE devices
                SET is_active = TRUE, updated_at = NOW()
                WHERE id = :device_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"device_id": device_id},
        ).mappings().first()

        if row is None:
            db.rollback()
            return None

        db.commit()
        SimAdminService.invalidate_admin_list_cache()
        return SimAdminService._fetch_device(device_id, db)

    @staticmethod
    def deactivate_device(device_id: int, db: Session) -> dict[str, Any] | None:
        row = db.execute(
            text(
                """
                UPDATE devices
                SET is_active = FALSE, updated_at = NOW()
                WHERE id = :device_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"device_id": device_id},
        ).mappings().first()

        if row is None:
            db.rollback()
            return None

        db.commit()
        SimAdminService.invalidate_admin_list_cache()
        return SimAdminService._fetch_device(device_id, db)

    @staticmethod
    def delete_device(device_id: int, db: Session) -> bool:
        # Delegate to DeviceRepository
        deleted = DeviceRepository.delete_device(device_id, db)
        if deleted:
            SimAdminService.invalidate_admin_list_cache()
        return deleted

    @staticmethod
    def update_heartbeat(
        device_id: int,
        db: Session,
        *,
        battery_level: int | None = None,
        signal_strength: int | None = None,
    ) -> None:
        """Update heartbeat fields from the runtime tick loop without raising outward."""
        try:
            db.execute(
                text(
                    """
                    UPDATE devices
                    SET
                        last_seen_at = NOW(),
                        battery_level = COALESCE(:battery_level, battery_level),
                        signal_strength = COALESCE(:signal_strength, signal_strength),
                        updated_at = NOW()
                    WHERE id = :device_id
                      AND deleted_at IS NULL
                    """
                ),
                {
                    "device_id": device_id,
                    "battery_level": battery_level,
                    "signal_strength": signal_strength,
                },
            )
            db.commit()
        except Exception:
            logger.warning("Heartbeat update failed for device_id=%s, rolling back", device_id, exc_info=True)
            db.rollback()

    @staticmethod
    def list_active_devices(db: Session) -> list[dict[str, Any]]:
        """Return full device info for every active (non-deleted) device.

        IS-008 fix: single batch JOIN query (was 1 + N roundtrips).
        """
        typed = DeviceRepository.list_admin_devices(db, active_only=True)
        return [d.model_dump() for d in typed]
