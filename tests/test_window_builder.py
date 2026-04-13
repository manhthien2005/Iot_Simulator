from __future__ import annotations

import unittest

from etl_pipeline.window_builder import build_motion_windows


class TestWindowBuilder(unittest.TestCase):
    def test_builds_fixed_length_windows(self) -> None:
        rows = []
        for idx in range(150):
            rows.append(
                {
                    "timestamp": f"2026-03-22T10:00:{idx:02d}",
                    "subject_id": "demo",
                    "source_dataset": "demo_ds",
                    "activity_label": "walking",
                    "fall_variant": None,
                    "accel_mps2": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "gyro_radps": {"x": 0.1, "y": 0.2, "z": 0.3},
                }
            )

        windows = build_motion_windows(rows, target_length=100, stride=25)
        self.assertEqual(len(windows), 3)
        self.assertEqual(len(windows[0]["accel_x"]), 100)
        self.assertEqual(windows[0]["activity_label"], "walking")


if __name__ == "__main__":
    unittest.main()
