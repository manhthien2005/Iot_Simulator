"""SleepService — extracted from SimulatorRuntime (Task 3.4).

Owns all sleep session construction, scoring (heuristic + AI), sleep-to-backend
push logic, sleep DB history queries, backfill, sleep-phase advancement, and
scenario-driven sleep session selection.

Thread-safety: public methods that touch shared state acquire ``self._lock``
(the *same* ``threading.RLock`` instance shared with ``SimulatorRuntime``).
"""

from __future__ import annotations

import json as _json
import logging
import os
import random as _random
from datetime import date, datetime, timedelta, timezone
from threading import RLock
from time import monotonic
from typing import TYPE_CHECKING, Any
import httpx

from sqlalchemy import text

# Dual import path: supports both package-level execution
#   (`python -m Iot_Simulator.api_server.main`)
# and direct execution from the project root
#   (`uvicorn api_server.main:app`).
try:
    from Iot_Simulator.api_server.db import session_scope
    from Iot_Simulator.api_server.utils import _utc_now_iso, _safe_float, _coerce_date, _normalize_gender
    from Iot_Simulator.api_server.schemas import (
        DbSleepHistoryRow,
        SleepHistoryRow,
        SleepSessionResponse,
        SleepStageSegment,
    )
    from Iot_Simulator.simulator_core.dataset_registry import DatasetRegistry
    from Iot_Simulator.simulator_core.sleep_ai_client import SleepAIClient
    from Iot_Simulator.simulator_core.sleep_vitals_enricher import enrich_sleep_record
except ModuleNotFoundError:
    from api_server.db import session_scope
    from api_server.utils import _utc_now_iso, _safe_float, _coerce_date, _normalize_gender
    from api_server.schemas import (
        DbSleepHistoryRow,
        SleepHistoryRow,
        SleepSessionResponse,
        SleepStageSegment,
    )
    from simulator_core.dataset_registry import DatasetRegistry
    from simulator_core.sleep_ai_client import SleepAIClient
    from simulator_core.sleep_vitals_enricher import enrich_sleep_record

if TYPE_CHECKING:
    from api_server.dependencies import DeviceRecord, SessionRecord

logger = logging.getLogger(__name__)


# IS-004: Scenario data moved to instance attributes (self._scenario_phases, self._scenario_profiles).
# Module-level dicts removed to prevent state leak across instances.


