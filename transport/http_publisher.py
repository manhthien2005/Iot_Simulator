from __future__ import annotations

from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .base_publisher import PublishResult, Publisher
from .json_utils import json_dumps


class HttpPublisher(Publisher):
    mode = "http"

    def __init__(
        self,
        endpoint: str,
        *,
        sender: Callable[[str, str], int] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self._sender = sender or self._default_sender
        self._headers: dict[str, str] = headers or {}

    def publish(self, messages: list[dict[str, Any]]) -> PublishResult:
        payload = json_dumps({"messages": messages})
        try:
            if self._headers:
                status_code = self._sender(self.endpoint, payload, self._headers)
            else:
                status_code = self._sender(self.endpoint, payload)
        except Exception as exc:  # pragma: no cover - network path not used in tests
            return PublishResult(
                ok=False,
                transport_mode=self.mode,
                target=self.endpoint,
                message_count=len(messages),
                error=str(exc),
            )
        ok = 200 <= status_code < 300
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
