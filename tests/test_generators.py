from __future__ import annotations

import unittest
from math import nan
from random import Random
from pathlib import Path

from Iot_Simulator.etl_pipeline.normalize import NormalizedArtifactPipeline
from Iot_Simulator.simulator_core.dataset_registry import DatasetRegistry
from Iot_Simulator.simulator_core.generators import MotionGenerator, VitalsGenerator
from Iot_Simulator.simulator_core.persona_engine import DeviceState, Persona
from Iot_Simulator.simulator_core.session import DataBinding, DeviceContext
from Iot_Simulator.simulator_core.persona_engine import PersonaEngine


class ReplayRegistryStub:
    def __init__(self, rows_by_binding: dict[tuple[str, str], list[dict[str, object]]]) -> None:
        self.rows_by_binding = rows_by_binding

    def get_vitals_baseline(
        self,
        activity: str | None = None,
        dataset: str | None = None,
        required_fields: tuple[str, ...] | None = None,
    ) -> dict[str, object] | None:
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

    def get_respiration_sample(self, activity: str | None = None) -> dict[str, object] | None:
        return None


class StressRegistryStub(ReplayRegistryStub):
    def __init__(self, stress_sample: dict[str, object] | None, baseline_mean: float | None) -> None:
        super().__init__({})
        self._stress_sample = stress_sample
        self._baseline_mean = baseline_mean

    def get_stress_sample(self, stress_state: str = "stress") -> dict[str, object] | None:
        return self._stress_sample

    def get_stress_baseline_mean(self) -> float | None:
        return self._baseline_mean


class VitalDbFallbackRegistryStub(ReplayRegistryStub):
    def __init__(self) -> None:
        super().__init__({})

    def get_vitals_baseline(
        self,
        activity: str | None = None,
        dataset: str | None = None,
        required_fields: tuple[str, ...] | None = None,
    ) -> dict[str, object] | None:
        if dataset == "VitalDB":
            return {
                "timestamp": "vitaldb-ts",
                "heart_rate": 75.0,
                "spo2": 96.0,
                "blood_pressure_sys": 132.0,
                "blood_pressure_dia": 84.0,
                "activity_label": "clinical",
                "dataset": "VitalDB",
            }
        return {
            "timestamp": "baseline-ts",
            "heart_rate": 72.0,
            "spo2": nan,
            "blood_pressure_sys": nan,
            "blood_pressure_dia": nan,
            "activity_label": activity or "walking",
            "dataset": "PPG-DaLiA",
        }


class RespirationRegistryStub(ReplayRegistryStub):
    def get_respiration_sample(self, activity: str | None = None) -> dict[str, object] | None:
        return {
            "timestamp": "bidmc-ts",
            "subject_id": "BIDMC_bidmc01",
            "dataset": "BIDMC",
            "respiration_rate": 18.4,
            "activity_label": activity,
        }


