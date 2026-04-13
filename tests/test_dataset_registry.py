from __future__ import annotations

import json
import unittest
from math import nan
from pathlib import Path
from tempfile import TemporaryDirectory

from etl_pipeline.normalize import NormalizedArtifactPipeline
from simulator_core.dataset_registry import DatasetRegistry


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            handle.write("\n")


class TestDatasetRegistry(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        artifacts_dir = Path(__file__).resolve().parents[1] / "normalized_artifacts_runtime_test"
        if not (artifacts_dir / "normalize_summary.json").exists():
            NormalizedArtifactPipeline(artifacts_dir).run()
        cls.registry = DatasetRegistry(artifacts_dir)

    def test_loads_motion_windows(self) -> None:
        windows = self.registry.get_motion_windows()
        self.assertTrue(len(windows) > 0)

    def test_filters_motion_by_activity(self) -> None:
        walking = self.registry.get_motion_windows(activity="walking")
        self.assertTrue(len(walking) > 0)
        self.assertTrue(all("walking" in str(window["activity_label"]).lower() for window in walking))

    def test_get_motion_windows_filters_by_dataset_and_fall_variant(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            _write_jsonl(
                artifacts_dir / "motion_windows.jsonl",
                [
                    {
                        "window_id": "walk-a",
                        "dataset": "PPG-DaLiA",
                        "activity_label": "walking",
                    },
                    {
                        "window_id": "walk-b",
                        "dataset": "PAMAP2",
                        "activity_label": "walking",
                    },
                    {
                        "window_id": "fall-a",
                        "dataset": "UP-Fall",
                        "activity_label": "fall_forward",
                        "fall_variant": "fall_1",
                    },
                    {
                        "window_id": "fall-b",
                        "dataset": "UP-Fall",
                        "activity_label": "fall_backward",
                        "fall_variant": "fall_2",
                    },
                ],
            )
            _write_jsonl(artifacts_dir / "event_catalog.jsonl", [])
            _write_jsonl(artifacts_dir / "vitals_stream.jsonl", [])

            registry = DatasetRegistry(artifacts_dir)
            walking = registry.get_motion_windows(dataset="PPG-DaLiA")
            fall_variant = registry.get_motion_windows(activity="fall", fall_variant="fall_2")

        self.assertEqual([row["window_id"] for row in walking], ["walk-a"])
        self.assertEqual([row["window_id"] for row in fall_variant], ["fall-b"])

    def test_gets_vitals_baseline(self) -> None:
        baseline = self.registry.get_vitals_baseline()
        self.assertIsNotNone(baseline)
        self.assertIn("heart_rate", baseline)

    def test_gets_fall_event(self) -> None:
        event = self.registry.get_fall_event("fall_1")
        self.assertIsNotNone(event)
        self.assertEqual(event["event_type"], "fall_detected")

    def test_sleep_sessions_optional(self) -> None:
        has_sleep = self.registry.has_sleep_sessions()
        self.assertIsInstance(has_sleep, bool)
        if has_sleep:
            sample = self.registry.sample_sleep_session()
            self.assertIn("phases", sample)
            self.assertIn("summary", sample)
        else:
            with self.assertRaises(LookupError):
                self.registry.sample_sleep_session()

    def test_get_vitals_timeline_sorted_by_timestamp(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            _write_jsonl(artifacts_dir / "motion_windows.jsonl", [])
            _write_jsonl(artifacts_dir / "event_catalog.jsonl", [])
            _write_jsonl(
                artifacts_dir / "vitals_stream.jsonl",
                [
                    {
                        "subject_id": "subject-1",
                        "dataset": "VitalDB",
                        "timestamp": "2024-01-01T00:00:03Z",
                        "heart_rate": 73,
                    },
                    {
                        "subject_id": "subject-1",
                        "dataset": "VitalDB",
                        "timestamp": "2024-01-01T00:00:01Z",
                        "heart_rate": 71,
                    },
                    {
                        "subject_id": "subject-1",
                        "dataset": "VitalDB",
                        "timestamp": "2024-01-01T00:00:02Z",
                        "heart_rate": 72,
                    },
                ],
            )

            registry = DatasetRegistry(artifacts_dir)
            timeline = registry.get_vitals_timeline("subject-1", "VitalDB")

        self.assertEqual(
            [row["timestamp"] for row in timeline],
            [
                "2024-01-01T00:00:01Z",
                "2024-01-01T00:00:02Z",
                "2024-01-01T00:00:03Z",
            ],
        )

    def test_get_vitals_sample_at_loop(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            _write_jsonl(artifacts_dir / "motion_windows.jsonl", [])
            _write_jsonl(artifacts_dir / "event_catalog.jsonl", [])
            _write_jsonl(
                artifacts_dir / "vitals_stream.jsonl",
                [
                    {
                        "subject_id": "subject-1",
                        "dataset": "VitalDB",
                        "timestamp": "2024-01-01T00:00:01Z",
                        "heart_rate": 71,
                    },
                    {
                        "subject_id": "subject-1",
                        "dataset": "VitalDB",
                        "timestamp": "2024-01-01T00:00:02Z",
                        "heart_rate": 72,
                    },
                ],
            )

            registry = DatasetRegistry(artifacts_dir)
            sample = registry.get_vitals_sample_at("subject-1", "VitalDB", 5)

        self.assertIsNotNone(sample)
        self.assertEqual(sample["timestamp"], "2024-01-01T00:00:02Z")

    def test_get_vitals_baseline_can_require_populated_fields(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            _write_jsonl(artifacts_dir / "motion_windows.jsonl", [])
            _write_jsonl(artifacts_dir / "event_catalog.jsonl", [])
            _write_jsonl(
                artifacts_dir / "vitals_stream.jsonl",
                [
                    {
                        "subject_id": "subject-1",
                        "dataset": "VitalDB",
                        "timestamp": "2024-01-01T00:00:01Z",
                        "heart_rate": 70,
                        "spo2": 98.0,
                        "blood_pressure_sys": nan,
                        "blood_pressure_dia": nan,
                    },
                    {
                        "subject_id": "subject-1",
                        "dataset": "VitalDB",
                        "timestamp": "2024-01-01T00:00:02Z",
                        "heart_rate": 71,
                        "spo2": 97.0,
                        "blood_pressure_sys": 128.0,
                        "blood_pressure_dia": 82.0,
                    },
                ],
            )

            registry = DatasetRegistry(artifacts_dir)
            baseline = registry.get_vitals_baseline(
                dataset="VitalDB",
                required_fields=("spo2", "blood_pressure_sys", "blood_pressure_dia"),
            )

        self.assertIsNotNone(baseline)
        self.assertEqual(baseline["timestamp"], "2024-01-01T00:00:02Z")
        self.assertEqual(baseline["blood_pressure_sys"], 128.0)

    def test_get_vitals_baseline_filters_by_activity_and_dataset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            _write_jsonl(artifacts_dir / "motion_windows.jsonl", [])
            _write_jsonl(artifacts_dir / "event_catalog.jsonl", [])
            _write_jsonl(
                artifacts_dir / "vitals_stream.jsonl",
                [
                    {
                        "subject_id": "subject-1",
                        "dataset": "VitalDB",
                        "timestamp": "2024-01-01T00:00:01Z",
                        "heart_rate": 70,
                        "activity_label": "resting",
                    },
                    {
                        "subject_id": "subject-2",
                        "dataset": "VitalDB",
                        "timestamp": "2024-01-01T00:00:02Z",
                        "heart_rate": 74,
                        "activity_label": "walking",
                    },
                    {
                        "subject_id": "subject-3",
                        "dataset": "PPG-DaLiA",
                        "timestamp": "2024-01-01T00:00:03Z",
                        "heart_rate": 78,
                        "activity_label": "walking",
                    },
                ],
            )

            registry = DatasetRegistry(artifacts_dir)
            baseline = registry.get_vitals_baseline(activity="walking", dataset="VitalDB")

        self.assertIsNotNone(baseline)
        self.assertEqual(baseline["timestamp"], "2024-01-01T00:00:02Z")
        self.assertEqual(baseline["heart_rate"], 74)

    def test_get_stress_sample_and_status(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            _write_jsonl(artifacts_dir / "motion_windows.jsonl", [])
            _write_jsonl(artifacts_dir / "event_catalog.jsonl", [])
            _write_jsonl(artifacts_dir / "vitals_stream.jsonl", [])
            _write_jsonl(
                artifacts_dir / "stress_stream.jsonl",
                [
                    {
                        "timestamp": "2024-01-01T00:00:00Z",
                        "subject_id": "WESAD_S2",
                        "stress_state": "neutral",
                        "heart_rate": 70.0,
                        "source_dataset": "WESAD",
                    },
                    {
                        "timestamp": "2024-01-01T00:00:10Z",
                        "subject_id": "WESAD_S2",
                        "stress_state": "stress",
                        "heart_rate": 86.0,
                        "source_dataset": "WESAD",
                    },
                ],
            )

            registry = DatasetRegistry(artifacts_dir)
            stress_sample = registry.get_stress_sample("stress")
            baseline_sample = registry.get_stress_sample("baseline")
            status = registry.status()

        self.assertTrue(registry.has_stress_data())
        self.assertIsNotNone(stress_sample)
        self.assertIsNotNone(baseline_sample)
        self.assertEqual(stress_sample["stress_state"], "stress")
        self.assertEqual(baseline_sample["stress_state"], "neutral")
        self.assertEqual(status["stressSource"], "real:WESAD")
        self.assertEqual(status["stressStates"]["stress"], 1)
        self.assertAlmostEqual(registry.get_stress_baseline_mean() or 0.0, 70.0)

    def test_list_datasets_uses_cached_rows(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            _write_jsonl(
                artifacts_dir / "motion_windows.jsonl",
                [{"window_id": "walk-a", "dataset": "PPG-DaLiA", "activity_label": "walking"}],
            )
            _write_jsonl(
                artifacts_dir / "vitals_stream.jsonl",
                [{"subject_id": "subject-1", "dataset": "VitalDB", "timestamp": "2024-01-01T00:00:01Z"}],
            )
            _write_jsonl(
                artifacts_dir / "event_catalog.jsonl",
                [{"event_id": "fall-1", "dataset": "UP-Fall", "event_type": "fall_detected"}],
            )
            _write_jsonl(
                artifacts_dir / "stress_stream.jsonl",
                [{"timestamp": "2024-01-01T00:00:00Z", "source_dataset": "WESAD", "stress_state": "stress"}],
            )
            _write_jsonl(
                artifacts_dir / "respiration_stream.jsonl",
                [{"timestamp": "2024-01-01T00:00:00Z", "dataset": "BIDMC", "respiration_rate": 16.0}],
            )

            registry = DatasetRegistry(artifacts_dir)
            registry._load_optional_artifact = lambda name: (_ for _ in ()).throw(AssertionError(f"unexpected optional load: {name}"))  # type: ignore[assignment]

            datasets = registry.list_datasets()

        self.assertEqual(datasets, ["BIDMC", "PPG-DaLiA", "UP-Fall", "VitalDB", "WESAD"])

    def test_get_respiration_sample_filters_by_activity(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            _write_jsonl(artifacts_dir / "motion_windows.jsonl", [])
            _write_jsonl(artifacts_dir / "event_catalog.jsonl", [])
            _write_jsonl(artifacts_dir / "vitals_stream.jsonl", [])
            _write_jsonl(
                artifacts_dir / "respiration_stream.jsonl",
                [
                    {
                        "subject_id": "BIDMC_bidmc01",
                        "dataset": "BIDMC",
                        "timestamp": "2024-01-01T00:00:01Z",
                        "respiration_rate": 18.0,
                        "activity_label": "walking",
                    },
                    {
                        "subject_id": "BIDMC_bidmc02",
                        "dataset": "BIDMC",
                        "timestamp": "2024-01-01T00:00:02Z",
                        "respiration_rate": 12.0,
                        "activity_label": "sleeping",
                    },
                ],
            )

            registry = DatasetRegistry(artifacts_dir)
            sample = registry.get_respiration_sample("sleeping")

        self.assertIsNotNone(sample)
        self.assertEqual(sample["respiration_rate"], 12.0)
        self.assertEqual(sample["timestamp"], "2024-01-01T00:00:02Z")


if __name__ == "__main__":
    unittest.main()
