from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from Iot_Simulator.dataset_adapters.sleep_edf_adapter import SleepEdfAdapter
from Iot_Simulator.dataset_adapters.types import SleepPhase


class TestSleepEdfAdapterUnit(unittest.TestCase):
    def test_stage_map_coverage(self) -> None:
        expected = {
            "Sleep stage W",
            "Sleep stage R",
            "Sleep stage 1",
            "Sleep stage 2",
            "Sleep stage 3",
            "Sleep stage 4",
            "Sleep stage ?",
            "Movement time",
        }
        self.assertEqual(set(SleepEdfAdapter.STAGE_MAP.keys()), expected)
        self.assertEqual(SleepEdfAdapter.STAGE_MAP["Sleep stage W"], "awake")
        self.assertIsNone(SleepEdfAdapter.STAGE_MAP["Sleep stage ?"])

    def test_merge_contiguous_stages(self) -> None:
        start = datetime(2026, 3, 23, 22, 0, tzinfo=timezone.utc)
        segments = [
            ("light", start, start + timedelta(seconds=30)),
            ("light", start + timedelta(seconds=30), start + timedelta(seconds=60)),
            ("deep", start + timedelta(seconds=60), start + timedelta(seconds=90)),
        ]
        merged = SleepEdfAdapter._merge_contiguous_segments(segments)
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0][0], "light")
        self.assertEqual(int((merged[0][2] - merged[0][1]).total_seconds()), 60)

    def test_summary_calculation(self) -> None:
        phases = [
            SleepPhase(stage="awake", start="2026-03-23T22:00:00+00:00", end="2026-03-23T22:01:00+00:00", duration_s=60),
            SleepPhase(stage="light", start="2026-03-23T22:01:00+00:00", end="2026-03-23T22:03:00+00:00", duration_s=120),
            SleepPhase(stage="rem", start="2026-03-23T22:03:00+00:00", end="2026-03-23T22:04:00+00:00", duration_s=60),
            SleepPhase(stage="awake", start="2026-03-23T22:04:00+00:00", end="2026-03-23T22:04:30+00:00", duration_s=30),
        ]
        summary = SleepEdfAdapter._build_summary(phases)
        self.assertEqual(summary["total_sleep_s"], 180)
        self.assertAlmostEqual(summary["sleep_efficiency"], 180 / 270, places=6)
        self.assertEqual(summary["wake_count"], 1)
        self.assertIn("deep", summary["stage_proportions"])

    def test_list_subjects_from_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "SC4001EC-Hypnogram.edf").write_bytes(b"")
            (root / "SC4011E0-Hypnogram.edf").write_bytes(b"")
            (root / "invalid.txt").write_text("x", encoding="utf-8")
            adapter = SleepEdfAdapter(dataset_root=root)
            subjects = adapter.list_subjects()
            self.assertEqual(subjects, ["SC4001", "SC4011"])


DATASET_ROOT = Path(__file__).resolve().parents[1] / "datasets" / "03_sleep" / "Sleep-EDF" / "Sleep-EDF_Raw" / "sleep-cassette"


@unittest.skipUnless(DATASET_ROOT.exists(), "Sleep-EDF local dataset is not present")
class TestSleepEdfAdapterIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adapter = SleepEdfAdapter(dataset_root=DATASET_ROOT)

    def test_load_one_subject(self) -> None:
        subjects = self.adapter.list_subjects()
        self.assertGreater(len(subjects), 0)
        subject_id = subjects[0]
        record = self.adapter.load_subject(subject_id)
        report = self.adapter.validate(record)
        self.assertEqual(record.subject_id, subject_id)
        self.assertGreater(len(record.phases), 0)
        self.assertTrue(report["durations_multiple_of_30"])
        self.assertTrue(report["stages_valid"])
        self.assertTrue(report["plausible_total_duration"])
        self.assertGreater(record.summary.get("total_sleep_s", 0), 0)


if __name__ == "__main__":
    unittest.main()
