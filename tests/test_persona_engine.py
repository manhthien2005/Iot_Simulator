"""Tests for PersonaEngine — validates state transitions, event injection,
battery drain, and fall/recovery lifecycle logic.

Every test asserts **correctness of state machine logic**, not just that
methods execute without errors.
"""

from __future__ import annotations

import pytest

from Iot_Simulator.simulator_core.persona_engine import (
    DeviceState,
    Persona,
    PersonaEngine,
    _BATTERY_DRAIN_FACTORS,
)


# ---------------------------------------------------------------------------
# Tests: Initial state
# ---------------------------------------------------------------------------


class TestPersonaEngineInitialState:
    """Verify PersonaEngine starts in a correct default state."""

    def test_default_activity_is_resting(self, persona_engine):
        """Initial activity_state must be 'resting'."""
        assert persona_engine.state.activity_state == "resting"

    def test_default_battery_is_full(self, persona_engine):
        """Initial battery must be 100%."""
        assert persona_engine.state.battery_level == 100

    def test_default_is_online(self, persona_engine):
        """Device must start online."""
        assert persona_engine.state.is_online is True

    def test_default_no_fall(self, persona_engine):
        """No fall variant should be set initially."""
        assert persona_engine.state.fall_variant is None

    def test_default_no_stress(self, persona_engine):
        """No stress state should be set initially."""
        assert persona_engine.state.stress_state is None

    def test_default_no_sleep_phase(self, persona_engine):
        """No sleep phase should be set initially."""
        assert persona_engine.state.sleep_phase is None


# ---------------------------------------------------------------------------
# Tests: State transitions via transition_to
# ---------------------------------------------------------------------------


class TestPersonaEngineTransitions:
    """Verify state transitions work correctly."""

    def test_transition_to_walking(self, persona_engine):
        """Transition to walking should update activity_state."""
        result = persona_engine.transition_to("walking")
        assert result.activity_state == "walking"
        assert persona_engine.state.activity_state == "walking"

    def test_transition_to_running(self, persona_engine):
        """Transition to running should update activity_state."""
        persona_engine.transition_to("running")
        assert persona_engine.state.activity_state == "running"

    def test_transition_to_sleeping(self, persona_engine):
        """Transition to sleeping should update activity_state."""
        persona_engine.transition_to("sleeping")
        assert persona_engine.state.activity_state == "sleeping"

    def test_transition_resets_ticks_in_state(self, persona_engine):
        """Transitioning should reset the ticks_in_state counter."""
        # Tick a few times in resting
        for _ in range(5):
            persona_engine.tick()
        assert persona_engine._ticks_in_state == 5

        # Transition resets counter
        persona_engine.transition_to("walking")
        assert persona_engine._ticks_in_state == 0

    def test_transition_sets_stress_state(self, persona_engine):
        """Transition can optionally set stress_state."""
        persona_engine.transition_to("resting", stress_state="stress")
        assert persona_engine.state.stress_state == "stress"

    def test_transition_away_from_fall_clears_variant(self, persona_engine):
        """Transitioning away from 'fall' should clear fall_variant."""
        persona_engine.transition_to("fall")
        persona_engine.state.fall_variant = "fall_1"
        assert persona_engine.state.fall_variant == "fall_1"

        persona_engine.transition_to("recovery")
        assert persona_engine.state.fall_variant is None

    def test_transition_to_fall_keeps_variant(self, persona_engine):
        """Transition to 'fall' should NOT clear fall_variant."""
        persona_engine.transition_to("fall")
        persona_engine.state.fall_variant = "fall_confirmed"
        # Re-transition to fall (edge case)
        persona_engine.transition_to("fall")
        # fall_variant should still be set (not cleared for fall state)
        # Actually per code: if activity_state != "fall": clear variant
        # So transitioning TO fall does NOT clear it
        assert persona_engine.state.fall_variant == "fall_confirmed"


# ---------------------------------------------------------------------------
# Tests: Event injection
# ---------------------------------------------------------------------------


