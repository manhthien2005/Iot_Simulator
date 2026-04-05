from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import unittest

try:
    from fastapi.testclient import TestClient

    from Iot_Simulator.api_server.dependencies import get_runtime, reset_runtime_for_tests
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

    def test_push_sleep_for_date_rejects_today_and_future(self) -> None:
        today = datetime.now(timezone.utc).date()
        device = self.client.post("/api/sim/devices", json={"name": "Sleep API Device", "type": "smartwatch"}).json()

        today_response = self.client.post(
            "/api/sim/scenarios/sleep/push-date",
            json={"device_id": device["id"], "target_date": today.isoformat(), "scenario_id": "good_sleep_night"},
        )
        self.assertEqual(today_response.status_code, 422)
        self.assertIn("hôm nay hoặc tương lai", today_response.json()["detail"])

        future_response = self.client.post(
            "/api/sim/scenarios/sleep/push-date",
            json={
                "device_id": device["id"],
                "target_date": (today + timedelta(days=1)).isoformat(),
                "scenario_id": "good_sleep_night",
            },
        )
        self.assertEqual(future_response.status_code, 422)
        self.assertIn("hôm nay hoặc tương lai", future_response.json()["detail"])

    def test_push_sleep_for_date_rejects_older_than_one_year(self) -> None:
        today = datetime.now(timezone.utc).date()
        device = self.client.post("/api/sim/devices", json={"name": "Sleep API Device 2", "type": "smartwatch"}).json()

        response = self.client.post(
            "/api/sim/scenarios/sleep/push-date",
            json={
                "device_id": device["id"],
                "target_date": (today - timedelta(days=366)).isoformat(),
                "scenario_id": "good_sleep_night",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("cũ hơn 1 năm", response.json()["detail"])

    def test_push_sleep_for_date_returns_runtime_result(self) -> None:
        runtime = get_runtime()
        device = self.client.post("/api/sim/devices", json={"name": "Sleep API Device 3", "type": "smartwatch"}).json()
        target_date = date(2026, 3, 25)

        original = runtime.push_sleep_session_for_date
        runtime.push_sleep_session_for_date = lambda device_id, target_date, scenario_id="good_sleep_night": {
            "success": True,
            "target_date": target_date.isoformat(),
            "scenario_id": scenario_id,
            "duration_minutes": 360,
            "sleep_score": 88,
            "disorder_tags": ["age_related"],
            "was_overwritten": True,
            "message": "Updated",
        }
        try:
            response = self.client.post(
                "/api/sim/scenarios/sleep/push-date",
                json={
                    "device_id": device["id"],
                    "target_date": target_date.isoformat(),
                    "scenario_id": "elderly_normal",
                },
            )
        finally:
            runtime.push_sleep_session_for_date = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "success": True,
                "target_date": "2026-03-25",
                "scenario_id": "elderly_normal",
                "duration_minutes": 360,
                "sleep_score": 88,
                "disorder_tags": ["age_related"],
                "was_overwritten": True,
                "message": "Updated",
            },
        )

    def test_get_sleep_history_returns_runtime_rows(self) -> None:
        runtime = get_runtime()
        device = self.client.post("/api/sim/devices", json={"name": "Sleep API Device 4", "type": "smartwatch"}).json()

        original = runtime.sleep_db_history
        runtime.sleep_db_history = lambda device_id, days=30: [
            {
                "date": "2026-03-25",
                "score": 88,
                "efficiency": 92.3,
                "durationMinutes": 390,
                "wakeCount": 1,
                "phases": {"light": 210, "deep": 80, "rem": 70, "awake": 30},
                "startTime": "2026-03-24T15:30:00Z",
                "endTime": "2026-03-24T22:00:00Z",
            }
        ]
        try:
            response = self.client.get(
                "/api/sim/analytics/sleep/history",
                params={"deviceId": device["id"], "days": 30},
            )
        finally:
            runtime.sleep_db_history = original

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "date": "2026-03-25",
                    "score": 88,
                    "efficiency": 92.3,
                    "durationMinutes": 390,
                    "wakeCount": 1,
                    "phases": {"light": 210, "deep": 80, "rem": 70, "awake": 30},
                    "startTime": "2026-03-24T15:30:00Z",
                    "endTime": "2026-03-24T22:00:00Z",
                }
            ],
        )


