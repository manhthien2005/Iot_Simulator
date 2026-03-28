from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .base_adapter import DatasetAdapter, SimpleDataFrame

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    pd = None

SOURCE_DATASET = "PAMAP2"

ACTIVITY_MAP: dict[int, str | None] = {
    0: None,
    1: "lying",
    2: "sitting",
    3: "standing",
    4: "walking",
    5: "running",
    6: "cycling",
    7: "nordic_walking",
    9: "watching_tv",
    10: "computer_work",
    11: "car_driving",
    12: "ascending_stairs",
    13: "descending_stairs",
    16: "vacuum_cleaning",
    17: "ironing",
    18: "folding_laundry",
    19: "house_cleaning",
    20: "playing_soccer",
    24: "rope_jumping",
}


def _safe_float(value: str) -> float | None:
    text = value.strip()
    if not text or text == "NaN":
        return None
    return float(text)


def _iso_timestamp(session_start: datetime, elapsed_seconds: float) -> str:
    return (session_start + timedelta(seconds=elapsed_seconds)).isoformat()


class PAMAP2Adapter(DatasetAdapter):
    REQUIRED_COLUMNS = [
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
    ]

    def __init__(self, dataset_root: str | Path | None = None) -> None:
        default_root = Path(__file__).resolve().parents[1] / "datasets" / "04_activity" / "PAMAP2" / "PAMAP2_Raw" / "Protocol"
        self.dataset_root = Path(dataset_root) if dataset_root else default_root
        if not self.dataset_root.exists():
            raise FileNotFoundError(f"PAMAP2 dataset root not found: {self.dataset_root}")
        self._last_report: dict[str, Any] = {}

    @property
    def last_report(self) -> dict[str, Any]:
        return dict(self._last_report)

    def list_subjects(self) -> list[str]:
        return sorted(path.stem for path in self.dataset_root.glob("subject*.dat"))

    def load_subject(self, subject_id: str, session_start: str) -> Any:
        file_path = self.dataset_root / f"{subject_id}.dat"
        if not file_path.exists():
            raise FileNotFoundError(f"PAMAP2 subject file not found: {file_path}")
        session_dt = datetime.fromisoformat(session_start.replace("Z", "+00:00"))

        rows: list[dict[str, Any]] = []
        hr_missing = 0
        activity_ids: set[int] = set()
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                parts = stripped.split()
                if len(parts) < 54:
                    continue
                activity_id = int(float(parts[1]))
                heart_rate = _safe_float(parts[2])
                if heart_rate is None:
                    hr_missing += 1
                activity_ids.add(activity_id)
                rows.append(
                    {
                        "timestamp": _iso_timestamp(session_dt, float(parts[0])),
                        "subject_id": f"PAMAP2_{subject_id}",
                        "accel_mps2": {
                            "x": float(parts[4]),
                            "y": float(parts[5]),
                            "z": float(parts[6]),
                        },
                        "gyro_radps": {
                            "x": float(parts[10]),
                            "y": float(parts[11]),
                            "z": float(parts[12]),
                        },
                        "orientation_deg": {"roll": None, "pitch": None, "yaw": None},
                        "heart_rate": heart_rate,
                        "activity_label": ACTIVITY_MAP.get(activity_id),
                        "activity_state": ACTIVITY_MAP.get(activity_id),
                        "source_dataset": SOURCE_DATASET,
                        "metadata_extra": {
                            "sensor_position": "hand",
                            "activity_id_raw": activity_id,
                            "hand_temp_c": _safe_float(parts[3]),
                            "chest_acc": [
                                _safe_float(parts[21]),
                                _safe_float(parts[22]),
                                _safe_float(parts[23]),
                            ],
                            "ankle_acc": [
                                _safe_float(parts[37]),
                                _safe_float(parts[38]),
                                _safe_float(parts[39]),
                            ],
                        },
                    }
                )

        self._last_report = {
            "subject_id": subject_id,
            "rows_loaded": len(rows),
            "activity_ids_found": sorted(activity_ids),
            "activity_labels_found": sorted({row["activity_label"] for row in rows if row["activity_label"]}),
            "heart_rate_missing_rows": hr_missing,
            "hand_acc_x_range": self._vector_range(rows, "accel_mps2", "x"),
            "hand_gyro_x_range": self._vector_range(rows, "gyro_radps", "x"),
        }
        return self._build_frame(rows)

    def validate(self, df: Any) -> dict[str, Any]:
        rows = self._rows_from_frame(df)
        columns = set(rows[0].keys()) if rows else set()
        accel_bounds_ok = all(
            self._vector_abs_max(row["accel_mps2"]) <= 50.0 for row in rows[: min(100, len(rows))]
        )
        gyro_bounds_ok = all(
            self._vector_abs_max(row["gyro_radps"]) <= 20.0 for row in rows[: min(100, len(rows))]
        )
        hr_nan_handled = all(
            row["heart_rate"] is None or isinstance(row["heart_rate"], float)
            for row in rows[: min(100, len(rows))]
        )
        return {
            **self._last_report,
            "row_count": len(rows),
            "required_columns_present": all(col in columns for col in self.REQUIRED_COLUMNS),
            "accel_bounds_ok": accel_bounds_ok,
            "gyro_bounds_ok": gyro_bounds_ok,
            "heart_rate_nan_handled": hr_nan_handled,
        }

    @staticmethod
    def format_validation_report(report: dict[str, Any]) -> str:
        return (
            f"[PAMAP2 ETL] Subject {report.get('subject_id', 'unknown')}\n"
            f"  Rows:             {report.get('row_count', report.get('rows_loaded', 0))}\n"
            f"  Activity IDs:     {report.get('activity_ids_found', [])}\n"
            f"  Labels found:     {report.get('activity_labels_found', [])}\n"
            f"  HR missing rows:  {report.get('heart_rate_missing_rows', 0)}\n"
            f"  hand_acc_x range: {report.get('hand_acc_x_range')}\n"
            f"  hand_gyro_x range:{report.get('hand_gyro_x_range')}"
        )

    def _build_frame(self, rows: list[dict[str, Any]]) -> Any:
        if pd is not None:
            frame = pd.DataFrame(rows)
            # Keep None values instead of NaN so downstream serialization/tests stay stable.
            frame["heart_rate"] = pd.Series([row.get("heart_rate") for row in rows], dtype="object")
            return frame
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
    def _vector_range(
        rows: list[dict[str, Any]],
        vector_key: str,
        axis: str,
    ) -> tuple[float, float] | None:
        values = [
            row[vector_key][axis]
            for row in rows
            if row.get(vector_key) and row[vector_key].get(axis) is not None
        ]
        if not values:
            return None
        return (round(min(values), 6), round(max(values), 6))


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate PAMAP2 ETL adapter")
    parser.add_argument("--subject", default="subject101")
    parser.add_argument("--session-start", default="2026-03-22T10:00:00+07:00")
    return parser


def main() -> int:
    args = _build_cli_parser().parse_args()
    adapter = PAMAP2Adapter()
    frame = adapter.load_subject(args.subject, args.session_start)
    report = adapter.validate(frame)
    print(PAMAP2Adapter.format_validation_report(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    raise SystemExit(main())
