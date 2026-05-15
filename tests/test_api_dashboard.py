from __future__ import annotations

import unittest
from unittest.mock import MagicMock

try:
    from fastapi.testclient import TestClient

    from api_server.dependencies import SessionRecord, SimulatorRuntime, reset_runtime_for_tests
    from api_server.main import app

    FASTAPI_READY = True
except Exception:
    FASTAPI_READY = False


@unittest.skipUnless(FASTAPI_READY, "FastAPI runtime is not available")
class TestApiDashboard(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_for_tests()
        self.client = TestClient(app)
        device = self.client.post(
            "/api/v1/sim/devices",
            json={"name": "Watch E", "type": "smartwatch", "persona_config": {"age": 31, "weight_kg": 65, "height_cm": 169, "seed": 6}},
        ).json()
        session = self.client.post("/api/v1/sim/sessions", json={"device_ids": [device["id"]], "speed": 1}).json()
        self.device_id = device["id"]
        self.session_id = session["id"]
        self.client.post(f"/api/v1/sim/sessions/{self.session_id}/start")

    def test_dashboard_summary(self) -> None:
        response = self.client.get("/api/v1/sim/dashboard/summary")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("totalDevices", payload)
        self.assertIn("activeDevices", payload)

    def test_registry_status(self) -> None:
        response = self.client.get("/api/v1/sim/registry/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("hasStressData", payload)
        self.assertIn("stressSource", payload)
        self.assertEqual(payload["stressSource"], "real:WESAD" if payload["hasStressData"] else "mock")

    def test_recent_events_endpoint(self) -> None:
        self.client.post("/api/v1/sim/events", json={"device_id": self.device_id, "event_type": "device_offline"})
        response = self.client.get("/api/v1/sim/events/recent?limit=5")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 1)

def test_dashboard_summary_uses_measured_publish_latency() -> None:
    runtime = SimulatorRuntime()
    runtime.sessions["session-1"] = SessionRecord(
        id="session-1",
        device_ids=[],
        speed=1,
        simulator=MagicMock(),
        status="running",
        last_publish_count=1,
        last_publish_latency_ms=42,
    )
    runtime.sessions["session-2"] = SessionRecord(
        id="session-2",
        device_ids=[],
        speed=1,
        simulator=MagicMock(),
        status="running",
        last_publish_count=1,
        last_publish_latency_ms=58,
    )

    summary = runtime.dashboard_summary()

    assert summary.avgLatencyMs == 50


if __name__ == "__main__":
    unittest.main()
