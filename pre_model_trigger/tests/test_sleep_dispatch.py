"""Tests for :mod:`pre_model_trigger.sleep_dispatch`.

Covers:

* :func:`filter_to_sleep_record` — projection to the canonical
  43-field set, missing-field rejection, ``None``-as-missing
  treatment, type rejection.
* :class:`SleepRiskDispatcher.dispatch` — happy-path submit,
  validation-failure swallowing, transport-failure swallowing,
  client-exception swallowing.

The :class:`MobileTelemetryClient` is replaced with a minimal stub
so the tests focus on dispatcher behaviour, not on the (separately
tested) client.
"""

from __future__ import annotations

from typing import Any

import pytest

from pre_model_trigger.sleep_dispatch import (
    REQUIRED_SLEEP_RECORD_FIELDS,
    SLEEP_RECORD_FIELDS,
    SleepRecordValidationError,
    SleepRiskDispatcher,
    filter_to_sleep_record,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _full_record(**overrides: Any) -> dict[str, Any]:
    """Build a 41-field SleepRecord populated with neutral values.

    Tests can mutate / drop individual fields via ``overrides`` (or
    via ``del`` on the returned dict) without re-listing every
    field.
    """
    base: dict[str, Any] = {
        "user_id": "u1",
        "date_recorded": "2026-04-27",
        "sleep_start_timestamp": "2026-04-27 23:00:00",
        "sleep_end_timestamp": "2026-04-28 06:30:00",
        "duration_minutes": 450.0,
        "sleep_latency_minutes": 12.0,
        "wake_after_sleep_onset_minutes": 8.0,
        "sleep_efficiency_pct": 92.0,
        "sleep_stage_deep_pct": 18.0,
        "sleep_stage_light_pct": 55.0,
        "sleep_stage_rem_pct": 22.0,
        "sleep_stage_awake_pct": 5.0,
        "heart_rate_mean_bpm": 58.0,
        "heart_rate_min_bpm": 49.0,
        "heart_rate_max_bpm": 78.0,
        "hrv_rmssd_ms": 55.0,
        "respiration_rate_bpm": 13.5,
        "spo2_mean_pct": 96.5,
        "spo2_min_pct": 93.0,
        "movement_count": 18.0,
        "snore_events": 4.0,
        "ambient_noise_db": 32.0,
        "room_temperature_c": 22.0,
        "room_humidity_pct": 48.0,
        "step_count_day": 6800.0,
        "caffeine_mg": 80.0,
        "alcohol_units": 0.0,
        "medication_flag": 0.0,
        "jetlag_hours": 0.0,
        "timezone": "Asia/Bangkok",
        "age": 35.0,
        "gender": "female",
        "weight_kg": 60.0,
        "height_cm": 165.0,
        "device_model": "VSmartwatch Simulator",
        "bedtime_consistency_std_min": 25.0,
        "stress_score": 30.0,
        "activity_before_bed_min": 15.0,
        "screen_time_before_bed_min": 35.0,
        "insomnia_flag": 0.0,
        "apnea_risk_score": 14.0,
        "nap_duration_minutes": 0.0,
        "created_at": "2026-04-28 06:30:00",
    }
    base.update(overrides)
    return base


class _StubClient:
    """Minimal stand-in for :class:`MobileTelemetryClient`.

    Captures calls + returns a configurable response so tests can
    assert what the dispatcher passed through.
    """

    def __init__(
        self,
        *,
        return_value: dict[str, Any] | None = None,
        raise_exception: Exception | None = None,
    ) -> None:
        self._return_value = return_value
        self._raise = raise_exception
        self.calls: list[dict[str, Any]] = []

    def submit_sleep_record(
        self, *, record: dict[str, Any], db_device_id: int, db_user_id: int,
    ) -> dict[str, Any] | None:
        self.calls.append({
            "record": dict(record),
            "db_device_id": db_device_id,
            "db_user_id": db_user_id,
        })
        if self._raise is not None:
            raise self._raise
        return self._return_value


# ---------------------------------------------------------------------------
# filter_to_sleep_record
# ---------------------------------------------------------------------------


class TestSleepRecordFieldset:
    def test_canonical_field_count_is_43(self) -> None:
        # Lock the count so a future contributor adding a field has
        # to update both this test AND the model-api schema together.
        # 43 = the model-api ``SleepRecord`` Pydantic schema field
        # count (see ``healthguard-model-api/app/schemas/sleep.py``).
        assert len(SLEEP_RECORD_FIELDS) == 43

    def test_required_set_equals_canonical_set(self) -> None:
        # Currently the model-api requires every field; if that ever
        # changes we want the test to flag it explicitly.
        assert REQUIRED_SLEEP_RECORD_FIELDS == SLEEP_RECORD_FIELDS


class TestFilterToSleepRecord:
    def test_strips_extras(self) -> None:
        record = _full_record()
        record["scenario_id"] = "good_sleep_night"  # simulator extra
        record["wake_count"] = 2  # simulator extra

        projected = filter_to_sleep_record(record)

        assert "scenario_id" not in projected
        assert "wake_count" not in projected
        # All canonical fields present.
        assert set(projected) == SLEEP_RECORD_FIELDS

    def test_rejects_missing_required_field(self) -> None:
        record = _full_record()
        del record["sleep_efficiency_pct"]
        with pytest.raises(SleepRecordValidationError) as exc:
            filter_to_sleep_record(record)
        assert exc.value.missing == ["sleep_efficiency_pct"]

    def test_rejects_multiple_missing_fields_with_sorted_list(self) -> None:
        record = _full_record()
        del record["caffeine_mg"]
        del record["age"]
        del record["timezone"]
        with pytest.raises(SleepRecordValidationError) as exc:
            filter_to_sleep_record(record)
        # Must be sorted so error messages are deterministic.
        assert exc.value.missing == ["age", "caffeine_mg", "timezone"]

    def test_treats_none_value_as_missing(self) -> None:
        # The model-api's float fields can't deserialise null; the
        # filter MUST raise rather than pass null through to a 422.
        record = _full_record(spo2_mean_pct=None)
        with pytest.raises(SleepRecordValidationError) as exc:
            filter_to_sleep_record(record)
        assert "spo2_mean_pct" in exc.value.missing

    def test_rejects_non_dict_input(self) -> None:
        with pytest.raises(TypeError):
            filter_to_sleep_record("not a dict")  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            filter_to_sleep_record(None)  # type: ignore[arg-type]

    def test_does_not_mutate_input(self) -> None:
        record = _full_record()
        record["scenario_id"] = "fragmented_sleep"
        original_keys = set(record)
        filter_to_sleep_record(record)
        # Caller's dict is preserved.
        assert set(record) == original_keys

    def test_empty_string_scalar_fields_are_allowed(self) -> None:
        # Empty strings on string-typed fields pass the simulator-side
        # validator; the model-api may still 422 but that's the
        # model-api's contract to enforce, not ours.
        record = _full_record(timezone="")
        projected = filter_to_sleep_record(record)
        assert projected["timezone"] == ""


# ---------------------------------------------------------------------------
# SleepRiskDispatcher.dispatch
# ---------------------------------------------------------------------------


class TestSleepRiskDispatcherHappyPath:
    def test_passes_projected_record_to_client(self) -> None:
        client = _StubClient(
            return_value={
                "status": "persisted", "risk_score_id": 99,
                "model_request_id": "req-abc",
            },
        )
        dispatcher = SleepRiskDispatcher(client)
        record = _full_record()
        record["scenario_id"] = "fragmented_sleep"  # extra

        result = dispatcher.dispatch(
            record=record, db_device_id=7, db_user_id=11,
        )

        assert result == {
            "status": "persisted", "risk_score_id": 99,
            "model_request_id": "req-abc",
        }
        assert len(client.calls) == 1
        call = client.calls[0]
        assert call["db_device_id"] == 7
        assert call["db_user_id"] == 11
        # The extra simulator field must be stripped before submit.
        assert "scenario_id" not in call["record"]
        # All 41 canonical fields present.
        assert set(call["record"]) == SLEEP_RECORD_FIELDS


class TestSleepRiskDispatcherFailures:
    def test_validation_failure_logs_and_returns_none(self) -> None:
        client = _StubClient(return_value={"status": "persisted"})
        dispatcher = SleepRiskDispatcher(client)
        record = _full_record()
        del record["sleep_efficiency_pct"]

        result = dispatcher.dispatch(
            record=record, db_device_id=7, db_user_id=11,
        )

        # Must NOT contact the client on validation failure.
        assert result is None
        assert client.calls == []

    def test_non_dict_record_returns_none_without_calling_client(self) -> None:
        client = _StubClient()
        dispatcher = SleepRiskDispatcher(client)

        result = dispatcher.dispatch(
            record="not a dict",  # type: ignore[arg-type]
            db_device_id=7, db_user_id=11,
        )

        assert result is None
        assert client.calls == []

    def test_transport_failure_returns_none(self) -> None:
        client = _StubClient(return_value=None)  # client says transport failed
        dispatcher = SleepRiskDispatcher(client)

        result = dispatcher.dispatch(
            record=_full_record(), db_device_id=7, db_user_id=11,
        )

        assert result is None
        # Client WAS called this time — the failure happened on the
        # client's side.
        assert len(client.calls) == 1

    def test_client_exception_is_swallowed(self) -> None:
        # The MobileTelemetryClient is supposed to swallow its own
        # exceptions, but if a future bug lets one slip through, the
        # dispatcher MUST still not crash the simulator tick.
        client = _StubClient(raise_exception=ConnectionError("simulated"))
        dispatcher = SleepRiskDispatcher(client)

        result = dispatcher.dispatch(
            record=_full_record(), db_device_id=7, db_user_id=11,
        )

        assert result is None
        assert len(client.calls) == 1


class TestSleepRiskDispatcherClientProperty:
    def test_client_property_exposes_the_injected_instance(self) -> None:
        client = _StubClient()
        dispatcher = SleepRiskDispatcher(client)  # type: ignore[arg-type]
        # Lets a future caller swap in a fresh client at runtime
        # without having to recreate the dispatcher (e.g. when the
        # base_url changes after a settings refresh).
        assert dispatcher.client is client