class SleepService:
    """Manages all sleep session logic: build, score, push, history, backfill."""

    def __init__(
        self,
        *,
        devices: dict[str, "DeviceRecord"],
        sessions: dict[str, "SessionRecord"],
        device_scenarios: dict[str, str],
        lock: RLock,
        registry: DatasetRegistry,
        sleep_ai_client: SleepAIClient,
        sleep_phase_tracker: dict[str, tuple[int, float]],
        health_backend_url: str,
        http_sender: Any,
        publish_device_log_fn: Any,
        require_device_fn: Any,
        internal_secret: str | None = None,
        sleep_scenario_phases: dict[str, Any] | None = None,
        sleep_scenario_profiles: dict[str, Any] | None = None,
    ) -> None:
        self.devices = devices
        self.sessions = sessions
        self.device_scenarios = device_scenarios
        self._lock = lock
        self.registry = registry
        self._sleep_ai_client = sleep_ai_client
        self._last_sleep_score_source = "heuristic"
        self._sleep_phase_tracker = sleep_phase_tracker
        self._health_backend_url = health_backend_url
        self._http_sender = http_sender
        self._publish_device_log = publish_device_log_fn
        self._require_device = require_device_fn
        self._internal_secret = internal_secret

        # IS-004 fix: scenario data as instance attributes (not module globals).
        self._scenario_phases: dict[str, Any] = dict(sleep_scenario_phases or {})
        self._scenario_profiles: dict[str, Any] = dict(sleep_scenario_profiles or {})

        # CRITICAL #2 fix: shared httpx.Client for sleep push requests
        # instead of creating a new TCP connection each call via httpx.post().
        self._http_client: httpx.Client | None = None

    def _build_internal_headers(self) -> dict[str, str]:
        """Build request headers with internal service auth per ADR-005."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-Internal-Service": "iot-simulator",
        }
        if self._internal_secret:
            headers["X-Internal-Secret"] = self._internal_secret
        return headers

    # ------------------------------------------------------------------
    # Sleep window computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_sleep_window(duration_minutes: int) -> tuple[date, datetime, datetime]:
        """Return a stable ``(sleep_date, start_time, end_time)`` window."""
        duration = max(1, int(duration_minutes))
        now = datetime.now(timezone.utc)
        yesterday = (now - timedelta(days=1)).date()

        start_floor = datetime(
            yesterday.year, yesterday.month, yesterday.day,
            21, 0, 0, tzinfo=timezone.utc,
        )
        start_time = start_floor + timedelta(minutes=_random.randint(0, 240))
        end_time = start_time + timedelta(minutes=duration)

        absolute_floor = datetime(
            yesterday.year, yesterday.month, yesterday.day,
            20, 0, 0, tzinfo=timezone.utc,
        )
        if end_time > now:
            end_time = now
            start_time = max(end_time - timedelta(minutes=duration), absolute_floor)

        return yesterday, start_time, end_time

    @staticmethod
    def _compute_sleep_window_for_date(target_date: date, duration_minutes: int) -> tuple[date, datetime, datetime]:
        duration = max(1, int(duration_minutes))
        start_floor = datetime(
            target_date.year, target_date.month, target_date.day,
            21, 0, 0, tzinfo=timezone.utc,
        )
        start_time = start_floor + timedelta(minutes=_random.randint(0, 240))
        end_time = start_time + timedelta(minutes=duration)
        return target_date, start_time, end_time

    # ------------------------------------------------------------------
    # Phase/segment helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _phase_minutes_from_segments(
        phases: list[SleepStageSegment],
        fallback_duration_minutes: int | None = None,
    ) -> tuple[dict[str, int], int]:
        phases_dict: dict[str, int] = {}
        for seg in phases:
            try:
                start = datetime.fromisoformat(seg.start.replace("Z", "+00:00"))
                end = datetime.fromisoformat(seg.end.replace("Z", "+00:00"))
                minutes = max(0, int((end - start).total_seconds() // 60))
                stage = str(seg.stage)
                phases_dict[stage] = phases_dict.get(stage, 0) + minutes
            except Exception:
                logger.warning("Failed to parse sleep phase segment: %s", seg, exc_info=True)
                continue

        if not phases_dict:
            phases_dict = {"awake": 30, "light": 180, "deep": 90, "rem": 60}

        duration_minutes = sum(phases_dict.values())
        if duration_minutes <= 0:
            try:
                duration_minutes = int(fallback_duration_minutes or 0)
            except (TypeError, ValueError):
                duration_minutes = 1
        return phases_dict, max(1, duration_minutes)

    @staticmethod
    def _coerce_phase_minutes_dict(phases_raw: Any) -> dict[str, int]:
        if isinstance(phases_raw, str):
            try:
                phases_data = _json.loads(phases_raw)
            except ValueError:
                phases_data = {}
        elif isinstance(phases_raw, dict):
            phases_data = phases_raw
        else:
            phases_data = {}

        normalized: dict[str, int] = {}
        for stage in ("deep", "light", "rem", "awake"):
            try:
                value = int(round(float(phases_data.get(stage, 0) or 0)))
            except (TypeError, ValueError):
                value = 0
            normalized[stage] = max(0, value)
        return normalized

    @staticmethod
    def _coerce_datetime_value(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
        return None

    @staticmethod
    def _datetime_to_iso(value: datetime | None) -> str:
        if value is None:
            return ""
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _apply_sleep_summary_override(
        base_summary: dict[str, Any],
        stats_override: dict[str, Any] | None,
    ) -> dict[str, Any]:
        summary = dict(base_summary or {})
        stage_proportions = dict(summary.get("stage_proportions") or {})
        if stats_override is None:
            summary["stage_proportions"] = stage_proportions
            return summary

        for key, value in stats_override.items():
            if key == "stage_proportions" and isinstance(value, dict):
                stage_proportions.update(value)
                continue
            if key == "total_sleep_s_override":
                summary["total_sleep_s"] = int(value)
                continue
            if key == "spo2_min_override":
                continue
            summary[key] = value

        summary["stage_proportions"] = stage_proportions
        return summary

    @staticmethod
    def _normalize_stage_proportions(stage_proportions: dict[str, Any] | None) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for stage in ("awake", "light", "deep", "rem"):
            value = _safe_float((stage_proportions or {}).get(stage), 0.0) or 0.0
            if value > 1:
                value /= 100.0
            normalized[stage] = max(0.0, value)

        total = sum(normalized.values())
        if normalized["awake"] == 0.0 and 0.0 < total < 1.0:
            normalized["awake"] = max(0.0, 1.0 - total)
            total = sum(normalized.values())

        if total <= 0:
            return {"awake": 0.10, "light": 0.55, "deep": 0.15, "rem": 0.20}
        if abs(total - 1.0) > 0.0001:
            normalized = {stage: value / total for stage, value in normalized.items()}
        return normalized

    @staticmethod
    def _split_minutes(total_minutes: int, parts: int) -> list[int]:
        if parts <= 0:
            return []
        base = max(0, total_minutes) // parts
        remainder = max(0, total_minutes) % parts
        return [base + (1 if idx < remainder else 0) for idx in range(parts)]

    @staticmethod
    def _segment_minutes(start_iso: str, end_iso: str) -> int:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
        delta = end - start
        return int(max(0, delta.total_seconds() // 60))

    @staticmethod
    def _build_sleep_segments(
        anchor_date: date,
        start_hour: int = 22,
        start_minute: int = 0,
    ) -> list[SleepStageSegment]:
        if start_hour == 22 and start_minute == 0:
            offset = _random.randint(0, 90)
            start_hour = 22 + (offset // 60)
            start_minute = offset % 60

        base = datetime(anchor_date.year, anchor_date.month, anchor_date.day, start_hour, start_minute, tzinfo=timezone.utc)
        pattern: list[tuple[str, int]] = [
            ("light", 35), ("deep", 60), ("rem", 25), ("light", 45),
            ("awake", 10), ("deep", 55), ("rem", 25), ("light", 45),
            ("awake", 7), ("rem", 28), ("light", 75),
        ]
        segments: list[SleepStageSegment] = []
        current = base
        for stage, duration in pattern:
            start = current
            end = current + timedelta(minutes=duration)
            segments.append(SleepStageSegment(stage=stage, start=start.isoformat(), end=end.isoformat()))  # type: ignore[arg-type]
            current = end
        return segments

    @staticmethod
    def _build_sleep_history(device_id: str, anchor_date: date) -> list[SleepHistoryRow]:
        seed = int(device_id[:8], 16)
        rows: list[SleepHistoryRow] = []
        for offset in range(6, -1, -1):
            date_value = (anchor_date - timedelta(days=offset)).isoformat()
            score = 78 + ((seed + offset * 3) % 18)
            efficiency = round(87.0 + ((seed >> (offset % 6)) % 10) * 0.9, 1)
            duration_minutes = 380 + ((seed + offset * 11) % 61)
            avg_hr = float(55 + ((seed + offset) % 9))
            min_spo2 = float(93 + ((seed + offset * 2) % 5))
            rows.append(
                SleepHistoryRow(
                    date=date_value,
                    score=score,
                    efficiency=efficiency,
                    durationMinutes=duration_minutes,
                    avgHeartRate=avg_hr,
                    minSpo2=min_spo2,
                )
            )
        return rows

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_sleep_score_from_summary(summary: dict[str, Any]) -> int:
        efficiency_ratio = _safe_float(summary.get("sleep_efficiency"), 0.0)
        if efficiency_ratio is None:
            efficiency_ratio = 0.0
        if efficiency_ratio > 1:
            efficiency_ratio /= 100
        efficiency_ratio = max(0.0, min(1.0, efficiency_ratio))
        stage_props = summary.get("stage_proportions") or {}
        deep_ratio = _safe_float(stage_props.get("deep"), 0.0)
        if deep_ratio is None:
            deep_ratio = 0.0
        if deep_ratio > 1:
            deep_ratio /= 100
        deep_ratio = max(0.0, min(1.0, deep_ratio))
        # LOW #3: add REM component to sleep score
        rem_ratio = _safe_float(stage_props.get("rem"), 0.0)
        if rem_ratio is None:
            rem_ratio = 0.0
        if rem_ratio > 1:
            rem_ratio /= 100
        rem_ratio = max(0.0, min(1.0, rem_ratio))
        rem_bonus = rem_ratio * 10
        wake_count = int(summary.get("wake_count") or 0)
        return max(0, min(100, round(25 + efficiency_ratio * 55 + deep_ratio * 20 + rem_bonus - min(wake_count, 8) * 2.5)))

    def _calc_sleep_score(self, raw: dict[str, Any]) -> int:
        summary = raw.get("summary") or {}
        efficiency_ratio = _safe_float(summary.get("sleep_efficiency"), 0.0)
        if efficiency_ratio > 1:
            efficiency_ratio /= 100
        efficiency_ratio = max(0.0, min(1.0, efficiency_ratio))
        stage_props = summary.get("stage_proportions") or {}
        deep_ratio = _safe_float(stage_props.get("deep"), 0.0)
        if deep_ratio > 1:
            deep_ratio /= 100
        deep_ratio = max(0.0, min(1.0, deep_ratio))
        # LOW #3: add REM component to sleep score
        rem_ratio = _safe_float(stage_props.get("rem"), 0.0)
        if rem_ratio is not None and rem_ratio > 1:
            rem_ratio /= 100
        rem_ratio = max(0.0, min(1.0, rem_ratio or 0.0))
        rem_bonus = rem_ratio * 10
        wake_count = int(summary.get("wake_count") or 0)
        wake_penalty = min(max(wake_count, 0), 8) * 2.5
        score = 25 + efficiency_ratio * 55 + deep_ratio * 20 + rem_bonus - wake_penalty
        return max(0, min(100, round(score)))

    def _compute_sleep_score_with_ai(self, sleep_ai_record: dict) -> int:
        client = self._sleep_ai_client
        if client is not None:
            result = client.predict(sleep_ai_record)
            predicted = _safe_float((result or {}).get("predicted_sleep_score"), None) if isinstance(result, dict) else None
            if predicted is not None:
                score = max(0, min(100, int(round(predicted))))
                self._last_sleep_score_source = "ai"
                logger.info("Sleep AI score: %s", score)
                return score

        fallback_summary = {
            "sleep_efficiency": (_safe_float(sleep_ai_record.get("sleep_efficiency_pct"), 0.0) or 0.0) / 100.0,
            "stage_proportions": {
                "deep": (_safe_float(sleep_ai_record.get("sleep_stage_deep_pct"), 0.0) or 0.0) / 100.0,
            },
            "wake_count": int(sleep_ai_record.get("wake_count") or 0),
        }
        fallback_score = self._compute_sleep_score_from_summary(fallback_summary)
        self._last_sleep_score_source = "heuristic"
        logger.warning("Sleep AI unavailable — using heuristic fallback score: %s", fallback_score)
        return fallback_score

    # ------------------------------------------------------------------
    # AI record building
    # ------------------------------------------------------------------

    def _build_sleep_ai_record(
        self,
        *,
        scenario_id: str,
        summary: dict[str, Any],
        phases_dict: dict[str, int],
        duration_minutes: int,
        sleep_date: date,
        start_time: datetime,
        end_time: datetime,
        user_id: int,
        persona_config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        scenario_defaults: dict[str, dict[str, float | int | str]] = {
            "good_sleep_night": {
                "sleep_latency_minutes": 12.0, "step_count_day": 7600.0, "caffeine_mg": 80.0,
                "alcohol_units": 0.0, "medication_flag": 0.0, "jetlag_hours": 0.0,
                "timezone": "Asia/Bangkok", "bedtime_consistency_std_min": 18.0,
                "stress_score": 27.0, "activity_before_bed_min": 20.0,
                "screen_time_before_bed_min": 35.0, "insomnia_flag": 0.0,
                "apnea_risk_score": 14.0, "nap_duration_minutes": 0.0,
                "device_model": "VSmartwatch Simulator",
            },
            "fragmented_sleep": {
                "sleep_latency_minutes": 22.0, "step_count_day": 5600.0, "caffeine_mg": 120.0,
                "alcohol_units": 0.5, "medication_flag": 0.0, "jetlag_hours": 0.0,
                "timezone": "Asia/Bangkok", "bedtime_consistency_std_min": 42.0,
                "stress_score": 54.0, "activity_before_bed_min": 12.0,
                "screen_time_before_bed_min": 62.0, "insomnia_flag": 1.0,
                "apnea_risk_score": 30.0, "nap_duration_minutes": 18.0,
                "device_model": "VSmartwatch Simulator",
            },
            "sleep_apnea_mild": {
                "sleep_latency_minutes": 18.0, "step_count_day": 5100.0, "caffeine_mg": 100.0,
                "alcohol_units": 0.5, "medication_flag": 0.0, "jetlag_hours": 0.0,
                "timezone": "Asia/Bangkok", "bedtime_consistency_std_min": 34.0,
                "stress_score": 60.0, "activity_before_bed_min": 15.0,
                "screen_time_before_bed_min": 50.0, "insomnia_flag": 0.0,
                "apnea_risk_score": 64.0, "nap_duration_minutes": 12.0,
                "device_model": "VSmartwatch Simulator",
            },
            "sleep_apnea_severe": {
                "sleep_latency_minutes": 20.0, "step_count_day": 4200.0, "caffeine_mg": 90.0,
                "alcohol_units": 0.0, "medication_flag": 0.0, "jetlag_hours": 0.0,
                "timezone": "Asia/Bangkok", "bedtime_consistency_std_min": 45.0,
                "stress_score": 68.0, "activity_before_bed_min": 5.0,
                "screen_time_before_bed_min": 40.0, "insomnia_flag": 0.0,
                "apnea_risk_score": 92.0, "nap_duration_minutes": 24.0,
                "device_model": "VSmartwatch Simulator",
            },
        }
        defaults = scenario_defaults.get(scenario_id, scenario_defaults["fragmented_sleep"])
        persona = dict(persona_config or {})
        enriched = enrich_sleep_record(scenario_id, summary, persona)
        total_minutes = max(1, int(duration_minutes))
        awake_minutes = max(0, int(phases_dict.get("awake", 0)))
        asleep_minutes = max(1, total_minutes - awake_minutes)

        sleep_efficiency = _safe_float(summary.get("sleep_efficiency"), None)
        if sleep_efficiency is None:
            sleep_efficiency_pct = round((asleep_minutes / total_minutes) * 100.0, 1)
        else:
            sleep_efficiency_pct = round(sleep_efficiency * 100.0 if sleep_efficiency <= 1 else sleep_efficiency, 1)

        def _pct(stage: str) -> float:
            return round((max(0, float(phases_dict.get(stage, 0))) / total_minutes) * 100.0, 1)

        def _float_value(key: str, default: float) -> float:
            raw = persona.get(key, defaults.get(key, default))
            value = _safe_float(raw, default)
            return float(default if value is None else value)

        def _int_value(key: str, default: int) -> int:
            raw = persona.get(key, defaults.get(key, default))
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default

        gender = _normalize_gender(persona.get("gender")) or "female"
        timezone_name = str(persona.get("timezone") or defaults["timezone"])
        device_model = str(persona.get("device_model") or defaults["device_model"])
        wake_count = int(summary.get("wake_count") or 0)

        return {
            "user_id": str(user_id),
            "date_recorded": sleep_date.isoformat(),
            "sleep_start_timestamp": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "sleep_end_timestamp": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_minutes": float(total_minutes),
            "sleep_latency_minutes": _float_value("sleep_latency_minutes", 15.0),
            "wake_after_sleep_onset_minutes": float(awake_minutes),
            "sleep_efficiency_pct": sleep_efficiency_pct,
            "sleep_stage_deep_pct": _pct("deep"),
            "sleep_stage_light_pct": _pct("light"),
            "sleep_stage_rem_pct": _pct("rem"),
            "sleep_stage_awake_pct": _pct("awake"),
            **enriched,
            "step_count_day": _float_value("step_count_day", 6000.0),
            "caffeine_mg": _float_value("caffeine_mg", 80.0),
            "alcohol_units": _float_value("alcohol_units", 0.0),
            "medication_flag": _float_value("medication_flag", 0.0),
            "jetlag_hours": _float_value("jetlag_hours", 0.0),
            "timezone": timezone_name,
            "age": float(_int_value("age", 35)),
            "gender": gender,
            "weight_kg": _float_value("weight_kg", 70.0),
            "height_cm": _float_value("height_cm", 170.0),
            "device_model": device_model,
            "bedtime_consistency_std_min": _float_value("bedtime_consistency_std_min", 25.0),
            "stress_score": _float_value("stress_score", 40.0),
            "activity_before_bed_min": _float_value("activity_before_bed_min", 15.0),
            "screen_time_before_bed_min": _float_value("screen_time_before_bed_min", 45.0),
            "insomnia_flag": _float_value("insomnia_flag", 0.0),
            "apnea_risk_score": _float_value("apnea_risk_score", 20.0),
            "nap_duration_minutes": _float_value("nap_duration_minutes", 0.0),
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "wake_count": wake_count,
            "scenario_id": scenario_id,
        }

    # ------------------------------------------------------------------
    # Backend push
    # ------------------------------------------------------------------

    def _get_http_client(self) -> httpx.Client:
        """Lazy-init shared httpx.Client for sleep push requests (CRITICAL #2 fix)."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.Client(timeout=5)
        return self._http_client

    def _push_sleep_to_backend(
        self,
        sim_device_id: str,
        sleep_resp: SleepSessionResponse,
        user_id: int | None = None,
    ) -> None:
        with self._lock:
            device = self.devices.get(sim_device_id)
            bound_db_device_id = device.bound_db_device_id if device is not None else None
        if bound_db_device_id is None:
            return
        resolved_user_id = user_id if user_id is not None else self._resolve_bound_device_user_id(bound_db_device_id)
        if resolved_user_id is None:
            self._publish_device_log(
                sim_device_id,
                level="ERROR",
                message=f"Sleep push failed: no owner found for db_device_id={bound_db_device_id}",
                timestamp=_utc_now_iso(),
            )
            return

        phases_dict, duration_minutes = self._phase_minutes_from_segments(
            sleep_resp.phases,
            fallback_duration_minutes=sleep_resp.durationMinutes,
        )
        sleep_date, start_time, end_time = self._compute_sleep_window(duration_minutes)

        payload = {
            "db_device_id": bound_db_device_id,
            "user_id": resolved_user_id,
            "date": sleep_date.isoformat(),
            "score": sleep_resp.score,
            "efficiency": sleep_resp.efficiency,
            "duration_minutes": duration_minutes,
            "phases": phases_dict,
            "start_time": start_time.isoformat().replace("+00:00", "Z"),
            "end_time": end_time.isoformat().replace("+00:00", "Z"),
        }
        endpoint = f"{self._health_backend_url}/mobile/telemetry/sleep"
        try:
            # CRITICAL #2 fix: use shared httpx.Client instead of httpx.post()
            client = self._get_http_client()
            resp = client.post(
                endpoint,
                content=_json.dumps(payload).encode("utf-8"),
                headers=self._build_internal_headers(),
            )
            code = resp.status_code
            self._publish_device_log(
                sim_device_id,
                level="INFO",
                message=f"Sleep push OK: HTTP {code} | date={sleep_date.isoformat()} | duration={duration_minutes}min",
                timestamp=_utc_now_iso(),
            )
        except Exception as exc:
            self._publish_device_log(
                sim_device_id,
                level="ERROR",
                message=f"Sleep push failed: {exc}",
                timestamp=_utc_now_iso(),
            )

    def _sleep_session_exists(
        self,
        *,
        db_device_id: int,
        user_id: int,
        target_date: date,
    ) -> bool:
        """Check if a sleep session already exists for the given date.

        Raises SQLAlchemyError on DB failure instead of silently returning False
        (IS-003 fix — prevent double-write on transient DB error).
        """
        with session_scope() as db:
            result = db.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM sleep_sessions
                        WHERE user_id = :user_id
                          AND device_id = :device_id
                          AND sleep_date = CAST(:sleep_date AS DATE)
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "device_id": db_device_id,
                    "sleep_date": target_date.isoformat(),
                },
            ).scalar()
        return bool(result)

    def _post_sleep_payload(self, *, payload: dict[str, Any], device_id: str) -> tuple[bool, int]:
        endpoint = f"{self._health_backend_url}/mobile/telemetry/sleep"
        # CRITICAL #2 fix: use shared httpx.Client instead of httpx.post()
        client = self._get_http_client()
        resp = client.post(
            endpoint,
            content=_json.dumps(payload).encode("utf-8"),
            headers=self._build_internal_headers(),
        )
        code = resp.status_code
        raw_body = resp.text.strip()
        if raw_body:
            try:
                body = _json.loads(raw_body)
            except ValueError:
                body = None
            if isinstance(body, dict):
                errors = body.get("errors")
                if isinstance(errors, list) and errors:
                    raise RuntimeError(f"Backend sleep ingest errors: {'; '.join(str(item) for item in errors)}")
                ingested = body.get("ingested")
                if ingested is not None:
                    try:
                        if int(ingested) <= 0:
                            raise RuntimeError("Backend sleep ingest reported 0 rows written")
                    except (TypeError, ValueError):
                        raise RuntimeError(f"Backend sleep ingest returned invalid ingested value: {ingested!r}")
        return 200 <= code < 300, code

    @staticmethod
    def _resolve_bound_device_user_id(db_device_id: int) -> int | None:
        try:
            with session_scope() as db:
                value = db.execute(
                    text(
                        """
                        SELECT user_id
                        FROM devices
                        WHERE id = :device_id
                          AND deleted_at IS NULL
                        LIMIT 1
                        """
                    ),
                    {"device_id": db_device_id},
                ).scalar()
        except Exception:
            logger.warning("Failed to resolve user_id for db_device_id=%s", db_device_id, exc_info=True)
            return None
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # DB history
    # ------------------------------------------------------------------

    def sleep_db_history(self, device_id: str, days: int = 30) -> list[DbSleepHistoryRow]:
        with self._lock:
            device = self._require_device(device_id)
            bound_db_device_id = device.bound_db_device_id

        if bound_db_device_id is None:
            return []

        cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)
        try:
            with session_scope() as db:
                rows = db.execute(
                    text(
                        """
                        SELECT
                            sleep_date,
                            start_time,
                            end_time,
                            sleep_score,
                            phases,
                            wake_count
                        FROM sleep_sessions
                        WHERE device_id = :device_id
                          AND sleep_date >= CAST(:cutoff_date AS DATE)
                        ORDER BY sleep_date DESC
                        LIMIT 90
                        """
                    ),
                    {
                        "device_id": bound_db_device_id,
                        "cutoff_date": cutoff_date.isoformat(),
                    },
                ).fetchall()
        except Exception:
            logger.warning("Failed to fetch sleep history from DB for db_device_id=%s", bound_db_device_id, exc_info=True)
            return []

        records: list[DbSleepHistoryRow] = []
        for row in rows:
            phases = self._coerce_phase_minutes_dict(getattr(row, "phases", None))
            fallback_duration = sum(phases.values())
            start_time = self._coerce_datetime_value(getattr(row, "start_time", None))
            end_time = self._coerce_datetime_value(getattr(row, "end_time", None))
            duration_minutes = fallback_duration
            if start_time is not None and end_time is not None:
                duration_minutes = max(0, int(round((end_time - start_time).total_seconds() / 60)))
            if duration_minutes <= 0:
                duration_minutes = fallback_duration

            awake_minutes = max(0, phases.get("awake", 0))
            asleep_minutes = max(0, duration_minutes - awake_minutes)
            efficiency = round((asleep_minutes / duration_minutes) * 100, 1) if duration_minutes > 0 else 0.0

            try:
                wake_count = int(getattr(row, "wake_count", 0) or 0)
            except (TypeError, ValueError):
                wake_count = 0
            if wake_count <= 0 and awake_minutes > 0:
                wake_count = max(1, awake_minutes // 30)

            sleep_date = _coerce_date(getattr(row, "sleep_date", None))
            if sleep_date is None and start_time is not None:
                sleep_date = start_time.date()
            if sleep_date is None:
                sleep_date = datetime.now(timezone.utc).date()

            try:
                score = int(getattr(row, "sleep_score", 0) or 0)
            except (TypeError, ValueError):
                score = 0

            records.append(
                DbSleepHistoryRow(
                    date=sleep_date.isoformat(),
                    score=score,
                    efficiency=efficiency,
                    durationMinutes=duration_minutes,
                    wakeCount=wake_count,
                    phases=phases,
                    startTime=self._datetime_to_iso(start_time),
                    endTime=self._datetime_to_iso(end_time),
                )
            )

        return records

    # ------------------------------------------------------------------
    # Session construction
    # ------------------------------------------------------------------

    def _build_scenario_phase_segments(
        self,
        *,
        raw: dict[str, Any],
        summary: dict[str, Any],
        phases_pattern_override: list[str] | None,
    ) -> list[SleepStageSegment]:
        total_sleep_s = int(summary.get("total_sleep_s") or 0)
        total_duration_minutes = max(1, int(round(total_sleep_s / 60))) if total_sleep_s > 0 else 360
        stage_proportions = self._normalize_stage_proportions(summary.get("stage_proportions"))
        ordered_stages = ["awake", "light", "deep", "rem"]
        stage_minutes: dict[str, int] = {}
        remaining_minutes = total_duration_minutes
        for stage in ordered_stages[:-1]:
            minutes = int(round(stage_proportions.get(stage, 0.0) * total_duration_minutes))
            minutes = max(0, min(remaining_minutes, minutes))
            stage_minutes[stage] = minutes
            remaining_minutes -= minutes
        stage_minutes[ordered_stages[-1]] = max(0, remaining_minutes)

        pattern = [stage for stage in (phases_pattern_override or ordered_stages) if stage_minutes.get(stage, 0) > 0]
        if not pattern:
            pattern = [stage for stage in ordered_stages if stage_minutes.get(stage, 0) > 0]
        if not pattern:
            pattern = ["light"]
            stage_minutes["light"] = total_duration_minutes

        occurrences = {stage: pattern.count(stage) for stage in set(pattern)}
        split_map: dict[str, list[int]] = {
            stage: self._split_minutes(stage_minutes.get(stage, 0), count)
            for stage, count in occurrences.items()
        }
        split_index = {stage: 0 for stage in occurrences}

        recording_start = str(raw.get("recording_start") or _utc_now_iso())
        try:
            current = datetime.fromisoformat(recording_start.replace("Z", "+00:00"))
        except ValueError:
            current = datetime.now(timezone.utc).replace(hour=22, minute=0, second=0, microsecond=0)

        segments: list[SleepStageSegment] = []
        for stage in pattern:
            minutes_list = split_map.get(stage) or []
            idx = split_index.get(stage, 0)
            if idx >= len(minutes_list):
                continue
            minutes = minutes_list[idx]
            split_index[stage] = idx + 1
            if minutes <= 0:
                continue
            start = current
            end = current + timedelta(minutes=minutes)
            segments.append(
                SleepStageSegment(
                    stage=stage,  # type: ignore[arg-type]
                    start=start.isoformat().replace("+00:00", "Z"),
                    end=end.isoformat().replace("+00:00", "Z"),
                )
            )
            current = end
        return segments

    def _select_session_for_scenario(self, scenario_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        profile = self._scenario_profiles.get(scenario_id, self._scenario_profiles.get("good_sleep_night", {}))
        pool = list(getattr(self.registry, "_sleep_sessions", []) or [])
        if not pool:
            return {}, {
                "scenario_id": scenario_id,
                "summary": self._apply_sleep_summary_override({}, profile.get("stats_override")),
                "use_summary_override": profile.get("stats_override") is not None,
                "disorder_tags": list(profile.get("disorder_tags", [])),
                "spo2_min_override": (profile.get("stats_override") or {}).get("spo2_min_override"),
                "phases_pattern_override": profile.get("phases_pattern_override"),
                "description": str(profile.get("description") or ""),
            }

        filter_fn = profile.get("filter")
        filtered = pool
        if callable(filter_fn):
            filtered = []
            for session in pool:
                try:
                    if filter_fn(session):
                        filtered.append(session)
                except Exception:
                    logger.warning("Sleep session filter_fn raised for session, skipping", exc_info=True)
                    continue
            if not filtered:
                filtered = pool

        raw = _random.choice(filtered)
        summary = self._apply_sleep_summary_override(raw.get("summary") or {}, profile.get("stats_override"))
        return raw, {
            "scenario_id": scenario_id,
            "summary": summary,
            "use_summary_override": profile.get("stats_override") is not None,
            "disorder_tags": list(profile.get("disorder_tags", [])),
            "spo2_min_override": (profile.get("stats_override") or {}).get("spo2_min_override"),
            "phases_pattern_override": profile.get("phases_pattern_override"),
            "description": str(profile.get("description") or ""),
        }

    def _sleep_stage_segments_from_raw(self, raw: dict[str, Any]) -> list[SleepStageSegment]:
        phases_raw_obj = raw.get("phases")
        if phases_raw_obj is None:
            phases_raw: list[Any] = []
        elif isinstance(phases_raw_obj, list):
            phases_raw = phases_raw_obj
        elif isinstance(phases_raw_obj, tuple):
            phases_raw = list(phases_raw_obj)
        elif hasattr(phases_raw_obj, "tolist"):
            converted = phases_raw_obj.tolist()
            phases_raw = converted if isinstance(converted, list) else [converted]
        else:
            phases_raw = [phases_raw_obj]
        segments: list[SleepStageSegment] = []
        for item in phases_raw:
            if not isinstance(item, dict):
                continue
            stage = str(item.get("stage") or "")
            start = item.get("start")
            end = item.get("end")
            if stage not in {"deep", "light", "rem", "awake"}:
                continue
            if not start or not end:
                continue
            segments.append(SleepStageSegment(stage=stage, start=str(start), end=str(end)))  # type: ignore[arg-type]
        return segments

    def _sleep_history_from_registry(self, limit: int = 7) -> list[SleepHistoryRow]:
        if not self.registry.has_sleep_sessions():
            return []

        all_sessions = list(getattr(self.registry, "_sleep_sessions", []) or [])
        if not all_sessions:
            return []

        import hashlib as _hashlib

        sample_size = min(max(1, limit * 2), len(all_sessions))
        sampled = _random.sample(all_sessions, sample_size)

        seen_dates: set[str] = set()
        rows: list[SleepHistoryRow] = []
        today = datetime.now(timezone.utc).date()
        for raw in sampled:
            summary = raw.get("summary") or {}
            session_hash = int(_hashlib.sha256(str(raw).encode("utf-8")).hexdigest()[:8], 16)
            date_value = (today - timedelta(days=(session_hash % 30) + 1)).isoformat()
            if date_value in seen_dates:
                continue
            seen_dates.add(date_value)
            efficiency_raw = _safe_float(summary.get("sleep_efficiency"), 0.0)
            efficiency = round(efficiency_raw * 100, 1) if efficiency_raw <= 1 else round(efficiency_raw, 1)
            total_sleep_s = int(summary.get("total_sleep_s") or 0)
            duration_minutes = max(1, int(round(total_sleep_s / 60)))
            stage_proportions = summary.get("stage_proportions") or {}
            deep_ratio = _safe_float(stage_proportions.get("deep"), 0.0)
            wake_count = int(summary.get("wake_count") or 0)
            rows.append(
                SleepHistoryRow(
                    date=date_value,
                    score=self._calc_sleep_score(raw),
                    efficiency=efficiency,
                    durationMinutes=duration_minutes,
                    avgHeartRate=round(max(48.0, min(78.0, 62.0 - deep_ratio * 9.0 + wake_count * 0.4)), 1),
                    minSpo2=round(max(90.0, min(99.0, 96.0 - wake_count * 0.25)), 1),
                )
            )
            if len(rows) >= limit:
                break
        rows.sort(key=lambda item: item.date)
        return rows[-limit:]

    def _fallback_sleep_session(self, device_id: str) -> SleepSessionResponse:
        today = datetime.now(timezone.utc).date()
        phases = self._build_sleep_segments(today)
        history = self._build_sleep_history(device_id=device_id, anchor_date=today)
        duration_minutes = sum(self._segment_minutes(segment.start, segment.end) for segment in phases)
        return SleepSessionResponse(
            deviceId=device_id,
            date=today.isoformat(),
            realismMode="fallback",
            score=84,
            efficiency=92.6,
            durationMinutes=duration_minutes,
            avgHeartRate=58.0,
            minSpo2=95.0,
            phases=phases,
            history=history,
            banner="Sleep Realism Mode: Fallback pattern (Phase 5A). Tai Sleep-EDF de nang cap.",
        )

    def _real_sleep_session_from_registry(
        self,
        *,
        device_id: str,
        raw: dict[str, Any],
        summary_override: dict[str, Any] | None = None,
        phases_pattern_override: list[str] | None = None,
        disorder_tags: list[str] | None = None,
        min_spo2_override: float | None = None,
        scenario_id: str | None = None,
        description: str | None = None,
    ) -> SleepSessionResponse:
        summary = dict(summary_override or raw.get("summary") or {})
        phases = (
            self._build_scenario_phase_segments(
                raw=raw,
                summary=summary,
                phases_pattern_override=phases_pattern_override,
            )
            if summary_override is not None or phases_pattern_override is not None
            else self._sleep_stage_segments_from_raw(raw)
        )
        recording_start = str(raw.get("recording_start") or _utc_now_iso())
        date_value = recording_start.split("T")[0]
        efficiency_raw = _safe_float(summary.get("sleep_efficiency"), 0.0)
        efficiency = round(efficiency_raw * 100, 1) if efficiency_raw <= 1 else round(efficiency_raw, 1)
        total_sleep_s = int(summary.get("total_sleep_s") or 0)
        duration_minutes = max(1, int(round(total_sleep_s / 60)))
        wake_count = int(summary.get("wake_count") or 0)
        stage_proportions = summary.get("stage_proportions") or {}
        deep_ratio = _safe_float(stage_proportions.get("deep"), 0.0)
        avg_heart_rate = round(max(48.0, min(78.0, 62.0 - deep_ratio * 9.0 + wake_count * 0.4)), 1)
        min_spo2 = (
            round(float(min_spo2_override), 1)
            if min_spo2_override is not None
            else round(max(90.0, min(99.0, 96.0 - wake_count * 0.25)), 1)
        )
        history = self._sleep_history_from_registry()
        effective_raw = dict(raw)
        effective_raw["summary"] = summary
        score = self._calc_sleep_score(effective_raw)
        banner = "Sleep Realism Mode: Real Sleep-EDF session."
        if scenario_id is not None:
            tag_suffix = ", ".join(disorder_tags or [])
            banner = f"Sleep Realism Mode: Scenario {scenario_id}."
            if description:
                banner = f"{banner} {description}"
            if tag_suffix:
                banner = f"{banner} Tags: {tag_suffix}."

        return SleepSessionResponse(
            deviceId=device_id,
            date=date_value,
            realismMode="real",
            score=score,
            efficiency=efficiency,
            durationMinutes=duration_minutes,
            avgHeartRate=avg_heart_rate,
            minSpo2=min_spo2,
            phases=phases,
            history=history,
            banner=banner,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def _build_sleep_session_locked(self, device_id: str) -> SleepSessionResponse:
        self._require_device(device_id)
        if self.registry.has_sleep_sessions():
            raw = self.registry.sample_sleep_session()
            return self._real_sleep_session_from_registry(device_id=device_id, raw=raw)
        return self._fallback_sleep_session(device_id=device_id)

    def _build_sleep_session_for_scenario_locked(
        self,
        device_id: str,
        scenario_id: str,
    ) -> SleepSessionResponse:
        self._require_device(device_id)
        if not self.registry.has_sleep_sessions():
            return self._fallback_sleep_session(device_id=device_id)

        raw, effective = self._select_session_for_scenario(scenario_id)
        return self._real_sleep_session_from_registry(
            device_id=device_id,
            raw=raw,
            summary_override=effective.get("summary") if effective.get("use_summary_override") else None,
            phases_pattern_override=effective.get("phases_pattern_override"),
            disorder_tags=effective.get("disorder_tags"),
            min_spo2_override=effective.get("spo2_min_override"),
            scenario_id=scenario_id,
            description=effective.get("description"),
        )

    def sleep_session(self, device_id: str) -> SleepSessionResponse:
        with self._lock:
            return self._build_sleep_session_locked(device_id)

    def push_sleep_session(self, device_id: str) -> SleepSessionResponse:
        with self._lock:
            result = self._build_sleep_session_locked(device_id)
        self._push_sleep_to_backend(sim_device_id=device_id, sleep_resp=result)
        return result

    def push_sleep_session_for_date(
        self,
        device_id: str,
        target_date: date,
        scenario_id: str = "good_sleep_night",
    ) -> dict[str, Any]:
        with self._lock:
            self._require_device(device_id)
            device = self.devices.get(device_id)
            bound_db_device_id = device.bound_db_device_id if device is not None else None
            has_registry_sessions = self.registry.has_sleep_sessions()
            if has_registry_sessions:
                raw, effective = self._select_session_for_scenario(scenario_id)
            else:
                raw, effective = {}, {
                    "summary": {},
                    "disorder_tags": [],
                    "spo2_min_override": None,
                    "phases_pattern_override": None,
                    "use_summary_override": False,
                    "description": "",
                }

        if bound_db_device_id is None:
            return {
                "success": False,
                "target_date": target_date.isoformat(),
                "scenario_id": scenario_id,
                "duration_minutes": 0,
                "sleep_score": 0,
                "disorder_tags": [],
                "was_overwritten": False,
                "message": "Device not bound",
            }
        user_id = self._resolve_bound_device_user_id(bound_db_device_id)
        if user_id is None:
            return {
                "success": False,
                "target_date": target_date.isoformat(),
                "scenario_id": scenario_id,
                "duration_minutes": 0,
                "sleep_score": 0,
                "disorder_tags": [],
                "was_overwritten": False,
                "message": f"No owner found for db_device_id={bound_db_device_id}",
            }

        if has_registry_sessions:
            summary = dict(effective.get("summary") or raw.get("summary") or {})
            phases = (
                self._build_scenario_phase_segments(
                    raw=raw,
                    summary=summary,
                    phases_pattern_override=effective.get("phases_pattern_override"),
                )
                if effective.get("use_summary_override") or effective.get("phases_pattern_override") is not None
                else self._sleep_stage_segments_from_raw(raw)
            )
            fallback_duration_minutes = int(summary.get("total_sleep_s") or 0) // 60 or 360
            phases_dict, duration_minutes = self._phase_minutes_from_segments(
                phases,
                fallback_duration_minutes=fallback_duration_minutes,
            )
            sleep_efficiency = _safe_float(summary.get("sleep_efficiency"), 0.85) or 0.85
            efficiency_pct = round(sleep_efficiency * 100 if sleep_efficiency <= 1 else sleep_efficiency, 1)
            disorder_tags = list(effective.get("disorder_tags") or [])
        else:
            fallback = self._fallback_sleep_session(device_id=device_id)
            phases_dict, duration_minutes = self._phase_minutes_from_segments(
                fallback.phases,
                fallback_duration_minutes=fallback.durationMinutes,
            )
            sleep_score = int(fallback.score)
            efficiency_pct = float(fallback.efficiency)
            disorder_tags = []

        was_overwritten = self._sleep_session_exists(
            db_device_id=bound_db_device_id,
            user_id=user_id,
            target_date=target_date,
        )
        sleep_date, start_time, end_time = self._compute_sleep_window_for_date(target_date, duration_minutes)
        persona_config = dict(device.persona_config or {}) if device is not None else {}
        sleep_ai_record: dict[str, Any] | None = None
        if has_registry_sessions:
            sleep_ai_record = self._build_sleep_ai_record(
                scenario_id=scenario_id,
                summary=summary,
                phases_dict=phases_dict,
                duration_minutes=duration_minutes,
                sleep_date=sleep_date,
                start_time=start_time,
                end_time=end_time,
                user_id=user_id,
                persona_config=persona_config,
            )
            sleep_score = self._compute_sleep_score_with_ai(sleep_ai_record)
        score_source = self._last_sleep_score_source

        payload = {
            "db_device_id": bound_db_device_id,
            "user_id": user_id,
            "date": sleep_date.isoformat(),
            "score": sleep_score,
            "efficiency": efficiency_pct,
            "duration_minutes": duration_minutes,
            "phases": phases_dict,
            "start_time": start_time.isoformat().replace("+00:00", "Z"),
            "end_time": end_time.isoformat().replace("+00:00", "Z"),
            "heart_rate_mean_bpm": (sleep_ai_record or {}).get("heart_rate_mean_bpm"),
            "heart_rate_min_bpm": (sleep_ai_record or {}).get("heart_rate_min_bpm"),
            "heart_rate_max_bpm": (sleep_ai_record or {}).get("heart_rate_max_bpm"),
            "hrv_rmssd_ms": (sleep_ai_record or {}).get("hrv_rmssd_ms"),
            "respiration_rate_bpm": (sleep_ai_record or {}).get("respiration_rate_bpm"),
            "spo2_mean_pct": (sleep_ai_record or {}).get("spo2_mean_pct"),
            "spo2_min_pct": (sleep_ai_record or {}).get("spo2_min_pct"),
            "movement_count": (sleep_ai_record or {}).get("movement_count"),
            "snore_events": (sleep_ai_record or {}).get("snore_events"),
        }

        try:
            ok, status_code = self._post_sleep_payload(
                payload=payload,
                device_id=device_id,
            )
            self._publish_device_log(
                device_id,
                level="INFO",
                message=(
                    f"Sleep backfill push OK: HTTP {status_code} | date={target_date.isoformat()} "
                    f"| duration={duration_minutes}min | scenario={scenario_id} | score_source={score_source}"
                ),
                timestamp=_utc_now_iso(),
            )
            return {
                "success": ok,
                "target_date": target_date.isoformat(),
                "scenario_id": scenario_id,
                "duration_minutes": duration_minutes,
                "sleep_score": sleep_score,
                "disorder_tags": disorder_tags,
                "was_overwritten": was_overwritten,
                "message": "Updated" if was_overwritten else "Created",
            }
        except Exception as exc:
            self._publish_device_log(
                device_id,
                level="ERROR",
                message=(
                    f"Sleep backfill push failed: {exc} | date={target_date.isoformat()} "
                    f"| scenario={scenario_id}"
                ),
                timestamp=_utc_now_iso(),
            )
            return {
                "success": False,
                "target_date": target_date.isoformat(),
                "scenario_id": scenario_id,
                "duration_minutes": duration_minutes,
                "sleep_score": sleep_score,
                "disorder_tags": disorder_tags,
                "was_overwritten": was_overwritten,
                "message": f"Failed: {type(exc).__name__}: {exc}",
            }

    # ------------------------------------------------------------------
    # Sleep phase advancement (called from tick loop)
    # ------------------------------------------------------------------

    def _get_device_engine(self, device_id: str) -> Any | None:
        for session in self.sessions.values():
            if session.status != "running" or device_id not in session.device_ids:
                continue
            for device in session.simulator.devices:
                if device.device_id == device_id:
                    return device.engine
        return None

    def _advance_sleep_phase_if_due(self, device_id: str) -> None:
        scenario_id = self.device_scenarios.get(device_id)
        if scenario_id not in self._scenario_phases:
            self._sleep_phase_tracker.pop(device_id, None)
            return

        engine = self._get_device_engine(device_id)
        if engine is None or engine.state.activity_state != "sleeping":
            self._sleep_phase_tracker.pop(device_id, None)
            return

        schedule = self._scenario_phases[scenario_id]
        now = monotonic()

        if device_id not in self._sleep_phase_tracker:
            self._sleep_phase_tracker[device_id] = (0, now)

        phase_idx, phase_started_at = self._sleep_phase_tracker[device_id]
        if phase_idx >= len(schedule):
            engine.inject_event("sleep_end", None)
            self._sleep_phase_tracker.pop(device_id, None)
            return

        _, phase_duration_minutes = schedule[phase_idx]
        elapsed_seconds = now - phase_started_at
        phase_duration_seconds = phase_duration_minutes * 60
        try:
            speed_factor = float(os.environ.get("SIM_SLEEP_SPEED_FACTOR", "60"))
        except (TypeError, ValueError):
            speed_factor = 60.0
        if speed_factor <= 0:
            speed_factor = 60.0
        phase_duration_sim_seconds = phase_duration_seconds / speed_factor
        if elapsed_seconds < phase_duration_sim_seconds:
            return

        next_idx = phase_idx + 1
        if next_idx >= len(schedule):
            engine.inject_event("sleep_end", None)
            self._sleep_phase_tracker.pop(device_id, None)
            return

        current_phase, _ = schedule[phase_idx]
        next_phase, _ = schedule[next_idx]
        engine.inject_event("sleep_phase_change", next_phase)
        self._sleep_phase_tracker[device_id] = (next_idx, now)
        self._publish_device_log(
            device_id,
            level="DEBUG",
            message=f"Sleep phase advanced: {current_phase} -> {next_phase}",
            timestamp=_utc_now_iso(),
        )
