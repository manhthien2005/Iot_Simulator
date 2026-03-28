from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from .base_adapter import DatasetAdapter, SimpleDataFrame

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    pd = None

G_TO_MPS2 = 9.81
DEG_TO_RAD = math.pi / 180.0
SOURCE_DATASET = "UP_Fall"
TIME_FORMAT = "%d-%b-%Y %H:%M:%S"

ACTIVITY_MAP: dict[str, dict[str, str | None]] = {
    "A01": {"activity_label": "Fall_1", "activity_state": "fall", "fall_variant": "fall_1"},
    "A02": {"activity_label": "Fall_2", "activity_state": "fall", "fall_variant": "fall_2"},
    "A03": {"activity_label": "Fall_3", "activity_state": "fall", "fall_variant": "fall_3"},
    "A04": {"activity_label": "Fall_4", "activity_state": "fall", "fall_variant": "fall_4"},
    "A05": {"activity_label": "Fall_5", "activity_state": "fall", "fall_variant": "fall_5"},
    "A06": {"activity_label": "Fall_6", "activity_state": "fall", "fall_variant": "fall_6"},
    "A07": {"activity_label": "Standing", "activity_state": "standing", "fall_variant": None},
    "A08": {"activity_label": "Walking", "activity_state": "walking", "fall_variant": None},
    "A09": {"activity_label": "Fall_7", "activity_state": "fall", "fall_variant": "fall_7"},
    "A10": {"activity_label": "Fall_8", "activity_state": "fall", "fall_variant": "fall_8"},
    "A11": {"activity_label": "Lying", "activity_state": "lying", "fall_variant": None},
}


def parse_up_fall_time(time_str: str) -> datetime:
    return datetime.strptime(time_str.strip(), TIME_FORMAT)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def _subject_sort_key(subject_id: str) -> tuple[int, str]:
    digits = "".join(ch for ch in subject_id if ch.isdigit())
    return (int(digits) if digits else 0, subject_id)


