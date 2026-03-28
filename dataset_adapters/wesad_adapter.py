from __future__ import annotations

import argparse
import csv
import io
import math
import pickle
import zipfile
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .base_adapter import DatasetAdapter, SimpleDataFrame

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    pd = None

try:
    import numpy as np  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    np = None

SOURCE_DATASET = "WESAD"
ACC_SCALE_E4_TO_MPS2 = 9.81 / 64.0

WESAD_LABELS = {
    0: None,
    1: "baseline",
    2: "stress",
    3: "amusement",
    4: "meditation",
    5: None,
    6: "baseline",
    7: "baseline",
}

WESAD_STRESS_MAP = {
    "baseline": "neutral",
    "stress": "stress",
    "amusement": "amusement",
    "meditation": "neutral",
}

QUEST_SEGMENT_MAP = {
    "Base": "baseline",
    "TSST": "stress",
    "Fun": "amusement",
    "Medi 1": "meditation",
    "Medi 2": "meditation",
    "sRead": "baseline",
    "fRead": "baseline",
}


def _utc_from_epoch(epoch_seconds: float) -> datetime:
    return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)


class WESADAdapter(DatasetAdapter):
    REQUIRED_COLUMNS = [
        "timestamp",
        "subject_id",
        "accel_mps2",
        "gyro_radps",
        "orientation_deg",
        "heart_rate",
        "activity_label",
        "stress_state",
        "source_dataset",
        "metadata_extra",
    ]

    def __init__(self, dataset_root: str | Path | None = None) -> None:
        default_root = Path(__file__).resolve().parents[1] / "datasets" / "02_wearable" / "WESAD" / "WESAD_Raw"
        self.dataset_root = Path(dataset_root) if dataset_root else default_root
        if not self.dataset_root.exists():
            raise FileNotFoundError(f"WESAD dataset root not found: {self.dataset_root}")
        self._last_report: dict[str, Any] = {}

    @property
    def last_report(self) -> dict[str, Any]:
        return dict(self._last_report)

    def list_subjects(self) -> list[str]:
        return sorted(path.name for path in self.dataset_root.iterdir() if path.is_dir() and path.name.startswith("S"))

    def load_subject(self, subject_id: str, session_start: str | None = None) -> Any:
        subject_dir = self.dataset_root / subject_id
        if not subject_dir.exists():
            raise FileNotFoundError(f"WESAD subject folder not found: {subject_dir}")

        used_fallback = False
        if np is not None:
            try:
                rows = self._load_from_pickle(subject_dir, subject_id)
            except Exception:
                used_fallback = True
                rows = self._load_from_e4_zip(subject_dir, subject_id)
        else:
            used_fallback = True
            rows = self._load_from_e4_zip(subject_dir, subject_id)

        self._last_report = self._build_report(subject_id, rows, used_fallback)
        return self._build_frame(rows)

    def validate(self, df: Any) -> dict[str, Any]:
        rows = self._rows_from_frame(df)
        columns = set(rows[0].keys()) if rows else set()
        stress_values = {
            str(row.get("stress_state"))
            for row in rows
            if row.get("stress_state") is not None and str(row.get("stress_state")).lower() != "nan"
        }
        hr_populated = any(row.get("heart_rate") is not None for row in rows[: min(5000, len(rows))])
        accel_bounds_ok = all(
            self._vector_abs_max(row["accel_mps2"]) <= 25.0 for row in rows[: min(100, len(rows))]
        )
        return {
            **self._last_report,
            "row_count": len(rows),
            "required_columns_present": all(col in columns for col in self.REQUIRED_COLUMNS),
            "stress_values_seen": sorted(stress_values),
            "heart_rate_populated": hr_populated,
            "accel_bounds_ok": accel_bounds_ok,
        }

    @staticmethod
    def format_validation_report(report: dict[str, Any]) -> str:
        return (
            f"[WESAD ETL] Subject {report.get('subject_id', 'unknown')}\n"
            f"  Rows:            {report.get('row_count', report.get('rows_loaded', 0))}\n"
            f"  Load mode:       {'fallback_e4' if report.get('used_fallback') else 'pickle'}\n"
            f"  Labels found:    {report.get('activity_labels_found', [])}\n"
            f"  Stress states:   {report.get('stress_values_seen', [])}\n"
            f"  ACC x range:     {report.get('acc_x_range')}"
        )

    def _load_from_pickle(self, subject_dir: Path, subject_id: str) -> list[dict[str, Any]]:
        if np is None:
            raise ModuleNotFoundError("numpy is required for pickle loading")
        pickle_path = subject_dir / f"{subject_id}.pkl"
        with pickle_path.open("rb") as handle:
            data = pickle.load(handle, encoding="latin1")
        wrist = data["signal"]["wrist"]
        acc = wrist["ACC"]
        labels = data["label"]
        timestamps = self._build_timestamps(subject_dir, subject_id, len(acc))
        rows: list[dict[str, Any]] = []
        for idx, acc_row in enumerate(acc):
            label_value = self._scaled_lookup(labels, idx, len(acc))
            label_idx = int(label_value) if label_value is not None else 0
            label = WESAD_LABELS.get(label_idx)
            rows.append(
                {
                    "timestamp": timestamps[idx].isoformat(),
                    "subject_id": f"WESAD_{subject_id}",
                    "accel_mps2": {
                        "x": round(float(acc_row[0]) * ACC_SCALE_E4_TO_MPS2, 6),
                        "y": round(float(acc_row[1]) * ACC_SCALE_E4_TO_MPS2, 6),
                        "z": round(float(acc_row[2]) * ACC_SCALE_E4_TO_MPS2, 6),
                    },
                    "gyro_radps": {"x": None, "y": None, "z": None},
                    "orientation_deg": {"roll": None, "pitch": None, "yaw": None},
                    "heart_rate": None,
                    "activity_label": label,
                    "stress_state": WESAD_STRESS_MAP.get(label),
                    "source_dataset": SOURCE_DATASET,
                    "metadata_extra": {"load_mode": "pickle", "sensor_position": "wrist"},
                }
            )
        return self._attach_hr_from_e4_zip(subject_dir, subject_id, rows)

    def _build_timestamps(self, subject_dir: Path, subject_id: str, count: int) -> list[datetime]:
        start_time, sample_rate = self._read_e4_header(subject_dir / f"{subject_id}_E4_Data.zip", "ACC.csv")
        return [_utc_from_epoch(start_time + idx / sample_rate) for idx in range(count)]

    def _load_from_e4_zip(self, subject_dir: Path, subject_id: str) -> list[dict[str, Any]]:
        zip_path = subject_dir / f"{subject_id}_E4_Data.zip"
        start_time, acc_rate, acc_rows = self._read_e4_signal(zip_path, "ACC.csv", 3)
        _, hr_rate, hr_rows = self._read_e4_signal(zip_path, "HR.csv", 1)
        hr_timestamps = [start_time + idx / hr_rate for idx in range(len(hr_rows))]
        segments = self._read_quest_segments(subject_dir / f"{subject_id}_quest.csv")
        rows: list[dict[str, Any]] = []
        for idx, acc_row in enumerate(acc_rows):
            ts_epoch = start_time + idx / acc_rate
            minute_offset = (ts_epoch - start_time) / 60.0
            label = self._label_for_minute(minute_offset, segments)
            rows.append(
                {
                    "timestamp": _utc_from_epoch(ts_epoch).isoformat(),
                    "subject_id": f"WESAD_{subject_id}",
                    "accel_mps2": {
                        "x": round(acc_row[0] * ACC_SCALE_E4_TO_MPS2, 6),
                        "y": round(acc_row[1] * ACC_SCALE_E4_TO_MPS2, 6),
                        "z": round(acc_row[2] * ACC_SCALE_E4_TO_MPS2, 6),
                    },
                    "gyro_radps": {"x": None, "y": None, "z": None},
                    "orientation_deg": {"roll": None, "pitch": None, "yaw": None},
                    "heart_rate": self._nearest_scalar(ts_epoch, hr_timestamps, hr_rows),
                    "activity_label": label,
                    "stress_state": WESAD_STRESS_MAP.get(label),
                    "source_dataset": SOURCE_DATASET,
                    "metadata_extra": {"load_mode": "fallback_e4", "sensor_position": "wrist"},
                }
            )
        return rows

    def _attach_hr_from_e4_zip(self, subject_dir: Path, subject_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        zip_path = subject_dir / f"{subject_id}_E4_Data.zip"
        start_time, hr_rate, hr_rows = self._read_e4_signal(zip_path, "HR.csv", 1)
        hr_timestamps = [start_time + idx / hr_rate for idx in range(len(hr_rows))]
        for row in rows:
            ts_epoch = datetime.fromisoformat(row["timestamp"]).timestamp()
            row["heart_rate"] = self._nearest_scalar(ts_epoch, hr_timestamps, hr_rows)
        return rows

    @staticmethod
    def _read_e4_header(zip_path: Path, entry_name: str) -> tuple[float, float]:
        with zipfile.ZipFile(zip_path) as archive:
            with archive.open(entry_name) as handle:
                reader = io.TextIOWrapper(handle, encoding="utf-8")
                start_row = next(reader).strip().split(",")
                rate_row = next(reader).strip().split(",")
        return float(start_row[0]), float(rate_row[0])

    def _read_e4_signal(self, zip_path: Path, entry_name: str, dimensions: int) -> tuple[float, float, list[Any]]:
        start_time, sample_rate = self._read_e4_header(zip_path, entry_name)
        values: list[Any] = []
        with zipfile.ZipFile(zip_path) as archive:
            with archive.open(entry_name) as handle:
                reader = io.TextIOWrapper(handle, encoding="utf-8")
                next(reader)
                next(reader)
                for line in reader:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    parts = [part.strip() for part in stripped.split(",")]
                    if dimensions == 1:
                        values.append(float(parts[0]))
                    else:
                        values.append(tuple(float(parts[idx]) for idx in range(dimensions)))
        return start_time, sample_rate, values

    @staticmethod
    def _read_quest_segments(quest_path: Path) -> list[tuple[float, float, str | None]]:
        order: list[str] = []
        starts: list[float] = []
        ends: list[float] = []
        with quest_path.open("r", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle, delimiter=";")
            for row in reader:
                if not row:
                    continue
                head = row[0].strip()
                if head == "# ORDER":
                    order = [cell.strip() for cell in row[1:] if cell.strip()]
                elif head == "# START":
                    starts = [float(cell.strip()) for cell in row[1:] if cell.strip()]
                elif head == "# END":
                    ends = [float(cell.strip()) for cell in row[1:] if cell.strip()]
        segments: list[tuple[float, float, str | None]] = []
        for label, start, end in zip(order, starts, ends):
            segments.append((start, end, QUEST_SEGMENT_MAP.get(label)))
        return segments

    @staticmethod
    def _label_for_minute(minute_offset: float, segments: list[tuple[float, float, str | None]]) -> str | None:
        for start, end, label in segments:
            if start <= minute_offset <= end:
                return label
        return None

    @staticmethod
    def _nearest_scalar(timestamp: float, scalar_timestamps: list[float], scalar_values: list[float]) -> float | None:
        if not scalar_timestamps:
            return None
        index = bisect_left(scalar_timestamps, timestamp)
        candidates: list[int] = []
        if index < len(scalar_timestamps):
            candidates.append(index)
        if index > 0:
            candidates.append(index - 1)
        nearest_index = min(candidates, key=lambda idx: abs(scalar_timestamps[idx] - timestamp))
        return round(float(scalar_values[nearest_index]), 6)

    @staticmethod
    def _scaled_lookup(series: Any, sample_index: int, target_length: int) -> float | None:
        if series is None:
            return None
        values = np.asarray(series).reshape(-1) if np is not None else list(series)
        total = int(values.shape[0] if hasattr(values, "shape") else len(values))
        if total <= 0 or target_length <= 0:
            return None
        if total == target_length:
            lookup_index = sample_index
        else:
            scale = total / target_length
            lookup_index = min(total - 1, max(0, int(sample_index * scale)))
        raw = values[lookup_index]
        try:
            cast = float(raw)
        except (TypeError, ValueError):
            return None
        if math.isnan(cast) or math.isinf(cast):
            return None
        return cast

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
    def _vector_abs_max(vector: dict[str, float | None]) -> float:
        values = [abs(v) for v in vector.values() if v is not None]
        return max(values) if values else 0.0

    @staticmethod
    def _vector_range(rows: list[dict[str, Any]], vector_key: str, axis: str) -> tuple[float, float] | None:
        values = [row[vector_key][axis] for row in rows if row.get(vector_key) and row[vector_key].get(axis) is not None]
        if not values:
            return None
        return (round(min(values), 6), round(max(values), 6))

    def _build_report(self, subject_id: str, rows: list[dict[str, Any]], used_fallback: bool) -> dict[str, Any]:
        return {
            "subject_id": subject_id,
            "rows_loaded": len(rows),
            "used_fallback": used_fallback,
            "activity_labels_found": sorted({row["activity_label"] for row in rows if row["activity_label"]}),
            "acc_x_range": self._vector_range(rows, "accel_mps2", "x"),
        }


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate WESAD ETL adapter")
    parser.add_argument("--subject", default="S2")
    return parser


def main() -> int:
    args = _build_cli_parser().parse_args()
    adapter = WESADAdapter()
    frame = adapter.load_subject(args.subject)
    report = adapter.validate(frame)
    print(WESADAdapter.format_validation_report(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    raise SystemExit(main())
