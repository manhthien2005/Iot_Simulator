from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Iot_Simulator.etl_pipeline.normalize import NormalizedArtifactPipeline
from tests.test_bidmc_adapter import build_bidmc_fixture
from tests.test_vitaldb_adapter import build_vitaldb_fixture


def _read_records(path: Path) -> list[dict[str, object]]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    import pandas as pd  # type: ignore

    return pd.read_parquet(path).to_dict(orient="records")


class TestNormalizedArtifactPipeline(unittest.TestCase):
    @patch("Iot_Simulator.etl_pipeline.normalize.normalize_sleep")
    @patch("Iot_Simulator.etl_pipeline.normalize.PIFV3Adapter")
    def test_pipeline_reuses_single_pif_load(self, pif_cls, normalize_sleep_mock) -> None:
        normalize_sleep_mock.return_value = {
            "skipped": True,
            "session_count": 0,
            "subjects_tried": 0,
            "output_path": None,
        }
        adapter = pif_cls.return_value
        adapter.load_subject.return_value = [
            {
                "timestamp": index,
                "subject_id": "PID1",
                "source_dataset": "PIF_v3",
                "activity_label": "walking",
                "heart_rate": 72.0,
                "spo2": 98.0,
                "blood_pressure_sys": 120.0,
                "blood_pressure_dia": 80.0,
                "accel_mps2": {"x": 0.1, "y": 0.2, "z": 9.7},
                "gyro_radps": {"x": 0.01, "y": 0.02, "z": 0.03},
                "fall_variant": None,
            }
            for index in range(100)
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "normalized_outputs"
            pipeline = NormalizedArtifactPipeline(output_dir)
            config = {
                "pif_v3": {"subjects": ["PID1"], "session_start": "2026-03-22T10:00:00+07:00"},
                "up_fall": {"subjects": []},
                "pamap2": {"subjects": [], "session_start": "2026-03-22T10:00:00+07:00"},
                "ppg_dalia": {"subjects": []},
                "vitaldb": {"enabled": False, "dataset_root": None, "cases": []},
                "bidmc": {"enabled": False, "dataset_root": None, "subjects": []},
                "wesad": {"enabled": False, "dataset_root": None, "subjects": []},
                "sleep": {"max_subjects": 0},
            }

            pipeline.run(config=config)

        self.assertEqual(adapter.load_subject.call_count, 1)

    def test_pipeline_writes_artifacts(self) -> None:
        output_dir = (
            Path(__file__).resolve().parents[1]
            / "normalized_artifacts_test"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        pipeline = NormalizedArtifactPipeline(output_dir)
        outputs = pipeline.run()

        for key in ("motion_windows", "vitals_stream", "event_catalog", "summary"):
            self.assertIn(key, outputs)
            self.assertTrue(Path(outputs[key]).exists())

        summary = json.loads(Path(outputs["summary"]).read_text(encoding="utf-8"))
        self.assertGreater(summary["counts"]["motion_windows"], 0)
        self.assertGreater(summary["counts"]["vitals_rows"], 0)
        self.assertGreater(summary["counts"]["event_rows"], 0)
        self.assertIn("stress_rows", summary["counts"])
        if summary["counts"]["stress_rows"] > 0:
            self.assertIn("stress_stream", outputs)
            self.assertTrue(Path(outputs["stress_stream"]).exists())

    @patch("Iot_Simulator.etl_pipeline.normalize.WESADAdapter")
    def test_pipeline_writes_stress_stream_from_wesad(self, wesad_cls) -> None:
        adapter = wesad_cls.return_value
        adapter.load_subject.return_value = [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "subject_id": "WESAD_S2",
                "stress_state": "stress",
                "heart_rate": 88.0,
                "source_dataset": "WESAD",
            },
            {
                "timestamp": "2024-01-01T00:00:02Z",
                "subject_id": "WESAD_S2",
                "stress_state": "neutral",
                "heart_rate": 70.0,
                "source_dataset": "WESAD",
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "normalized_outputs"
            pipeline = NormalizedArtifactPipeline(output_dir)
            config = {
                "pif_v3": {"subjects": [], "session_start": "2026-03-22T10:00:00+07:00"},
                "up_fall": {"subjects": []},
                "pamap2": {"subjects": [], "session_start": "2026-03-22T10:00:00+07:00"},
                "ppg_dalia": {"subjects": []},
                "vitaldb": {"enabled": False, "dataset_root": None, "cases": []},
                "wesad": {"enabled": True, "dataset_root": None, "subjects": ["S2"]},
                "sleep": {"max_subjects": 0},
            }

            outputs = pipeline.run(config=config)
            self.assertIn("stress_stream", outputs)

            stress_path = Path(outputs["stress_stream"])
            rows = _read_records(stress_path)
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["stress_state"] for row in rows}, {"stress", "neutral"})
            self.assertTrue(all(row["source_dataset"] == "WESAD" for row in rows))

            summary = json.loads(Path(outputs["summary"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["counts"]["stress_rows"], 2)

    def test_pipeline_supports_opt_in_vitaldb_only_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset_root = root / "VitalDB"
            output_dir = root / "normalized_outputs"
            build_vitaldb_fixture(dataset_root)

            pipeline = NormalizedArtifactPipeline(output_dir)
            config = {
                "pif_v3": {"subjects": [], "session_start": "2026-03-22T10:00:00+07:00"},
                "up_fall": {"subjects": []},
                "pamap2": {"subjects": [], "session_start": "2026-03-22T10:00:00+07:00"},
                "ppg_dalia": {"subjects": []},
                "vitaldb": {
                    "enabled": True,
                    "dataset_root": str(dataset_root),
                    "cases": [{"caseid": "1", "session_start": "2026-03-22T10:00:00+07:00"}],
                },
                "wesad": {"enabled": False, "dataset_root": None, "subjects": []},
                "sleep": {"max_subjects": 0},
            }

            outputs = pipeline.run(config=config)
            summary = json.loads(Path(outputs["summary"]).read_text(encoding="utf-8"))

            self.assertGreater(summary["counts"]["vitals_rows"], 0)
            self.assertEqual(summary["counts"]["vitaldb_cases_loaded"], 1)
            self.assertEqual(summary["counts"]["motion_rows"], 0)
            self.assertEqual(summary["counts"]["event_rows"], 0)
            default_vitaldb = NormalizedArtifactPipeline.default_config()["vitaldb"]
            self.assertEqual(default_vitaldb["enabled"], bool(default_vitaldb["cases"]))

            vitals_path = Path(outputs["vitals_stream"])
            rows = _read_records(vitals_path)

            self.assertTrue(rows)
            self.assertTrue(any(row["dataset"] == "VitalDB" for row in rows))
            self.assertTrue(any(row["subject_id"] == "VITALDB_CASE_1" for row in rows))
            self.assertTrue(all(row["spo2"] is not None for row in rows))
            self.assertTrue(all(row["blood_pressure_sys"] is not None for row in rows))
            self.assertTrue(all(row["blood_pressure_dia"] is not None for row in rows))

    def test_pipeline_supports_opt_in_bidmc_only_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dataset_root = root / "BIDMC_Raw"
            output_dir = root / "normalized_outputs"
            build_bidmc_fixture(dataset_root)

            pipeline = NormalizedArtifactPipeline(output_dir)
            config = {
                "pif_v3": {"subjects": [], "session_start": "2026-03-22T10:00:00+07:00"},
                "up_fall": {"subjects": []},
                "pamap2": {"subjects": [], "session_start": "2026-03-22T10:00:00+07:00"},
                "ppg_dalia": {"subjects": []},
                "vitaldb": {"enabled": False, "dataset_root": None, "cases": []},
                "bidmc": {
                    "enabled": True,
                    "dataset_root": str(dataset_root),
                    "subjects": ["bidmc01"],
                },
                "wesad": {"enabled": False, "dataset_root": None, "subjects": []},
                "sleep": {"max_subjects": 0},
            }

            outputs = pipeline.run(config=config)
            summary = json.loads(Path(outputs["summary"]).read_text(encoding="utf-8"))

            self.assertIn("respiration_stream", outputs)
            self.assertGreater(summary["counts"]["respiration_rows"], 0)
            self.assertEqual(summary["counts"]["vitals_rows"], 0)
            self.assertEqual(summary["counts"]["motion_rows"], 0)
            rows = _read_records(Path(outputs["respiration_stream"]))
            self.assertTrue(rows)
            self.assertTrue(all(row["dataset"] == "BIDMC" for row in rows))
            self.assertTrue(all(row["respiration_rate"] is not None for row in rows))


if __name__ == "__main__":
    unittest.main()
