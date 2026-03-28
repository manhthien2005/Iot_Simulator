from __future__ import annotations

import unittest
from pathlib import Path

from Iot_Simulator.dataset_adapters import SimpleDataFrame, UPFallAdapter


class TestUPFallAdapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        dataset_root = (
            Path(__file__).resolve().parents[1]
        / "datasets"
            / "05_fall"
            / "UP-Fall"
            / "UP-Fall_Raw"
        )
        cls.adapter = UPFallAdapter(dataset_root=dataset_root)
        cls.frame = cls.adapter.load_trial("Subject_01", "A01", "S01_A01_T01.csv")
        cls.report = cls.adapter.validate(cls.frame)
        if isinstance(cls.frame, SimpleDataFrame):
            cls.rows = cls.frame.to_dict()
        else:
            cls.rows = cls.frame.to_dict(orient="records")

    def test_lists_all_subjects(self) -> None:
        subjects = self.adapter.list_subjects()
        self.assertEqual(len(subjects), 4)
        self.assertEqual(subjects[0], "Subject_01")
        self.assertEqual(subjects[-1], "Subject_04")

    def test_trial_loads_rows(self) -> None:
        self.assertGreater(len(self.rows), 0)
        self.assertTrue(self.report["timestamp_parse_ok"])

    def test_required_columns_exist(self) -> None:
        expected = {
            "timestamp",
            "subject_id",
            "accel_mps2",
            "gyro_radps",
            "orientation_deg",
            "activity_label",
            "activity_state",
            "fall_variant",
            "source_dataset",
            "metadata_extra",
        }
        self.assertTrue(expected.issubset(set(self.rows[0].keys())))

    def test_accel_is_converted_to_mps2(self) -> None:
        accel_x_values = [row["accel_mps2"]["x"] for row in self.rows[:20]]
        self.assertTrue(all(value is not None for value in accel_x_values))
        self.assertLessEqual(max(abs(value) for value in accel_x_values), 25.0)

    def test_label_map_is_correct_for_a01(self) -> None:
        labels = {row["activity_label"] for row in self.rows}
        states = {row["activity_state"] for row in self.rows}
        fall_variants = {row["fall_variant"] for row in self.rows}
        self.assertEqual(labels, {"Fall_1"})
        self.assertEqual(states, {"fall"})
        self.assertEqual(fall_variants, {"fall_1"})

    def test_trial_metadata_is_present(self) -> None:
        trials = {row["metadata_extra"]["trial"] for row in self.rows}
        self.assertEqual(trials, {1})


if __name__ == "__main__":
    unittest.main()
