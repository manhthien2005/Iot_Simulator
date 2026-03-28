from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "datasets"
    / "01_vitals"
    / "VitalDB"
    / "etl"
    / "download_vitaldb_subset.py"
)

SPEC = importlib.util.spec_from_file_location("vitaldb_subset_downloader", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def gzip_csv_bytes(fieldnames: list[str], rows: list[dict[str, str]]) -> bytes:
    payload = [",".join(fieldnames)]
    for row in rows:
        payload.append(",".join(row.get(field, "") for field in fieldnames))
    return gzip.compress("\n".join(payload).encode("utf-8"))


class TestVitalDBSelectionHelpers(unittest.TestCase):
    def test_select_tracks_exact_match_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            trks_path = Path(temp_dir) / "trks.csv.gz"
            rows = [
                {"caseid": "2", "tname": "Solar8000/HR", "tid": "12"},
                {"caseid": "1", "tname": "Solar8000/PLETH_SPO2", "tid": "10"},
                {"caseid": "5", "tname": "Solar8000/NIBP_SBP", "tid": "40"},
                {"caseid": "4", "tname": "Solar8000/NIBP_DBP", "tid": "31"},
                {"caseid": "8", "tname": "SNUADC/HR_RAW", "tid": "99"},
                {"caseid": "9", "tname": "Solar8000/HR", "tid": ""},
            ]
            trks_path.write_bytes(gzip_csv_bytes(["caseid", "tname", "tid"], rows))

            total_rows, selected_rows, invalid_rows = MODULE.select_tracks_from_trks(trks_path)

            self.assertEqual(total_rows, 6)
            self.assertEqual(invalid_rows, 1)
            self.assertEqual([row["tid"] for row in selected_rows], ["10", "12", "31", "40"])
            self.assertEqual({row["tname"] for row in selected_rows}, set(MODULE.TRACK_DIRECTORY_MAP.keys()))
            self.assertEqual(
                {row["source_tname"] for row in selected_rows},
                {
                    "Solar8000/PLETH_SPO2",
                    "Solar8000/HR",
                    "Solar8000/NIBP_DBP",
                    "Solar8000/NIBP_SBP",
                },
            )

    def test_track_destination_uses_expected_directory_alias(self) -> None:
        root = Path("D:/tmp/VitalDB_Raw/tracks")
        row = {"caseid": "7", "tname": "Solar8000/NIBP_SYS", "tid": "12345"}
        destination = MODULE.track_destination(root, row)
        self.assertEqual(
            destination,
            root / "Solar8000_NIBP_SYS" / "12345.csv.gz",
        )


class TestVitalDBDownloaderRun(unittest.TestCase):
    def test_run_writes_metadata_selection_manifest_and_supports_skip_existing(self) -> None:
        cases_payload = gzip_csv_bytes(
            ["caseid", "age", "sex"],
            [
                {"caseid": "1", "age": "65", "sex": "M"},
                {"caseid": "2", "age": "70", "sex": "F"},
            ],
        )
        trks_payload = gzip_csv_bytes(
            ["caseid", "tname", "tid"],
            [
                {"caseid": "1", "tname": "Solar8000/HR", "tid": "11"},
                {"caseid": "1", "tname": "Solar8000/NIBP_SBP", "tid": "21"},
                {"caseid": "2", "tname": "Solar8000/PLETH_SPO2", "tid": "31"},
                {"caseid": "2", "tname": "Solar8000/NIBP_DBP", "tid": "41"},
            ],
        )
        track_payloads = {
            "https://api.vitaldb.net/11": b"time,val\n0,82\n",
            "https://api.vitaldb.net/21": gzip.compress(b"time,val\n0,121\n"),
            "https://api.vitaldb.net/31": b"time,val\n0,98\n",
            "https://api.vitaldb.net/41": b"time,val\n0,77\n",
        }

        fetch_calls: list[str] = []

        def fake_fetcher(url: str) -> bytes:
            fetch_calls.append(url)
            if url == MODULE.CASES_ENDPOINT:
                return cases_payload
            if url == MODULE.TRKS_ENDPOINT:
                return trks_payload
            return track_payloads[url]

        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_root = Path(temp_dir) / "VitalDB"
            downloader = MODULE.VitalDBSubsetDownloader(
                dataset_root=dataset_root,
                workers=2,
                fetcher=fake_fetcher,
            )

            manifest_first = downloader.run(limit_tids=3)

            self.assertEqual(manifest_first["counts"]["total_cases"], 2)
            self.assertEqual(manifest_first["counts"]["total_tracks"], 4)
            self.assertEqual(manifest_first["counts"]["selected_tracks"], 4)
            self.assertEqual(manifest_first["counts"]["queued_track_downloads"], 3)
            self.assertEqual(manifest_first["counts"]["downloaded"], 3)
            self.assertEqual(manifest_first["counts"]["skipped_existing"], 0)
            self.assertEqual(manifest_first["counts"]["failed"], 0)

            self.assertTrue((dataset_root / "VitalDB_Raw" / "metadata" / "cases.csv.gz").exists())
            self.assertTrue((dataset_root / "VitalDB_Raw" / "metadata" / "trks.csv.gz").exists())
            self.assertTrue((dataset_root / "VitalDB_Raw" / "metadata" / "selected_tracks.csv").exists())
            self.assertTrue((dataset_root / "download_manifest.json").exists())

            selected_tracks_rows: list[dict[str, str]] = []
            with (dataset_root / "VitalDB_Raw" / "metadata" / "selected_tracks.csv").open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                selected_tracks_rows = list(csv.DictReader(handle))
            self.assertEqual(len(selected_tracks_rows), 4)
            self.assertEqual(set(row["tname"] for row in selected_tracks_rows), set(MODULE.TRACK_DIRECTORY_MAP.keys()))
            self.assertIn("source_tname", selected_tracks_rows[0])

            hr_track = dataset_root / "VitalDB_Raw" / "tracks" / "SNUADC_HR" / "11.csv.gz"
            self.assertTrue(hr_track.exists())
            with gzip.open(hr_track, "rt", encoding="utf-8") as handle:
                self.assertIn("time,val", handle.read())

            calls_after_first_run = list(fetch_calls)

            manifest_second = downloader.run(limit_tids=3)

            self.assertEqual(manifest_second["counts"]["downloaded"], 0)
            self.assertEqual(manifest_second["counts"]["skipped_existing"], 3)
            self.assertEqual(manifest_second["counts"]["failed"], 0)
            self.assertEqual(calls_after_first_run, fetch_calls)

            manifest_disk = json.loads((dataset_root / "download_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest_disk["counts"]["skipped_existing"],
                manifest_second["counts"]["skipped_existing"],
            )


if __name__ == "__main__":
    unittest.main()
