from __future__ import annotations

import argparse
import csv
import math
from bisect import bisect_left
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from .base_adapter import DatasetAdapter, SimpleDataFrame
except ImportError:  # pragma: no cover - direct script execution fallback
    from base_adapter import DatasetAdapter, SimpleDataFrame

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    pd = None

G_TO_MPS2 = 9.81
DEG_TO_RAD = math.pi / 180.0
DEFAULT_TOLERANCE_SECONDS = 0.5
SOURCE_DATASET = "PIF_v3"

LABEL_MAP: dict[str, dict[str, Any]] = {
    "Rest": {"activity_state": "resting", "fall_variant": None},
    "Relax": {"activity_state": "resting", "fall_variant": None},
    "Relaxing": {"activity_state": "resting", "fall_variant": None},
    "Standing": {"activity_state": "standing", "fall_variant": None},
    "Sitting": {"activity_state": "sitting", "fall_variant": None},
    "Walking": {"activity_state": "walking", "fall_variant": None},
    "Left Fall while Standing": {
        "activity_state": "fall",
        "fall_variant": "left_standing",
    },
    "Right Fall while Standing": {
        "activity_state": "fall",
        "fall_variant": "right_standing",
    },
    "Forward Fall while Standing": {
        "activity_state": "fall",
        "fall_variant": "forward_standing",
    },
    "Left Fall while Sitting": {
        "activity_state": "fall",
        "fall_variant": "left_sitting",
    },
    "Right Fall while Sitting": {
        "activity_state": "fall",
        "fall_variant": "right_sitting",
    },
    "Forward Fall while Sitting": {
        "activity_state": "fall",
        "fall_variant": "forward_sitting",
    },
    "Anxiety": {"activity_state": "resting", "stress_state": "stress"},
    "Sad": {"activity_state": "resting", "stress_state": "stress"},
    "Motivate": {"activity_state": "resting", "stress_state": "amusement"},
    "Motivational": {"activity_state": "resting", "stress_state": "amusement"},
    "Funny": {"activity_state": "resting", "stress_state": "amusement"},
    "Fist": {"activity_state": "resting", "behavioral_marker": "fist"},
    "Stress Ball": {
        "activity_state": "resting",
        "behavioral_marker": "stress_ball",
    },
    "Pressing Stress Ball": {
        "activity_state": "resting",
        "behavioral_marker": "stress_ball",
    },
    "Hand at Rest": {"activity_state": "resting", "behavioral_marker": "hand_at_rest"},
}


def parse_pif_time(t_str: str) -> float:
    """Return elapsed seconds from PIF v3 `MM:SS.d` time strings."""
    raw = (t_str or "").strip()
    if not raw:
        raise ValueError("PIF time string is empty")
    parts = raw.split(":")
    if len(parts) != 2:
        raise ValueError(f"Unsupported PIF time format: {t_str!r}")
    return int(parts[0]) * 60 + float(parts[1])


def _subject_sort_key(subject_id: str) -> tuple[int, str]:
    digits = "".join(ch for ch in subject_id if ch.isdigit())
    return (int(digits) if digits else 0, subject_id)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def _iso_timestamp(session_start: datetime, elapsed_seconds: float) -> str:
    ts = session_start + timedelta(seconds=elapsed_seconds)
    return ts.isoformat()


