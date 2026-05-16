"""Module FA — focused unit tests for the fall AI integration.

These tests cover the new code paths the Fall Lab redesign added:

  1. ``simulator_core.fall_ai_client.motion_window_to_samples`` —
     column-array motion window → list of model-API samples.
  2. ``simulator_core.fall_ai_client.normalise_verdict`` — projection of
     the model-api response into the FE-friendly verdict shape.
  3. ``SimulatorRuntime._resolve_fall_variant_policy`` — variant strings
     map to the right ``_FallVariantPolicy`` + persona variant.
  4. ``SimulatorRuntime.inject_event`` — variant policy is applied to
     ``device.state`` and the AI verdict is cached for the FE.
  5. ``SimulatorRuntime.fall_state`` — surfaces the AI verdict +
     variant-aware countdown total, not the legacy 30 s constant.
  6. Tick-loop dedupe — operator-injected falls don't duplicate the
     ``fall_detected`` event when the persona engine maintains
     ``activity_state == "fall"`` across subsequent ticks.

The tests bypass the mobile backend by monkey-patching the runtime's
``_mobile_telemetry_client`` with a stub that returns deterministic
``ImuWindowResponse``-shaped verdicts (ADR-019 Phase 7 S9). The legacy
alias ``_stub_ai_client`` is retained so existing call sites keep
compiling; new tests should use ``_stub_mobile_telemetry_client``.
Keeps the suite hermetic — no network, no model server, no backend.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from api_server.dependencies import (
    DeviceRecord,
    SessionRecord,
    SimulatorRuntime,
    _FALL_VARIANT_POLICIES,
    _FALL_VARIANT_TO_PERSONA,
)
from simulator_core.fall_ai_client import (
    MIN_WINDOW_SAMPLES,
    motion_window_to_samples,
    normalise_verdict,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_motion_window(
    *,
    sample_count: int = MIN_WINDOW_SAMPLES,
    accel_value: float = 9.81,
    fall_variant: str | None = None,
) -> dict[str, Any]:
    """Build a column-array motion window in the simulator's tick shape."""
    return {
        "sample_rate": 50.0,
        "fall_variant": fall_variant,
        "accel_x": [0.0] * sample_count,
        "accel_y": [0.0] * sample_count,
        "accel_z": [accel_value] * sample_count,
        "accel_mag": [accel_value] * sample_count,
        "gyro_x": [0.0] * sample_count,
        "gyro_y": [0.0] * sample_count,
        "gyro_z": [0.0] * sample_count,
    }


def _stub_mobile_telemetry_client(verdict: dict[str, Any] | None) -> MagicMock:
    """Return a MagicMock that mimics ``MobileTelemetryClient.submit_imu_window``.

    ADR-019 Phase 7 S9: the runtime stopped calling the model-api
    directly and instead posts the IMU window to the mobile BE
    (``POST /api/v1/mobile/telemetry/imu-window``). Tests still
    parametrise on the **legacy model-api raw verdict shape** for
    readability, so this helper projects that into the BE compact
    ``ImuWindowResponse`` shape the runtime now expects:

    * ``predicted_fall_probability`` → ``fall_probability``
    * ``prediction.prediction_label`` (or ``risk_level``) → ``prediction_band``
    * ``predicted_fall`` (or derived from band) → ``predicted_fall``
    * ``requires_attention`` → ``requires_attention``
    * Always populates ``fall_event_id`` so back-link assertions work.

    Passing ``verdict=None`` simulates a transport / breaker failure —
    the client returns ``None`` (its public failure signal).
    """
    client = MagicMock()
    client.base_url = "http://stub:8000"

    if verdict is None:
        client.submit_imu_window.return_value = None
    else:
        risk_level = str(verdict.get("risk_level") or "normal").strip().lower()
        prediction_block = verdict.get("prediction") or {}
        prediction_band = str(
            prediction_block.get("prediction_label")
            or risk_level
            or "normal"
        ).strip().lower()
        probability = float(verdict.get("predicted_fall_probability") or 0.0)
        predicted_fall = bool(
            verdict.get("predicted_fall")
            or risk_level in {"critical", "warning"}
            or prediction_band in {"critical_fall", "likely_fall", "possible_fall"}
        )
        client.submit_imu_window.return_value = {
            "status": "ok",
            "fall_event_id": 12345,
            "fall_probability": probability,
            "prediction_band": prediction_band,
            "predicted_fall": predicted_fall,
            "requires_attention": bool(verdict.get("requires_attention", False)),
            "model_request_id": str(verdict.get("model_request_id") or "stub-request-id"),
        }

    return client


