from __future__ import annotations

import os
from threading import RLock
from time import monotonic
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class SimAdminService:
    """Direct database operations for simulator admin device management."""

    _ADMIN_LIST_CACHE_TTL_SECONDS = max(
        float(os.environ.get("SIM_ADMIN_DB_DEVICE_CACHE_TTL_SECONDS", "30")),
        0.0,
    )
    _admin_list_cache_lock = RLock()
    _admin_list_cache_expires_at = 0.0
    _admin_list_cache_rows: tuple[dict[str, Any], ...] | None = None

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

    @staticmethod
    def _normalize_optional_string(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

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
        row = db.execute(
            text(SimAdminService._DEVICE_DETAIL_SQL),
            {"device_id": device_id},
        ).mappings().first()
        return dict(row) if row is not None else None

    @staticmethod
    def _check_duplicate_identity(
        *,
        serial_number: str | None,
        mqtt_client_id: str | None,
        db: Session,
    ) -> None:
        if not serial_number and not mqtt_client_id:
            return

        row = db.execute(
            text(
                """
                SELECT id
                FROM devices
                WHERE deleted_at IS NULL
                  AND (
                    (:serial_number IS NOT NULL AND serial_number = :serial_number)
                    OR (:mqtt_client_id IS NOT NULL AND mqtt_client_id = :mqtt_client_id)
                  )
                LIMIT 1
                """
            ),
            {
                "serial_number": serial_number,
                "mqtt_client_id": mqtt_client_id,
            },
        ).mappings().first()

        if row is not None:
            raise ValueError("Device identity already exists (duplicate serial_number or mqtt_client_id)")

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

        rows = db.execute(text(cls._ADMIN_LIST_SQL)).mappings().all()
        devices = [dict(row) for row in rows]

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
    def create_device(
        db: Session,
        *,
        device_name: str,
        device_type: str = "smartwatch",
        serial_number: str | None = None,
        mqtt_client_id: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        normalized_name = device_name.strip()
        normalized_serial = SimAdminService._normalize_optional_string(serial_number)
        normalized_mqtt = SimAdminService._normalize_optional_string(mqtt_client_id)

        if not normalized_name:
            raise ValueError("device_name must not be empty")

        SimAdminService._check_duplicate_identity(
            serial_number=normalized_serial,
            mqtt_client_id=normalized_mqtt,
            db=db,
        )

        row = db.execute(
            text(
                """
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
            ),
            {
                "user_id": user_id,
                "device_name": normalized_name,
                "device_type": device_type,
                "serial_number": normalized_serial,
                "mqtt_client_id": normalized_mqtt,
            },
        ).mappings().first()

        if row is None:
            db.rollback()
            raise ValueError("Failed to create device")

        db.commit()
        SimAdminService.invalidate_admin_list_cache()
        created = SimAdminService._fetch_device(int(row["id"]), db)
        if created is None:
            raise ValueError("Failed to reload device after creation")
        return created

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
        row = db.execute(
            text(
                """
                UPDATE devices
                SET deleted_at = NOW(), is_active = FALSE, updated_at = NOW()
                WHERE id = :device_id
                  AND deleted_at IS NULL
                RETURNING id
                """
            ),
            {"device_id": device_id},
        ).mappings().first()

        if row is None:
            db.rollback()
            return False

        db.commit()
        SimAdminService.invalidate_admin_list_cache()
        return True

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
            db.rollback()
