"""ADR-019 Phase 7 S10 — sleep risk dispatcher integration tests.

These tests cover the new dispatcher-driven score path in
:meth:`SleepService._compute_sleep_score_with_ai`:

  1. Dispatcher returns ``status=ok`` with a valid ``predicted_sleep_score``
     → score is taken from the BE response and source is ``ai``.
  2. Dispatcher returns ``status=model_unavailable`` (BE breaker open
     or upstream failed) → heuristic fallback is used.
  3. Dispatcher returns ``None`` (transport / 5xx failure) → heuristic
     fallback is used.
  4. Dispatcher is ``None`` (DI omitted in legacy harness) → heuristic
     fallback is used.
  5. ``db_device_id`` / ``db_user_id`` is ``None`` → dispatcher is NOT
     called (we cannot resolve FK without these IDs); heuristic
     fallback is returned instead.
  6. Predicted score is clamped to [0, 100] to stay within the response
     contract (``risk_score`` axis is 0–100 in
     :class:`SleepRiskResponse`).
  7. ``_last_sleep_score_source`` toggles correctly between calls so the
     dashboard ``modelApi.lastScoreSource`` reflects the latest path.

The tests construct ``SleepService`` directly with the minimum DI it
needs — no ``SimulatorRuntime`` boot, no network, no DB. The dispatcher
is replaced by a :class:`MagicMock` configured per-test so we can assert
both the call shape (``record`` / ``db_device_id`` / ``db_user_id``)
and the resolved score in one go.
"""

from __future__ import annotations

from threading import RLock
from typing import Any
from unittest.mock import MagicMock

import pytest

from api_server.services.sleep_service import SleepService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sleep_record(
    *,
    sleep_efficiency_pct: float = 80.0,
    sleep_stage_deep_pct: float = 20.0,
    wake_count: int = 2,
) -> dict[str, Any]:
    """Build a minimum sleep_ai_record the heuristic fallback can consume.

    The full ``SleepRecord`` carries 40+ fields, but
    ``_compute_sleep_score_from_summary`` only inspects efficiency,
    deep-stage ratio, and wake count, so we keep the fixture small.
    """
    return {
        "sleep_efficiency_pct": sleep_efficiency_pct,
        "sleep_stage_deep_pct": sleep_stage_deep_pct,
        "wake_count": wake_count,
        # A few extra fields so the dispatcher mock receives a realistic
        # payload shape — they are not consumed by the heuristic.
        "sleep_stage_rem_pct": 22.0,
        "sleep_stage_light_pct": 50.0,
        "sleep_stage_wake_pct": 8.0,
        "heart_rate_mean_bpm": 62.0,
    }