# ADR-019 Phase 7 S9: legacy alias kept so any tests referencing the
# old factory name (``_stub_ai_client``) keep working. New tests should
# call ``_stub_mobile_telemetry_client`` directly.
_stub_ai_client = _stub_mobile_telemetry_client


def _build_runtime_with_session(
    *,
    motion: dict[str, Any] | None = None,
    ai_verdict: dict[str, Any] | None = None,
) -> tuple[SimulatorRuntime, SessionRecord, str]:
    """Build a runtime with one device + one running session.

    The session's ``simulator.tick()`` returns a single payload that has
    the supplied motion window so the runtime's AI call has fresh data
    to pass into the (stubbed) telemetry client.

    ADR-019 Phase 7 S9: ``bound_db_device_id`` is now required on the
    device — ``_call_fall_ai_locked`` skips the dispatch (returns
    ``modelStatus=skipped``) when the simulator device isn't bound to
    a backend ``devices`` row. Tests set a deterministic id (42) so
    the dispatch path is always exercised.
    """
    runtime = SimulatorRuntime()
    runtime._mobile_telemetry_client = _stub_mobile_telemetry_client(  # type: ignore[assignment]
        ai_verdict
    )

    device_id = "device-fa-1"
    runtime.devices[device_id] = DeviceRecord(
        id=device_id,
        name="Fall AI Watch",
        serial_number="SIM-FA-1",
        mqtt_client_id="sim-fa-1",
        device_type="smartwatch",
        bound_db_device_id=42,
    )

    payload = {
        "device_id": device_id,
        "vitals": {
            "heart_rate": 80.0,
            "spo2": 97.0,
            "blood_pressure_sys": 120.0,
            "blood_pressure_dia": 78.0,
            "respiratory_rate": 16.0,
            "temperature": 36.7,
        },
        "state": {"activity_state": "fall", "fall_variant": "fall_1"},
        "motion": motion or _make_motion_window(),
        "emitted_at": "2026-01-01T00:00:00+00:00",
    }
    simulator = MagicMock()
    simulator.tick.return_value = [payload]
    simulator.devices = []
    simulator.inject_event = MagicMock()

    record = SessionRecord(
        id="session-fa-1",
        device_ids=[device_id],
        speed=1,
        simulator=simulator,
        status="running",
        source_modes={device_id: "synthetic"},
    )
    runtime.sessions[record.id] = record
    return runtime, record, device_id


# ---------------------------------------------------------------------------
# 1. motion_window_to_samples
# ---------------------------------------------------------------------------


