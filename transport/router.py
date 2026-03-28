from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base_publisher import PublishResult
from .http_publisher import HttpPublisher
from .mqtt_publisher import MqttPublisher


@dataclass
class RoutedPublishResult:
    primary: PublishResult
    fallback: PublishResult | None = None


class TransportRouter:
    def __init__(
        self,
        mqtt_publisher: MqttPublisher,
        http_publisher: HttpPublisher,
    ) -> None:
        self.mqtt_publisher = mqtt_publisher
        self.http_publisher = http_publisher

    def publish(self, messages: list[dict[str, Any]], mode: str = "mqtt") -> RoutedPublishResult:
        normalized_mode = mode.strip().lower()
        if normalized_mode == "http":
            return RoutedPublishResult(primary=self.http_publisher.publish(messages))

        primary = self.mqtt_publisher.publish(messages)
        if primary.ok:
            return RoutedPublishResult(primary=primary)

        fallback = self.http_publisher.publish(messages)
        return RoutedPublishResult(primary=primary, fallback=fallback)
