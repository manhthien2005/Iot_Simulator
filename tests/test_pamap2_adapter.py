from __future__ import annotations

import unittest
from pathlib import Path

from dataset_adapters import PAMAP2Adapter, SimpleDataFrame


class TestPAMAP2Adapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        dataset_root = (
            Path(__file__).resolve().parents[1]
        / "datasets"
            / "04_activity"
            / "PAMAP2"
            / "PAMAP2_Raw"
            / "Protocol"
        )
        cls.adapter = PAMAP2Adapter(dataset_root=dataset_root)
        cls.frame = cls.adapter.load_subject("subject101", "2026-03-22T10:00:00+07:00")
        cls.report = cls.adapter.validate(cls.frame)
        if isinstance(cls.frame, SimpleDataFrame):
            cls.rows = cls.frame.to_dict()
        else:
            cls.rows = cls.frame.to_dict(orient="records")

    def test_lists_all_subjects(self) -> None:
        subjects = self.adapter.list_subjects()
        self.assertEqual(len(subjects), 9)
        self.assertEqual(subjects[0], "subject101")
        self.assertEqual(subjects[-1], "subject109")

    def test_required_columns_exist(self) -> None:
        expected = {
            "timestamp",
            "subject_id",
            "accel_mps2",
            "gyro_radps",
            "orientation_deg",
            "heart_rate",
            "activity_label",
            "activity_state",
            "source_dataset",
            "metadata_extra",
        }
        self.assertTrue(expected.issubset(set(self.rows[0].keys())))

    def test_heart_rate_nan_is_none(self) -> None:
        self.assertIsNone(self.rows[1]["heart_rate"])

    def test_units_are_preserved(self) -> None:
        accel_x_values = [row["accel_mps2"]["x"] for row in self.rows[:25]]
        gyro_x_values = [row["gyro_radps"]["x"] for row in self.rows[:25]]
        self.assertLessEqual(max(abs(value) for value in accel_x_values), 50.0)
        self.assertLessEqual(max(abs(value) for value in gyro_x_values), 20.0)

    def test_activity_map_is_valid(self) -> None:
        self.assertIn("lying", set(label for label in self.report["activity_labels_found"] if label))


if __name__ == "__main__":
    unittest.main()
