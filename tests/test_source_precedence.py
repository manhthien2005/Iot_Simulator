from __future__ import annotations

from unittest.mock import MagicMock

from Iot_Simulator.api_server.dependencies import DeviceRecord, SessionRecord, SimulatorRuntime


def _build_runtime(
    *,
    source_mode: str,
    scenario_id: str,
    vitals: dict[str, float],
    state: dict[str, object] | None = None,
) -> tuple[SimulatorRuntime, SessionRecord]:
    runtime = SimulatorRuntime()
    device_id = "device-1"
    runtime.devices[device_id] = DeviceRecord(
        id=device_id,
        name="Source Precedence Device",
        serial_number="SIM-0001",
        mqtt_client_id="sim-device-1",
        device_type="smartwatch",
    )
    runtime.device_scenarios[device_id] = scenario_id

    payload = {
        "device_id": device_id,
        "vitals": dict(vitals),
        "state": dict(state or {"activity_state": "resting"}),
        "emitted_at": "2026-01-01T00:00:00+00:00",
    }
    simulator = MagicMock()
    simulator.tick.return_value = [payload]

    record = SessionRecord(
        id="session-1",
        device_ids=[device_id],
        speed=1,
        simulator=simulator,
        status="running",
        source_modes={device_id: source_mode},
    )
    runtime.sessions[record.id] = record
    return runtime, record


def test_replay_mode_preserves_dataset_vitals_and_adds_annotation() -> None:
    runtime, record = _build_runtime(
        source_mode="replay",
        scenario_id="tachycardia_warning",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
            "blood_pressure_sys": 118.0,
            "blood_pressure_dia": 76.0,
            "respiratory_rate": 15.0,
            "temperature": 36.6,
        },
    )

    runtime._tick_session_locked(record, force=True)

    output = record.last_tick_outputs[0]
    assert output["vitals"]["heart_rate"] == 72.0
    assert output["vitals"]["spo2"] == 98.0
    assert output["vitals"]["blood_pressure_sys"] == 118.0
    assert output["vitals"]["blood_pressure_dia"] == 76.0
    assert output["scenario_annotation"]["scenario_id"] == "tachycardia_warning"
    assert output["scenario_annotation"]["overlay_blocked"] is True
    assert output["scenario_annotation"]["state_hint"] == "warning"


def test_replay_fall_mode_keeps_vitals_and_records_event() -> None:
    runtime, record = _build_runtime(
        source_mode="replay",
        scenario_id="fall_high_confidence",
        vitals={
            "heart_rate": 74.0,
            "spo2": 97.0,
            "blood_pressure_sys": 120.0,
            "blood_pressure_dia": 78.0,
            "respiratory_rate": 15.0,
            "temperature": 36.7,
        },
        state={"activity_state": "fall", "fall_variant": "fall_high_confidence"},
    )

    runtime._tick_session_locked(record, force=True)

    output = record.last_tick_outputs[0]
    assert output["vitals"]["heart_rate"] == 74.0
    assert output["vitals"]["spo2"] == 97.0
    assert output["vitals"]["blood_pressure_sys"] == 120.0
    assert output["scenario_annotation"]["scenario_id"] == "fall_high_confidence"
    assert output["scenario_annotation"]["state_hint"] == "fall_countdown"
    assert output["scenario_annotation"]["event_hint"] == "fall_detected"
    assert any(event.event_type == "fall_detected" for event in runtime.event_history)


def test_synthetic_mode_still_overrides_vitals() -> None:
    runtime, record = _build_runtime(
        source_mode="synthetic",
        scenario_id="tachycardia_warning",
        vitals={
            "heart_rate": 72.0,
            "spo2": 98.0,
            "blood_pressure_sys": 118.0,
            "blood_pressure_dia": 76.0,
            "respiratory_rate": 15.0,
            "temperature": 36.6,
        },
    )

    runtime._tick_session_locked(record, force=True)

    output = record.last_tick_outputs[0]
    assert output["vitals"]["heart_rate"] > 100.0
    assert "scenario_annotation" not in output
