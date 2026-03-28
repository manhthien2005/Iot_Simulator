from __future__ import annotations

import unittest

from Iot_Simulator.simulator_core.persona_engine import Persona, PersonaEngine


class TestPersonaEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PersonaEngine(Persona())

    def test_transition_updates_activity_label(self) -> None:
        self.engine.transition_to("walking")
        self.assertEqual(self.engine.current_activity_label(), "walking")

    def test_time_in_state_is_non_negative(self) -> None:
        self.assertGreaterEqual(self.engine.time_in_state(), 0.0)

    def test_inject_fall_sets_flag(self) -> None:
        self.engine.inject_event("fall_detected", "fall_1")
        self.assertTrue(self.engine.is_fall_event())
        self.assertEqual(self.engine.state.fall_variant, "fall_1")

    def test_tick_advances_fall_to_recovery(self) -> None:
        self.engine.inject_event("fall_detected", "fall_1")
        for _ in range(self.engine.FALL_DURATION_TICKS - 1):
            state = self.engine.tick()
            self.assertIn(state.activity_state, {"fall", "recovery"})

        state = self.engine.tick()
        self.assertEqual(state.activity_state, "recovery")

        for _ in range(self.engine.RECOVERY_DURATION_TICKS):
            state = self.engine.tick()

        self.assertEqual(state.activity_state, "standing")


if __name__ == "__main__":
    unittest.main()
