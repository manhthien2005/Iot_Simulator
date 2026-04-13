from __future__ import annotations

import unittest
from pathlib import Path

from dataset_adapters import PPGDaLiAAdapter, SimpleDataFrame


class TestPPGDaLiAAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        dataset_root = (
            Path(__file__).resolve().parents[1]
        / "datasets"
            / "02_wearable"
            / "PPG-DaLiA"
            / "PPG-DaLiA_Raw"
        )
        cls.adapter = PPGDaLiAAdapter(dataset_root=dataset_root)
        cls.frame = cls.adapter.load_subject("S1")
        cls.report = cls.adapter.validate(cls.frame)
        if isinstance(cls.frame, SimpleDataFrame):
            cls.rows = cls.frame.to_dict()
        else:
            cls.rows = cls.frame.to_dict(orient="records")

    def test_lists_all_subjects(self) -> None:
        subjects = self.adapter.list_subjects()
        self.assertEqual(len(subjects), 15)
        self.assertEqual(subjects[0], "S1")

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

    def test_accel_values_are_scaled(self) -> None:
        accel_x_values = [row["accel_mps2"]["x"] for row in self.rows[:50]]
        self.assertLessEqual(max(abs(value) for value in accel_x_values), 25.0)

    def test_activity_is_populated(self) -> None:
        labels = {row["activity_label"] for row in self.rows[:5000] if row["activity_label"] is not None}
        self.assertTrue(len(labels) > 0)

    def test_heart_rate_is_populated(self) -> None:
        hr_values = [row["heart_rate"] for row in self.rows[:5000] if row["heart_rate"] is not None]
        self.assertTrue(len(hr_values) > 0)


if __name__ == "__main__":
    unittest.main()
