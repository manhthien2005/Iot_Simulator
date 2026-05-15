"""HTTP client for the Health Backend risk/prediction API.

The ``HealthGuardAPIClient`` (aliased as ``TriggerAPIClient`` in
``dependencies.py``) sends vitals data to the Health Backend for ML
model inference when the rule engine decides a model call is needed.

Architecture reference: plans/alert-threshold-architecture-plan.md §5.1
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from pre_model_trigger.types import TriggerActionItem

logger = logging.getLogger(__name__)

# Type alias for the HTTP sender function injected from dependencies.py
# Signature: (endpoint: str, payload: str, headers: dict | None) -> int
HttpSenderFn = Callable[[str, str, dict[str, str] | None], int]


class HealthGuardAPIClient:
    """Thin HTTP client that forwards vitals to the Health Backend.

    The actual HTTP transport is injected via ``http_sender`` so that
    the client is testable without real network calls.

    Parameters
    ----------
    base_url:
        Health Backend base URL (e.g. ``http://localhost:8000``).
    http_sender:
        Callable that performs the HTTP POST.  Signature:
        ``(endpoint, payload_json, headers) -> status_code``.

    Usage in ``dependencies.py``::

        api_client = HealthGuardAPIClient(
            base_url=self._health_backend_url,
            http_sender=self._http_sender,
        )
    """

    _PREDICT_PATH = "/api/v1/mobile/risk/calculate"
    _HEALTH_CHECK_PATH = "/api/health"

    def __init__(
        self,
        base_url: str,
        http_sender: HttpSenderFn,
        internal_secret: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http_sender = http_sender
        self._internal_secret = internal_secret

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def request_prediction(
        self,
        device_id: str,
        vitals: dict[str, Any],
        persona: dict[str, Any] | None = None,
        db_device_id: int | None = None,
    ) -> list[TriggerActionItem]:
        """Send a risk-calculation request to the Health Backend.

        Parameters
        ----------
        device_id:
            Simulator device identifier (used for logging only).
        vitals:
            Current vitals snapshot (ignored by backend — it fetches
            vitals directly from its DB).
        persona:
            Optional patient profile metadata (ignored by backend).
        db_device_id:
            **Required for a successful call.** The bound integer device
            ID in the Health Backend DB.  If ``None`` the request is
            skipped and an empty list is returned.

        Returns
        -------
        list[TriggerActionItem]
            Actions derived from the prediction response.  Returns an
            empty list when the backend is unreachable, returns an
            error, or ``db_device_id`` is not provided.
        """
        if db_device_id is None:
            logger.debug(
                "request_prediction skipped for device %s: db_device_id not provided",
                device_id,
            )
            return []

        endpoint = f"{self._base_url}{self._PREDICT_PATH}"
        payload: dict[str, Any] = {"device_id": db_device_id}
        payload_json = json.dumps(payload)
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-Internal-Service": "iot-simulator",
        }
        if self._internal_secret:
            headers["X-Internal-Secret"] = self._internal_secret

        try:
            status_code = self._http_sender(endpoint, payload_json, headers)
        except Exception as exc:
            logger.warning(
                "Health prediction request failed for device %s: %s",
                device_id,
                exc,
            )
            return []

        if 200 <= status_code < 300:
            logger.debug(
                "Health prediction OK for device %s (status=%d)",
                device_id,
                status_code,
            )
            # The backend processes asynchronously; the response body
            # is not parsed here.  The orchestrator treats a 2xx as
            # "model call dispatched successfully."
            return [TriggerActionItem(
                action_type="model_call",
                severity="SEND_TO_RISK_MODEL",
                message=f"Health prediction dispatched (status={status_code})",
                source="healthguard_client",
                metadata={
                    "device_id": device_id,
                    "status_code": str(status_code),
                },
                reason_codes=["MODEL_CALL_DISPATCHED"],
            )]

        logger.warning(
            "Health prediction returned non-2xx for device %s: status=%d",
            device_id,
            status_code,
        )
        return []

    def health_check(self) -> bool:
        """Ping the Health Backend health endpoint.

        Returns ``True`` if the backend responds with 2xx.
        """
        endpoint = f"{self._base_url}{self._HEALTH_CHECK_PATH}"
        try:
            status_code = self._http_sender(endpoint, "", None)
            return 200 <= status_code < 300
        except Exception:
            return False


__all__ = ["HealthGuardAPIClient"]
