from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from Iot_Simulator.api_server.dependencies import DeviceRecord, SessionRecord, SimulatorRuntime
from Iot_Simulator.api_server.schemas import VitalsSample


def _build_runtime_with_payload(*, source_mode: str, vitals: dict[str, object]) -> tuple[SimulatorRuntime, str]:
    runtime = SimulatorRuntime()
    device_id = "device-1"
    runtime.devices[device_id] = DeviceRecord(
        id=device_id,
        name="Medical Policy Device",
        serial_number="SIM-0002",
        mqtt_client_id="sim-device-2",
        device_type="smartwatch",
    )
    runtime.sessions["session-1"] = SessionRecord(
        id="session-1",
        device_ids=[device_id],
        speed=1,
        simulator=MagicMock(),
        status="stopped",
        last_tick_outputs=[
            {
                "device_id": device_id,
                "vitals": dict(vitals),
                "state": {"activity_state": "resting"},
                "emitted_at": "2026-01-01T00:00:00+00:00",
            }
        ],
        source_modes={device_id: source_mode},
    )
    return runtime, device_id


def test_replay_temperature_defaults_when_missing() -> None:
    runtime, device_id = _build_runtime_with_payload(
        source_mode="replay",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
            "blood_pressure_sys": 118.0,
            "blood_pressure_dia": 76.0,
        },
    )

    sample = runtime.latest_vitals(device_id)

    assert sample.temperature == 36.7
    assert sample.respiratoryRate is None


def test_synthetic_temperature_has_default() -> None:
    runtime, device_id = _build_runtime_with_payload(
        source_mode="synthetic",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
        },
    )

    sample = runtime.latest_vitals(device_id)

    assert sample.temperature == 36.7
    assert sample.respiratoryRate == 15.0


def test_hr_thresholds_distinguish_warning_and_critical() -> None:
    warning = SimulatorRuntime._to_vitals({"heart_rate": 115.0, "spo2": 98.0, "respiratory_rate": 16.0}, stale=False)
    critical = SimulatorRuntime._to_vitals({"heart_rate": 125.0, "spo2": 98.0, "respiratory_rate": 16.0}, stale=False)

    assert warning.severity == "warning"
    assert critical.severity == "critical"


def test_spo2_and_bp_thresholds_follow_medical_policy() -> None:
    spo2_warning = SimulatorRuntime._to_vitals({"heart_rate": 72.0, "spo2": 93.0, "respiratory_rate": 16.0}, stale=False)
    spo2_critical = SimulatorRuntime._to_vitals({"heart_rate": 72.0, "spo2": 89.0, "respiratory_rate": 16.0}, stale=False)
    systolic_warning = SimulatorRuntime._to_vitals(
        {"heart_rate": 72.0, "spo2": 98.0, "blood_pressure_sys": 145.0, "blood_pressure_dia": 92.0, "respiratory_rate": 16.0},
        stale=False,
    )
    systolic_critical = SimulatorRuntime._to_vitals(
        {"heart_rate": 72.0, "spo2": 98.0, "blood_pressure_sys": 78.0, "blood_pressure_dia": 54.0, "respiratory_rate": 16.0},
        stale=False,
    )

    assert spo2_warning.severity == "warning"
    assert spo2_critical.severity == "critical"
    assert systolic_warning.severity == "warning"
    assert systolic_critical.severity == "critical"


def test_respiratory_rate_critical_thresholds_follow_policy() -> None:
    low_rr = SimulatorRuntime._to_vitals({"heart_rate": 72.0, "spo2": 98.0, "respiratory_rate": 9.0}, stale=False)
    high_rr = SimulatorRuntime._to_vitals({"heart_rate": 72.0, "spo2": 98.0, "respiratory_rate": 26.0}, stale=False)

    assert low_rr.severity == "critical"
    assert high_rr.severity == "critical"


def test_frontend_types_match_backend() -> None:
    schema = VitalsSample.model_json_schema()
    nullable_fields = ("temperature", "bloodPressureSys", "bloodPressureDia", "respiratoryRate")
    for field in nullable_fields:
        field_schema = schema["properties"][field]
        any_of = field_schema.get("anyOf", [])
        assert any(option.get("type") == "number" for option in any_of)
        assert any(option.get("type") == "null" for option in any_of)

    frontend_types = Path("D:/DoAn2/VSmartwatch/Iot_Simulator/simulator-web/src/types/vitals.ts").read_text(encoding="utf-8")
    assert "temperature: number | null;" in frontend_types
    assert "bloodPressureSys: number | null;" in frontend_types
    assert "bloodPressureDia: number | null;" in frontend_types
    assert "respiratoryRate: number | null;" in frontend_types
