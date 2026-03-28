from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from Iot_Simulator.dataset_adapters.bidmc_adapter import BIDMCAdapter, SOURCE_DATASET


def write_plain_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_bidmc_fixture(raw_root: Path) -> None:
    numerics_dir = raw_root / "bidmc_csv"
    write_plain_csv(
        numerics_dir / "bidmc_01_Numerics.csv",
        ["Time [s]", "HR", "PULSE", "RESP", "SpO2"],
        [
            {"Time [s]": "0", "HR": "94", "PULSE": "93", "RESP": "25", "SpO2": "97"},
            {"Time [s]": "1", "HR": "92", "PULSE": "91", "RESP": "26", "SpO2": "96"},
        ],
    )
    write_plain_csv(
        numerics_dir / "bidmc_02_Numerics.csv",
        ["Time [s]", "HR", "RR", "SpO2"],
        [
            {"Time [s]": "0", "HR": "80", "RR": "18", "SpO2": "98"},
            {"Time [s]": "2", "HR": "81", "RR": "19", "SpO2": "97"},
        ],
    )


class TestBIDMCAdapter(unittest.TestCase):
    def test_list_subjects_discovers_numerics_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_root = Path(temp_dir) / "BIDMC_Raw"
            build_bidmc_fixture(raw_root)

            adapter = BIDMCAdapter(dataset_root=raw_root)

            self.assertEqual(adapter.list_subjects(), ["bidmc01", "bidmc02"])

    def test_load_subject_maps_resp_column_and_default_session_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_root = Path(temp_dir) / "BIDMC_Raw"
            build_bidmc_fixture(raw_root)

            adapter = BIDMCAdapter(dataset_root=raw_root)
            frame = adapter.load_subject("bidmc01")
            rows = frame.to_dict(orient="records")

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["timestamp"], "2026-03-22T10:00:00+07:00")
            self.assertEqual(rows[0]["subject_id"], "BIDMC_bidmc01")
            self.assertEqual(rows[0]["heart_rate"], 94.0)
            self.assertEqual(rows[0]["spo2"], 97.0)
            self.assertEqual(rows[0]["respiration_rate"], 25.0)
            self.assertEqual(rows[0]["source_dataset"], SOURCE_DATASET)

    def test_validate_supports_rr_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_root = Path(temp_dir) / "BIDMC_Raw"
            build_bidmc_fixture(raw_root)

            adapter = BIDMCAdapter(dataset_root=raw_root)
            frame = adapter.load_subject("bidmc02", "2026-03-22T10:00:00+07:00")
            report = adapter.validate(frame)

            self.assertTrue(report["required_columns_present"])
            self.assertTrue(report["heart_rate_populated"])
            self.assertTrue(report["respiration_populated"])
            self.assertTrue(report["heart_rate_range_ok"])
            self.assertTrue(report["respiration_range_ok"])
            self.assertTrue(report["spo2_range_ok"])


if __name__ == "__main__":
    unittest.main()
