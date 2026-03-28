from __future__ import annotations

import unittest
from pathlib import Path

from Iot_Simulator.etl_pipeline.normalize import NormalizedArtifactPipeline
from Iot_Simulator.simulator_core.dataset_registry import DatasetRegistry
from Iot_Simulator.simulator_core.session import DataBinding, SimulatorSession, build_device


class SessionRegistryStub:
    def __init__(self, rows_by_binding: dict[tuple[str, str], list[dict[str, object]]]) -> None:
        self.rows_by_binding = rows_by_binding

    def get_vitals_baseline(self, activity: str | None = None, dataset: str | None = None) -> dict[str, object] | None:
        return {
            "timestamp": "baseline-ts",
            "heart_rate": 72.0,
            "spo2": 98.0,
            "blood_pressure_sys": 120.0,
            "blood_pressure_dia": 80.0,
            "activity_label": activity or "resting",
            "dataset": dataset or "baseline",
        }

    def get_vitals_sample_at(self, subject_id: str, dataset: str, cursor_index: int) -> dict[str, object] | None:
        rows = self.rows_by_binding.get((subject_id, dataset), [])
        if not rows:
            return None
        return rows[cursor_index % len(rows)]

    def get_motion_windows(
        self,
        activity: str | None = None,
        activity_label: str | None = None,
        dataset: str | None = None,
        fall_variant: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        return [{"window_id": f"{activity or activity_label or 'rest'}-window", "dataset": dataset or "stub"}]

    def get_fall_event(self, variant: str) -> dict[str, object] | None:
        return {"event_type": "fall_detected", "fall_variant": variant}


class TestSimulatorSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        artifacts_dir = Path(__file__).resolve().parents[1] / "normalized_artifacts_runtime_test"
        if not (artifacts_dir / "normalize_summary.json").exists():
            NormalizedArtifactPipeline(artifacts_dir).run()
        registry = DatasetRegistry(artifacts_dir)
        device = build_device("sim-dev-001")
        device.engine.set_activity("walking")
        cls.session = SimulatorSession(registry, [device])
        cls.session.start()

    def test_tick_emits_payload(self) -> None:
        outputs = self.session.tick()
        self.assertEqual(len(outputs), 1)
        payload = outputs[0]
        self.assertIn("vitals", payload)
        self.assertIn("motion", payload)

    def test_inject_fall_changes_state(self) -> None:
        self.session.inject_event("sim-dev-001", "fall_detected", "fall_1")
        payload = self.session.tick()[0]
        self.assertIn(payload["state"]["activity_state"], {"fall", "recovery"})

    def test_two_devices_different_bindings(self) -> None:
        registry = SessionRegistryStub(
            {
                ("subject-1", "VitalDB"): [
                    {"timestamp": "2024-01-01T00:00:01Z", "heart_rate": 70},
                    {"timestamp": "2024-01-01T00:00:02Z", "heart_rate": 71},
                ],
                ("subject-2", "VitalDB"): [
                    {"timestamp": "2024-02-01T00:00:01Z", "heart_rate": 80},
                    {"timestamp": "2024-02-01T00:00:02Z", "heart_rate": 81},
                ],
            }
        )
        first_device = build_device(
            "sim-dev-101",
            data_binding=DataBinding(subject_id="subject-1", dataset="VitalDB", source_mode="replay"),
        )
        second_device = build_device(
            "sim-dev-202",
            data_binding=DataBinding(subject_id="subject-2", dataset="VitalDB", source_mode="replay"),
        )
        first_device.engine.set_activity("walking")
        second_device.engine.set_activity("walking")

        session = SimulatorSession(registry, [first_device, second_device])  # type: ignore[arg-type]
        session.start()

        first_tick = session.tick()
        second_tick = session.tick()

        self.assertEqual(first_tick[0]["vitals"]["timestamp"], "2024-01-01T00:00:01Z")
        self.assertEqual(first_tick[1]["vitals"]["timestamp"], "2024-02-01T00:00:01Z")
        self.assertEqual(second_tick[0]["vitals"]["timestamp"], "2024-01-01T00:00:02Z")
        self.assertEqual(second_tick[1]["vitals"]["timestamp"], "2024-02-01T00:00:02Z")


if __name__ == "__main__":
    unittest.main()
