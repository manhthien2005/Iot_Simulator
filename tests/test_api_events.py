from __future__ import annotations

import unittest

try:
    from fastapi.testclient import TestClient

    from api_server.dependencies import reset_runtime_for_tests
    from api_server.main import app

    FASTAPI_READY = True
except Exception:
    FASTAPI_READY = False


@unittest.skipUnless(FASTAPI_READY, "FastAPI runtime is not available")
class TestApiEvents(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_for_tests()
        self.client = TestClient(app)
        device = self.client.post(
            "/api/sim/devices",
            json={"name": "Watch C", "type": "smartwatch", "persona_config": {"age": 29, "weight_kg": 63, "height_cm": 167, "seed": 4}},
        ).json()
        session = self.client.post("/api/sim/sessions", json={"device_ids": [device["id"]], "speed": 1}).json()
        self.device_id = device["id"]
        self.session_id = session["id"]
        self.client.post(f"/api/sim/sessions/{self.session_id}/start")

    def test_inject_fall_event(self) -> None:
        injected = self.client.post(
            "/api/sim/events",
            json={"device_id": self.device_id, "event_type": "fall_detected", "variant": "fall_1"},
        )
        self.assertEqual(injected.status_code, 204)

        verification = self.client.get(f"/api/sim/verification/latest?sessionId={self.session_id}")
        self.assertEqual(verification.status_code, 200)
        self.assertTrue(verification.json()["alertReceived"])


if __name__ == "__main__":
    unittest.main()