class TestPersonaEngineEventInjection:
    """Verify inject_event handles all event types correctly."""

    def test_fall_detected_event(self, persona_engine):
        """Injecting fall_detected should set activity to 'fall' + set variant."""
        result = persona_engine.inject_event("fall_detected", variant="fall_1")
        assert result.activity_state == "fall"
        assert result.fall_variant == "fall_1"

    def test_fall_detected_default_variant(self, persona_engine):
        """Fall without variant should use 'fall_generic'."""
        result = persona_engine.inject_event("fall_detected")
        assert result.fall_variant == "fall_generic"

    def test_sleep_start_event(self, persona_engine):
        """Injecting sleep_start should set sleeping + sleep_phase."""
        result = persona_engine.inject_event("sleep_start", variant="deep")
        assert result.activity_state == "sleeping"
        assert result.sleep_phase == "deep"

    def test_sleep_start_default_phase(self, persona_engine):
        """Sleep start without variant should default to 'light'."""
        result = persona_engine.inject_event("sleep_start")
        assert result.sleep_phase == "light"

    def test_sleep_end_event(self, persona_engine):
        """Injecting sleep_end should transition to resting + clear phase."""
        persona_engine.inject_event("sleep_start", variant="deep")
        result = persona_engine.inject_event("sleep_end")
        assert result.activity_state == "resting"
        assert result.sleep_phase is None

    def test_sleep_phase_change_during_sleep(self, persona_engine):
        """Sleep phase change only works when already sleeping."""
        persona_engine.inject_event("sleep_start", variant="light")
        result = persona_engine.inject_event("sleep_phase_change", variant="rem")
        assert result.sleep_phase == "rem"
        assert result.activity_state == "sleeping"

    def test_sleep_phase_change_ignored_when_not_sleeping(self, persona_engine):
        """Sleep phase change should be ignored when not sleeping."""
        # Default is resting, not sleeping
        result = persona_engine.inject_event("sleep_phase_change", variant="rem")
        assert result.sleep_phase is None  # Should not change
        assert result.activity_state == "resting"

    def test_low_battery_event(self, persona_engine):
        """Low battery event should cap battery at 15%."""
        assert persona_engine.state.battery_level == 100
        result = persona_engine.inject_event("low_battery")
        assert result.battery_level == 15

    def test_low_battery_already_below_15(self, persona_engine):
        """Low battery when already at 10% should stay at 10%."""
        persona_engine.state.battery_level = 10
        result = persona_engine.inject_event("low_battery")
        assert result.battery_level == 10

    def test_device_offline_event(self, persona_engine):
        """Device offline should set is_online to False."""
        result = persona_engine.inject_event("device_offline")
        assert result.is_online is False

    def test_device_online_event(self, persona_engine):
        """Device online should set is_online to True."""
        persona_engine.inject_event("device_offline")
        result = persona_engine.inject_event("device_online")
        assert result.is_online is True

    def test_stress_event(self, persona_engine):
        """Stress event should set stress_state."""
        result = persona_engine.inject_event("stress")
        assert result.stress_state == "stress"

    def test_neutral_event(self, persona_engine):
        """Neutral event should set stress_state to 'neutral'."""
        persona_engine.inject_event("stress")
        result = persona_engine.inject_event("neutral")
        assert result.stress_state == "neutral"


# ---------------------------------------------------------------------------
# Tests: Fall → Recovery → Standing lifecycle
# ---------------------------------------------------------------------------


