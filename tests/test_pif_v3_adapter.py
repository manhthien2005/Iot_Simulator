from __future__ import annotations

import unittest
from pathlib import Path

from Iot_Simulator.dataset_adapters import PIFV3Adapter, SimpleDataFrame


class TestPIFV3Adapter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        dataset_root = (
            Path(__file__).resolve().parents[1]
        / "datasets"
            / "05_fall"
            / "PIF_v3"
            / "PIF_v3_Raw"
            / "Pif3_Dataset"
        )
        cls.adapter = PIFV3Adapter(dataset_root=dataset_root)
        cls.frame = cls.adapter.load_subject("PID1", "2026-03-22T10:00:00+07:00")
        cls.report = cls.adapter.validate(cls.frame)
        if isinstance(cls.frame, SimpleDataFrame):
            cls.rows = cls.frame.to_dict()
        else:
            cls.rows = cls.frame.to_dict(orient="records")

    def test_lists_all_subjects(self) -> None:
        subjects = self.adapter.list_subjects()
        self.assertEqual(len(subjects), 32)
        self.assertEqual(subjects[0], "PID1")
        self.assertEqual(subjects[-1], "PID32")

    def test_required_columns_exist(self) -> None:
        columns = set(self.rows[0].keys())
        expected = {
            "timestamp",
            "accel_mps2",
            "gyro_radps",
            "orientation_deg",
            "heart_rate",
            "blood_pressure_sys",
            "blood_pressure_dia",
            "spo2",
            "activity_label",
            "fall_variant",
        }
        self.assertTrue(expected.issubset(columns))

    def test_match_rate_is_good_for_pid1(self) -> None:
        self.assertGreaterEqual(self.report["bpm_match_rate_pct"], 85.0)

    def test_accel_is_converted_to_mps2(self) -> None:
        accel_x_values = [row["accel_mps2"]["x"] for row in self.rows[:25]]
        self.assertTrue(all(value is not None for value in accel_x_values))
        self.assertLessEqual(max(abs(value) for value in accel_x_values), 25.0)

    def test_gyro_is_converted_to_radps(self) -> None:
        gyro_x_values = [row["gyro_radps"]["x"] for row in self.rows[:25]]
        self.assertTrue(all(value is not None for value in gyro_x_values))
        self.assertLessEqual(max(abs(value) for value in gyro_x_values), 4.0)

    def test_yaw_is_not_mapped(self) -> None:
        yaw_values = [row["orientation_deg"]["yaw"] for row in self.rows[:50]]
        self.assertTrue(all(value is None for value in yaw_values))


if __name__ == "__main__":
    unittest.main()