class PIFV3Adapter(DatasetAdapter):
    REQUIRED_COLUMNS = [
        "timestamp",
        "subject_id",
        "accel_mps2",
        "gyro_radps",
        "orientation_deg",
        "heart_rate",
        "blood_pressure_sys",
        "blood_pressure_dia",
        "spo2",
        "activity_label",
        "fall_variant",
    ]

    def __init__(self, dataset_root: str | Path | None = None) -> None:
        default_root = Path(__file__).resolve().parents[1] / "datasets" / "05_fall" / "PIF_v3" / "PIF_v3_Raw" / "Pif3_Dataset"
        self.dataset_root = Path(dataset_root) if dataset_root else default_root
        if not self.dataset_root.exists():
            raise FileNotFoundError(f"PIF v3 dataset root not found: {self.dataset_root}")
        self._last_report: dict[str, Any] = {}

    @property
    def last_report(self) -> dict[str, Any]:
        return dict(self._last_report)

    def list_subjects(self) -> list[str]:
        subjects = [p.name for p in self.dataset_root.iterdir() if p.is_dir() and p.name.upper().startswith("PID")]
        return sorted(subjects, key=_subject_sort_key)

    def load_subject(self, subject_id: str, session_start: str) -> Any:
        subject_dir = self.dataset_root / subject_id
        if not subject_dir.exists():
            raise FileNotFoundError(f"Subject folder not found: {subject_dir}")

        subject_num = "".join(ch for ch in subject_id if ch.isdigit())
        inertial_path = subject_dir / f"PID_{subject_num}.csv"
        bpm_path = subject_dir / f"PID_{subject_num}_BPM.csv"
        inertial_rows = self._read_csv(inertial_path)
        bpm_rows = self._read_csv(bpm_path)

        session_dt = datetime.fromisoformat(session_start.replace("Z", "+00:00"))
        bpm_elapsed = [row["elapsed_seconds"] for row in bpm_rows]

        normalized_rows: list[dict[str, Any]] = []
        matched_rows = 0

        for row in inertial_rows:
            bpm_row = self._match_bpm_row(row["elapsed_seconds"], bpm_rows, bpm_elapsed)
            if bpm_row is not None:
                matched_rows += 1
            normalized_rows.append(
                self._normalize_row(
                    subject_id=subject_id,
                    inertial_row=row,
                    bpm_row=bpm_row,
                    session_start=session_dt,
                )
            )

        labels_found = sorted({r["activity_label"] for r in normalized_rows if r.get("activity_label")})
        report = {
            "subject_id": subject_id,
            "inertial_rows": len(inertial_rows),
            "bpm_rows": len(bpm_rows),
            "merged_rows": len(normalized_rows),
            "bpm_match_rate_pct": round((matched_rows / len(inertial_rows)) * 100, 2) if inertial_rows else 0.0,
            "labels_found": labels_found,
            "accx_g_range": self._range_from_rows(inertial_rows, "AccX"),
            "gyrox_deg_s_range": self._range_from_rows(inertial_rows, "GyroX"),
            "required_columns_present": all(
                col in (normalized_rows[0].keys() if normalized_rows else [])
                for col in self.REQUIRED_COLUMNS
            ),
        }
        self._last_report = report
        return self._build_frame(normalized_rows)

    def validate(self, df: Any) -> dict[str, Any]:
        rows = self._rows_from_frame(df)
        columns = set(rows[0].keys()) if rows else set()

        heart_rate_missing = sum(1 for row in rows if row.get("heart_rate") is None)
        accel_bounds_ok = all(
            self._vector_abs_max(row.get("accel_mps2")) <= 25.0
            for row in rows
            if row.get("accel_mps2") is not None
        )
        gyro_bounds_ok = all(
            self._vector_abs_max(row.get("gyro_radps")) <= 4.0
            for row in rows
            if row.get("gyro_radps") is not None
        )
        yaw_is_none = all(
            (row.get("orientation_deg") or {}).get("yaw") is None for row in rows
        )

        report = {
            **self._last_report,
            "row_count": len(rows),
            "required_columns_present": all(col in columns for col in self.REQUIRED_COLUMNS),
            "heart_rate_missing_rows": heart_rate_missing,
            "accel_bounds_ok": accel_bounds_ok,
            "gyro_bounds_ok": gyro_bounds_ok,
            "yaw_is_none": yaw_is_none,
        }
        return report

    @staticmethod
    def format_validation_report(report: dict[str, Any]) -> str:
        labels = report.get("labels_found", [])
        labels_text = ", ".join(repr(label) for label in labels[:8])
        if len(labels) > 8:
            labels_text += ", ..."
        return (
            f"[PIF_v3 ETL] Subject {report.get('subject_id', 'unknown')}\n"
            f"  Inertial rows:  {report.get('inertial_rows', 0)}\n"
            f"  BPM rows:       {report.get('bpm_rows', 0)}\n"
            f"  Merged rows:    {report.get('merged_rows', 0)}\n"
            f"  BPM match rate: {report.get('bpm_match_rate_pct', 0):.2f}%\n"
            f"  Labels found:   [{labels_text}]\n"
            f"  AccX range:     {report.get('accx_g_range')}\n"
            f"  GyroX range:    {report.get('gyrox_deg_s_range')}"
        )

    def _read_csv(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise ValueError(f"CSV file has no header: {path}")
            normalized_headers = [header.strip() for header in reader.fieldnames]
            for raw_row in reader:
                row = {
                    normalized_headers[idx]: (value.strip() if isinstance(value, str) else value)
                    for idx, value in enumerate(raw_row.values())
                }
                row["elapsed_seconds"] = parse_pif_time(str(row["Datetime"]))
                rows.append(row)

        rows.sort(key=lambda item: item["elapsed_seconds"])
        return rows

    def _match_bpm_row(
        self,
        elapsed_seconds: float,
        bpm_rows: list[dict[str, Any]],
        bpm_elapsed: list[float],
    ) -> dict[str, Any] | None:
        if not bpm_rows:
            return None
        index = bisect_left(bpm_elapsed, elapsed_seconds)
        candidates: list[dict[str, Any]] = []
        if index < len(bpm_rows):
            candidates.append(bpm_rows[index])
        if index > 0:
            candidates.append(bpm_rows[index - 1])
        if not candidates:
            return None
        nearest = min(
            candidates,
            key=lambda row: abs(row["elapsed_seconds"] - elapsed_seconds),
        )
        if abs(nearest["elapsed_seconds"] - elapsed_seconds) > DEFAULT_TOLERANCE_SECONDS:
            return None
        return nearest

    def _normalize_row(
        self,
        subject_id: str,
        inertial_row: dict[str, Any],
        bpm_row: dict[str, Any] | None,
        session_start: datetime,
    ) -> dict[str, Any]:
        activity_label = inertial_row.get("Features") or inertial_row.get("features")
        label_info = LABEL_MAP.get(activity_label or "", {})
        elapsed_seconds = inertial_row["elapsed_seconds"]

        accel_g = {
            "x": _safe_float(inertial_row.get("AccX")),
            "y": _safe_float(inertial_row.get("AccY")),
            "z": _safe_float(inertial_row.get("AccZ")),
        }
        gyro_deg = {
            "x": _safe_float(inertial_row.get("GyroX")),
            "y": _safe_float(inertial_row.get("GyroY")),
            "z": _safe_float(inertial_row.get("GyroZ")),
        }

        accel_mps2 = {
            axis: None if value is None else round(value * G_TO_MPS2, 6)
            for axis, value in accel_g.items()
        }
        gyro_radps = {
            axis: None if value is None else round(value * DEG_TO_RAD, 6)
            for axis, value in gyro_deg.items()
        }

        row = {
            "timestamp": _iso_timestamp(session_start, elapsed_seconds),
            "subject_id": f"PIF_{subject_id}",
            "elapsed_seconds": elapsed_seconds,
            "accel_mps2": accel_mps2,
            "gyro_radps": gyro_radps,
            "orientation_deg": {
                "roll": _safe_float(inertial_row.get("Combroll")),
                "pitch": _safe_float(inertial_row.get("Combpitch")),
                "yaw": None,
            },
            "heart_rate": _safe_float(bpm_row.get("hr")) if bpm_row else None,
            "blood_pressure_sys": _safe_float(bpm_row.get("sys")) if bpm_row else None,
            "blood_pressure_dia": _safe_float(bpm_row.get("dia")) if bpm_row else None,
            "spo2": _safe_float(bpm_row.get("spo2")) if bpm_row else None,
            "activity_label": activity_label,
            "activity_state": label_info.get("activity_state"),
            "stress_state": label_info.get("stress_state"),
            "behavioral_marker": label_info.get("behavioral_marker"),
            "fall_variant": label_info.get("fall_variant"),
            "source_dataset": SOURCE_DATASET,
            "metadata_extra": {
                "gyaw_candidate": _safe_float(inertial_row.get("Gy")),
                "ecg_raw": _safe_float(inertial_row.get("ECGR")),
                "gsr_raw": _safe_float(inertial_row.get("GSRR")),
                "emg_raw": _safe_float(inertial_row.get("EMGR")),
                "bpm_activity_label": (bpm_row.get("features") if bpm_row else None),
                "unit_assumptions": {
                    "accel_input": "g",
                    "gyro_input": "deg/s",
                    "orientation_input": "deg",
                },
            },
        }
        return row

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
    def _range_from_rows(rows: list[dict[str, Any]], field: str) -> tuple[float, float] | None:
        values = [
            float(row[field])
            for row in rows
            if row.get(field) not in (None, "")
        ]
        if not values:
            return None
        return (round(min(values), 6), round(max(values), 6))

    @staticmethod
    def _vector_abs_max(vector: dict[str, float | None] | None) -> float:
        if not vector:
            return 0.0
        values = [abs(v) for v in vector.values() if v is not None]
        return max(values) if values else 0.0


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate PIF v3 ETL adapter")
    parser.add_argument("--subject", default="PID1", help="Subject folder to load, e.g. PID1")
    parser.add_argument(
        "--session-start",
        default="2026-03-22T10:00:00+07:00",
        help="ISO timestamp used as recording start",
    )
    return parser


def main() -> int:
    parser = _build_cli_parser()
    args = parser.parse_args()
    adapter = PIFV3Adapter()
    frame = adapter.load_subject(args.subject, args.session_start)
    report = adapter.validate(frame)
    print(PIFV3Adapter.format_validation_report(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    raise SystemExit(main())
