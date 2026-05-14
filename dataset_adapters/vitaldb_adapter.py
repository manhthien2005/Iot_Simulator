from __future__ import annotations

import csv
import gzip
from bisect import bisect_left, bisect_right
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

SOURCE_DATASET = "VitalDB"
HR_TRACK = "SNUADC/HR"
SPO2_TRACK = "SNUADC/SPO2"
BP_SYS_TRACK = "Solar8000/NIBP_SYS"
BP_DIA_TRACK = "Solar8000/NIBP_DIA"

TRACK_DIRECTORY_MAP = {
    HR_TRACK: "SNUADC_HR",
    SPO2_TRACK: "SNUADC_SPO2",
    BP_SYS_TRACK: "Solar8000_NIBP_SYS",
    BP_DIA_TRACK: "Solar8000_NIBP_DIA",
}
TRACK_ORDER = (HR_TRACK, SPO2_TRACK, BP_SYS_TRACK, BP_DIA_TRACK)
# IS-013: tracks required by ETL pipeline for full vitals ingestion (HR + SpO2 + BP).
# Promoted from etl_pipeline.normalize._default_vitaldb_cases inline literal.
REQUIRED_TRACKS_FOR_VITALS: tuple[str, ...] = (SPO2_TRACK, BP_SYS_TRACK, BP_DIA_TRACK)
REQUIRED_COLUMNS = [
    "timestamp",
    "subject_id",
    "heart_rate",
    "spo2",
    "blood_pressure_sys",
    "blood_pressure_dia",
    "activity_label",
    "source_dataset",
    "metadata_extra",
]
NEAREST_TOLERANCE_SECONDS = 3.0
BP_CARRY_FORWARD_MAX_AGE_SECONDS = 300.0
DEMOGRAPHIC_FIELDS = ("age", "sex", "height", "weight", "bmi", "asa")


def _case_sort_key(caseid: str) -> tuple[int, str]:
    digits = "".join(ch for ch in str(caseid) if ch.isdigit())
    return (int(digits) if digits else 0, str(caseid))


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return float(text)


