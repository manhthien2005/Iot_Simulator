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
class TestApiScenarios(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_for_tests()
        self.client = TestClient(app)

    def test_list_scenarios(self) -> None:
        response = self.client.get("/api/sim/scenarios")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload), 8)
        categories = {item.get("category") for item in payload}
        self.assertTrue({"vitals", "fall", "sleep", "risk"}.issubset(categories))
        self.assertTrue(all(item.get("expectedOutcome") for item in payload))

    def test_apply_scenario_changes_vitals_profile(self) -> None:
        device = self.client.post("/api/sim/devices", json={"name": "Scenario Device", "type": "smartwatch"}).json()
        session = self.client.post("/api/sim/sessions", json={"device_ids": [device["id"]], "speed": 1}).json()
        self.client.post(f"/api/sim/sessions/{session['id']}/start")

        normal = self.client.get("/api/sim/vitals/latest", params={"deviceId": device["id"]}).json()

        apply_hypoxia = self.client.post(
            "/api/sim/scenarios/apply",
            json={"device_id": device["id"], "scenario_id": "hypoxia_critical"},
        )
        self.assertEqual(apply_hypoxia.status_code, 204)

        hypoxia = self.client.get("/api/sim/vitals/latest", params={"deviceId": device["id"]}).json()

        self.assertLess(float(hypoxia["spo2"]), float(normal["spo2"]))
        self.assertGreater(float(hypoxia["heartRate"]), float(normal["heartRate"]))


if __name__ == "__main__":
    unittest.main()
