"""Dispatcher that submits a 43-field ``SleepRecord`` to the backend's
``/api/v1/mobile/telemetry/sleep-risk`` route.

Phase 4A-full slice 3a (see plan
``risk-core-final-completion-9ea607.md`` slice 3a). Wraps the existing
:class:`MobileTelemetryClient` (slice 2b) with three concerns:

1. **Field projection.** The simulator's existing
   ``SleepService._build_sleep_ai_record`` returns 43 keys — the 41
   model-api ``SleepRecord`` fields plus internal extras
   (``wake_count``, ``scenario_id``). The dispatcher strips the
   extras before submit so the model-api never sees fields it
   doesn't model.
2. **Required-field validation.** Any missing required field raises
   :class:`SleepRecordValidationError` *before* the network call —
   surfacing the bug at the simulator layer is far easier to debug
   than chasing an HTTP 422 from the backend through CloudWatch.
3. **Best-effort submit.** On a transport failure (the underlying
   client returns ``None``), the dispatcher logs and returns
   ``None`` — the simulator's tick loop must NOT crash because the
   backend is briefly down.

Usage::

    client = MobileTelemetryClient(base_url=..., http_sender=...)
    dispatcher = SleepRiskDispatcher(client)
    result = dispatcher.dispatch(
        record=sleep_ai_record,    # dict from _build_sleep_ai_record
        db_device_id=device.id,
        db_user_id=user.id,
    )
    if result is not None:
        # result has {risk_score_id, model_request_id, ...}
        ...
"""

from __future__ import annotations

import logging
from typing import Any

from pre_model_trigger.mobile_telemetry_client import MobileTelemetryClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical SleepRecord field list
# ---------------------------------------------------------------------------

#: The 43 fields of the model-api ``SleepRecord`` (see
#: ``healthguard-model-api/app/schemas/sleep.py``). Any key in the
#: simulator's ``_build_sleep_ai_record`` dict that is NOT in this set
#: is silently dropped by :func:`filter_to_sleep_record`.
SLEEP_RECORD_FIELDS: frozenset[str] = frozenset({
    "user_id",
    "date_recorded",
    "sleep_start_timestamp",
    "sleep_end_timestamp",
    "duration_minutes",
    "sleep_latency_minutes",
    "wake_after_sleep_onset_minutes",
    "sleep_efficiency_pct",
    "sleep_stage_deep_pct",
    "sleep_stage_light_pct",
    "sleep_stage_rem_pct",
    "sleep_stage_awake_pct",
    "heart_rate_mean_bpm",
    "heart_rate_min_bpm",
    "heart_rate_max_bpm",
    "hrv_rmssd_ms",
    "respiration_rate_bpm",
    "spo2_mean_pct",
    "spo2_min_pct",
    "movement_count",
    "snore_events",
    "ambient_noise_db",
    "room_temperature_c",
    "room_humidity_pct",
    "step_count_day",
    "caffeine_mg",
    "alcohol_units",
    "medication_flag",
    "jetlag_hours",
    "timezone",
    "age",
    "gender",
    "weight_kg",
    "height_cm",
    "device_model",
    "bedtime_consistency_std_min",
    "stress_score",
    "activity_before_bed_min",
    "screen_time_before_bed_min",
    "insomnia_flag",
    "apnea_risk_score",
    "nap_duration_minutes",
    "created_at",
})

#: Subset of :data:`SLEEP_RECORD_FIELDS` that must be present (the
#: model-api will 422 otherwise). All 41 fields are required by the
#: model-api Pydantic schema, but the simulator's existing builder
#: occasionally falls back to neutral defaults — we re-enforce
#: presence here as a safety net.
REQUIRED_SLEEP_RECORD_FIELDS: frozenset[str] = SLEEP_RECORD_FIELDS


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class SleepRecordValidationError(ValueError):
    """Raised when ``record`` is missing one or more required fields.

    Carries the missing field set on :attr:`missing` so the caller
    can log it cleanly without parsing the message string.
    """

    def __init__(self, missing: set[str]) -> None:
        self.missing = sorted(missing)
        super().__init__(
            f"SleepRecord missing required fields: {', '.join(self.missing)}"
        )


