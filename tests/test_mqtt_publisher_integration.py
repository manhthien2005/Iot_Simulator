from __future__ import annotations

import socket
import unittest
from importlib import util

from Iot_Simulator.transport.mqtt_publisher import MqttPublisher


def _has_paho() -> bool:
    return util.find_spec("paho.mqtt.client") is not None


def _broker_available(host: str = "localhost", port: int = 1883, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@unittest.skipUnless(_has_paho(), "paho-mqtt is not installed")
@unittest.skipUnless(_broker_available(), "MQTT broker localhost:1883 is not available")
class TestMqttPublisherIntegration(unittest.TestCase):
    def test_publish_to_local_broker(self) -> None:
        publisher = MqttPublisher("sim/test", host="localhost", port=1883, connect_async=False)
        result = publisher.publish([{"device_id": "device-1", "event_type": "integration_ping"}])
        self.assertTrue(result.ok)
        self.assertEqual(result.ack_count, 1)


if __name__ == "__main__":
    unittest.main()
