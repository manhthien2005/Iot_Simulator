from __future__ import annotations

from typing import Any, Callable

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover - optional dependency
    mqtt = None

from .base_publisher import PublishResult, Publisher
from .json_utils import json_dumps


class MqttPublisher(Publisher):
    mode = "mqtt"

    def __init__(
        self,
        topic_prefix: str,
        *,
        host: str = "localhost",
        port: int = 1883,
        keepalive: int = 60,
        qos: int = 0,
        connect_async: bool = True,
        client_factory: Callable[[], Any] | None = None,
        client: Callable[[str, str], bool] | None = None,
    ) -> None:
        self.topic_prefix = topic_prefix.rstrip("/")
        self.host = host
        self.port = port
        self.keepalive = keepalive
        self.qos = qos
        self._publish_callback = client
        self._client = None
        self._connect_error: str | None = None

        if self._publish_callback is not None:
            return

        if mqtt is None:
            self._connect_error = "paho_mqtt_not_installed"
            return

        factory = client_factory or mqtt.Client
        try:
            self._client = factory()
            if connect_async:
                self._client.connect_async(host, port, keepalive)
            else:
                self._client.connect(host, port, keepalive)
            self._client.loop_start()
        except Exception as exc:  # pragma: no cover - depends on broker runtime
            self._connect_error = str(exc)

    def publish(self, messages: list[dict[str, Any]]) -> PublishResult:
        ack_count = 0
        message_count = len(messages)
        try:
            if self._publish_callback is not None:
                for message in messages:
                    device_id = message.get("device_id", "unknown")
                    topic = f"{self.topic_prefix}/{device_id}"
                    payload = json_dumps(message)
                    if self._publish_callback(topic, payload):
                        ack_count += 1
                ok = ack_count == message_count
                return PublishResult(
                    ok=ok,
                    transport_mode=self.mode,
                    target=self.topic_prefix,
                    message_count=message_count,
                    ack_count=ack_count,
                    error=None if ok else "partial_mqtt_publish",
                )

            if self._connect_error:
                return PublishResult(
                    ok=False,
                    transport_mode=self.mode,
                    target=f"{self.host}:{self.port}",
                    message_count=message_count,
                    ack_count=0,
                    error=self._connect_error,
                )

            if self._client is None:
                return PublishResult(
                    ok=False,
                    transport_mode=self.mode,
                    target=f"{self.host}:{self.port}",
                    message_count=message_count,
                    ack_count=0,
                    error="mqtt_client_unavailable",
                )

            for message in messages:
                device_id = message.get("device_id", "unknown")
                topic = f"{self.topic_prefix}/{device_id}"
                payload = json_dumps(message)
                result = self._client.publish(topic, payload, qos=self.qos)
                if getattr(result, "rc", 1) == 0:
                    ack_count += 1
        except Exception as exc:
            return PublishResult(
                ok=False,
                transport_mode=self.mode,
                target=f"{self.host}:{self.port}",
                message_count=message_count,
                ack_count=ack_count,
                error=str(exc),
            )
        ok = ack_count == message_count
        return PublishResult(
            ok=ok,
            transport_mode=self.mode,
            target=f"{self.host}:{self.port}",
            ack_count=ack_count,
            message_count=message_count,
            error=None if ok else "partial_mqtt_publish",
        )
