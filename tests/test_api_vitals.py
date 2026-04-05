from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

try:
    from fastapi.testclient import TestClient

    from Iot_Simulator.api_server.dependencies import (
        DeviceRecord,
        SessionRecord,
        SimulatorRuntime,
        reset_runtime_for_tests,
    )
    from Iot_Simulator.api_server.main import app

    FASTAPI_READY = True
except Exception:
    FASTAPI_READY = False


@unittest.skipUnless(FASTAPI_READY, "FastAPI runtime is not available")
class TestApiVitals(unittest.TestCase):
    def setUp(self) -> None:
        reset_runtime_for_tests()
        self.client = TestClient(app)
        device = self.client.post(
            "/api/sim/devices",
            json={"name": "Watch D", "type": "smartwatch", "persona_config": {"age": 38, "weight_kg": 78, "height_cm": 174, "seed": 2}},
        ).json()
        session = self.client.post("/api/sim/sessions", json={"device_ids": [device["id"]], "speed": 1}).json()
        self.device_id = device["id"]
        self.session_id = session["id"]
        self.client.post(f"/api/sim/sessions/{self.session_id}/start")

    def test_latest_vitals_after_start(self) -> None:
        response = self.client.get(f"/api/sim/vitals/latest?deviceId={self.device_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("heartRate", payload)
        self.assertIn("respiratoryRate", payload)
        self.assertIn("severity", payload)
        self.assertIn("activityLabel", payload)
        self.assertIn("motionTag", payload)
        self.assertFalse(payload["isStale"])
        self.assertEqual(payload["activityLabel"], "resting")
        self.assertEqual(payload["motionTag"], "resting")

    def test_to_vitals_maps_internal_fall_state(self) -> None:
        sample = SimulatorRuntime._to_vitals(
            {"heart_rate": 72.0},
            stale=False,
            emitted_at="2026-01-01T00:00:00Z",
            activity_state="fall",
        )
        self.assertEqual(sample.activityLabel, "falling")
        self.assertEqual(sample.motionTag, "falling")


def _build_runtime_with_payload(
    *,
    source_mode: str,
    vitals: dict[str, object],
    activity_state: str = "resting",
) -> tuple[SimulatorRuntime, SessionRecord, str]:
    runtime = SimulatorRuntime()
    device_id = "device-1"
    runtime.devices[device_id] = DeviceRecord(
        id=device_id,
        name="Vitals Test Device",
        serial_number="SIM-0001",
        mqtt_client_id="sim-device-1",
        device_type="smartwatch",
    )
    record = SessionRecord(
        id="session-1",
        device_ids=[device_id],
        speed=1,
        simulator=MagicMock(),
        status="stopped",
        last_tick_outputs=[
            {
                "device_id": device_id,
                "vitals": dict(vitals),
                "state": {"activity_state": activity_state},
                "emitted_at": "2026-01-01T00:00:00+00:00",
            }
        ],
        source_modes={device_id: source_mode},
    )
    runtime.sessions[record.id] = record
    return runtime, record, device_id


def test_replay_mode_provenance_populated() -> None:
    runtime, _, device_id = _build_runtime_with_payload(
        source_mode="replay",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
            "blood_pressure_sys": 118.0,
            "blood_pressure_dia": 76.0,
        },
    )

    sample = runtime.latest_vitals(device_id)

    assert sample.fieldProvenance is not None
    assert sample.fieldProvenance["heartRate"] == "measured"
    assert sample.fieldProvenance["temperature"] == "unknown"
    assert sample.sourceMode == "replay"
    assert sample.bpObservationAgeSec == 0.0
    assert sample.bpIsStale is False


def test_bp_stale_after_300s() -> None:
    runtime, record, device_id = _build_runtime_with_payload(
        source_mode="replay",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
            "blood_pressure_sys": 118.0,
            "blood_pressure_dia": 76.0,
        },
    )

    with patch("Iot_Simulator.api_server.dependencies.monotonic", side_effect=[100.0, 401.2]):
        first = runtime.latest_vitals(device_id)
        record.last_tick_outputs = [
            {
                "device_id": device_id,
                "vitals": {"heart_rate": 73.0, "spo2": 97.0},
                "state": {"activity_state": "resting"},
                "emitted_at": "2026-01-01T00:05:01+00:00",
            }
        ]
        second = runtime.latest_vitals(device_id)

    assert first.bpIsStale is False
    assert second.bpIsStale is True
    assert second.bpObservationAgeSec == 301.2
    assert second.bloodPressureSys is None
    assert second.bloodPressureDia is None


def test_synthetic_mode_no_provenance() -> None:
    runtime, _, device_id = _build_runtime_with_payload(
        source_mode="synthetic",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
        },
    )

    sample = runtime.latest_vitals(device_id)

    assert sample.fieldProvenance is None
    assert sample.sourceMode is None


def test_latest_vitals_does_not_tick_active() -> None:
    runtime, _, device_id = _build_runtime_with_payload(
        source_mode="synthetic",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
        },
    )
    runtime.tick_active = MagicMock(side_effect=AssertionError("latest_vitals must be read-only"))  # type: ignore[method-assign]

    sample = runtime.latest_vitals(device_id)

    assert sample.heartRate == 72.0


def test_latest_vitals_maps_respiration_rate_alias() -> None:
    runtime, _, device_id = _build_runtime_with_payload(
        source_mode="synthetic",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
            "respiration_rate": 18.5,
        },
    )

    sample = runtime.latest_vitals(device_id)

    assert sample.respiratoryRate == 18.5


def test_latest_vitals_prefers_generator_activity_label_for_sleeping() -> None:
    runtime, _, device_id = _build_runtime_with_payload(
        source_mode="synthetic",
        vitals={
            "heart_rate": 55.5,
            "spo2": 97.0,
            "respiratory_rate": 12.0,
            "activity_label": "sleeping",
            "sleep_phase": "deep",
        },
        activity_state="resting",
    )

    sample = runtime.latest_vitals(device_id)

    assert sample.activityLabel == "sleeping"
    assert sample.motionTag == "sleeping"


def test_verification_uses_measured_publish_latency() -> None:
    runtime, record, _ = _build_runtime_with_payload(
        source_mode="synthetic",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
            "respiratory_rate": 18.0,
        },
    )
    record.last_publish_latency_ms = 41

    verification = runtime.verification(record.id)

    assert verification.latencyMs == 41


def test_verification_does_not_tick_active() -> None:
    runtime, record, _ = _build_runtime_with_payload(
        source_mode="synthetic",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
            "respiratory_rate": 18.0,
        },
    )
    runtime.tick_active = MagicMock(side_effect=AssertionError("verification must be read-only"))  # type: ignore[method-assign]

    verification = runtime.verification(record.id)

    assert verification.deviceId == "device-1"


if __name__ == "__main__":
    unittest.main()