class TestMotionWindowToSamples:
    def test_empty_window_returns_empty(self) -> None:
        assert motion_window_to_samples(None) == []
        assert motion_window_to_samples({}) == []

    def test_full_window_produces_min_samples(self) -> None:
        window = _make_motion_window(sample_count=60)
        samples = motion_window_to_samples(window)
        assert len(samples) == 60

    def test_each_sample_has_required_blocks(self) -> None:
        samples = motion_window_to_samples(_make_motion_window())
        first = samples[0]
        # Same shape the model-api expects (mirrors FallPredictionRequest).
        assert set(first.keys()) == {
            "timestamp",
            "accel",
            "gyro",
            "orientation",
            "environment",
        }
        assert set(first["accel"].keys()) == {"x", "y", "z"}
        assert set(first["gyro"].keys()) == {"x", "y", "z"}
        assert set(first["orientation"].keys()) == {"pitch", "roll", "yaw"}
        assert set(first["environment"].keys()) == {
            "floor_vibration",
            "room_occupancy",
            "pressure_mat",
        }

    def test_orientation_derived_from_gravity_vector(self) -> None:
        # Pure-Z gravity → pitch=0, roll=0 (atan2 of zeros).
        samples = motion_window_to_samples(_make_motion_window(accel_value=9.81))
        first = samples[0]
        assert first["orientation"]["pitch"] == pytest.approx(0.0, abs=1e-6)
        assert first["orientation"]["roll"] == pytest.approx(0.0, abs=1e-6)
        # Yaw stays at 0 because the simulator IMU has no magnetometer.
        assert first["orientation"]["yaw"] == 0.0

    def test_environment_defaults_to_zero(self) -> None:
        samples = motion_window_to_samples(_make_motion_window())
        for sample in samples:
            assert sample["environment"]["floor_vibration"] == 0.0
            assert sample["environment"]["room_occupancy"] == 0.0
            assert sample["environment"]["pressure_mat"] == 0.0

    def test_timestamps_are_evenly_spaced(self) -> None:
        samples = motion_window_to_samples(_make_motion_window(), sampling_rate_hz=50)
        timestamps = [sample["timestamp"] for sample in samples]
        # 50 Hz → 20 ms interval.
        for i in range(1, len(timestamps)):
            assert timestamps[i] - timestamps[i - 1] == 20

    def test_numpy_arrays_dont_trigger_truth_value_ambiguous(self) -> None:
        """Regression: motion windows from MotionGenerator are numpy arrays.

        The earlier code path used ``motion.get(key) or []`` which calls
        ``bool(arr)`` on the array; numpy raises
        ``ValueError: truth value of an array is ambiguous`` for arrays
        with more than one element.  This test feeds real numpy arrays
        through to make sure the conversion still works.
        """
        np = pytest.importorskip("numpy")
        n = MIN_WINDOW_SAMPLES
        window = {
            "sample_rate": 50.0,
            "accel_x": np.zeros(n, dtype=np.float64),
            "accel_y": np.zeros(n, dtype=np.float64),
            "accel_z": np.full(n, 9.81, dtype=np.float64),
            "gyro_x": np.zeros(n, dtype=np.float64),
            "gyro_y": np.zeros(n, dtype=np.float64),
            "gyro_z": np.zeros(n, dtype=np.float64),
        }
        # The real bug raised before reaching the loop body — so just
        # asserting the call returns N samples is sufficient.
        samples = motion_window_to_samples(window)
        assert len(samples) == n
        assert samples[0]["accel"]["z"] == pytest.approx(9.81)


# ---------------------------------------------------------------------------
# 2. normalise_verdict
# ---------------------------------------------------------------------------


class TestNormaliseVerdict:
    def test_real_api_response_shape(self) -> None:
        """Mirrors the actual ``/api/v1/fall/predict`` response shape.

        Probed live on 2026-04-30: ``top_features`` carries ``feature``
        (not ``name``) + ``impact`` (not ``contribution``) + a ``direction``
        sign hint; ``explanation`` uses ``short_text`` (not ``summary``).
        """
        raw = {
            "predicted_fall_probability": 0.87,
            "predicted_fall": True,
            "risk_level": "critical",
            "requires_attention": True,
            "high_priority_alert": True,
            "prediction": {
                "prediction_label": "critical_fall",
                "prediction_score": 0.87,
                "confidence": 0.91,
            },
            "top_features": [
                {"feature": "accel_mag_max", "impact": 0.62, "direction": "risk_up", "reason": "Đỉnh gia tốc rất cao"},
                {"feature": "floor_vibration_mean", "impact": 0.31, "direction": "risk_down", "reason": "Sàn không rung"},
            ],
            "explanation": {"short_text": "Va chạm mạnh + bất động sau đó."},
        }
        verdict = normalise_verdict(raw)
        assert verdict["label"] == "critical_fall"
        assert verdict["probability"] == pytest.approx(0.87)
        assert verdict["confidence"] == pytest.approx(0.91)
        assert verdict["riskBand"] == "critical"
        assert verdict["requiresAttention"] is True
        assert verdict["highPriorityAlert"] is True
        assert verdict["explanationSummary"] == "Va chạm mạnh + bất động sau đó."
        assert len(verdict["topFeatures"]) == 2
        # risk_up keeps the impact sign positive.
        assert verdict["topFeatures"][0]["featureName"] == "accel_mag_max"
        assert verdict["topFeatures"][0]["contribution"] == pytest.approx(0.62)
        assert verdict["topFeatures"][0]["severity"] == "critical"
        # risk_down inverts the sign so the FE shows the feature as
        # protective (negative contribution).
        assert verdict["topFeatures"][1]["featureName"] == "floor_vibration_mean"
        assert verdict["topFeatures"][1]["contribution"] == pytest.approx(-0.31)

    def test_legacy_field_names_still_work(self) -> None:
        """Backwards-compat: older API responses used name/contribution/summary."""
        raw = {
            "predicted_fall_probability": 0.5,
            "risk_level": "warning",
            "prediction": {"prediction_label": "possible_fall"},
            "top_features": [
                {"name": "gyro_mag_max", "contribution": 0.4, "reason": "Đỉnh con quay"},
            ],
            "explanation": {"summary": "Cảnh báo nhẹ."},
        }
        verdict = normalise_verdict(raw)
        assert verdict["topFeatures"][0]["featureName"] == "gyro_mag_max"
        assert verdict["topFeatures"][0]["contribution"] == pytest.approx(0.4)
        assert verdict["explanationSummary"] == "Cảnh báo nhẹ."

    def test_invalid_band_falls_back_to_normal(self) -> None:
        raw = {"predicted_fall_probability": 0.1, "risk_level": "garbage"}
        verdict = normalise_verdict(raw)
        assert verdict["riskBand"] == "normal"

    def test_invalid_label_falls_back_to_normal(self) -> None:
        raw = {"prediction": {"prediction_label": "not_a_real_label"}}
        verdict = normalise_verdict(raw)
        assert verdict["label"] == "normal"

    def test_top_features_capped_at_three(self) -> None:
        raw = {
            "top_features": [
                {"name": f"feat_{i}", "contribution": 0.5 - i * 0.05, "reason": f"reason {i}"}
                for i in range(5)
            ]
        }
        verdict = normalise_verdict(raw)
        assert len(verdict["topFeatures"]) == 3

    def test_severity_thresholds(self) -> None:
        raw = {
            "top_features": [
                {"name": "high", "contribution": 0.6, "reason": "h"},
                {"name": "mid", "contribution": 0.25, "reason": "m"},
                {"name": "low", "contribution": 0.05, "reason": "l"},
            ]
        }
        verdict = normalise_verdict(raw)
        assert verdict["topFeatures"][0]["severity"] == "critical"
        assert verdict["topFeatures"][1]["severity"] == "warning"
        assert verdict["topFeatures"][2]["severity"] == "normal"


