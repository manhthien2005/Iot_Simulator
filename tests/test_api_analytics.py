from __future__ import annotations

import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient

    try:
        from Iot_Simulator.api_server.dependencies import SimulatorRuntime, reset_runtime_for_tests
        from Iot_Simulator.api_server.main import app
    except ModuleNotFoundError:
        from api_server.dependencies import SimulatorRuntime, reset_runtime_for_tests
        from api_server.main import app

    FASTAPI_READY = True
except Exception:
    FASTAPI_READY = False


@unittest.skipUnless(FASTAPI_READY, "FastAPI runtime is not available")
class TestApiAnalytics(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_for_tests()
        self.client = TestClient(app)
        device = self.client.post(
            "/api/v1/sim/devices",
            json={"name": "Watch Analytics", "type": "smartwatch", "persona_config": {"age": 40, "weight_kg": 71, "height_cm": 170, "seed": 8}},
        ).json()
        session = self.client.post("/api/v1/sim/sessions", json={"device_ids": [device["id"]], "speed": 1}).json()
        self.device_id = device["id"]
        self.session_id = session["id"]
        self.client.post(f"/api/v1/sim/sessions/{self.session_id}/start")

    def test_sleep_session_available(self) -> None:
        response = self.client.get(f"/api/v1/sim/analytics/sleep?deviceId={self.device_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(payload["realismMode"], {"fallback", "real", "edf"})
        self.assertGreater(len(payload["phases"]), 0)
        self.assertGreater(len(payload["history"]), 0)

    def test_sleep_session_get_does_not_push_sleep_data(self) -> None:
        with patch.object(SimulatorRuntime, "_push_sleep_to_backend") as push_mock:
            response = self.client.get(f"/api/v1/sim/analytics/sleep?deviceId={self.device_id}")

        self.assertEqual(response.status_code, 200)
        push_mock.assert_not_called()

    def test_sleep_push_endpoint_pushes_explicitly(self) -> None:
        with patch.object(SimulatorRuntime, "_push_sleep_to_backend") as push_mock:
            response = self.client.post(f"/api/v1/sim/analytics/sleep/{self.device_id}/push")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["deviceId"], self.device_id)
        push_mock.assert_called_once()

    def test_risk_trigger_endpoint_disposed(self) -> None:
        # ADR-020 Phase 7 S7: ``POST /analytics/risk/trigger`` was removed.
        # The mobile BE now auto-calls ``calculate_device_risk`` after
        # every successful ``/telemetry/ingest`` (cooldown
        # ``RISK_COOLDOWN_SECONDS``, default 60s) so the simulator no
        # longer needs an on-demand trigger. ``GET /analytics/risk``
        # remains so the dashboard can still read the latest score.
        trigger = self.client.post(
            "/api/v1/sim/analytics/risk/trigger",
            json={"device_id": self.device_id},
        )
        self.assertEqual(trigger.status_code, 404)

        score = self.client.get(f"/api/v1/sim/analytics/risk?deviceId={self.device_id}")
        self.assertEqual(score.status_code, 200)
        payload = score.json()
        self.assertGreaterEqual(payload["score"], 0.0)
        self.assertLessEqual(payload["score"], 1.0)

    def test_risk_inject(self) -> None:
        injected = self.client.post(
            "/api/v1/sim/events/risk-inject",
            json={"device_id": self.device_id, "risk_type": "cardiac", "risk_level": "HIGH", "score": 0.79},
        )
        self.assertEqual(injected.status_code, 204)
        risk = self.client.get(f"/api/v1/sim/analytics/risk?deviceId={self.device_id}").json()
        self.assertEqual(risk["riskLevel"], "HIGH")
        self.assertAlmostEqual(risk["score"], 0.79, places=2)


if __name__ == "__main__":
    unittest.main()