# ---------------------------------------------------------------------------
# Field projection
# ---------------------------------------------------------------------------


def filter_to_sleep_record(record: dict[str, Any]) -> dict[str, Any]:
    """Strip simulator-internal keys + validate required-field presence.

    Returns a new dict containing only keys in
    :data:`SLEEP_RECORD_FIELDS`. Raises
    :class:`SleepRecordValidationError` when any required field is
    absent (or has value ``None`` — model-api floats can't accept
    null).

    Empty-string string fields (``user_id``, ``date_recorded``,
    ``timezone``, etc.) ARE allowed at this layer — the model-api
    will reject them at request time, and double-validating here
    would couple the simulator to the model-api's exact rules.
    """
    if not isinstance(record, dict):
        raise TypeError(
            f"record must be a dict; got {type(record).__name__}"
        )
    projected = {k: record[k] for k in SLEEP_RECORD_FIELDS if k in record}
    missing = REQUIRED_SLEEP_RECORD_FIELDS - set(projected)
    # Treat explicit ``None`` as missing too — the model-api's float
    # fields can't deserialise null and would 422.
    none_keys = {k for k, v in projected.items() if v is None}
    missing = missing | none_keys
    if missing:
        raise SleepRecordValidationError(missing)
    return projected


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class SleepRiskDispatcher:
    """Submit a 43-field ``SleepRecord`` to the backend.

    Holds a reference to a :class:`MobileTelemetryClient` (slice 2b)
    so callers can inject a test stub without touching the network.

    The dispatcher is intentionally tiny — it owns the field
    projection + the call indirection + the logging contract, and
    nothing else. The simulator's ``SleepService`` continues to own
    when / how often a sleep record is built.
    """

    def __init__(self, client: MobileTelemetryClient) -> None:
        self._client = client

    @property
    def client(self) -> MobileTelemetryClient:
        return self._client

    def dispatch(
        self,
        *,
        record: dict[str, Any],
        db_device_id: int,
        db_user_id: int,
    ) -> dict[str, Any] | None:
        """Filter ``record`` to the canonical 41 fields and POST it.

        Returns the parsed response dict on success
        (e.g. ``{"status": "persisted", "risk_score_id": 123,
        "model_request_id": "..."}``), or ``None`` on:

        * Validation failure (missing required field).
        * Transport failure (``client.submit_sleep_record`` returned
          ``None``).
        * Any unexpected exception inside the client (defensive —
          the simulator's tick loop must not crash on a backend
          outage).

        Validation failures are logged at WARNING with the missing
        field names so an operator can spot the bug quickly.
        Transport failures are logged at INFO (transient, not the
        simulator's fault).
        """
        try:
            projected = filter_to_sleep_record(record)
        except SleepRecordValidationError as exc:
            logger.warning(
                "SleepRiskDispatcher rejecting record for db_device_id=%s: %s",
                db_device_id, exc,
            )
            return None
        except (TypeError, ValueError) as exc:
            logger.warning(
                "SleepRiskDispatcher could not project record for db_device_id=%s: %r",
                db_device_id, exc,
            )
            return None

        try:
            result = self._client.submit_sleep_record(
                record=projected,
                db_device_id=int(db_device_id),
                db_user_id=int(db_user_id),
            )
        except Exception as exc:  # noqa: BLE001 - client is supposed to swallow but defend anyway
            logger.warning(
                "SleepRiskDispatcher unexpected client failure for db_device_id=%s: %r",
                db_device_id, exc,
            )
            return None

        if result is None:
            logger.info(
                "SleepRiskDispatcher transport-level skip for db_device_id=%s",
                db_device_id,
            )
            return None

        logger.info(
            "SleepRiskDispatcher submitted record: db_device_id=%s db_user_id=%s status=%s",
            db_device_id, db_user_id, result.get("status"),
        )
        return result


__all__ = [
    "REQUIRED_SLEEP_RECORD_FIELDS",
    "SLEEP_RECORD_FIELDS",
    "SleepRecordValidationError",
    "SleepRiskDispatcher",
    "filter_to_sleep_record",
]
