from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient

    from Iot_Simulator.api_server.dependencies import reset_runtime_for_tests
    from Iot_Simulator.api_server.main import app

    FASTAPI_READY = True
except Exception:
    FASTAPI_READY = False


@unittest.skipUnless(FASTAPI_READY, "FastAPI runtime is not available")
class TestApiAnalytics(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_for_tests()
        self.client = TestClient(app)
        device = self.client.post(
            "/api/sim/devices",
            json={"name": "Watch Analytics", "type": "smartwatch", "persona_config": {"age": 40, "weight_kg": 71, "height_cm": 170, "seed": 8}},
        ).json()
        session = self.client.post("/api/sim/sessions", json={"device_ids": [device["id"]], "speed": 1}).json()
        self.device_id = device["id"]
        self.session_id = session["id"]
        self.client.post(f"/api/sim/sessions/{self.session_id}/start")

    def test_sleep_session_available(self) -> None:
        response = self.client.get(f"/api/sim/analytics/sleep?deviceId={self.device_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(payload["realismMode"], {"fallback", "real", "edf"})
        self.assertGreater(len(payload["phases"]), 0)
        self.assertGreater(len(payload["history"]), 0)

    def test_risk_trigger_and_fetch(self) -> None:
        trigger = self.client.post("/api/sim/analytics/risk/trigger", json={"device_id": self.device_id})
        self.assertEqual(trigger.status_code, 204)
        score = self.client.get(f"/api/sim/analytics/risk?deviceId={self.device_id}")
        self.assertEqual(score.status_code, 200)
        payload = score.json()
        self.assertGreaterEqual(payload["score"], 0.0)
        self.assertLessEqual(payload["score"], 1.0)
        self.assertGreater(len(payload["history"]), 0)

    def test_risk_inject(self) -> None:
        injected = self.client.post(
            "/api/sim/events/risk-inject",
            json={"device_id": self.device_id, "risk_type": "cardiac", "risk_level": "HIGH", "score": 0.79},
        )
        self.assertEqual(injected.status_code, 204)
        risk = self.client.get(f"/api/sim/analytics/risk?deviceId={self.device_id}").json()
        self.assertEqual(risk["riskLevel"], "HIGH")
        self.assertAlmostEqual(risk["score"], 0.79, places=2)


if __name__ == "__main__":
    unittest.main()