class VitalDBAdapter(DatasetAdapter):
    REQUIRED_COLUMNS = REQUIRED_COLUMNS

    def __init__(
        self,
        dataset_root: str | Path | None = None,
        nearest_tolerance_seconds: float = NEAREST_TOLERANCE_SECONDS,
        bp_carry_forward_seconds: float = BP_CARRY_FORWARD_MAX_AGE_SECONDS,
    ) -> None:
        default_root = Path(__file__).resolve().parents[1] / "datasets" / "01_vitals" / "VitalDB"
        self.dataset_root = Path(dataset_root) if dataset_root else default_root
        self.raw_root = self.dataset_root / "VitalDB_Raw"
        self.metadata_dir = self.raw_root / "metadata"
        self.tracks_dir = self.raw_root / "tracks"
        self.selected_tracks_path = self.metadata_dir / "selected_tracks.csv"
        self.cases_path = self.metadata_dir / "cases.csv.gz"
        self.nearest_tolerance_seconds = float(nearest_tolerance_seconds)
        self.bp_carry_forward_seconds = float(bp_carry_forward_seconds)

        if not self.dataset_root.exists():
            raise FileNotFoundError(f"VitalDB dataset root not found: {self.dataset_root}")
        if not self.selected_tracks_path.exists():
            raise FileNotFoundError(f"VitalDB selected tracks metadata not found: {self.selected_tracks_path}")
        if not self.cases_path.exists():
            raise FileNotFoundError(f"VitalDB cases metadata not found: {self.cases_path}")

        self._selected_tracks = self._load_selected_tracks()
        self._cases_index = self._load_cases_index()
        self._last_report: dict[str, Any] = {}

    @property
    def last_report(self) -> dict[str, Any]:
        return dict(self._last_report)

    def list_subjects(self) -> list[str]:
        subjects = [
            caseid
            for caseid in self._selected_tracks
            if self._resolve_track(caseid, HR_TRACK) is not None
        ]
        return sorted(subjects, key=_case_sort_key)

    def has_required_tracks(self, caseid: str | int) -> bool:
        """Check whether case has all tracks needed for vitals ingestion.

        Returns True if every track in REQUIRED_TRACKS_FOR_VITALS resolves
        to an existing file. Used by the ETL pipeline to filter cases
        before loading (replaces external private `_resolve_track` access).
        """
        case_str = str(caseid)
        return all(
            self._resolve_track(case_str, track) is not None
            for track in REQUIRED_TRACKS_FOR_VITALS
        )

    def load_subject(self, subject_id: str, session_start: str) -> Any:
        caseid = str(subject_id)
        session_dt = self._parse_session_start(session_start)

        hr_track = self._resolve_track(caseid, HR_TRACK)
        if hr_track is None:
            raise FileNotFoundError(f"VitalDB HR track not available locally for case {caseid}")

        available_tracks = {
            tname: self._resolve_track(caseid, tname)
            for tname in TRACK_ORDER
        }
        track_presence = {tname: info is not None for tname, info in available_tracks.items()}
        hr_samples = self._read_track_samples(hr_track)
        if not hr_samples:
            raise ValueError(f"VitalDB HR track for case {caseid} is empty: {hr_track['tid']}")

        spo2_samples = self._read_track_samples(available_tracks[SPO2_TRACK]) if available_tracks[SPO2_TRACK] else []
        bp_sys_samples = self._read_track_samples(available_tracks[BP_SYS_TRACK]) if available_tracks[BP_SYS_TRACK] else []
        bp_dia_samples = self._read_track_samples(available_tracks[BP_DIA_TRACK]) if available_tracks[BP_DIA_TRACK] else []

        hr_times = [sample[0] for sample in hr_samples]
        spo2_times = [sample[0] for sample in spo2_samples]
        bp_sys_times = [sample[0] for sample in bp_sys_samples]
        bp_dia_times = [sample[0] for sample in bp_dia_samples]
        case_profile = self._cases_index.get(caseid, {})
        metadata_template = {
            "caseid": caseid,
            "source_tracks_present": track_presence,
            "track_tids": {
                tname: info["tid"] if info else None
                for tname, info in available_tracks.items()
            },
            "source_track_names": {
                tname: info["source_tname"] if info else None
                for tname, info in available_tracks.items()
            },
            "demographics": case_profile,
        }

        rows: list[dict[str, Any]] = []
        for elapsed_seconds, heart_rate in hr_samples:
            timestamp = (session_dt + timedelta(seconds=elapsed_seconds)).isoformat()
            rows.append(
                {
                    "timestamp": timestamp,
                    "subject_id": f"VITALDB_CASE_{caseid}",
                    "heart_rate": round(heart_rate, 6),
                    "spo2": self._nearest_value(
                        spo2_samples,
                        spo2_times,
                        elapsed_seconds,
                        self.nearest_tolerance_seconds,
                    ),
                    "blood_pressure_sys": self._carry_forward_value(
                        bp_sys_samples,
                        bp_sys_times,
                        elapsed_seconds,
                        self.bp_carry_forward_seconds,
                    ),
                    "blood_pressure_dia": self._carry_forward_value(
                        bp_dia_samples,
                        bp_dia_times,
                        elapsed_seconds,
                        self.bp_carry_forward_seconds,
                    ),
                    "activity_label": None,
                    "source_dataset": SOURCE_DATASET,
                    "metadata_extra": dict(metadata_template),
                }
            )

        self._last_report = {
            "subject_id": f"VITALDB_CASE_{caseid}",
            "caseid": caseid,
            "rows_loaded": len(rows),
            "source_tracks_present": track_presence,
            "track_sample_counts": {
                HR_TRACK: len(hr_samples),
                SPO2_TRACK: len(spo2_samples),
                BP_SYS_TRACK: len(bp_sys_samples),
                BP_DIA_TRACK: len(bp_dia_samples),
            },
        }
        return self._build_frame(rows)

    def validate(self, df: Any) -> dict[str, Any]:
        rows = self._rows_from_frame(df)
        columns = set(rows[0].keys()) if rows else set()

        heart_rate_values = [float(row["heart_rate"]) for row in rows if row.get("heart_rate") is not None]
        spo2_values = [float(row["spo2"]) for row in rows if row.get("spo2") is not None]
        bp_sys_values = [float(row["blood_pressure_sys"]) for row in rows if row.get("blood_pressure_sys") is not None]
        bp_dia_values = [float(row["blood_pressure_dia"]) for row in rows if row.get("blood_pressure_dia") is not None]
        metadata_extra = rows[0].get("metadata_extra", {}) if rows else {}

        return {
            **self._last_report,
            "row_count": len(rows),
            "required_columns_present": all(column in columns for column in self.REQUIRED_COLUMNS),
            "heart_rate_populated": bool(heart_rate_values),
            "heart_rate_range_ok": all(20.0 <= value <= 260.0 for value in heart_rate_values),
            "spo2_range_ok": all(0.0 <= value <= 100.0 for value in spo2_values),
            "blood_pressure_range_ok": all(40.0 <= value <= 300.0 for value in bp_sys_values)
            and all(20.0 <= value <= 200.0 for value in bp_dia_values),
            "source_tracks_present": metadata_extra.get("source_tracks_present", {}),
        }

    @staticmethod
    def format_validation_report(report: dict[str, Any]) -> str:
        return (
            f"[VitalDB ETL] Case {report.get('caseid', 'unknown')}\n"
            f"  Rows:         {report.get('row_count', report.get('rows_loaded', 0))}\n"
            f"  HR populated: {report.get('heart_rate_populated')}\n"
            f"  Tracks:       {report.get('source_tracks_present', {})}"
        )

    def _load_selected_tracks(self) -> dict[str, dict[str, list[dict[str, Any]]]]:
        index: dict[str, dict[str, list[dict[str, Any]]]] = {}
        with self.selected_tracks_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                caseid = (row.get("caseid") or "").strip()
                tname = (row.get("tname") or "").strip()
                tid = (row.get("tid") or "").strip()
                if not caseid or not tname or not tid or tname not in TRACK_DIRECTORY_MAP:
                    continue
                index.setdefault(caseid, {}).setdefault(tname, []).append(
                    {
                        "tid": tid,
                        "source_tname": (row.get("source_tname") or tname).strip() or tname,
                        "path": self._track_path(tname, tid),
                    }
                )

        for track_map in index.values():
            for track_infos in track_map.values():
                track_infos.sort(key=lambda info: str(info["tid"]))
        return index

    def _load_cases_index(self) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        with gzip.open(self.cases_path, "rt", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                caseid = (row.get("caseid") or "").strip()
                if not caseid:
                    continue
                index[caseid] = {
                    field: row[field]
                    for field in DEMOGRAPHIC_FIELDS
                    if row.get(field) not in (None, "")
                }
        return index

    def _resolve_track(self, caseid: str, tname: str) -> dict[str, Any] | None:
        candidates = self._selected_tracks.get(caseid, {}).get(tname, [])
        for info in candidates:
            if Path(info["path"]).exists():
                return info
        return None

    @staticmethod
    def _read_track_samples(track_info: dict[str, Any] | None) -> list[tuple[float, float]]:
        if track_info is None:
            return []

        path = Path(track_info["path"])
        samples: list[tuple[float, float]] = []
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            value_columns = [name for name in fieldnames if name and name != "Time"]
            if not value_columns:
                raise ValueError(f"VitalDB track {path} does not contain a value column")
            value_column = value_columns[0]
            for row in reader:
                elapsed_seconds = _safe_float(row.get("Time"))
                value = _safe_float(row.get(value_column))
                if elapsed_seconds is None or value is None:
                    continue
                samples.append((elapsed_seconds, value))
        samples.sort(key=lambda item: item[0])
        return samples

    @staticmethod
    def _nearest_value(
        samples: list[tuple[float, float]],
        times: list[float],
        target_time: float,
        tolerance_seconds: float,
    ) -> float | None:
        if not samples:
            return None

        insert_at = bisect_left(times, target_time)
        candidates: list[tuple[float, float]] = []
        if insert_at < len(samples):
            candidates.append(samples[insert_at])
        if insert_at > 0:
            candidates.append(samples[insert_at - 1])
        if not candidates:
            return None

        best_time, best_value = min(candidates, key=lambda sample: abs(sample[0] - target_time))
        if abs(best_time - target_time) > tolerance_seconds:
            return None
        return round(best_value, 6)

    @staticmethod
    def _carry_forward_value(
        samples: list[tuple[float, float]],
        times: list[float],
        target_time: float,
        max_age_seconds: float,
    ) -> float | None:
        if not samples:
            return None

        insert_at = bisect_right(times, target_time) - 1
        if insert_at < 0:
            return None

        sample_time, sample_value = samples[insert_at]
        if target_time - sample_time > max_age_seconds:
            return None
        return round(sample_value, 6)

    @staticmethod
    def _parse_session_start(session_start: str) -> datetime:
        if not session_start:
            raise ValueError("VitalDB session_start is required")
        return datetime.fromisoformat(session_start.replace("Z", "+00:00"))

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

    def _track_path(self, tname: str, tid: str) -> Path:
        return self.tracks_dir / TRACK_DIRECTORY_MAP[tname] / f"{tid}.csv.gz"