def _make_service(dispatcher: Any | None) -> SleepService:
    """Construct a ``SleepService`` with the minimum DI for score tests.

    Only the dispatcher and the lock genuinely matter here; everything
    else is a stub so the constructor can finish without booting the
    full simulator runtime.
    """
    return SleepService(
        devices={},
        sessions={},
        device_scenarios={},
        lock=RLock(),
        registry=MagicMock(),
        sleep_ai_client=None,
        sleep_phase_tracker={},
        health_backend_url="http://test-backend",
        http_sender=MagicMock(),
        publish_device_log_fn=MagicMock(),
        require_device_fn=MagicMock(),
        internal_secret=None,
        sleep_scenario_phases={},
        sleep_scenario_profiles={},
        sleep_risk_dispatcher=dispatcher,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComputeSleepScoreWithAi:
    """Behaviour of :meth:`SleepService._compute_sleep_score_with_ai`."""

    def test_dispatcher_ok_uses_predicted_score(self) -> None:
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = {
            "status": "ok",
            "predicted_sleep_score": 78.0,
            "risk_score": 22.0,
            "risk_level": "low",
        }
        service = _make_service(dispatcher)
        record = _make_sleep_record()

        score = service._compute_sleep_score_with_ai(
            record,
            db_device_id=42,
            db_user_id=7,
        )

        assert score == 78
        assert service._last_sleep_score_source == "ai"
        dispatcher.dispatch.assert_called_once()
        kwargs = dispatcher.dispatch.call_args.kwargs
        assert kwargs["record"] is record
        assert kwargs["db_device_id"] == 42
        assert kwargs["db_user_id"] == 7

    def test_dispatcher_rounds_predicted_score(self) -> None:
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = {
            "status": "ok",
            "predicted_sleep_score": 84.6,
        }
        service = _make_service(dispatcher)

        score = service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=1,
            db_user_id=1,
        )

        assert score == 85
        assert service._last_sleep_score_source == "ai"

    @pytest.mark.parametrize(
        "predicted, expected",
        [
            (150.0, 100),  # over upper bound → clamp
            (-10.0, 0),    # under lower bound → clamp
            (0.0, 0),
            (100.0, 100),
        ],
    )
    def test_predicted_score_is_clamped(self, predicted: float, expected: int) -> None:
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = {
            "status": "ok",
            "predicted_sleep_score": predicted,
        }
        service = _make_service(dispatcher)

        score = service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=1,
            db_user_id=1,
        )

        assert score == expected
        assert service._last_sleep_score_source == "ai"

    def test_dispatcher_model_unavailable_falls_back(self) -> None:
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = {
            "status": "model_unavailable",
            "predicted_sleep_score": 0.0,
        }
        service = _make_service(dispatcher)
        record = _make_sleep_record(
            sleep_efficiency_pct=90.0,
            sleep_stage_deep_pct=25.0,
            wake_count=1,
        )

        score = service._compute_sleep_score_with_ai(
            record,
            db_device_id=1,
            db_user_id=1,
        )

        # Heuristic falls in the high-quality range for these inputs.
        assert 0 <= score <= 100
        assert service._last_sleep_score_source == "heuristic"
        dispatcher.dispatch.assert_called_once()

    def test_dispatcher_returns_none_falls_back(self) -> None:
        """Transport failure / 5xx → dispatcher returns ``None``."""
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = None
        service = _make_service(dispatcher)

        score = service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=1,
            db_user_id=1,
        )

        assert 0 <= score <= 100
        assert service._last_sleep_score_source == "heuristic"

    def test_dispatcher_missing_predicted_score_falls_back(self) -> None:
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = {
            "status": "ok",
            # ``predicted_sleep_score`` absent — should not crash, fall
            # back to heuristic instead.
        }
        service = _make_service(dispatcher)

        score = service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=1,
            db_user_id=1,
        )

        assert service._last_sleep_score_source == "heuristic"
        assert 0 <= score <= 100

    def test_dispatcher_none_falls_back_without_calling(self) -> None:
        """Legacy harness without DI → heuristic-only path."""
        service = _make_service(dispatcher=None)

        score = service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=1,
            db_user_id=1,
        )

        assert service._last_sleep_score_source == "heuristic"
        assert 0 <= score <= 100

    def test_missing_db_device_id_skips_dispatcher(self) -> None:
        """Cannot resolve FK without ``db_device_id`` → fallback path."""
        dispatcher = MagicMock()
        service = _make_service(dispatcher)

        score = service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=None,
            db_user_id=1,
        )

        dispatcher.dispatch.assert_not_called()
        assert service._last_sleep_score_source == "heuristic"
        assert 0 <= score <= 100

    def test_missing_db_user_id_skips_dispatcher(self) -> None:
        dispatcher = MagicMock()
        service = _make_service(dispatcher)

        score = service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=1,
            db_user_id=None,
        )

        dispatcher.dispatch.assert_not_called()
        assert service._last_sleep_score_source == "heuristic"

    def test_score_source_toggles_between_calls(self) -> None:
        """``_last_sleep_score_source`` reflects the most recent path.

        Dashboard ``modelApi.lastScoreSource`` reads this attribute, so
        it must update on every call rather than latch on first success.
        """
        dispatcher = MagicMock()
        service = _make_service(dispatcher)

        # 1) Dispatcher OK → "ai".
        dispatcher.dispatch.return_value = {
            "status": "ok",
            "predicted_sleep_score": 70.0,
        }
        service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=1,
            db_user_id=1,
        )
        assert service._last_sleep_score_source == "ai"

        # 2) Dispatcher reports unavailable → fallback flips to "heuristic".
        dispatcher.dispatch.return_value = {"status": "model_unavailable"}
        service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=1,
            db_user_id=1,
        )
        assert service._last_sleep_score_source == "heuristic"

        # 3) Back to OK → flips back to "ai".
        dispatcher.dispatch.return_value = {
            "status": "ok",
            "predicted_sleep_score": 65.0,
        }
        service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=1,
            db_user_id=1,
        )
        assert service._last_sleep_score_source == "ai"

    def test_dispatcher_kwargs_only_calling_convention(self) -> None:
        """The runtime calls ``dispatcher.dispatch`` with kwargs only.

        :meth:`SleepRiskDispatcher.dispatch` declares ``record``,
        ``db_device_id``, ``db_user_id`` as keyword-only — verify the
        service honours that contract so future signature changes
        won't silently regress.
        """
        dispatcher = MagicMock()
        dispatcher.dispatch.return_value = {
            "status": "ok",
            "predicted_sleep_score": 50.0,
        }
        service = _make_service(dispatcher)

        service._compute_sleep_score_with_ai(
            _make_sleep_record(),
            db_device_id=99,
            db_user_id=33,
        )

        call = dispatcher.dispatch.call_args
        assert call.args == ()
        assert set(call.kwargs.keys()) == {"record", "db_device_id", "db_user_id"}
