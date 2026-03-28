from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Iot_Simulator.dataset_adapters.types import SleepPhase, SleepSessionRecord
from Iot_Simulator.etl_pipeline.normalize import normalize_sleep


class _FakeSleepAdapter:
    def list_subjects(self) -> list[str]:
        return ["S01", "S02"]

    def load_subject(self, subject_id: str) -> SleepSessionRecord:
        return SleepSessionRecord(
            subject_id=subject_id,
            recording_start="2024-01-01T00:00:00+00:00",
            phases=[
                SleepPhase(
                    stage="light",
                    start="2024-01-01T00:00:00+00:00",
                    end="2024-01-01T00:30:00+00:00",
                    duration_s=1800,
                ),
                SleepPhase(
                    stage="deep",
                    start="2024-01-01T00:30:00+00:00",
                    end="2024-01-01T01:30:00+00:00",
                    duration_s=3600,
                ),
            ],
            summary={
                "total_sleep_s": 5400,
                "sleep_efficiency": 0.9,
                "stage_proportions": {
                    "awake": 0.0,
                    "rem": 0.0,
                    "light": 0.33,
                    "deep": 0.67,
                },
                "wake_count": 0,
            },
        )

    def validate(self, record: SleepSessionRecord) -> dict[str, bool]:
        return {
            "stages_valid": True,
            "plausible_total_duration": record.subject_id == "S01",
        }


class TestNormalizeSleepPipeline(unittest.TestCase):
    def test_normalize_sleep_skips_when_dataset_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            with (
                patch(
                    "Iot_Simulator.etl_pipeline.normalize.SleepEdfAdapter",
                    side_effect=FileNotFoundError("missing sleep-edf"),
                ),
                patch("Iot_Simulator.etl_pipeline.normalize.logger.warning") as warning_mock,
            ):
                result = normalize_sleep(output_dir=output_dir, max_subjects=2)

            self.assertTrue(result["skipped"])
            self.assertEqual(result["session_count"], 0)
            self.assertEqual(result["subjects_tried"], 0)
            warning_mock.assert_called_once()

    def test_normalize_sleep_writes_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            with patch("Iot_Simulator.etl_pipeline.normalize.SleepEdfAdapter", _FakeSleepAdapter):
                result = normalize_sleep(output_dir=output_dir, max_subjects=2)

            self.assertFalse(result["skipped"])
            self.assertEqual(result["subjects_tried"], 2)
            self.assertEqual(result["session_count"], 1)
            self.assertIsNotNone(result["output_path"])
            assert result["output_path"] is not None
            self.assertTrue(Path(result["output_path"]).exists())


if __name__ == "__main__":
    unittest.main()
