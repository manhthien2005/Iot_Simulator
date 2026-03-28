from __future__ import annotations

import csv
import gzip
import tempfile
import unittest
from pathlib import Path

from Iot_Simulator.dataset_adapters.vitaldb_adapter import (
    BP_DIA_TRACK,
    BP_SYS_TRACK,
    HR_TRACK,
    SOURCE_DATASET,
    SPO2_TRACK,
    VitalDBAdapter,
)


def write_gzip_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_plain_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_vitaldb_fixture(dataset_root: Path) -> None:
    metadata_dir = dataset_root / "VitalDB_Raw" / "metadata"
    tracks_dir = dataset_root / "VitalDB_Raw" / "tracks"

    write_plain_csv(
        metadata_dir / "selected_tracks.csv",
        ["caseid", "tname", "tid", "source_tname"],
        [
            {"caseid": "1", "tname": HR_TRACK, "tid": "hr1", "source_tname": "Solar8000/HR"},
            {"caseid": "1", "tname": SPO2_TRACK, "tid": "spo21", "source_tname": "Solar8000/PLETH_SPO2"},
            {"caseid": "1", "tname": BP_SYS_TRACK, "tid": "sys1", "source_tname": "Solar8000/NIBP_SBP"},
            {"caseid": "1", "tname": BP_DIA_TRACK, "tid": "dia1", "source_tname": "Solar8000/NIBP_DBP"},
            {"caseid": "2", "tname": HR_TRACK, "tid": "hr2", "source_tname": "Solar8000/HR"},
            {"caseid": "3", "tname": HR_TRACK, "tid": "hr3", "source_tname": "Solar8000/HR"},
        ],
    )

    write_gzip_csv(
        metadata_dir / "cases.csv.gz",
        ["caseid", "age", "sex", "height", "weight", "bmi", "asa"],
        [
            {"caseid": "1", "age": "77", "sex": "M", "height": "160.2", "weight": "67.5", "bmi": "26.3", "asa": "2"},
            {"caseid": "2", "age": "70", "sex": "F", "height": "155.0", "weight": "60.0", "bmi": "24.9", "asa": "3"},
            {"caseid": "3", "age": "62", "sex": "F", "height": "158.0", "weight": "58.0", "bmi": "23.2", "asa": "2"},
        ],
    )

    write_gzip_csv(
        tracks_dir / "SNUADC_HR" / "hr1.csv.gz",
        ["Time", "Solar8000/HR"],
        [
            {"Time": "1.0", "Solar8000/HR": "80"},
            {"Time": "3.0", "Solar8000/HR": "82"},
            {"Time": "5.0", "Solar8000/HR": "81"},
        ],
    )
    write_gzip_csv(
        tracks_dir / "SNUADC_SPO2" / "spo21.csv.gz",
        ["Time", "Solar8000/PLETH_SPO2"],
        [
            {"Time": "1.2", "Solar8000/PLETH_SPO2": "97"},
            {"Time": "5.2", "Solar8000/PLETH_SPO2": "98"},
        ],
    )
    write_gzip_csv(
        tracks_dir / "Solar8000_NIBP_SYS" / "sys1.csv.gz",
        ["Time", "Solar8000/NIBP_SBP"],
        [
            {"Time": "1.0", "Solar8000/NIBP_SBP": "120"},
            {"Time": "4.0", "Solar8000/NIBP_SBP": "121"},
        ],
    )
    write_gzip_csv(
        tracks_dir / "Solar8000_NIBP_DIA" / "dia1.csv.gz",
        ["Time", "Solar8000/NIBP_DBP"],
        [
            {"Time": "1.0", "Solar8000/NIBP_DBP": "80"},
            {"Time": "4.0", "Solar8000/NIBP_DBP": "81"},
        ],
    )
    write_gzip_csv(
        tracks_dir / "SNUADC_HR" / "hr3.csv.gz",
        ["Time", "Solar8000/HR"],
        [
            {"Time": "2.0", "Solar8000/HR": "72"},
            {"Time": "4.0", "Solar8000/HR": "74"},
        ],
    )


class TestVitalDBAdapter(unittest.TestCase):
    def test_list_subjects_only_returns_cases_with_local_hr_track(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_root = Path(temp_dir) / "VitalDB"
            build_vitaldb_fixture(dataset_root)

            adapter = VitalDBAdapter(dataset_root=dataset_root)

            self.assertEqual(adapter.list_subjects(), ["1", "3"])

    def test_load_subject_maps_hr_spo2_and_bp_on_hr_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_root = Path(temp_dir) / "VitalDB"
            build_vitaldb_fixture(dataset_root)

            adapter = VitalDBAdapter(dataset_root=dataset_root)
            frame = adapter.load_subject("1", "2026-03-22T10:00:00+07:00")
            rows = frame.to_dict(orient="records")

            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["timestamp"], "2026-03-22T10:00:01+07:00")
            self.assertEqual(rows[0]["subject_id"], "VITALDB_CASE_1")
            self.assertEqual(rows[0]["heart_rate"], 80.0)
            self.assertEqual(rows[0]["spo2"], 97.0)
            self.assertEqual(rows[0]["blood_pressure_sys"], 120.0)
            self.assertEqual(rows[0]["blood_pressure_dia"], 80.0)
            self.assertEqual(rows[1]["blood_pressure_sys"], 120.0)
            self.assertEqual(rows[1]["blood_pressure_dia"], 80.0)
            self.assertEqual(rows[2]["blood_pressure_sys"], 121.0)
            self.assertEqual(rows[2]["blood_pressure_dia"], 81.0)
            self.assertEqual(rows[2]["spo2"], 98.0)
            self.assertEqual(rows[0]["source_dataset"], SOURCE_DATASET)
            self.assertEqual(rows[0]["metadata_extra"]["demographics"]["age"], "77")

    def test_validate_passes_with_missing_optional_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_root = Path(temp_dir) / "VitalDB"
            build_vitaldb_fixture(dataset_root)

            adapter = VitalDBAdapter(dataset_root=dataset_root)
            frame = adapter.load_subject("3", "2026-03-22T10:00:00+07:00")
            report = adapter.validate(frame)

            self.assertTrue(report["required_columns_present"])
            self.assertTrue(report["heart_rate_populated"])
            self.assertTrue(report["heart_rate_range_ok"])
            self.assertTrue(report["spo2_range_ok"])
            self.assertTrue(report["blood_pressure_range_ok"])
            self.assertEqual(
                report["source_tracks_present"],
                {
                    HR_TRACK: True,
                    SPO2_TRACK: False,
                    BP_SYS_TRACK: False,
                    BP_DIA_TRACK: False,
                },
            )


if __name__ == "__main__":
    unittest.main()
