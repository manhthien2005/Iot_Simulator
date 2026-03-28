from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .base_adapter import DatasetAdapter, SimpleDataFrame

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    pd = None

SOURCE_DATASET = "BIDMC"
DEFAULT_SESSION_START = "2026-03-22T10:00:00+07:00"
REQUIRED_COLUMNS = [
    "timestamp",
    "subject_id",
    "heart_rate",
    "spo2",
    "respiration_rate",
    "activity_label",
    "source_dataset",
]


def _normalize_header(value: str) -> str:
    return "".join(ch.lower() for ch in str(value).strip() if ch.isalnum())


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _subject_sort_key(subject_id: str) -> tuple[int, str]:
    digits = "".join(ch for ch in str(subject_id) if ch.isdigit())
    return (int(digits) if digits else 0, str(subject_id))


class BIDMCAdapter(DatasetAdapter):
    REQUIRED_COLUMNS = REQUIRED_COLUMNS

    def __init__(
        self,
        dataset_root: str | Path | None = None,
        default_session_start: str = DEFAULT_SESSION_START,
    ) -> None:
        default_root = (
            Path(__file__).resolve().parents[1]
            / "datasets"
            / "06_clinical_optional"
            / "BIDMC"
            / "BIDMC_Raw"
        )
        root = Path(dataset_root) if dataset_root else default_root
        self.dataset_root = root
        self.numerics_dir = root if root.name.lower() == "bidmc_csv" else root / "bidmc_csv"
        self.default_session_start = default_session_start
        self._last_report: dict[str, Any] = {}

        if not self.numerics_dir.exists():
            raise FileNotFoundError(f"BIDMC numerics directory not found: {self.numerics_dir}")

    @property
    def last_report(self) -> dict[str, Any]:
        return dict(self._last_report)

    def list_subjects(self) -> list[str]:
        subjects = []
        for path in self.numerics_dir.glob("bidmc_*_Numerics.csv"):
            digits = "".join(ch for ch in path.stem if ch.isdigit())
            if not digits:
                continue
            subjects.append(f"bidmc{int(digits):02d}")
        return sorted(set(subjects), key=_subject_sort_key)

    def load_subject(self, subject_id: str, session_start: str | None = None) -> Any:
        canonical_subject = self._canonical_subject_id(subject_id)
        path = self.numerics_dir / f"bidmc_{canonical_subject[-2:]}_Numerics.csv"
        if not path.exists():
            raise FileNotFoundError(f"BIDMC numerics file not found for {canonical_subject}: {path}")

        session_dt = self._parse_session_start(session_start or self.default_session_start)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            resolved_columns = self._resolve_columns(fieldnames)
            rows: list[dict[str, Any]] = []
            for raw_row in reader:
                elapsed_seconds = _safe_float(raw_row.get(resolved_columns["timestamp"]))
                if elapsed_seconds is None:
                    continue
                heart_rate = _safe_float(raw_row.get(resolved_columns["heart_rate"])) if resolved_columns["heart_rate"] else None
                spo2 = _safe_float(raw_row.get(resolved_columns["spo2"])) if resolved_columns["spo2"] else None
                respiration_rate = _safe_float(raw_row.get(resolved_columns["respiration_rate"]))
                rows.append(
                    {
                        "timestamp": (session_dt + timedelta(seconds=elapsed_seconds)).isoformat(),
                        "subject_id": f"BIDMC_{canonical_subject}",
                        "heart_rate": heart_rate,
                        "spo2": spo2,
                        "respiration_rate": respiration_rate,
                        "activity_label": None,
                        "source_dataset": SOURCE_DATASET,
                    }
                )

        self._last_report = {
            "subject_id": f"BIDMC_{canonical_subject}",
            "source_file": str(path),
            "rows_loaded": len(rows),
            "resolved_columns": dict(resolved_columns),
        }
        return self._build_frame(rows)

    def validate(self, df: Any) -> dict[str, Any]:
        rows = self._rows_from_frame(df)
        columns = set(rows[0].keys()) if rows else set()
        heart_rate_values = [float(row["heart_rate"]) for row in rows if row.get("heart_rate") is not None]
        respiration_values = [float(row["respiration_rate"]) for row in rows if row.get("respiration_rate") is not None]
        spo2_values = [float(row["spo2"]) for row in rows if row.get("spo2") is not None]

        return {
            **self._last_report,
            "row_count": len(rows),
            "required_columns_present": all(column in columns for column in self.REQUIRED_COLUMNS),
            "heart_rate_populated": bool(heart_rate_values),
            "respiration_populated": bool(respiration_values),
            "heart_rate_range_ok": all(30.0 <= value <= 200.0 for value in heart_rate_values),
            "respiration_range_ok": all(8.0 <= value <= 40.0 for value in respiration_values),
            "spo2_range_ok": all(0.0 <= value <= 100.0 for value in spo2_values),
        }

    @staticmethod
    def format_validation_report(report: dict[str, Any]) -> str:
        return (
            f"[BIDMC ETL] Subject {report.get('subject_id', 'unknown')}\n"
            f"  Rows:            {report.get('row_count', report.get('rows_loaded', 0))}\n"
            f"  RR populated:    {report.get('respiration_populated')}\n"
            f"  RR range valid:  {report.get('respiration_range_ok')}"
        )

    @staticmethod
    def _canonical_subject_id(subject_id: str) -> str:
        digits = "".join(ch for ch in str(subject_id) if ch.isdigit())
        if not digits:
            raise ValueError(f"Invalid BIDMC subject id: {subject_id!r}")
        return f"bidmc{int(digits):02d}"

    @staticmethod
    def _parse_session_start(session_start: str) -> datetime:
        if not session_start:
            raise ValueError("BIDMC session_start is required")
        return datetime.fromisoformat(session_start.replace("Z", "+00:00"))

    @staticmethod
    def _resolve_columns(fieldnames: list[str]) -> dict[str, str | None]:
        normalized_headers = {_normalize_header(name): name for name in fieldnames}

        def pick(*aliases: str) -> str | None:
            for alias in aliases:
                match = normalized_headers.get(_normalize_header(alias))
                if match is not None:
                    return match
            return None

        resolved = {
            "timestamp": pick("Time [s]", "Time", "Seconds"),
            "heart_rate": pick("HR", "Heart Rate"),
            "spo2": pick("SpO2", "SPO2", "O2Sat"),
            "respiration_rate": pick("RESP", "RR", "Respiratory Rate", "Respiration Rate"),
        }
        if resolved["timestamp"] is None:
            raise ValueError(f"BIDMC numerics file is missing timestamp column: {fieldnames}")
        if resolved["respiration_rate"] is None:
            raise ValueError(f"BIDMC numerics file is missing respiration column: {fieldnames}")
        return resolved

    @staticmethod
    def _build_frame(rows: list[dict[str, Any]]) -> Any:
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