class TestGenerators(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        artifacts_dir = Path(__file__).resolve().parents[1] / "normalized_artifacts_runtime_test"
        if not (artifacts_dir / "normalize_summary.json").exists():
            NormalizedArtifactPipeline(artifacts_dir).run()
        cls.registry = DatasetRegistry(artifacts_dir)
        cls.persona = Persona()

    def test_vitals_generator_generate_tick(self) -> None:
        generator = VitalsGenerator(self.registry)
        payload = generator.generate_tick(DeviceState(activity_state="walking"), self.persona, sim_time=12.5)
        self.assertIn("heart_rate", payload)
        self.assertIn("temperature", payload)
        self.assertEqual(payload["activity_label"], "walking")
        self.assertEqual(payload["sim_time"], 12.5)
        self.assertGreaterEqual(payload["temperature"], 36.4)
        self.assertLessEqual(payload["temperature"], 37.0)

    def test_vitals_generator_uses_wesad_stress_delta(self) -> None:
        registry = StressRegistryStub(
            stress_sample={"heart_rate": 82.0, "stress_state": "stress", "source_dataset": "WESAD"},
            baseline_mean=70.0,
        )
        generator = VitalsGenerator(registry)  # type: ignore[arg-type]
        payload = generator.generate(DeviceState(activity_state="walking", stress_state="stress"), self.persona)

        expected_noise = Random(11).uniform(-1.5, 1.5)
        expected_hr = round(72.0 + (82.0 - 70.0) + expected_noise, 2)

        self.assertEqual(payload["stress_data_source"], "real:WESAD")
        self.assertEqual(payload["heart_rate"], expected_hr)

    def test_vitals_generator_falls_back_to_mock_stress_adjust(self) -> None:
        registry = StressRegistryStub(stress_sample=None, baseline_mean=None)
        generator = VitalsGenerator(registry)  # type: ignore[arg-type]
        payload = generator.generate(DeviceState(activity_state="walking", stress_state="stress"), self.persona)

        expected_noise = Random(11).uniform(-1.5, 1.5)
        expected_hr = round(72.0 + 8.0 + expected_noise, 2)

        self.assertEqual(payload["stress_data_source"], "mock")
        self.assertEqual(payload["heart_rate"], expected_hr)

    def test_vitals_generator_fills_missing_spo2_and_bp_from_vitaldb(self) -> None:
        registry = VitalDbFallbackRegistryStub()
        generator = VitalsGenerator(registry)  # type: ignore[arg-type]

        payload = generator.generate(DeviceState(activity_state="walking"), self.persona)

        expected_noise = Random(11).uniform(-1.5, 1.5)
        expected_hr = round(72.0 + expected_noise, 2)

        self.assertEqual(payload["heart_rate"], expected_hr)
        self.assertEqual(payload["spo2"], 96.0)
        self.assertEqual(payload["blood_pressure_sys"], 132.0)
        self.assertEqual(payload["blood_pressure_dia"], 84.0)
        self.assertEqual(payload["spo2_source"], "real:VitalDB")
        self.assertEqual(payload["dataset"], "PPG-DaLiA")

    def test_vitals_generator_adds_respiration_rate_from_bidmc(self) -> None:
        registry = RespirationRegistryStub({})
        generator = VitalsGenerator(registry)  # type: ignore[arg-type]

        payload = generator.generate(DeviceState(activity_state="walking"), self.persona)

        self.assertEqual(payload["respiratory_rate"], 18.4)
        self.assertNotIn("respiration_rate", payload)
        self.assertEqual(payload["rr_source"], "real:BIDMC")
        self.assertGreaterEqual(payload["temperature"], 36.4)
        self.assertLessEqual(payload["temperature"], 37.0)

    def test_motion_generator_returns_window_for_state(self) -> None:
        generator = MotionGenerator(self.registry)
        window = generator.get_window_for_state(DeviceState(activity_state="walking"))
        self.assertIsNotNone(window)
        self.assertIn("window_id", window)

    def test_replay_mode_returns_real_rows(self) -> None:
        registry = ReplayRegistryStub(
            {
                ("subject-1", "VitalDB"): [
                    {"timestamp": "2024-01-01T00:00:01Z", "heart_rate": 70, "spo2": 98},
                    {"timestamp": "2024-01-01T00:00:02Z", "heart_rate": 71, "spo2": 97},
                ]
            }
        )
        generator = VitalsGenerator(registry)  # type: ignore[arg-type]
        device = DeviceContext(
            device_id="device-1",
            engine=PersonaEngine(self.persona),
            data_binding=DataBinding(subject_id="subject-1", dataset="VitalDB", source_mode="replay"),
        )

        first = generator.generate_tick(DeviceState(activity_state="walking"), self.persona, sim_time=1.0, device_context=device)
        second = generator.generate_tick(DeviceState(activity_state="walking"), self.persona, sim_time=2.0, device_context=device)

        self.assertEqual(first["timestamp"], "2024-01-01T00:00:01Z")
        self.assertEqual(second["timestamp"], "2024-01-01T00:00:02Z")
        self.assertEqual(first["source_mode"], "replay")
        self.assertEqual(first["sim_time"], 1.0)
        self.assertGreaterEqual(first["temperature"], 36.4)
        self.assertLessEqual(first["temperature"], 37.0)

    def test_replay_loop_wraps_around(self) -> None:
        registry = ReplayRegistryStub(
            {
                ("subject-1", "VitalDB"): [
                    {"timestamp": "2024-01-01T00:00:01Z", "heart_rate": 70},
                    {"timestamp": "2024-01-01T00:00:02Z", "heart_rate": 71},
                ]
            }
        )
        generator = VitalsGenerator(registry)  # type: ignore[arg-type]
        device = DeviceContext(
            device_id="device-1",
            engine=PersonaEngine(self.persona),
            data_binding=DataBinding(subject_id="subject-1", dataset="VitalDB", source_mode="replay"),
        )

        timestamps = [
            generator.generate_tick(DeviceState(activity_state="walking"), self.persona, device_context=device)["timestamp"]
            for _ in range(3)
        ]

        self.assertEqual(
            timestamps,
            [
                "2024-01-01T00:00:01Z",
                "2024-01-01T00:00:02Z",
                "2024-01-01T00:00:01Z",
            ],
        )

    def test_null_field_not_filled(self) -> None:
        registry = ReplayRegistryStub(
            {
                ("subject-1", "VitalDB"): [
                    {
                        "timestamp": "2024-01-01T00:00:01Z",
                        "heart_rate": 70,
                        "spo2": None,
                        "signal_quality": None,
                    }
                ]
            }
        )
        generator = VitalsGenerator(registry)  # type: ignore[arg-type]
        device = DeviceContext(
            device_id="device-1",
            engine=PersonaEngine(self.persona),
            data_binding=DataBinding(subject_id="subject-1", dataset="VitalDB", source_mode="replay"),
        )

        payload = generator.generate_tick(DeviceState(activity_state="walking"), self.persona, device_context=device)

        self.assertIsNone(payload["spo2"])
        self.assertIsNone(payload["signal_quality"])


if __name__ == "__main__":
    unittest.main()