class UPFallAdapter(DatasetAdapter):
    REQUIRED_COLUMNS = [
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
    ]

    def __init__(self, dataset_root: str | Path | None = None) -> None:
        default_root = Path(__file__).resolve().parents[1] / "datasets" / "05_fall" / "UP-Fall" / "UP-Fall_Raw"
        self.dataset_root = Path(dataset_root) if dataset_root else default_root
        if not self.dataset_root.exists():
            raise FileNotFoundError(f"UP-Fall dataset root not found: {self.dataset_root}")
        self._last_report: dict[str, Any] = {}

    @property
    def last_report(self) -> dict[str, Any]:
        return dict(self._last_report)

    def list_subjects(self) -> list[str]:
        subjects = [p.name for p in self.dataset_root.iterdir() if p.is_dir() and p.name.startswith("Subject_")]
        return sorted(subjects, key=_subject_sort_key)

    def load_subject(self, subject_id: str, session_start: str | None = None) -> Any:
        subject_dir = self.dataset_root / subject_id
        if not subject_dir.exists():
            raise FileNotFoundError(f"Subject folder not found: {subject_dir}")

        rows: list[dict[str, Any]] = []
        trials_loaded = 0
        activity_codes: list[str] = []
        for activity_dir in sorted([p for p in subject_dir.iterdir() if p.is_dir()]):
            activity_code = activity_dir.name
            activity_codes.append(activity_code)
            for csv_path in sorted(activity_dir.glob("*.csv")):
                rows.extend(self._load_trial_rows(subject_id, activity_code, csv_path))
                trials_loaded += 1

        self._last_report = self._build_report(subject_id, rows, trials_loaded, activity_codes)
        return self._build_frame(rows)

    def load_trial(self, subject_id: str, activity_code: str, trial_name: str) -> Any:
        csv_path = self.dataset_root / subject_id / activity_code / trial_name
        rows = self._load_trial_rows(subject_id, activity_code, csv_path)
        self._last_report = self._build_report(subject_id, rows, 1, [activity_code])
        return self._build_frame(rows)

    def validate(self, df: Any) -> dict[str, Any]:
        rows = self._rows_from_frame(df)
        columns = set(rows[0].keys()) if rows else set()
        accel_bounds_ok = all(
            self._vector_abs_max(row.get("accel_mps2")) <= 25.0
            for row in rows
            if row.get("accel_mps2") is not None
        )
        gyro_has_values = all(
            row.get("gyro_radps") is not None and any(v is not None for v in row["gyro_radps"].values())
            for row in rows[: min(20, len(rows))]
        )
        timestamp_parse_ok = all("T" in str(row.get("timestamp")) for row in rows[: min(20, len(rows))])

        return {
            **self._last_report,
            "row_count": len(rows),
            "required_columns_present": all(col in columns for col in self.REQUIRED_COLUMNS),
            "accel_bounds_ok": accel_bounds_ok,
            "gyro_has_values": gyro_has_values,
            "timestamp_parse_ok": timestamp_parse_ok,
        }

    @staticmethod
    def format_validation_report(report: dict[str, Any]) -> str:
        labels = ", ".join(sorted(report.get("activity_labels_found", [])))
        return (
            f"[UP_Fall ETL] Subject {report.get('subject_id', 'unknown')}\n"
            f"  Rows:           {report.get('row_count', report.get('rows_loaded', 0))}\n"
            f"  Trials loaded:  {report.get('trials_loaded', 0)}\n"
            f"  Activity codes: {report.get('activity_codes', [])}\n"
            f"  Labels found:   [{labels}]\n"
            f"  WRST_ACC_X g:   {report.get('wrist_acc_x_g_range')}\n"
            f"  WRST_ANG_X d/s: {report.get('wrist_ang_x_deg_range')}"
        )

    def _load_trial_rows(
        self,
        subject_id: str,
        activity_code: str,
        csv_path: Path,
    ) -> list[dict[str, Any]]:
        if not csv_path.exists():
            raise FileNotFoundError(f"UP-Fall trial not found: {csv_path}")
        mapping = ACTIVITY_MAP.get(activity_code, {
            "activity_label": activity_code,
            "activity_state": "unknown",
            "fall_variant": None,
        })
        trial = self._extract_trial(csv_path.stem)

        rows: list[dict[str, Any]] = []
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(f"CSV file has no header: {csv_path}")
            for raw_row in reader:
                row = {key.strip(): (value.strip() if isinstance(value, str) else value) for key, value in raw_row.items()}
                timestamp = parse_up_fall_time(str(row["TIME"]))
                rows.append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "subject_id": f"UP_{subject_id}",
                        "accel_mps2": {
                            "x": self._convert_acc(row.get("WRST_ACC_X")),
                            "y": self._convert_acc(row.get("WRST_ACC_Y")),
                            "z": self._convert_acc(row.get("WRST_ACC_Z")),
                        },
                        "gyro_radps": {
                            "x": self._convert_gyro(row.get("WRST_ANG_X")),
                            "y": self._convert_gyro(row.get("WRST_ANG_Y")),
                            "z": self._convert_gyro(row.get("WRST_ANG_Z")),
                        },
                        "orientation_deg": {"roll": None, "pitch": None, "yaw": None},
                        "activity_label": mapping["activity_label"],
                        "activity_state": mapping["activity_state"],
                        "fall_variant": mapping["fall_variant"],
                        "source_dataset": SOURCE_DATASET,
                        "metadata_extra": {
                            "trial": trial,
                            "activity_code": activity_code,
                            "sensor_position": "wrist",
                            "wrist_luminosity": _safe_float(row.get("WRST_LUMINOSITY")),
                            "belt_acc": [
                                _safe_float(row.get("BELT_ACC_X")),
                                _safe_float(row.get("BELT_ACC_Y")),
                                _safe_float(row.get("BELT_ACC_Z")),
                            ],
                            "neck_acc": [
                                _safe_float(row.get("NECK_ACC_X")),
                                _safe_float(row.get("NECK_ACC_Y")),
                                _safe_float(row.get("NECK_ACC_Z")),
                            ],
                        },
                    }
                )
        return rows

    @staticmethod
    def _extract_trial(stem: str) -> int | None:
        parts = stem.split("_")
        for part in parts:
            if part.startswith("T") and part[1:].isdigit():
                return int(part[1:])
        return None

    @staticmethod
    def _convert_acc(value: Any) -> float | None:
        parsed = _safe_float(value)
        return None if parsed is None else round(parsed * G_TO_MPS2, 6)

    @staticmethod
    def _convert_gyro(value: Any) -> float | None:
        parsed = _safe_float(value)
        return None if parsed is None else round(parsed * DEG_TO_RAD, 6)

    def _build_frame(self, rows: list[dict[str, Any]]) -> Any:
        if pd is not None:
            return pd.DataFrame(rows)
        return SimpleDataFrame(rows)

    @staticmethod
    def _rows_from_frame(frame: Any) -> list[dict[str, Any]]:
        if hasattr(frame, "to_dict"):
            try:
                return list(frame.to_dict(orient="records"))
            except TypeError:
                pass
        if isinstance(frame, SimpleDataFrame):
            return frame.to_dict()
        if isinstance(frame, list):
            return frame
        raise TypeError(f"Unsupported frame type: {type(frame)!r}")

    @staticmethod
    def _vector_abs_max(vector: dict[str, float | None] | None) -> float:
        if not vector:
            return 0.0
        values = [abs(v) for v in vector.values() if v is not None]
        return max(values) if values else 0.0

    @staticmethod
    def _range_from_rows(rows: list[dict[str, Any]], vector_key: str, axis: str) -> tuple[float, float] | None:
        values = [
            row[vector_key][axis]
            for row in rows
            if row.get(vector_key) and row[vector_key].get(axis) is not None
        ]
        if not values:
            return None
        return (round(min(values), 6), round(max(values), 6))

    def _build_report(
        self,
        subject_id: str,
        rows: list[dict[str, Any]],
        trials_loaded: int,
        activity_codes: list[str],
    ) -> dict[str, Any]:
        return {
            "subject_id": subject_id,
            "rows_loaded": len(rows),
            "trials_loaded": trials_loaded,
            "activity_codes": sorted(set(activity_codes)),
            "activity_labels_found": sorted({row["activity_label"] for row in rows}),
            "wrist_acc_x_g_range": self._raw_range(rows, "accel_mps2", "x", G_TO_MPS2),
            "wrist_ang_x_deg_range": self._raw_range(rows, "gyro_radps", "x", DEG_TO_RAD),
        }

    @staticmethod
    def _raw_range(
        rows: list[dict[str, Any]],
        vector_key: str,
        axis: str,
        factor: float,
    ) -> tuple[float, float] | None:
        values = [
            row[vector_key][axis] / factor
            for row in rows
            if row.get(vector_key) and row[vector_key].get(axis) is not None
        ]
        if not values:
            return None
        return (round(min(values), 6), round(max(values), 6))


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate UP-Fall ETL adapter")
    parser.add_argument("--subject", default="Subject_01")
    parser.add_argument("--activity", default="A01")
    parser.add_argument("--trial", default="S01_A01_T01.csv")
    parser.add_argument("--mode", choices=["subject", "trial"], default="trial")
    return parser


def main() -> int:
    args = _build_cli_parser().parse_args()
    adapter = UPFallAdapter()
    if args.mode == "subject":
        frame = adapter.load_subject(args.subject)
    else:
        frame = adapter.load_trial(args.subject, args.activity, args.trial)
    report = adapter.validate(frame)
    print(UPFallAdapter.format_validation_report(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    raise SystemExit(main())
