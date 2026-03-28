from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .base_adapter import DatasetAdapter
from .types import SleepPhase, SleepSessionRecord

try:
    import pyedflib  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pyedflib = None


class SleepEdfAdapter(DatasetAdapter):
    SOURCE_DATASET = "Sleep-EDF"

    STAGE_MAP: dict[str, str | None] = {
        "Sleep stage W": "awake",
        "Sleep stage R": "rem",
        "Sleep stage 1": "light",
        "Sleep stage 2": "light",
        "Sleep stage 3": "deep",
        "Sleep stage 4": "deep",
        "Sleep stage ?": None,
        "Movement time": None,
    }

    def __init__(self, dataset_root: str | Path | None = None) -> None:
        default_root = Path(__file__).resolve().parents[1] / "datasets" / "03_sleep" / "Sleep-EDF" / "Sleep-EDF_Raw" / "sleep-cassette"
        self.dataset_root = Path(dataset_root) if dataset_root else default_root
        if not self.dataset_root.exists():
            raise FileNotFoundError(f"Sleep-EDF dataset root not found: {self.dataset_root}")
        self._last_report: dict[str, Any] = {}

    @property
    def last_report(self) -> dict[str, Any]:
        return dict(self._last_report)

    def list_subjects(self) -> list[str]:
        subjects: set[str] = set()
        for path in self.dataset_root.glob("*-Hypnogram.edf"):
            subject = self._subject_from_filename(path.name)
            if subject:
                subjects.add(subject)
        return sorted(subjects)

    def load_subject(self, subject_id: str, session_start: str | None = None) -> SleepSessionRecord:
        hypnogram_path = self._resolve_hypnogram_file(subject_id)
        recording_start = self._read_recording_start(hypnogram_path)
        annotations = self._read_annotations(hypnogram_path)
        phases = self._build_phases(recording_start, annotations)
        summary = self._build_summary(phases)

        record = SleepSessionRecord(
            subject_id=subject_id,
            recording_start=recording_start.isoformat(),
            phases=phases,
            summary=summary,
            source_dataset=self.SOURCE_DATASET,
            realism_mode="real",
        )
        self._last_report = {
            "subject_id": subject_id,
            "recording_start": record.recording_start,
            "phase_count": len(record.phases),
            "total_duration_s": sum(phase.duration_s for phase in record.phases),
            "source_file": hypnogram_path.name,
            "stages_seen": sorted({phase.stage for phase in record.phases}),
        }
        return record

    def validate(self, df: Any) -> dict[str, Any]:
        record = self._coerce_record(df)
        total_duration = sum(phase.duration_s for phase in record.phases)
        durations_mod_30 = all(phase.duration_s % 30 == 0 for phase in record.phases)
        stages_valid = all(phase.stage in {"awake", "rem", "light", "deep"} for phase in record.phases)
        strictly_positive = all(phase.duration_s > 0 for phase in record.phases)
        summary = record.summary or {}
        total_sleep = int(summary.get("total_sleep_s", 0) or 0)
        plausible_duration = 4 * 3600 <= total_sleep <= 12 * 3600
        stage_props = summary.get("stage_proportions") or {}
        stage_keys_valid = set(stage_props.keys()) <= {"awake", "rem", "light", "deep"}

        return {
            **self._last_report,
            "phase_count": len(record.phases),
            "total_duration_s": total_duration,
            "total_sleep_s": total_sleep,
            "durations_multiple_of_30": durations_mod_30,
            "stages_valid": stages_valid,
            "durations_positive": strictly_positive,
            "plausible_total_duration": plausible_duration,
            "summary_has_required_keys": all(
                key in summary for key in ("total_sleep_s", "sleep_efficiency", "stage_proportions", "wake_count")
            ),
            "summary_stage_keys_valid": stage_keys_valid,
        }

    @staticmethod
    def format_validation_report(report: dict[str, Any]) -> str:
        return (
            f"[Sleep-EDF ETL] Subject {report.get('subject_id', 'unknown')}\n"
            f"  Source file:      {report.get('source_file')}\n"
            f"  Recording start:  {report.get('recording_start')}\n"
            f"  Phases:           {report.get('phase_count', 0)}\n"
            f"  Total duration:   {report.get('total_duration_s', 0)}s\n"
            f"  Stages seen:      {report.get('stages_seen', [])}\n"
            f"  Sleep efficiency: {report.get('sleep_efficiency', 'n/a')}"
        )

    def _resolve_hypnogram_file(self, subject_id: str) -> Path:
        matches = sorted(self.dataset_root.glob(f"{subject_id}*-Hypnogram.edf"))
        if not matches:
            raise FileNotFoundError(f"Hypnogram EDF not found for subject: {subject_id}")
        return matches[0]

    @staticmethod
    def _subject_from_filename(filename: str) -> str | None:
        prefix = filename.split("-")[0]
        if not prefix.startswith("SC") or len(prefix) < 6:
            return None
        return prefix[:6]

    @staticmethod
    def _read_recording_start(path: Path) -> datetime:
        with path.open("rb") as handle:
            header = handle.read(256)
        date_raw = header[168:176].decode("ascii", errors="ignore").strip()
        time_raw = header[176:184].decode("ascii", errors="ignore").strip()
        if not date_raw or not time_raw:
            raise ValueError(f"Invalid EDF header date/time in file: {path}")

        day, month, year_short = [int(part) for part in date_raw.split(".")]
        hour, minute, second = [int(part) for part in time_raw.split(".")]
        year = 1900 + year_short if year_short >= 85 else 2000 + year_short
        return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)

    def _read_annotations(self, path: Path) -> list[tuple[float, float, str]]:
        if pyedflib is not None:
            try:
                reader = pyedflib.EdfReader(str(path))
                onsets, durations, descriptions = reader.readAnnotations()
                reader.close()
                rows: list[tuple[float, float, str]] = []
                for onset, duration, description in zip(onsets, durations, descriptions):
                    label = description.decode("utf-8", errors="ignore") if isinstance(description, bytes) else str(description)
                    rows.append((float(onset), float(duration), label.strip()))
                if rows:
                    return rows
            except Exception:
                pass
        return self._read_edf_annotations_raw(path)

    @staticmethod
    def _read_edf_annotations_raw(path: Path) -> list[tuple[float, float, str]]:
        raw = path.read_bytes()
        header_len_raw = raw[184:192].decode("ascii", errors="ignore").strip()
        header_len = int(header_len_raw) if header_len_raw.isdigit() else 256
        text = raw[header_len:].decode("latin1", errors="ignore")

        rows: list[tuple[float, float, str]] = []
        pattern = re.compile(r"([+-]?\d+(?:\.\d+)?)\x15(\d+(?:\.\d+)?)\x14(Sleep stage [WR1234\?]|Movement time)\x14")
        for match in pattern.finditer(text):
            onset = float(match.group(1))
            duration = float(match.group(2))
            label = match.group(3).strip()
            rows.append((onset, duration, label))

        if rows:
            return rows

        # Some TAL entries omit duration; fallback to 30-second default epoch.
        fallback = re.compile(r"([+-]?\d+(?:\.\d+)?)\x14(Sleep stage [WR1234\?]|Movement time)\x14")
        for match in fallback.finditer(text):
            onset = float(match.group(1))
            label = match.group(2).strip()
            rows.append((onset, 30.0, label))
        return rows

    def _build_phases(
        self,
        recording_start: datetime,
        annotations: list[tuple[float, float, str]],
    ) -> list[SleepPhase]:
        segments: list[tuple[str, datetime, datetime]] = []
        for onset_s, duration_s, stage_text in sorted(annotations, key=lambda item: item[0]):
            mapped = self.STAGE_MAP.get(stage_text)
            if mapped is None:
                continue
            if duration_s <= 0:
                continue
            start_dt = recording_start + timedelta(seconds=onset_s)
            end_dt = start_dt + timedelta(seconds=duration_s)
            segments.append((mapped, start_dt, end_dt))

        merged = self._merge_contiguous_segments(segments)
        phases: list[SleepPhase] = []
        for stage, start_dt, end_dt in merged:
            duration = int(round((end_dt - start_dt).total_seconds()))
            phases.append(
                SleepPhase(
                    stage=stage,  # type: ignore[arg-type]
                    start=start_dt.isoformat(),
                    end=end_dt.isoformat(),
                    duration_s=duration,
                )
            )
        return phases

    @staticmethod
    def _merge_contiguous_segments(
        segments: list[tuple[str, datetime, datetime]],
    ) -> list[tuple[str, datetime, datetime]]:
        if not segments:
            return []
        merged: list[tuple[str, datetime, datetime]] = [segments[0]]
        for stage, start_dt, end_dt in segments[1:]:
            last_stage, last_start, last_end = merged[-1]
            if stage == last_stage and start_dt <= last_end:
                merged[-1] = (last_stage, last_start, max(last_end, end_dt))
            else:
                merged.append((stage, start_dt, end_dt))
        return merged

    @staticmethod
    def _build_summary(phases: list[SleepPhase]) -> dict[str, Any]:
        total_duration = sum(phase.duration_s for phase in phases)
        stage_totals = {
            "awake": sum(phase.duration_s for phase in phases if phase.stage == "awake"),
            "rem": sum(phase.duration_s for phase in phases if phase.stage == "rem"),
            "light": sum(phase.duration_s for phase in phases if phase.stage == "light"),
            "deep": sum(phase.duration_s for phase in phases if phase.stage == "deep"),
        }
        total_sleep = stage_totals["rem"] + stage_totals["light"] + stage_totals["deep"]
        sleep_efficiency = (total_sleep / total_duration) if total_duration else 0.0

        stage_proportions = {
            stage: (duration / total_duration if total_duration else 0.0)
            for stage, duration in stage_totals.items()
        }

        asleep_seen = False
        wake_count = 0
        for phase in phases:
            if phase.stage == "awake":
                if asleep_seen:
                    wake_count += 1
            else:
                asleep_seen = True

        return {
            "total_sleep_s": total_sleep,
            "sleep_efficiency": round(sleep_efficiency, 6),
            "stage_proportions": {stage: round(value, 6) for stage, value in stage_proportions.items()},
            "wake_count": wake_count,
        }

    @staticmethod
    def _coerce_record(value: Any) -> SleepSessionRecord:
        if isinstance(value, SleepSessionRecord):
            return value
        if isinstance(value, dict):
            phases_raw = value.get("phases") or []
            phases = [
                phase if isinstance(phase, SleepPhase) else SleepPhase(**phase)
                for phase in phases_raw
            ]
            return SleepSessionRecord(
                subject_id=value["subject_id"],
                recording_start=value["recording_start"],
                phases=phases,
                summary=value.get("summary") or {},
                source_dataset=value.get("source_dataset", "Sleep-EDF"),
                realism_mode=value.get("realism_mode", "real"),
            )
        raise TypeError(f"Unsupported record type: {type(value)!r}")


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Sleep-EDF ETL adapter")
    parser.add_argument("--subject", default="SC4001")
    return parser


def main() -> int:
    args = _build_cli_parser().parse_args()
    adapter = SleepEdfAdapter()
    record = adapter.load_subject(args.subject)
    report = adapter.validate(record)
    print(SleepEdfAdapter.format_validation_report(report))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    raise SystemExit(main())
