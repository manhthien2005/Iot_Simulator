"""HTTP client for the simulator → backend mobile-telemetry surface.

Distinct from :class:`HealthGuardAPIClient` in
``healthguard_client.py`` (which talks to the older
``/api/risk/predict`` vitals dispatch path with a status-only sender).
This client targets the v0.8 mobile-telemetry routes:

* ``POST /api/v1/mobile/telemetry/imu-window`` — fall window ingest
  (slice 2b, this module's primary purpose).
* ``POST /api/v1/mobile/telemetry/sleep-risk`` — sleep ingest
  (slice 3a follow-up; method stub provided so tests can lock the URL
  shape now).

Both routes return JSON bodies with ``fall_event_id`` /
``model_request_id`` / ``risk_score_id`` fields that the simulator
needs for log correlation, so this client uses an HTTP sender that
returns ``(status_code, body)`` rather than the older status-only
form. The two senders co-exist in the codebase: ``HealthGuardAPIClient``
keeps its narrow contract; this client opts into the richer one.

Architecture reference: plan ``risk-core-final-completion-9ea607.md``
slice 2b.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sender contract
# ---------------------------------------------------------------------------

#: HTTP sender contract used by this client.
#:
#: ``(endpoint, payload_json, headers, timeout) -> (status_code, body_text)``.
#:
#: Status code ``< 0`` signals a transport-level failure (connection
#: refused, timeout). Status code ``>= 100`` is the HTTP response code.
#: ``body_text`` is the raw response body string (may be empty).
HttpSenderWithBodyFn = Callable[
    [str, str, dict[str, str] | None, float], tuple[int, str]
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

_IMU_WINDOW_PATH = "/api/v1/mobile/telemetry/imu-window"
_SLEEP_RISK_PATH = "/api/v1/mobile/telemetry/sleep-risk"

#: Default timeout for one POST. Backend's predict_fall path includes an
#: external model-api call so allow generous margin; production
#: ``ModelApiClient`` defaults to 5 s, the backend route adds maybe 100 ms
#: of FastAPI overhead on top.
DEFAULT_TIMEOUT_SECONDS: float = 8.0


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class MobileTelemetryClient:
    """Posts IMU windows + sleep records to the backend's mobile-telemetry
    surface and returns the parsed JSON response.

    Parameters
    ----------
    base_url:
        Health Backend base URL (e.g. ``http://localhost:8000``). The
        ``/api/v1/...`` paths are appended internally.
    http_sender:
        Injectable HTTP transport. Signature matches
        :data:`HttpSenderWithBodyFn`.
    timeout:
        Per-request timeout in seconds.

    Errors are logged + swallowed; the public methods return ``None``
    on any failure so callers can branch on "we got a result" vs
    "transport blew up" without try/except boilerplate.
    """

    def __init__(
        self,
        *,
        base_url: str,
        http_sender: HttpSenderWithBodyFn,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        internal_secret: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._http_sender = http_sender
        self._timeout = timeout
        self._internal_secret = internal_secret

    # ------------------------------------------------------------------
    # IMU window dispatch (slice 2b)
    # ------------------------------------------------------------------

    def submit_imu_window(
        self,
        *,
        device_id: str,
        window_data: list[dict[str, Any]],
        db_device_id: int,
        sampling_rate: int = 50,
    ) -> dict[str, Any] | None:
        """POST a 50-sample IMU window to ``/api/v1/mobile/telemetry/imu-window``.

        Returns the parsed JSON response on 2xx, or ``None`` on transport
        failure / non-2xx / malformed body. The shape of the success
        response is the backend's ``ImuWindowAccepted`` schema:

        * ``status`` — ``"persisted"`` | ``"model_unavailable"``
        * ``fall_event_id`` — int (only when ``status="persisted"``)
        * ``model_request_id`` — str | null
        * Additional fields (``predicted_fall``, ``risk_level``, etc.)

        Parameters
        ----------
        device_id:
            Stable simulator-side device id (logged on the backend for
            traceability — does NOT have to match ``db_device_id``).
        window_data:
            List of ``SensorSample``-shaped dicts. Length should match
            the model-api's ``fall_min_sequence_samples`` (50 by default);
            shorter windows will be rejected by the backend with HTTP 422.
        db_device_id:
            Numeric primary-key on the backend's ``devices`` table. The
            backend uses this for auth + persistence.
        sampling_rate:
            Hz. Defaults to 50 to match the model-api's expected input.
        """
        payload = {
            "device_id": device_id,
            "db_device_id": int(db_device_id),
            "sampling_rate": int(sampling_rate),
            "window_size": len(window_data),
            "data": window_data,
        }
        return self._post_json(_IMU_WINDOW_PATH, payload)

    # ------------------------------------------------------------------
    # Sleep dispatch — stubbed for slice 3a
    # ------------------------------------------------------------------

    def submit_sleep_record(
        self,
        *,
        record: dict[str, Any],
        db_device_id: int,
        db_user_id: int,
    ) -> dict[str, Any] | None:
        """POST a 40-field ``SleepRecord`` to ``/api/v1/mobile/telemetry/sleep-risk``.

        Provided as a stub so slice 3a (simulator sleep mapper) doesn't
        need to extend the client — only build the record and call this.
        Returns the same shape as the backend's ``SleepRiskAccepted``
        schema: ``{status, risk_score_id, model_request_id, ...}``.
        """
        payload = {
            "db_device_id": int(db_device_id),
            "db_user_id": int(db_user_id),
            "record": dict(record),
        }
        return self._post_json(_SLEEP_RISK_PATH, payload)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _post_json(
        self, path: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        endpoint = f"{self._base_url}{path}"
        body_str = json.dumps(payload, default=str)
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-Internal-Service": "iot-simulator",
        }
        if self._internal_secret:
            headers["X-Internal-Secret"] = self._internal_secret
        try:
            status, body_text = self._http_sender(
                endpoint, body_str, headers, self._timeout
            )
        except Exception as exc:  # noqa: BLE001 - swallow + log per docstring
            logger.warning("POST %s raised %r — treating as transport failure", endpoint, exc)
            return None
        if status < 0:
            logger.warning("POST %s reported transport failure: status=%d", endpoint, status)
            return None
        if not (200 <= status < 300):
            logger.warning(
                "POST %s returned non-2xx: status=%d body=%s",
                endpoint, status, _summarise(body_text),
            )
            return None
        try:
            parsed = json.loads(body_text) if body_text else {}
        except json.JSONDecodeError:
            logger.warning(
                "POST %s returned 2xx but body is not JSON: %s",
                endpoint, _summarise(body_text),
            )
            return None
        if not isinstance(parsed, dict):
            logger.warning(
                "POST %s returned 2xx JSON but not an object: %s",
                endpoint, _summarise(body_text),
            )
            return None
        return parsed


def _summarise(body: str | None, *, max_len: int = 200) -> str:
    """Truncate a response body for logging without exploding the log line."""
    if not body:
        return ""
    text = body.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...(truncated)"


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "HttpSenderWithBodyFn",
    "MobileTelemetryClient",
]
