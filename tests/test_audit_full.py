"""Quick audit: scenario bounds + fall E2E test."""
from __future__ import annotations
import time
import unittest
from fastapi.testclient import TestClient
from api_server.dependencies import SimulatorRuntime, reset_runtime_for_tests
from api_server.main import app


ELDERLY = {"age": 72, "weight_kg": 68, "height_cm": 168}
TS = "2026-06-01T12:00:00+00:00"

SCENARIO_BOUNDS = [
    ("normal_rest",           {"hr": (48, 95),   "spo2": (91, 100), "bp_sys": (100, 175), "rr": (9, 21)}),
    ("tachycardia_warning",   {"hr": (92, 142),  "spo2": (88, 100), "bp_sys": (110, 190), "rr": (13, 30)}),
    ("hypoxia_critical",      {"hr": (88, 158),  "spo2": (76, 95),  "bp_sys": (110, 215), "rr": (16, 38)}),
    ("hypertension_moderate", {"hr": (58, 108),  "spo2": (88, 100), "bp_sys": (125, 225), "rr": (10, 24)}),
    ("good_sleep_night",      {"hr": (36, 76),   "spo2": (90, 100), "bp_sys": (78, 155),  "rr": (8, 17)}),
    ("fragmented_sleep",      {"hr": (58, 106),  "spo2": (84, 100), "bp_sys": (95, 195),  "rr": (11, 26)}),
    ("high_risk_cardiac",     {"hr": (95, 178),  "spo2": (74, 100), "bp_sys": (125, 235), "rr": (15, 40)}),
    ("medium_risk_general",   {"hr": (68, 128),  "spo2": (83, 100), "bp_sys": (108, 220), "rr": (11, 29)}),
]


def _snap(sid, activity="resting", pcfg=None, variant=None):
    state = {"activity_state": activity}
    if variant:
        state["fall_variant"] = variant
    p = {"device_id": f"audit-{sid}", "vitals": {}, "emitted_at": TS,
         "state": state, "persona_config": pcfg or ELDERLY}
    SimulatorRuntime._apply_scenario_overrides(p, sid)
    v = p["vitals"]
    v["_severity"] = SimulatorRuntime._to_vitals(v, False, activity_state=activity).severity
    return v


class TestScenarioBounds(unittest.TestCase):
    """Part 1: All scenarios within clinical bounds for elderly persona."""

    def test_all_scenarios_in_bounds(self):
        rows = []
        for sid, bounds in SCENARIO_BOUNDS:
            v = _snap(sid)
            vals = {
                "hr": v.get("heart_rate", -1),
                "spo2": v.get("spo2", -1),
                "bp_sys": v.get("blood_pressure_sys", -1),
                "rr": v.get("respiratory_rate", -1),
            }
            issues = [
                f"{k}={vals[k]:.1f} not in [{lo},{hi}]"
                for k, (lo, hi) in bounds.items()
                if not (lo <= vals[k] <= hi)
            ]
            rows.append((sid, vals, v["_severity"], issues))
            print(f"  {'OK' if not issues else 'FAIL':4s} {sid:25s} "
                  f"HR={vals['hr']:5.1f} SpO2={vals['spo2']:5.1f} "
                  f"BPsys={vals['bp_sys']:5.0f} RR={vals['rr']:4.1f} "
                  f"sev={v['_severity']:8s}",
                  "  !! " + ", ".join(issues) if issues else "")
            with self.subTest(scenario=sid):
                self.assertEqual(issues, [], f"{sid}: {'; '.join(issues)}")

    def test_severity_classification(self):
        """Critical scenarios must be critical, normal must be normal."""
        self.assertEqual(_snap("hypoxia_critical")["_severity"], "critical")
        self.assertEqual(_snap("high_risk_cardiac")["_severity"], "critical")
        # normal_rest elderly may be warning or normal — both acceptable
        self.assertIn(_snap("normal_rest")["_severity"], {"normal", "warning"})
        self.assertEqual(_snap("good_sleep_night")["_severity"], "normal")


