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
class TestApiDevices(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_for_tests()
        self.client = TestClient(app)

    def test_device_crud(self) -> None:
        created = self.client.post(
            "/api/sim/devices",
            json={"name": "Watch A", "type": "smartwatch", "persona_config": {"age": 41, "weight_kg": 68, "height_cm": 171, "seed": 9}},
        )
        self.assertEqual(created.status_code, 201)
        device_id = created.json()["id"]

        listed = self.client.get("/api/sim/devices")
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(any(item["id"] == device_id for item in listed.json()))

        deleted = self.client.delete(f"/api/sim/devices/{device_id}")
        self.assertEqual(deleted.status_code, 204)

    def test_device_bind_unbind_flow(self) -> None:
        created = self.client.post(
            "/api/sim/devices",
            json={"name": "Watch B", "type": "smartwatch"},
        )
        self.assertEqual(created.status_code, 201)
        device_id = created.json()["id"]

        bound = self.client.post(
            f"/api/sim/devices/{device_id}/bind",
            json={"db_device_id": 101},
        )
        self.assertEqual(bound.status_code, 200)
        self.assertEqual(
            bound.json(),
            {"sim_device_id": device_id, "db_device_id": 101, "status": "bound"},
        )

        listed = self.client.get("/api/sim/devices")
        self.assertEqual(listed.status_code, 200)
        bound_device = next(item for item in listed.json() if item["id"] == device_id)
        self.assertEqual(bound_device["boundDbDeviceId"], 101)
        self.assertEqual(bound_device["bindStatus"], "bound")

        unbound = self.client.delete(f"/api/sim/devices/{device_id}/bind")
        self.assertEqual(unbound.status_code, 200)
        self.assertEqual(
            unbound.json(),
            {"sim_device_id": device_id, "db_device_id": None, "status": "unbound"},
        )

        listed_after = self.client.get("/api/sim/devices")
        self.assertEqual(listed_after.status_code, 200)
        unbound_device = next(item for item in listed_after.json() if item["id"] == device_id)
        self.assertIsNone(unbound_device["boundDbDeviceId"])
        self.assertEqual(unbound_device["bindStatus"], "unbound")


if __name__ == "__main__":
    unittest.main()