# ---------------------------------------------------------------------------
# 3. _resolve_fall_variant_policy
# ---------------------------------------------------------------------------


class TestResolveFallVariantPolicy:
    @pytest.mark.parametrize(
        "variant,expected_countdown,expected_persona",
        [
            ("false_fall", 0, "fall_brief"),
            ("slip_recovery", 0, "fall_brief"),
            ("fall_brief", 10, "fall_brief"),
            ("fall_from_bed", 30, "fall_no_response"),
            ("confirmed", 30, "fall_1"),
            ("fall_no_response", 30, "fall_no_response"),
        ],
    )
    def test_known_variants(
        self, variant: str, expected_countdown: int, expected_persona: str
    ) -> None:
        policy, persona = SimulatorRuntime._resolve_fall_variant_policy(variant)
        assert policy.countdown_sec == expected_countdown
        assert persona == expected_persona

    def test_unknown_variant_falls_back_to_confirmed(self) -> None:
        policy, persona = SimulatorRuntime._resolve_fall_variant_policy("totally_made_up")
        # Unknown variants get the confirmed policy + fall_1 persona.
        assert policy is _FALL_VARIANT_POLICIES["confirmed"]
        assert persona == "fall_1"

    def test_none_variant_uses_confirmed(self) -> None:
        policy, persona = SimulatorRuntime._resolve_fall_variant_policy(None)
        assert policy is _FALL_VARIANT_POLICIES["confirmed"]
        assert persona == "fall_1"

    def test_false_fall_does_not_enter_countdown_state(self) -> None:
        # The variant policy table must keep "streaming" for the
        # AI-only variants — otherwise the FE renders an SOS card for
        # what should be a non-event.
        for variant in ("false_fall", "slip_recovery"):
            policy, _ = SimulatorRuntime._resolve_fall_variant_policy(variant)
            assert policy.device_state_on_inject == "streaming"
            assert policy.push_alert is False

    def test_critical_variants_push_alert(self) -> None:
        for variant in ("confirmed", "fall_no_response", "fall_from_bed"):
            policy, _ = SimulatorRuntime._resolve_fall_variant_policy(variant)
            assert policy.push_alert is True
            assert policy.device_state_on_inject == "fall_countdown"

    def test_persona_mapping_is_subset_of_variant_table(self) -> None:
        """Every variant in the policy table must have a persona mapping."""
        for variant_id in _FALL_VARIANT_POLICIES:
            assert variant_id in _FALL_VARIANT_TO_PERSONA

    def test_simulated_confidence_floors(self) -> None:
        """Variant table must declare deterministic confidence floors so the
        BE confidence gate (default 0.7) puts each variant on the expected
        branch.
        """
        # Below threshold → soft alert path (no SOS, no FCM takeover).
        assert _FALL_VARIANT_POLICIES["false_fall"].simulated_confidence < 0.7
        assert _FALL_VARIANT_POLICIES["slip_recovery"].simulated_confidence < 0.7
        assert _FALL_VARIANT_POLICIES["fall_brief"].simulated_confidence < 0.7
        # Above threshold → SOS escalation + FCM takeover.
        assert _FALL_VARIANT_POLICIES["fall_from_bed"].simulated_confidence >= 0.7
        assert _FALL_VARIANT_POLICIES["confirmed"].simulated_confidence >= 0.7
        assert _FALL_VARIANT_POLICIES["fall_no_response"].simulated_confidence >= 0.7
        # The worst-case variant should be near 1.0 to demonstrate the
        # "no operator override" path.
        assert _FALL_VARIANT_POLICIES["fall_no_response"].simulated_confidence >= 0.95