class TestFallPipelineE2E(unittest.TestCase):
    """Part 2: Fall pipeline live test via TestClient."""

    def setUp(self):
        reset_runtime_for_tests()
        self.client = TestClient(app)
        dev = self.client.post("/api/v1/sim/devices", json={
            "name": "FallAuditDevice", "type": "smartwatch",
            "persona_config": {"age": 70, "weight_kg": 65, "height_cm": 165}
        }).json()
        self.device_id = dev["id"]
        ses = self.client.post("/api/v1/sim/sessions", json={
            "device_ids": [self.device_id], "speed": 1
        }).json()
        self.session_id = ses["id"]
        self.client.post(f"/api/v1/sim/sessions/{self.session_id}/start")

    def tearDown(self):
        self.client.post(f"/api/v1/sim/sessions/{self.session_id}/stop")

    def _vitals(self):
        return self.client.get("/api/v1/sim/vitals/latest",
                               params={"deviceId": self.device_id}).json()

    def test_baseline_normal_rest_has_activity_label(self):
        v = self._vitals()
        self.assertIn("activityLabel", v)
        self.assertIn("severity", v)
        print(f"\n  Baseline: HR={v.get('heartRate'):.1f} SpO2={v.get('spo2'):.1f} "
              f"label={v.get('activityLabel')} sev={v.get('severity')}")

    def test_fall_high_confidence_raises_hr_and_drops_spo2(self):
        baseline = self._vitals()
        self.client.post("/api/v1/sim/scenarios/apply", json={
            "device_id": self.device_id, "scenario_id": "fall_high_confidence"
        })
        time.sleep(1.5)
        after = self._vitals()
        print(f"\n  fall_high_confidence: HR {baseline.get('heartRate'):.1f} -> {after.get('heartRate'):.1f} | "
              f"SpO2 {baseline.get('spo2'):.1f} -> {after.get('spo2'):.1f} | "
              f"label={after.get('activityLabel')} sev={after.get('severity')}")
        self.assertGreater(after.get("heartRate", 0), baseline.get("heartRate", 0) + 10,
                           "fall_high_confidence must raise HR by >10")
        self.assertLess(after.get("spo2", 100), baseline.get("spo2", 100),
                        "fall_high_confidence must drop SpO2")
        self.assertEqual(after.get("severity"), "critical")

    def test_fall_no_response_event_causes_bradycardia_and_hypoxia(self):
        self.client.post("/api/v1/sim/scenarios/apply", json={
            "device_id": self.device_id, "scenario_id": "normal_rest"
        })
        time.sleep(1.5)
        baseline = self._vitals()
        self.client.post("/api/v1/sim/events/inject", json={
            "device_id": self.device_id,
            "event_type": "fall_detected",
            "variant": "fall_no_response"
        })
        time.sleep(1.5)
        after = self._vitals()
        print(f"\n  fall_no_response: HR {baseline.get('heartRate'):.1f} -> {after.get('heartRate'):.1f} | "
              f"SpO2 {baseline.get('spo2'):.1f} -> {after.get('spo2'):.1f} | "
              f"BPsys {baseline.get('bloodPressureSys'):.0f} -> {after.get('bloodPressureSys'):.0f} | "
              f"label={after.get('activityLabel')} sev={after.get('severity')}")
        self.assertLess(after.get("spo2", 100), 90,
                        "fall_no_response SpO2 must be < 90%")
        self.assertLess(after.get("heartRate", 200), baseline.get("heartRate", 0),
                        "fall_no_response must cause bradycardia (HR lower than baseline)")
        self.assertEqual(after.get("severity"), "critical")

    def test_stress_event_raises_hr(self):
        self.client.post("/api/v1/sim/scenarios/apply", json={
            "device_id": self.device_id, "scenario_id": "normal_rest"
        })
        time.sleep(1.5)
        before = self._vitals()
        self.client.post("/api/v1/sim/events/inject", json={
            "device_id": self.device_id, "event_type": "stress"
        })
        time.sleep(1.5)
        after = self._vitals()
        delta = after.get("heartRate", 0) - before.get("heartRate", 0)
        print(f"\n  stress event: HR delta = +{delta:.1f} bpm (must be >5)")
        self.assertGreater(delta, 5, f"Stress must raise HR by >5 bpm, got {delta:.1f}")

    def test_activity_label_changes_on_fall_event(self):
        before = self._vitals()
        self.client.post("/api/v1/sim/events/inject", json={
            "device_id": self.device_id,
            "event_type": "fall_detected",
            "variant": "fall_1"
        })
        time.sleep(1.5)
        after = self._vitals()
        print(f"\n  activityLabel: {before.get('activityLabel')} -> {after.get('activityLabel')}")
        self.assertIn(after.get("activityLabel"), {"falling", "recovery"},
                      "activityLabel must be 'falling' or 'recovery' after fall event")


if __name__ == "__main__":
    unittest.main(verbosity=2)
