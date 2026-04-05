from __future__ import annotations

import csv
import gzip
import json
import logging
from math import isnan
import random
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


def normalize_stress_state(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    if normalized in {"baseline", "neutral", "rest"}:
        return "neutral"
    if normalized in {"stress", "amusement"}:
        return normalized
    return None


class DatasetRegistry:
    def __init__(self, artifacts_dir: str | Path) -> None:
        self.artifacts_dir = Path(artifacts_dir)
        if not self.artifacts_dir.exists():
            raise FileNotFoundError(f"Artifacts directory not found: {self.artifacts_dir}")
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._indexes_built = False
        self._motion_index: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
        self._vitals_index: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
        self._vitals_activity_index: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
        self._respiration_activity_index: dict[str | None, list[dict[str, Any]]] = {}
        self._timeline_cache: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
        self._event_index: dict[str | None, list[dict[str, Any]]] = {}
        self._stress_index: dict[str, list[dict[str, Any]]] = {}
        self._sleep_sessions: list[dict[str, Any]] = self._load_optional_artifact("sleep_sessions")
        self._stress_rows: list[dict[str, Any]] = self._load_optional_artifact("stress_stream")
        self._respiration_rows: list[dict[str, Any]] = self._load_optional_artifact("respiration_stream")
        self._stress_baseline_mean: float | None = self._compute_stress_baseline_mean(self._stress_rows)
        self._vitaldb_case_index: dict[str, dict[str, Any]] | None = None
        self._warned_missing_vitaldb_cases = False

    def get_motion_windows(
        self,
        activity: str | None = None,
        activity_label: str | None = None,
        dataset: str | None = None,
        fall_variant: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_indexes()
        requested_activity = activity_label if activity_label is not None else activity
        normalized_activity = self._normalize_activity(requested_activity)
        records = list(self._motion_index.get((dataset, normalized_activity), []))
        if fall_variant is not None:
            records = [row for row in records if row.get("fall_variant") == fall_variant]
        if limit is not None and limit < len(records):
            return random.sample(records, limit)
        return records

    def get_vitals_snapshot(
        self,
        subject_id: str,
        dataset: str,
        timestamp_hint: str | None = None,
    ) -> dict[str, Any] | None:
        self._ensure_indexes()
        records = self._vitals_index.get((subject_id, dataset), [])
        if not records:
            return None
        if timestamp_hint is None:
            return records[len(records) // 2]
        exact = [row for row in records if row.get("timestamp") == timestamp_hint]
        return exact[0] if exact else records[len(records) // 2]

    def get_vitals_timeline(self, subject_id: str, dataset: str) -> list[dict[str, Any]]:
        self._ensure_indexes()
        key = (subject_id, dataset)
        if key not in self._timeline_cache:
            rows = list(self._vitals_index.get(key, []))
            rows.sort(key=lambda row: str(row.get("timestamp") or ""))
            self._timeline_cache[key] = rows
        return self._timeline_cache[key]

    def get_vitals_sample_at(
        self,
        subject_id: str,
        dataset: str,
        cursor_index: int,
    ) -> dict[str, Any] | None:
        timeline = self.get_vitals_timeline(subject_id, dataset)
        if not timeline:
            return None
        index = cursor_index % len(timeline)
        return timeline[index]

    def get_case_demographics(self, subject_id: str, dataset: str) -> dict[str, Any] | None:
        if str(dataset).strip().lower() != "vitaldb":
            return None
        lookup = str(subject_id).strip()
        if not lookup:
            return None
        index = self._load_vitaldb_case_index()
        demographics = index.get(lookup)
        return dict(demographics) if demographics else None

    def get_events(
        self,
        event_type: str | None = None,
        dataset: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_indexes()
        events = self._load_artifact("event_catalog")
        return [
            event
            for event in events
            if (event_type is None or event.get("event_type") == event_type)
            and (dataset is None or event.get("dataset") == dataset)
        ]

    def get_fall_event(self, variant: str) -> dict[str, Any] | None:
        for event in self.get_events(event_type="fall_detected"):
            if event.get("fall_variant") == variant:
                return event
        return None

    def get_vitals_baseline(
        self,
        activity: str | None = None,
        dataset: str | None = None,
        required_fields: tuple[str, ...] | None = None,
    ) -> dict[str, Any] | None:
        self._ensure_indexes()
        normalized_activity = self._normalize_activity(activity)
        records = list(self._vitals_activity_index.get((dataset, normalized_activity), []))
        if not records:
            return None
        if required_fields:
            required_records = [
                row
                for row in records
                if all(not self._is_missing_value(row.get(field)) for field in required_fields)
            ]
            if required_records:
                records = required_records
        # LOW #6: use random.choice instead of fixed midpoint for more variation
        return random.choice(records)

    def get_stress_sample(self, stress_state: str = "stress") -> dict[str, Any] | None:
        self._ensure_indexes()
        normalized_state = self._normalize_stress_state(stress_state)
        if normalized_state is None:
            return None
        records = self._stress_index.get(normalized_state, [])
        if not records:
            return None
        return random.choice(records)

    def get_respiration_sample(self, activity: str | None = None) -> dict[str, Any] | None:
        self._ensure_indexes()
        normalized_activity = self._normalize_activity(activity)
        records = list(self._respiration_activity_index.get(normalized_activity, []))
        if not records:
            return None
        return records[len(records) // 2]

    def has_stress_data(self) -> bool:
        return len(self._stress_rows) > 0

    def get_stress_baseline_mean(self) -> float | None:
        return self._stress_baseline_mean

    def stress_source(self) -> str:
        return "real:WESAD" if self.has_stress_data() else "mock"

    def list_datasets(self) -> list[str]:
        self._ensure_indexes()
        datasets = set()
        dataset_sources = (
            self._cache.get("motion_windows", []),
            self._cache.get("vitals_stream", []),
            self._cache.get("event_catalog", []),
            self._stress_rows,
            self._respiration_rows,
        )
        for rows in dataset_sources:
            for row in rows:
                dataset = row.get("dataset") or row.get("source_dataset")
                if dataset:
                    datasets.add(dataset)
        return sorted(datasets)

    def summary(self) -> dict[str, Any]:
        self._ensure_indexes()
        motion_rows = self._load_artifact("motion_windows")
        vitals_rows = self._load_artifact("vitals_stream")
        event_rows = self._load_artifact("event_catalog")
        activities = sorted(
            {
                activity
                for activity in (
                    self._normalize_activity(row.get("activity_label")) for row in motion_rows + vitals_rows
                )
                if activity
            }
        )
        return {
            "motion_windows": len(motion_rows),
            "vitals_rows": len(vitals_rows),
            "stress_rows": len(self._stress_rows),
            "respiration_rows": len(self._respiration_rows),
            "events": len(event_rows),
            "datasets": self.list_datasets(),
            "activities": activities,
            "event_types": sorted({row.get("event_type") for row in event_rows if row.get("event_type")}),
            "sleep_sessions": len(self._sleep_sessions),
            "stress_source": self.stress_source(),
        }

    def status(self) -> dict[str, Any]:
        self._ensure_indexes()
        return {
            "artifactsDir": str(self.artifacts_dir),
            "datasets": self.list_datasets(),
            "hasSleepSessions": self.has_sleep_sessions(),
            "hasStressData": self.has_stress_data(),
            "stressSource": self.stress_source(),
            "stressRows": len(self._stress_rows),
            "stressStates": {state: len(rows) for state, rows in sorted(self._stress_index.items())},
        }

    def has_sleep_sessions(self) -> bool:
        """True when sleep_sessions artifact has at least one parsed session."""
        return len(self._sleep_sessions) > 0

    def sample_sleep_session(self) -> dict[str, Any]:
        """Get one random sleep session from sleep_sessions artifact."""
        if not self._sleep_sessions:
            raise LookupError("No sleep sessions available in artifact registry")
        return random.choice(self._sleep_sessions)

    @staticmethod
    def _normalize_activity(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if "fall" in normalized:
            return "fall"
        return normalized

    @staticmethod
    def _normalize_stress_state(value: Any) -> str | None:
        return normalize_stress_state(value)

    @staticmethod
    def _compute_stress_baseline_mean(rows: list[dict[str, Any]]) -> float | None:
        baseline_values = [
            float(row["heart_rate"])
            for row in rows
            if row.get("heart_rate") is not None
            and DatasetRegistry._normalize_stress_state(row.get("stress_state")) == "neutral"
        ]
        if not baseline_values:
            return None
        return sum(baseline_values) / len(baseline_values)

    def _ensure_indexes(self) -> None:
        if self._indexes_built:
            return
        self._motion_index = {}
        self._vitals_index = {}
        self._vitals_activity_index = {}
        self._respiration_activity_index = {}
        self._timeline_cache = {}
        self._event_index = {}
        self._stress_index = {}
        for row in self._load_artifact("motion_windows"):
            dataset = row.get("dataset")
            activity = self._normalize_activity(row.get("activity_label"))
            for key in self._activity_lookup_keys(dataset, activity):
                self._motion_index.setdefault(key, []).append(row)
        for row in self._load_artifact("vitals_stream"):
            key = (row.get("subject_id"), row.get("dataset"))
            self._vitals_index.setdefault(key, []).append(row)
            dataset = row.get("dataset")
            activity = self._normalize_activity(row.get("activity_label"))
            for activity_key in self._activity_lookup_keys(dataset, activity):
                self._vitals_activity_index.setdefault(activity_key, []).append(row)
        for row in self._load_artifact("event_catalog"):
            key = row.get("event_type")
            self._event_index.setdefault(key, []).append(row)
        for row in self._stress_rows:
            state = self._normalize_stress_state(row.get("stress_state"))
            if state is not None:
                self._stress_index.setdefault(state, []).append(row)
        for row in self._respiration_rows:
            activity = self._normalize_activity(row.get("activity_label"))
            for activity_key in {activity, None}:
                self._respiration_activity_index.setdefault(activity_key, []).append(row)
        self._indexes_built = True

    @staticmethod
    def _activity_lookup_keys(dataset: str | None, activity: str | None) -> set[tuple[str | None, str | None]]:
        return {
            (dataset, activity),
            (dataset, None),
            (None, activity),
            (None, None),
        }

    def _load_artifact(self, name: str) -> list[dict[str, Any]]:
        if name in self._cache:
            return self._cache[name]

        parquet_path = self.artifacts_dir / f"{name}.parquet"
        jsonl_path = self.artifacts_dir / f"{name}.jsonl"
        if parquet_path.exists():
            records = self._read_parquet(parquet_path)
        elif jsonl_path.exists():
            records = self._read_jsonl(jsonl_path)
        else:
            raise FileNotFoundError(f"Artifact not found: {name}")
        self._cache[name] = records
        return records

    def _load_optional_artifact(self, name: str) -> list[dict[str, Any]]:
        try:
            return self._load_artifact(name)
        except FileNotFoundError:
            return []

    def _load_vitaldb_case_index(self) -> dict[str, dict[str, Any]]:
        if self._vitaldb_case_index is not None:
            return self._vitaldb_case_index

        path = (
            self.artifacts_dir.parent
            / "datasets"
            / "01_vitals"
            / "VitalDB"
            / "VitalDB_Raw"
            / "metadata"
            / "cases.csv.gz"
        )
        if not path.exists():
            if not self._warned_missing_vitaldb_cases:
                logger.warning("VitalDB case metadata file not found: %s", path)
                self._warned_missing_vitaldb_cases = True
            self._vitaldb_case_index = {}
            return self._vitaldb_case_index

        index: dict[str, dict[str, Any]] = {}
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                case_id = str(row.get("caseid") or "").strip()
                subject_lookup = str(row.get("subjectid") or "").strip()
                demographics: dict[str, Any] = {}

                age = self._to_int(row.get("age"))
                if age is not None:
                    demographics["age"] = age
                weight_kg = self._to_float(row.get("weight"))
                if weight_kg is not None:
                    demographics["weight_kg"] = weight_kg
                height_cm = self._to_float(row.get("height"))
                if height_cm is not None:
                    demographics["height_cm"] = height_cm

                if not demographics:
                    continue
                if case_id:
                    index[case_id] = dict(demographics)
                if subject_lookup and subject_lookup not in index:
                    index[subject_lookup] = dict(demographics)

        self._vitaldb_case_index = index
        return self._vitaldb_case_index

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        parsed = DatasetRegistry._to_float(value)
        if parsed is None:
            return None
        return int(parsed)

    @staticmethod
    def _is_missing_value(value: Any) -> bool:
        return value is None or (isinstance(value, float) and isnan(value))

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    records.append(json.loads(stripped))
        return records

    @staticmethod
    def _read_parquet(path: Path) -> list[dict[str, Any]]:
        import pandas as pd  # type: ignore

        return pd.read_parquet(path).to_dict(orient="records")
