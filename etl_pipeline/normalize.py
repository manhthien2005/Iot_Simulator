from __future__ import annotations

import argparse
import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from dataset_adapters import (
    BIDMCAdapter,
    PAMAP2Adapter,
    PIFV3Adapter,
    PPGDaLiAAdapter,
    UPFallAdapter,
    VitalDBAdapter,
    WESADAdapter,
)
from dataset_adapters.vitaldb_adapter import BP_DIA_TRACK, BP_SYS_TRACK, SPO2_TRACK
from dataset_adapters.sleep_edf_adapter import SleepEdfAdapter
from simulator_core.dataset_registry import normalize_stress_state

from .artifact_writer import ArtifactWriter
from .window_builder import build_motion_windows


logger = logging.getLogger(__name__)
DEFAULT_VITALDB_SESSION_START = "2026-03-22T10:00:00+07:00"
DEFAULT_VITALDB_CASE_LIMIT = 5


def normalize_sleep(output_dir: Path, max_subjects: int = 10) -> dict[str, Any]:
    """Build sleep_sessions artifact from Sleep-EDF hypnogram annotations."""
    try:
        adapter = SleepEdfAdapter()
    except FileNotFoundError:
        logger.warning("Sleep-EDF dataset not found - skipping sleep stage.")
        return {
            "skipped": True,
            "session_count": 0,
            "subjects_tried": 0,
            "output_path": None,
        }

    subjects = adapter.list_subjects()[:max_subjects]
    sessions: list[dict[str, Any]] = []
    for subject_id in subjects:
        try:
            record = adapter.load_subject(subject_id)
            valid = adapter.validate(record)
            if valid.get("stages_valid") and valid.get("plausible_total_duration"):
                sessions.append(record.to_dict())
        except Exception as exc:  # pragma: no cover - defensive ETL guard
            logger.warning("Skip sleep subject %s: %s", subject_id, exc)

    output_path: str | None = None
    if sessions:
        writer = ArtifactWriter(output_dir)
        output_path = str(writer.write_records("sleep_sessions", sessions))

    return {
        "skipped": False,
        "session_count": len(sessions),
        "subjects_tried": len(subjects),
        "output_path": output_path,
    }


