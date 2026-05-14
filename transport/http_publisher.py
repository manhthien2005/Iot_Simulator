from __future__ import annotations

import logging
import time
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .base_publisher import PublishResult, Publisher
from .json_utils import json_dumps

logger = logging.getLogger(__name__)

_HTTP_PUBLISH_MAX_RETRIES = 3
_HTTP_PUBLISH_BACKOFF_BASE = 1  # seconds


class HttpPublisher(Publisher):
    mode = "http"

    def __init__(
        self,
        endpoint: str,
        *,
        sender: Callable[[str, str], int] | None = None,
        headers: dict[str, str] | None = None,
        internal_secret: str | None = None,
    ) -> None:
        self.endpoint = endpoint
        self._sender = sender or self._default_sender

        # IS-010: auto-inject internal service headers per ADR-005.
        merged: dict[str, str] = {"X-Internal-Service": "iot-simulator"}
        if internal_secret:
            merged["X-Internal-Secret"] = internal_secret
        if headers:
            merged.update(headers)
        self._headers = merged

    def publish(self, messages: list[dict[str, Any]]) -> PublishResult:
        """Publish messages with retry + exponential backoff (IS-011)."""
        payload = json_dumps({"messages": messages})
        last_exc: Exception | None = None
        status_code: int | None = None

        for attempt in range(1, _HTTP_PUBLISH_MAX_RETRIES + 1):
            try:
                status_code = self._sender(self.endpoint, payload, self._headers)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt < _HTTP_PUBLISH_MAX_RETRIES:
                    delay = _HTTP_PUBLISH_BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "HttpPublisher attempt %d/%d failed, retrying in %ds: %s",
                        attempt,
                        _HTTP_PUBLISH_MAX_RETRIES,
                        delay,
                        exc,
                    )
                    time.sleep(delay)

        if last_exc is not None:
            return PublishResult(
                ok=False,
                transport_mode=self.mode,
                target=self.endpoint,
                message_count=len(messages),
                error=str(last_exc),
            )

        ok = 200 <= (status_code or 0) < 300
        return PublishResult(
            ok=ok,
            transport_mode=self.mode,
            target=self.endpoint,
            message_count=len(messages),
            ack_count=len(messages) if ok else 0,
            error=None if ok else f"HTTP {status_code}",
        )

    @staticmethod
    def _default_sender(
        endpoint: str,
        payload: str,
        headers: dict[str, str] | None = None,
    ) -> int:
        merged = {"Content-Type": "application/json"}
        if headers:
            merged.update(headers)
        request = Request(
            endpoint,
            data=payload.encode("utf-8"),
            method="POST",
            headers=merged,
        )
        try:
            with urlopen(request, timeout=10) as response:
                return int(response.getcode() or 200)
        except HTTPError as exc:
            return int(exc.code)
