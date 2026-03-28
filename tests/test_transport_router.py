from __future__ import annotations

import unittest

from Iot_Simulator.transport import HttpPublisher, MqttPublisher, TransportRouter


class TestTransportRouter(unittest.TestCase):
    def test_mqtt_success_keeps_primary(self) -> None:
        mqtt = MqttPublisher("devices/test", client=lambda topic, payload: True)
        http = HttpPublisher("http://localhost/ingest", sender=lambda endpoint, payload: 202)
        router = TransportRouter(mqtt, http)
        result = router.publish([{"device_id": "dev-1", "vitals": {"heart_rate": 72}}], mode="mqtt")
        self.assertTrue(result.primary.ok)
        self.assertIsNone(result.fallback)

    def test_mqtt_failure_falls_back_to_http(self) -> None:
        mqtt = MqttPublisher("devices/test", client=lambda topic, payload: (_ for _ in ()).throw(RuntimeError("broker down")))
        http = HttpPublisher("http://localhost/ingest", sender=lambda endpoint, payload: 200)
        router = TransportRouter(mqtt, http)
        result = router.publish([{"device_id": "dev-1", "vitals": {"heart_rate": 72}}], mode="mqtt")
        self.assertFalse(result.primary.ok)
        self.assertIsNotNone(result.fallback)
        self.assertTrue(result.fallback.ok)

    def test_http_mode_uses_http_directly(self) -> None:
        mqtt = MqttPublisher("devices/test", client=lambda topic, payload: True)
        http = HttpPublisher("http://localhost/ingest", sender=lambda endpoint, payload: 201)
        router = TransportRouter(mqtt, http)
        result = router.publish([{"device_id": "dev-1"}], mode="http")
        self.assertEqual(result.primary.transport_mode, "http")
        self.assertIsNone(result.fallback)


if __name__ == "__main__":
    unittest.main()