class NormalizedArtifactPipeline:
    def __init__(self, output_dir: str | Path) -> None:
        self.writer = ArtifactWriter(output_dir)
        self.output_dir = Path(output_dir)

    @staticmethod
    def _rows_from_frame(frame: Any) -> list[dict[str, Any]]:
        if hasattr(frame, "to_dict"):
            try:
                return list(frame.to_dict(orient="records"))
            except TypeError:
                pass
        if isinstance(frame, list):
            return frame
        return frame.to_dict()

    def run(self, config: dict[str, Any] | None = None) -> dict[str, str]:
        config = config or self.default_config()
        pif_rows = self._load_pif_rows(config)
        motion_rows = self._load_motion_rows(config, pif_rows=pif_rows)
        vitals_rows, vitaldb_cases_loaded = self._load_vitals_rows(config, pif_rows=pif_rows)
        respiration_rows = self._load_respiration_rows(config)
        stress_rows = self._load_stress_rows(config)
        event_rows = self._load_event_rows(config, pif_rows=pif_rows)
        sleep_stats = normalize_sleep(
            output_dir=self.output_dir,
            max_subjects=int(config.get("sleep", {}).get("max_subjects", 10)),
        )

        motion_windows = build_motion_windows(motion_rows)
        output_paths = {
            "motion_windows": str(self.writer.write_records("motion_windows", motion_windows)),
            "vitals_stream": str(self.writer.write_records("vitals_stream", vitals_rows)),
            "event_catalog": str(self.writer.write_records("event_catalog", event_rows)),
        }
        if stress_rows:
            output_paths["stress_stream"] = str(self.writer.write_records("stress_stream", stress_rows))
        if respiration_rows:
            output_paths["respiration_stream"] = str(self.writer.write_records("respiration_stream", respiration_rows))
        if sleep_stats.get("output_path"):
            output_paths["sleep_sessions"] = str(sleep_stats["output_path"])

        summary_path = self.output_dir / "normalize_summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now().isoformat(),
                    "counts": {
                        "motion_rows": len(motion_rows),
                        "motion_windows": len(motion_windows),
                        "vitals_rows": len(vitals_rows),
                        "respiration_rows": len(respiration_rows),
                        "vitaldb_cases_loaded": vitaldb_cases_loaded,
                        "stress_rows": len(stress_rows),
                        "event_rows": len(event_rows),
                        "sleep_session_count": int(sleep_stats.get("session_count", 0)),
                        "sleep_subjects_tried": int(sleep_stats.get("subjects_tried", 0)),
                        "sleep_skipped": bool(sleep_stats.get("skipped", False)),
                    },
                    "outputs": output_paths,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        output_paths["summary"] = str(summary_path)
        return output_paths

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        vitaldb_cases = cls._default_vitaldb_cases()
        return {
            "pif_v3": {"subjects": ["PID1"], "session_start": "2026-03-22T10:00:00+07:00"},
            "up_fall": {"subjects": ["Subject_01", "Subject_02", "Subject_03", "Subject_04"]},
            "pamap2": {"subjects": ["subject101"], "session_start": "2026-03-22T10:00:00+07:00"},
            "ppg_dalia": {"subjects": ["S1"]},
            "vitaldb": {
                "enabled": bool(vitaldb_cases),
                "dataset_root": None,
                "cases": vitaldb_cases,
            },
            "bidmc": {
                "enabled": True,
                "dataset_root": None,
                "subjects": ["bidmc01", "bidmc02", "bidmc03"],
            },
            "wesad": {
                "enabled": True,
                "dataset_root": None,
                "subjects": ["S2", "S3"],
            },
            "sleep": {"max_subjects": 10},
        }

    @staticmethod
    def _default_vitaldb_cases(
        limit: int = DEFAULT_VITALDB_CASE_LIMIT,
        session_start: str = DEFAULT_VITALDB_SESSION_START,
    ) -> list[dict[str, str]]:
        try:
            vitaldb = VitalDBAdapter()
        except (FileNotFoundError, ValueError):
            return []

        selected_cases: list[dict[str, str]] = []
        for caseid in vitaldb.list_subjects():
            has_required_tracks = (
                vitaldb._resolve_track(caseid, SPO2_TRACK) is not None
                and vitaldb._resolve_track(caseid, BP_SYS_TRACK) is not None
                and vitaldb._resolve_track(caseid, BP_DIA_TRACK) is not None
            )
            if not has_required_tracks:
                continue
            selected_cases.append({"caseid": str(caseid), "session_start": session_start})
            if len(selected_cases) >= limit:
                break
        return selected_cases

    def _load_pif_rows(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        pif_config = config.get("pif_v3", {})
        pif_subjects = list(pif_config.get("subjects", []))
        if not pif_subjects:
            return []

        pif = PIFV3Adapter()
        rows: list[dict[str, Any]] = []
        for subject in pif_subjects:
            rows.extend(self._rows_from_frame(pif.load_subject(subject, pif_config["session_start"])))
        return rows

    def _load_motion_rows(
        self,
        config: dict[str, Any],
        *,
        pif_rows: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        rows.extend(pif_rows if pif_rows is not None else self._load_pif_rows(config))

        up_config = config.get("up_fall", {})
        up_subjects = list(up_config.get("subjects", []))
        if up_subjects:
            try:
                up = UPFallAdapter()
            except FileNotFoundError as exc:
                logger.warning("UP-Fall dataset not found — skipping fall motion rows: %s", exc)
                up = None
            if up is not None:
                for subject in up_subjects:
                    try:
                        rows.extend(self._rows_from_frame(up.load_subject(subject)))
                    except FileNotFoundError:
                        logger.debug("UP-Fall subject %s not found — skipping", subject)
                    except Exception as exc:  # pragma: no cover — defensive ETL guard
                        logger.warning("Skip UP-Fall subject %s: %s", subject, exc)

        pamap2_config = config.get("pamap2", {})
        pamap2_subjects = list(pamap2_config.get("subjects", []))
        if pamap2_subjects:
            pamap2 = PAMAP2Adapter()
            for subject in pamap2_subjects:
                rows.extend(self._rows_from_frame(pamap2.load_subject(subject, pamap2_config["session_start"])))

        return rows

    def _load_vitals_rows(
        self,
        config: dict[str, Any],
        *,
        pif_rows: list[dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rows: list[dict[str, Any]] = []
        vitaldb_cases_loaded = 0

        for row in pif_rows if pif_rows is not None else self._load_pif_rows(config):
            if row.get("heart_rate") is None:
                continue
            rows.append(
                {
                    "timestamp": row["timestamp"],
                    "subject_id": row["subject_id"],
                    "dataset": row["source_dataset"],
                    "heart_rate": row["heart_rate"],
                    "spo2": row.get("spo2"),
                    "blood_pressure_sys": row.get("blood_pressure_sys"),
                    "blood_pressure_dia": row.get("blood_pressure_dia"),
                    "activity_label": row.get("activity_label"),
                }
            )

        ppg_config = config.get("ppg_dalia", {})
        ppg_subjects = list(ppg_config.get("subjects", []))
        if ppg_subjects:
            ppg = PPGDaLiAAdapter()
            for subject in ppg_subjects:
                subject_rows = self._rows_from_frame(ppg.load_subject(subject))
                for row in subject_rows:
                    if row.get("heart_rate") is None:
                        continue
                    rows.append(
                        {
                            "timestamp": row["timestamp"],
                            "subject_id": row["subject_id"],
                            "dataset": row["source_dataset"],
                            "heart_rate": row["heart_rate"],
                            "spo2": None,
                            "blood_pressure_sys": None,
                            "blood_pressure_dia": None,
                            "activity_label": row.get("activity_label"),
                        }
                    )

        vitaldb_config = config.get("vitaldb", {})
        if vitaldb_config.get("enabled"):
            cases = list(vitaldb_config.get("cases", []))
            if not cases:
                raise ValueError("VitalDB is enabled but no cases were configured")

            vitaldb = VitalDBAdapter(dataset_root=vitaldb_config.get("dataset_root"))
            for case_config in cases:
                caseid = str(case_config.get("caseid", "")).strip()
                session_start = str(case_config.get("session_start", "")).strip()
                if not caseid or not session_start:
                    raise ValueError("Each VitalDB case config must include caseid and session_start")

                subject_rows = self._rows_from_frame(vitaldb.load_subject(caseid, session_start))
                case_row_count = 0
                for row in subject_rows:
                    if row.get("heart_rate") is None:
                        continue
                    case_row_count += 1
                    rows.append(
                        {
                            "timestamp": row["timestamp"],
                            "subject_id": row["subject_id"],
                            "dataset": row["source_dataset"],
                            "heart_rate": row["heart_rate"],
                            "spo2": row.get("spo2"),
                            "blood_pressure_sys": row.get("blood_pressure_sys"),
                            "blood_pressure_dia": row.get("blood_pressure_dia"),
                            "activity_label": row.get("activity_label"),
                        }
                    )
                if case_row_count > 0:
                    vitaldb_cases_loaded += 1
        return rows, vitaldb_cases_loaded

    def _load_respiration_rows(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        bidmc_config = config.get("bidmc", {})
        if not bidmc_config.get("enabled", False):
            return []

        subjects = list(bidmc_config.get("subjects", []))
        if not subjects:
            return []

        try:
            adapter = BIDMCAdapter(dataset_root=bidmc_config.get("dataset_root"))
        except FileNotFoundError:
            logger.warning("BIDMC dataset not found - skipping respiration stream.")
            return []

        rows: list[dict[str, Any]] = []
        for subject in subjects:
            try:
                subject_rows = self._rows_from_frame(
                    adapter.load_subject(subject, bidmc_config.get("session_start"))
                )
            except FileNotFoundError as exc:
                logger.warning("Skip BIDMC subject %s: %s", subject, exc)
                continue
            except Exception as exc:  # pragma: no cover - defensive ETL guard
                logger.warning("Skip BIDMC subject %s: %s", subject, exc)
                continue

            for row in subject_rows:
                respiration_rate = row.get("respiration_rate")
                if respiration_rate is None:
                    continue
                rows.append(
                    {
                        "timestamp": row["timestamp"],
                        "subject_id": row["subject_id"],
                        "dataset": row["source_dataset"],
                        "respiration_rate": respiration_rate,
                        "heart_rate": row.get("heart_rate"),
                        "spo2": row.get("spo2"),
                        "activity_label": row.get("activity_label"),
                    }
                )
        return rows

    def _load_stress_rows(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        stress_config = config.get("wesad", {})
        if not stress_config.get("enabled", False):
            return []

        subjects = list(stress_config.get("subjects", []))[:3]
        if not subjects:
            return []

        try:
            wesad = WESADAdapter(dataset_root=stress_config.get("dataset_root"))
        except FileNotFoundError:
            logger.warning("WESAD dataset not found - skipping stress stream.")
            return []

        rows: list[dict[str, Any]] = []
        for subject in subjects:
            try:
                subject_rows = self._rows_from_frame(wesad.load_subject(subject))
            except FileNotFoundError as exc:
                logger.warning("Skip WESAD subject %s: %s", subject, exc)
                continue
            except Exception as exc:  # pragma: no cover - defensive ETL guard
                logger.warning("Skip WESAD subject %s: %s", subject, exc)
                continue

            for row in subject_rows:
                stress_state = normalize_stress_state(row.get("stress_state"))
                heart_rate = row.get("heart_rate")
                if stress_state is None or heart_rate is None:
                    continue
                rows.append(
                    {
                        "timestamp": row["timestamp"],
                        "subject_id": row["subject_id"],
                        "stress_state": stress_state,
                        "heart_rate": heart_rate,
                        "source_dataset": row.get("source_dataset", "WESAD"),
                    }
                )
        return rows

    def _load_event_rows(
        self,
        config: dict[str, Any],
        *,
        pif_rows: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        if pif_rows is not None:
            rows.extend(self._extract_events(pif_rows))
        else:
            pif_subject_rows = self._load_pif_rows(config)
            if pif_subject_rows:
                rows.extend(self._extract_events(pif_subject_rows))

        up_config = config.get("up_fall", {})
        up_subjects = list(up_config.get("subjects", []))
        if up_subjects:
            up = UPFallAdapter()
            for subject in up_subjects:
                subject_rows = self._rows_from_frame(up.load_subject(subject))
                rows.extend(self._extract_events(subject_rows))
        return rows

    def _extract_events(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        fall_rows = [row for row in rows if row.get("fall_variant")]
        if not fall_rows:
            return events

        current_segment: list[dict[str, Any]] = []
        current_key: tuple[str | None, str | None] | None = None

        def _event_sort_key(item: dict[str, Any]) -> tuple[str, str, tuple[int, float | str]]:
            timestamp = item.get("timestamp")
            if isinstance(timestamp, (int, float)):
                ts_key: tuple[int, float | str] = (0, float(timestamp))
            else:
                ts_key = (1, str(timestamp or ""))
            return (
                str(item.get("subject_id") or ""),
                str(item.get("fall_variant") or ""),
                ts_key,
            )

        for row in sorted(fall_rows, key=_event_sort_key):
            key = (row.get("subject_id"), row.get("fall_variant"))
            if current_key is None or key == current_key:
                current_segment.append(row)
                current_key = key
                continue
            events.append(self._segment_to_event(current_segment, rows))
            current_segment = [row]
            current_key = key

        if current_segment:
            events.append(self._segment_to_event(current_segment, rows))
        return events

    @staticmethod
    def _segment_to_event(segment: list[dict[str, Any]], all_rows: list[dict[str, Any]]) -> dict[str, Any]:
        first = segment[0]
        last = segment[-1]
        subject_rows = [row for row in all_rows if row.get("subject_id") == first.get("subject_id")]
        start_index = subject_rows.index(first) if first in subject_rows else 0
        end_index = subject_rows.index(last) if last in subject_rows else len(subject_rows) - 1
        pre_slice = subject_rows[max(0, start_index - 5) : start_index]
        post_slice = subject_rows[end_index + 1 : end_index + 6]
        accel_peaks = [
            math.sqrt(sum((value or 0) ** 2 for value in row["accel_mps2"].values()))
            for row in segment
        ]
        return {
            "event_id": f"{first['subject_id']}_{first['fall_variant']}_{first['timestamp']}",
            "subject_id": first["subject_id"],
            "dataset": first["source_dataset"],
            "event_type": "fall_detected",
            "fall_variant": first["fall_variant"],
            "event_start_ts": first["timestamp"],
            "event_end_ts": last["timestamp"],
            "pre_vitals": _snapshot_vitals(pre_slice[-1] if pre_slice else None),
            "post_vitals": _snapshot_vitals(post_slice[-1] if post_slice else None),
            "peak_accel_mag": round(max(accel_peaks), 6) if accel_peaks else None,
        }


def _snapshot_vitals(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    if row.get("heart_rate") is None and row.get("spo2") is None:
        return None
    return {
        "heart_rate": row.get("heart_rate"),
        "spo2": row.get("spo2"),
        "blood_pressure_sys": row.get("blood_pressure_sys"),
        "blood_pressure_dia": row.get("blood_pressure_dia"),
    }


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build normalized artifacts for IoT Simulator")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "normalized_artifacts"),
    )
    return parser


def main() -> int:
    args = _build_cli_parser().parse_args()
    pipeline = NormalizedArtifactPipeline(args.output_dir)
    outputs = pipeline.run()
    print(json.dumps(outputs, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    raise SystemExit(main())