# ---------------------------------------------------------------------------
# 4b. Confidence bridge — the alert metadata sent to the HealthGuard backend
# ---------------------------------------------------------------------------


class TestConfidenceBridge:
    """Module FA-2 fix: simulator must send ``confidence`` (not just
    ``ai_probability``) so the BE confidence gate at
    ``health_system/backend/app/api/routes/telemetry.py::_fall_confidence_threshold``
    can correctly escalate to SOS for high-confidence variants.

    We patch ``SimulatorRuntime._push_alert_to_backend`` directly — that's
    the synchronous wrapper invoked from ``_run_session_side_effects``;
    bypassing it stops the call before it hits the thread-pool executor,
    keeping the test deterministic.  The real call uses kwargs:
    ``self._push_alert_to_backend(sim_device_id, event_type=..., severity=..., metadata=...)``.
    """

    @staticmethod
    def _patch_capture(runtime: SimulatorRuntime) -> list[dict[str, str]]:
        captured: list[dict[str, str]] = []

        def _capture(
            sim_device_id: str,
            *,
            event_type: str,
            severity: str,
            metadata: dict[str, str] | None = None,
        ) -> None:
            captured.append(
                {
                    "sim_device_id": sim_device_id,
                    "event_type": event_type,
                    "severity": severity,
                    **(metadata or {}),
                }
            )

        runtime._push_alert_to_backend = _capture  # type: ignore[method-assign]
        return captured

    def test_confirmed_variant_metadata_clears_be_threshold(self) -> None:
        """``confirmed`` must produce ``confidence ≥ 0.95`` regardless of AI."""
        runtime, _record, device_id = _build_runtime_with_session(ai_verdict=None)
        captured = self._patch_capture(runtime)

        runtime.inject_event(device_id, "fall_detected", "confirmed")

        fall_pushes = [c for c in captured if c["event_type"] == "fall_detected"]
        assert len(fall_pushes) == 1, captured
        meta = fall_pushes[0]
        assert "confidence" in meta, meta
        assert float(meta["confidence"]) >= 0.95
        assert float(meta["confidence"]) >= 0.7  # clears BE gate
        assert meta["variant"] == "confirmed"
        assert meta["simulated_confidence"] == "0.9500"

    def test_false_fall_metadata_stays_below_threshold(self) -> None:
        """``false_fall`` has push_alert=False so no alert is dispatched."""
        runtime, _record, device_id = _build_runtime_with_session(ai_verdict=None)
        captured = self._patch_capture(runtime)

        runtime.inject_event(device_id, "fall_detected", "false_fall")

        fall_pushes = [c for c in captured if c["event_type"] == "fall_detected"]
        # No alert → no entry captured.  The BE never even sees this fall.
        assert fall_pushes == []

    def test_ai_probability_overrides_simulated_floor_when_higher(self) -> None:
        """High AI verdict must be respected even on a low-floor variant."""
        ai_verdict = {
            "predicted_fall_probability": 0.97,
            "risk_level": "critical",
            "high_priority_alert": True,  # forces push_alert even for false_fall
            "prediction": {"prediction_label": "critical_fall", "confidence": 0.97},
            "top_features": [],
            "explanation": {"summary": "AI very confident."},
        }
        runtime, _record, device_id = _build_runtime_with_session(ai_verdict=ai_verdict)
        captured = self._patch_capture(runtime)

        # Use a variant with floor 0.10 — AI's 0.97 should win.
        runtime.inject_event(device_id, "fall_detected", "false_fall")

        fall_pushes = [c for c in captured if c["event_type"] == "fall_detected"]
        assert len(fall_pushes) == 1, captured
        meta = fall_pushes[0]
        assert float(meta["confidence"]) == pytest.approx(0.97, abs=1e-3)
        assert float(meta["confidence"]) > float(meta["simulated_confidence"])

    def test_fall_no_response_metadata_max_confidence(self) -> None:
        """Worst-case variant should always be ≥ 0.99 in metadata."""
        runtime, _record, device_id = _build_runtime_with_session(ai_verdict=None)
        captured = self._patch_capture(runtime)

        runtime.inject_event(device_id, "fall_detected", "fall_no_response")

        fall_pushes = [c for c in captured if c["event_type"] == "fall_detected"]
        assert len(fall_pushes) == 1, captured
        assert float(fall_pushes[0]["confidence"]) >= 0.99


