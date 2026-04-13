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
class TestApiSessions(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_for_tests()
        self.client = TestClient(app)
        create = self.client.post(
            "/api/sim/devices",
            json={"name": "Watch B", "type": "smartwatch", "persona_config": {"age": 35, "weight_kg": 70, "height_cm": 170, "seed": 3}},
        )
        self.device_id = create.json()["id"]

    def test_create_start_stop_session(self) -> None:
        created = self.client.post("/api/sim/sessions", json={"device_ids": [self.device_id], "speed": 1})
        self.assertEqual(created.status_code, 201)
        session_id = created.json()["id"]

        started = self.client.post(f"/api/sim/sessions/{session_id}/start")
        self.assertEqual(started.status_code, 204)

        listed = self.client.get("/api/sim/sessions")
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(any(item["id"] == session_id for item in listed.json()))

        stopped = self.client.post(f"/api/sim/sessions/{session_id}/stop")
        self.assertEqual(stopped.status_code, 204)


if __name__ == "__main__":
    unittest.main()