@unittest.skipUnless(FASTAPI_READY, "FastAPI runtime is not available")
class TestBackfillEndpoint(unittest.TestCase):
    """FIX-2: Test coverage cho POST /scenarios/sleep/backfill — 05/phase1."""

    def setUp(self) -> None:
        reset_runtime_for_tests()
        self.client = TestClient(app)
        self.runtime = get_runtime()

    def _make_device(self) -> str:
        return self.client.post(
            "/api/sim/devices", json={"name": "Backfill Test Device", "type": "smartwatch"}
        ).json()["id"]

    def test_backfill_calls_push_for_each_day(self) -> None:
        """days_behind=3 → push được gọi 3 lần với 3 ngày khác nhau."""
        device_id = self._make_device()
        pushed_dates: list[str] = []

        original = self.runtime.push_sleep_session_for_date

        def fake_push(device_id: str, target_date, scenario_id: str = "good_sleep_night"):
            pushed_dates.append(str(target_date))
            return {
                "success": True,
                "target_date": str(target_date),
                "scenario_id": scenario_id,
                "duration_minutes": 360,
                "sleep_score": 80,
                "disorder_tags": [],
                "was_overwritten": False,
                "message": "ok",
            }

        self.runtime.push_sleep_session_for_date = fake_push
        try:
            response = self.client.post(
                "/api/sim/scenarios/sleep/backfill",
                json={"device_id": device_id, "days_behind": 3, "scenario_id": "good_sleep_night"},
            )
        finally:
            self.runtime.push_sleep_session_for_date = original

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["pushed"], 3)
        self.assertEqual(data["errors"], [])
        # 3 ngày khác nhau, không trùng
        self.assertEqual(len(pushed_dates), 3)
        self.assertEqual(len(set(pushed_dates)), 3, "Expected 3 distinct dates")

    def test_backfill_dates_are_all_in_past(self) -> None:
        """Tất cả target_date phải < today."""
        device_id = self._make_device()
        today = datetime.now(timezone.utc).date()
        pushed_dates: list[date] = []

        original = self.runtime.push_sleep_session_for_date

        def fake_push(device_id: str, target_date, scenario_id: str = "good_sleep_night"):
            pushed_dates.append(target_date)
            return {
                "success": True,
                "target_date": str(target_date),
                "scenario_id": scenario_id,
                "duration_minutes": 360,
                "sleep_score": 80,
                "disorder_tags": [],
                "was_overwritten": False,
                "message": "ok",
            }

        self.runtime.push_sleep_session_for_date = fake_push
        try:
            self.client.post(
                "/api/sim/scenarios/sleep/backfill",
                json={"device_id": device_id, "days_behind": 5, "scenario_id": "fragmented_sleep"},
            )
        finally:
            self.runtime.push_sleep_session_for_date = original

        self.assertEqual(len(pushed_dates), 5)
        for d in pushed_dates:
            self.assertLess(d, today, f"Expected {d} < {today}")

    def test_backfill_partial_failure_does_not_abort(self) -> None:
        """Nếu 1 ngày fail, các ngày khác vẫn được push — không abort toàn bộ."""
        device_id = self._make_device()
        call_count = [0]

        original = self.runtime.push_sleep_session_for_date

        def fake_push(device_id: str, target_date, scenario_id: str = "good_sleep_night"):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("Simulated backend failure on day 2")
            return {
                "success": True,
                "target_date": str(target_date),
                "scenario_id": scenario_id,
                "duration_minutes": 360,
                "sleep_score": 80,
                "disorder_tags": [],
                "was_overwritten": False,
                "message": "ok",
            }

        self.runtime.push_sleep_session_for_date = fake_push
        try:
            response = self.client.post(
                "/api/sim/scenarios/sleep/backfill",
                json={"device_id": device_id, "days_behind": 3, "scenario_id": "good_sleep_night"},
            )
        finally:
            self.runtime.push_sleep_session_for_date = original

        # Response phải thành công (200), không phải 500
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # 2 pushed thành công, 1 error
        self.assertEqual(data["pushed"], 2)
        self.assertEqual(len(data["errors"]), 1)
        self.assertIn("day 2", data["errors"][0].lower())


if __name__ == "__main__":
    unittest.main()