# ---------------------------------------------------------------------------
# 4 + 5. inject_event + fall_state with AI verdict
# ---------------------------------------------------------------------------


class TestInjectEventVariantPolicy:
    def test_confirmed_variant_enters_countdown_and_caches_ai(self) -> None:
        ai_verdict = {
            "predicted_fall_probability": 0.92,
            "risk_level": "critical",
            "requires_attention": True,
            "high_priority_alert": True,
            "prediction": {"prediction_label": "critical_fall", "confidence": 0.93},
            "top_features": [{"name": "accel_mag_max", "contribution": 0.7, "reason": "Đỉnh"}],
            "explanation": {"summary": "Va chạm mạnh."},
        }
        runtime, record, device_id = _build_runtime_with_session(ai_verdict=ai_verdict)

        runtime.inject_event(device_id, "fall_detected", "confirmed")

        # Device.state should reflect the confirmed policy: fall_countdown.
        assert runtime.devices[device_id].state == "fall_countdown"
        # AI verdict cached for the FE.
        cached = runtime._fall_predictions[device_id]
        assert cached.label == "critical_fall"
        assert cached.riskBand == "critical"
        assert cached.modelStatus == "ok"
        assert cached.probability == pytest.approx(0.92)
        # Countdown policy cached + matches the variant table.
        policy = runtime._fall_countdown_policies[device_id]
        assert policy.totalSec == 30
        assert policy.allowsCancel is True
        assert policy.autoResolve is False
        # Motion window ref captured for FE alignment.
        assert runtime._fall_motion_refs[device_id].sampleCount == MIN_WINDOW_SAMPLES

    def test_false_fall_does_not_enter_countdown(self) -> None:
        ai_verdict = {
            "predicted_fall_probability": 0.04,
            "risk_level": "normal",
            "requires_attention": False,
            "high_priority_alert": False,
            "prediction": {"prediction_label": "normal", "confidence": 0.95},
            "top_features": [],
            "explanation": {"summary": "Không phải té ngã."},
        }
        runtime, record, device_id = _build_runtime_with_session(ai_verdict=ai_verdict)
        # Pre-set the device to "streaming" so we can prove inject_event
        # didn't transition it to fall_countdown.
        runtime.devices[device_id].state = "streaming"

        runtime.inject_event(device_id, "fall_detected", "false_fall")

        assert runtime.devices[device_id].state == "streaming"
        # AI verdict still cached (so the FE can show the verification).
        assert runtime._fall_predictions[device_id].riskBand == "normal"
        # Countdown policy stays at 0s (no countdown).
        assert runtime._fall_countdown_policies[device_id].totalSec == 0

    def test_event_records_only_once(self) -> None:
        runtime, record, device_id = _build_runtime_with_session(ai_verdict=None)
        runtime.inject_event(device_id, "fall_detected", "confirmed")
        # Tick the session several times to make sure the 60 s dedupe
        # window holds even when activity_state == "fall" persists
        # across subsequent ticks (FALL_DURATION_TICKS = 10).
        for _ in range(5):
            runtime._tick_session_locked(record, force=True)
        fall_events = [
            event for event in runtime.event_history if event.event_type == "fall_detected"
        ]
        assert len(fall_events) == 1, (
            "Expected exactly one fall_detected event after operator inject + N ticks; "
            f"got {len(fall_events)}: {[e.metadata.get('source') for e in fall_events]}"
        )
        # The canonical event must carry the operator-supplied variant +
        # the inject_event source marker — proves the tick loop didn't
        # win the recording race.
        canonical = fall_events[0]
        assert canonical.metadata.get("source") == "inject_event"
        assert canonical.metadata.get("variant") == "confirmed"

    def test_ai_metadata_attached_to_recorded_event(self) -> None:
        ai_verdict = {
            "predicted_fall_probability": 0.55,
            "risk_level": "warning",
            "prediction": {"prediction_label": "possible_fall", "confidence": 0.78},
            "top_features": [],
            "explanation": {"summary": "Khả năng té ngã trung bình."},
        }
        runtime, record, device_id = _build_runtime_with_session(ai_verdict=ai_verdict)
        runtime.inject_event(device_id, "fall_detected", "fall_brief")
        recorded = next(
            event
            for event in runtime.event_history
            if event.event_type == "fall_detected"
        )
        assert recorded.metadata["variant"] == "fall_brief"
        assert recorded.metadata["ai_label"] == "possible_fall"
        assert recorded.metadata["ai_band"] == "warning"
        assert recorded.metadata["ai_status"] == "ok"

    def test_sos_cancel_clears_ai_caches(self) -> None:
        ai_verdict = {
            "predicted_fall_probability": 0.92,
            "risk_level": "critical",
            "prediction": {"prediction_label": "critical_fall", "confidence": 0.93},
            "top_features": [],
            "explanation": {"summary": "Va chạm."},
        }
        runtime, record, device_id = _build_runtime_with_session(ai_verdict=ai_verdict)
        runtime.inject_event(device_id, "fall_detected", "confirmed")
        assert device_id in runtime._fall_predictions

        runtime.inject_event(device_id, "sos_cancel", None)

        assert device_id not in runtime._fall_predictions
        assert device_id not in runtime._fall_motion_refs
        assert device_id not in runtime._fall_countdown_policies
        assert runtime.devices[device_id].state == "streaming"


