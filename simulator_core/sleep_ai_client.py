"""HTTP client for the local Sleep AI inference API.

This client targets **port 8001** (healthguard-model-api) for AI-based sleep
stage prediction.  Database persistence of sleep records is handled separately
by :mod:`api_server.dependencies` which POSTs to the health_system backend on
**port 8000** via ``/api/v1/mobile/telemetry/sleep``.

This dual-endpoint design is intentional:
  - Port 8001 → AI inference (sleep stage classification)
  - Port 8000 → DB storage  (sleep session persistence)
"""

from __future__ import annotations

import json
import logging
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)

# P2-3 (2026-05-18): once a transient network error flipped ``_available``
# to False, ``predict()`` short-circuited indefinitely. Reset the
# circuit-breaker after this many seconds so the next call probes the
# upstream again instead of staying stuck in the open state forever.
_RECOVERY_BACKOFF_SECONDS: float = 60.0


class SleepAIClient:
    """Small stdlib-only client with a self-resetting circuit breaker."""

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._available: bool | None = None
        self._unavailable_since: float | None = None
        self._internal_secret: str | None = os.getenv("INTERNAL_SERVICE_SECRET")

    def _build_headers(self) -> dict[str, str]:
        """Build request headers with internal service auth per ADR-005."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-Internal-Service": "iot-simulator",
        }
        if self._internal_secret:
            headers["X-Internal-Secret"] = self._internal_secret
        return headers

    def _mark_unavailable(self) -> None:
        self._available = False
        self._unavailable_since = time.monotonic()

    def _is_in_recovery_backoff(self) -> bool:
        """P2-3: stay short-circuited only until ``_RECOVERY_BACKOFF_SECONDS``
        elapse, then let the next call probe the upstream again."""
        if self._available is not False:
            return False
        if self._unavailable_since is None:
            return True
        return (time.monotonic() - self._unavailable_since) < _RECOVERY_BACKOFF_SECONDS

    def check_availability(self) -> bool:
        """Probe the model-info endpoint and update availability state."""
        request = Request(
            f"{self.base_url}/api/v1/sleep/model-info",
            method="GET",
            headers=self._build_headers(),
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                if int(response.getcode() or 200) >= 400:
                    self._mark_unavailable()
                    return False
                self._available = True
                self._unavailable_since = None
                return True
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, Exception) as exc:
            LOGGER.warning("Sleep AI health check failed: %s", exc)
            self._mark_unavailable()
            return False

    def predict(self, sleep_record: dict) -> dict | None:
        """Send one sleep record for inference and return the first prediction."""
        # P2-3: only short-circuit while still inside the backoff window.
        # After the backoff expires, fall through and let the request
        # probe the upstream again (success will reset the breaker).
        if self._is_in_recovery_backoff():
            return None

        payload = json.dumps({"backend": "onnx", "records": [sleep_record]}).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/v1/sleep/predict",
            data=payload,
            method="POST",
            headers=self._build_headers(),
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
                prediction = body["results"][0]
                self._available = True
                self._unavailable_since = None
                return prediction
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, Exception) as exc:
            LOGGER.warning("Sleep AI predict failed: %s", exc)
            self._mark_unavailable()
            return None