class TestPersonaEngineFallLifecycle:
    """Verify the automatic fall → recovery → standing transition logic."""

    def test_fall_auto_transitions_to_recovery(self, persona_engine):
        """After FALL_DURATION_TICKS, fall should auto-transition to recovery."""
        persona_engine.inject_event("fall_detected", variant="fall_confirmed")
        assert persona_engine.state.activity_state == "fall"

        # Tick for exactly FALL_DURATION_TICKS
        for i in range(PersonaEngine.FALL_DURATION_TICKS):
            persona_engine.tick()

        assert persona_engine.state.activity_state == "recovery", (
            f"After {PersonaEngine.FALL_DURATION_TICKS} ticks in 'fall', "
            f"should auto-transition to 'recovery', got '{persona_engine.state.activity_state}'"
        )

    def test_recovery_auto_transitions_to_standing(self, persona_engine):
        """After RECOVERY_DURATION_TICKS in recovery, should transition to standing."""
        persona_engine.transition_to("recovery")

        for _ in range(PersonaEngine.RECOVERY_DURATION_TICKS):
            persona_engine.tick()

        assert persona_engine.state.activity_state == "standing", (
            f"After {PersonaEngine.RECOVERY_DURATION_TICKS} ticks in 'recovery', "
            f"should auto-transition to 'standing', got '{persona_engine.state.activity_state}'"
        )

    def test_full_fall_lifecycle(self, persona_engine):
        """Full lifecycle: resting → fall → recovery → standing."""
        assert persona_engine.state.activity_state == "resting"

        # Inject fall
        persona_engine.inject_event("fall_detected", variant="fall_1")
        assert persona_engine.state.activity_state == "fall"

        # Tick through fall phase
        for _ in range(PersonaEngine.FALL_DURATION_TICKS):
            persona_engine.tick()
        assert persona_engine.state.activity_state == "recovery"

        # Tick through recovery phase
        for _ in range(PersonaEngine.RECOVERY_DURATION_TICKS):
            persona_engine.tick()
        assert persona_engine.state.activity_state == "standing"

    def test_fall_variant_cleared_after_recovery(self, persona_engine):
        """Fall variant should be cleared when transitioning out of fall."""
        persona_engine.inject_event("fall_detected", variant="fall_hard")
        assert persona_engine.state.fall_variant == "fall_hard"

        # Auto-transition to recovery
        for _ in range(PersonaEngine.FALL_DURATION_TICKS):
            persona_engine.tick()

        # Recovery clears fall_variant
        assert persona_engine.state.fall_variant is None


# ---------------------------------------------------------------------------
# Tests: Battery drain logic
# ---------------------------------------------------------------------------


class TestPersonaEngineBatteryDrain:
    """Verify activity-dependent battery drain logic."""

    def test_battery_drains_over_time(self, persona_engine):
        """Battery should drain after enough ticks (factor-dependent).

        Resting drain factor is 0.8.  After 60 ticks the accumulator
        reaches 0.8 (< 1.0 → no drain yet).  After 120 ticks the
        accumulator reaches 1.6 → drains 1 unit.
        """
        initial = persona_engine.state.battery_level

        # After 60 ticks with resting factor=0.8: accumulator=0.8, no drain
        for _ in range(60):
            persona_engine.tick()
        assert persona_engine.state.battery_level == initial

        # After 120 ticks: accumulator reaches 1.6 → drain 1
        for _ in range(60):
            persona_engine.tick()
        assert persona_engine.state.battery_level < initial, (
            "Battery should have drained after 120 ticks at resting factor 0.8"
        )

    def test_sleeping_drains_slower_than_running(self):
        """Sleeping drain factor (0.5) should drain slower than running (1.5)."""
        # Sleeping: factor 0.5 → accumulator += 0.5 each 60-tick mark
        # Running: factor 1.5 → accumulator += 1.5 each 60-tick mark
        assert _BATTERY_DRAIN_FACTORS["sleeping"] < _BATTERY_DRAIN_FACTORS["running"]

        # After 120 ticks of running (2 drain events):
        # accumulator = 3.0 → drain 3
        engine_run = PersonaEngine(Persona(seed=7))
        engine_run.transition_to("running")
        for _ in range(120):
            engine_run.tick()
        run_battery = engine_run.state.battery_level

        engine_sleep = PersonaEngine(Persona(seed=7))
        engine_sleep.transition_to("sleeping")
        for _ in range(120):
            engine_sleep.tick()
        sleep_battery = engine_sleep.state.battery_level

        assert sleep_battery > run_battery, (
            f"Sleeping battery ({sleep_battery}) should be > "
            f"Running battery ({run_battery}) after same ticks"
        )

    def test_battery_never_below_zero(self, persona_engine):
        """Battery should never go below 0."""
        persona_engine.state.battery_level = 1
        persona_engine.transition_to("running")

        for _ in range(300):
            persona_engine.tick()

        assert persona_engine.state.battery_level >= 0

    def test_all_activities_have_drain_factors(self):
        """All known activities should have defined drain factors."""
        expected_activities = ["sleeping", "resting", "walking", "running", "standing", "fall", "recovery"]
        for activity in expected_activities:
            assert activity in _BATTERY_DRAIN_FACTORS, (
                f"Activity '{activity}' missing from _BATTERY_DRAIN_FACTORS"
            )