class TestFallStateSurfacesAI:
    def test_fall_state_returns_ai_verdict_and_policy(self) -> None:
        ai_verdict = {
            "predicted_fall_probability": 0.78,
            "risk_level": "warning",
            "prediction": {"prediction_label": "likely_fall", "confidence": 0.82},
            "top_features": [
                {"name": "accel_mag_max", "contribution": 0.45, "reason": "Đỉnh gia tốc"},
            ],
            "explanation": {"summary": "Va chạm vừa phải."},
        }
        runtime, record, device_id = _build_runtime_with_session(ai_verdict=ai_verdict)
        runtime.inject_event(device_id, "fall_detected", "fall_brief")

        state = runtime.fall_state(record.id, device_id)

        # AI verdict surfaced to FE.
        assert state.aiPrediction is not None
        assert state.aiPrediction.label == "likely_fall"
        assert state.aiPrediction.riskBand == "warning"
        # fall_brief variant uses 10 s countdown (not the legacy 30 s).
        assert state.countdownTotalSec == 10
        assert state.countdownPolicy is not None
        assert state.countdownPolicy.totalSec == 10
        assert state.countdownPolicy.autoResolve is True
        # Motion window ref present for FE alignment.
        assert state.motionWindowRef is not None
        assert state.motionWindowRef.sampleCount == MIN_WINDOW_SAMPLES

    def test_fall_state_legacy_30s_when_no_policy_cached(self) -> None:
        """Defensive: fall_state must keep working for legacy events
        recorded before the runtime started caching policies."""
        runtime, record, device_id = _build_runtime_with_session(ai_verdict=None)
        # Manually record a fall event without going through inject_event,
        # so the policy cache stays empty.
        runtime._record_event(
            device_id=device_id,
            event_type="fall_detected",
            severity="critical",
            message="legacy",
            metadata={},
        )
        runtime.devices[device_id].state = "fall_countdown"

        state = runtime.fall_state(record.id, device_id)

        # Falls back to the legacy 30 s constant.
        assert state.countdownTotalSec == int(SimulatorRuntime._SOS_COUNTDOWN_SECONDS)
        assert state.countdownPolicy is None
