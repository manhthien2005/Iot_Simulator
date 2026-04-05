from __future__ import annotations

import json as _json
import logging
import os
from typing import Any
from urllib.parse import quote, urlencode

import httpx


logger = logging.getLogger(__name__)


class BackendAdminClientError(RuntimeError):
    def __init__(
        self,
        *,
        method: str,
        path: str,
        status_code: int | None = None,
        body: str | None = None,
        reason: str | None = None,
    ) -> None:
        parts = [f"{method} {path}"]
        if status_code is not None:
            parts.append(f"HTTP {status_code}")
        if reason:
            parts.append(reason)
        if body:
            parts.append(body)
        super().__init__(" -> ".join(parts))
        self.method = method
        self.path = path
        self.status_code = status_code
        self.body = body
        self.reason = reason


class BackendAdminClient:
    _TIMEOUT_SECONDS = 10

    def __init__(self, base_url: str | None = None) -> None:
        self._backend_root = self._resolve_backend_base_url(base_url)
        self._base = f"{self._backend_root}/mobile/admin"
        # Reusable sync client with connection pooling
        self._sync_client = httpx.Client(
            base_url=self._base,
            timeout=httpx.Timeout(self._TIMEOUT_SECONDS),
            headers={"X-Internal-Service": "iot-simulator"},
        )
        # Lazy-initialized async client (created on first async call)
        self._async_client: httpx.AsyncClient | None = None

    def _ensure_async_client(self) -> httpx.AsyncClient:
        """Lazily create the async client to avoid event-loop issues at init time."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self._base,
                timeout=httpx.Timeout(self._TIMEOUT_SECONDS),
                headers={"X-Internal-Service": "iot-simulator"},
            )
        return self._async_client

    @staticmethod
    def _resolve_backend_base_url(base_url: str | None = None) -> str:
        raw = base_url
        if raw is None:
            raw = os.environ.get("HEALTH_BACKEND_URL", "http://localhost:8000")
        normalized = raw.strip().rstrip("/")
        return normalized or "http://localhost:8000"

    @staticmethod
    def _headers(*, has_body: bool) -> dict[str, str]:
        headers: dict[str, str] = {}
        if has_body:
            headers["Content-Type"] = "application/json"
        return headers

    # ------------------------------------------------------------------
    # Sync transport (httpx.Client — connection-pooled, non-blocking-friendly)
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        allow_statuses: set[int] | None = None,
    ) -> Any:
        extra_headers = self._headers(has_body=body is not None)
        content: bytes | None = None
        if body is not None:
            content = _json.dumps(body).encode("utf-8")

        try:
            response = self._sync_client.request(
                method,
                path,
                content=content,
                headers=extra_headers,
            )
        except httpx.ConnectError as exc:
            raise BackendAdminClientError(
                method=method,
                path=path,
                reason=str(exc),
            ) from exc
        except httpx.TimeoutException as exc:
            raise BackendAdminClientError(
                method=method,
                path=path,
                reason=f"timeout: {exc}",
            ) from exc

        if response.status_code >= 400:
            if allow_statuses and response.status_code in allow_statuses:
                return None
            raise BackendAdminClientError(
                method=method,
                path=path,
                status_code=response.status_code,
                body=response.text or None,
            )

        raw = response.content
        if not raw:
            return None
        return _json.loads(raw.decode("utf-8"))

    # ------------------------------------------------------------------
    # Async transport (httpx.AsyncClient — non-blocking for event loop)
    # ------------------------------------------------------------------

    async def _arequest(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        allow_statuses: set[int] | None = None,
    ) -> Any:
        client = self._ensure_async_client()
        extra_headers = self._headers(has_body=body is not None)
        content: bytes | None = None
        if body is not None:
            content = _json.dumps(body).encode("utf-8")

        try:
            response = await client.request(
                method,
                path,
                content=content,
                headers=extra_headers,
            )
        except httpx.ConnectError as exc:
            raise BackendAdminClientError(
                method=method,
                path=path,
                reason=str(exc),
            ) from exc
        except httpx.TimeoutException as exc:
            raise BackendAdminClientError(
                method=method,
                path=path,
                reason=f"timeout: {exc}",
            ) from exc

        if response.status_code >= 400:
            if allow_statuses and response.status_code in allow_statuses:
                return None
            raise BackendAdminClientError(
                method=method,
                path=path,
                status_code=response.status_code,
                body=response.text or None,
            )

        raw = response.content
        if not raw:
            return None
        return _json.loads(raw.decode("utf-8"))

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the sync client and release pooled connections."""
        self._sync_client.close()

    async def aclose(self) -> None:
        """Close the async client and release pooled connections."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    # ------------------------------------------------------------------
    # Sync public API (backward-compatible)
    # ------------------------------------------------------------------

    def list_devices(self, user_id: int | None = None) -> list[dict[str, Any]]:
        query = ""
        if user_id is not None:
            query = "?" + urlencode({"user_id": user_id})
        result = self._request("GET", f"/devices{query}")
        return result if isinstance(result, list) else []

    def create_device(
        self,
        *,
        device_name: str,
        device_type: str = "smartwatch",
        serial_number: str | None = None,
        mqtt_client_id: str | None = None,
        model: str | None = None,
        user_email: str | None = None,
        firmware_version: str | None = None,
        mac_address: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "device_name": device_name,
            "device_type": device_type,
            "serial_number": serial_number,
            "mqtt_client_id": mqtt_client_id,
            "model": model,
            "user_email": user_email,
            "firmware_version": firmware_version,
            "mac_address": mac_address,
        }
        return self._request("POST", "/devices", body=payload)

    def update_device(self, device_id: int, **kwargs: Any) -> dict[str, Any]:
        allowed_fields = {
            "device_name",
            "firmware_version",
            "battery_level",
            "signal_strength",
        }
        payload = {
            key: value
            for key, value in kwargs.items()
            if key in allowed_fields and value is not None
        }
        return self._request("PATCH", f"/devices/{device_id}", body=payload)

    def delete_device(self, device_id: int) -> dict[str, Any]:
        return self._request("DELETE", f"/devices/{device_id}")

    def assign_device(self, device_id: int, email: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/devices/{device_id}/assign",
            body={"user_email": email},
        )

    def activate_device(self, device_id: int) -> dict[str, Any]:
        return self._request("POST", f"/devices/{device_id}/activate")

    def deactivate_device(self, device_id: int) -> dict[str, Any]:
        return self._request("POST", f"/devices/{device_id}/deactivate")

    def update_heartbeat(
        self,
        device_id: int,
        battery_level: int | None = None,
        signal_strength: int | None = None,
    ) -> dict[str, Any] | None:
        try:
            return self._request(
                "POST",
                f"/devices/{device_id}/heartbeat",
                body={
                    "battery_level": battery_level,
                    "signal_strength": signal_strength,
                },
            )
        except Exception as exc:
            logger.warning("Heartbeat update failed for device %s: %s", device_id, exc)
            return None

    def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        quoted_email = quote(email, safe="")
        result = self._request(
            "GET",
            f"/users/search?email={quoted_email}",
            allow_statuses={404},
        )
        return result if isinstance(result, dict) else None

    # ------------------------------------------------------------------
    # Async public API (mirrors sync API for async callers)
    # ------------------------------------------------------------------

    async def alist_devices(self, user_id: int | None = None) -> list[dict[str, Any]]:
        query = ""
        if user_id is not None:
            query = "?" + urlencode({"user_id": user_id})
        result = await self._arequest("GET", f"/devices{query}")
        return result if isinstance(result, list) else []

    async def aupdate_heartbeat(
        self,
        device_id: int,
        battery_level: int | None = None,
        signal_strength: int | None = None,
    ) -> dict[str, Any] | None:
        try:
            return await self._arequest(
                "POST",
                f"/devices/{device_id}/heartbeat",
                body={
                    "battery_level": battery_level,
                    "signal_strength": signal_strength,
                },
            )
        except Exception as exc:
            logger.warning("Async heartbeat update failed for device %s: %s", device_id, exc)
            return None

    async def afind_user_by_email(self, email: str) -> dict[str, Any] | None:
        quoted_email = quote(email, safe="")
        result = await self._arequest(
            "GET",
            f"/users/search?email={quoted_email}",
            allow_statuses={404},
        )
        return result if isinstance(result, dict) else None


_client_singleton: BackendAdminClient | None = None


def get_backend_admin_client() -> BackendAdminClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = BackendAdminClient()
    return _client_singleton


def reset_backend_admin_client_for_tests() -> None:
    global _client_singleton
    _client_singleton = BackendAdminClient()
