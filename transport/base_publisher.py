from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class PublishResult:
    ok: bool
    transport_mode: str
    target: str
    message_count: int
    ack_count: int = 0
    error: str | None = None


class Publisher(ABC):
    mode: str

    @abstractmethod
    def publish(self, messages: list[dict[str, Any]]) -> PublishResult:
        raise NotImplementedError
