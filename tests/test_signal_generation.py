from __future__ import annotations

import math
import unittest
from datetime import datetime

try:
    from fastapi.testclient import TestClient

    from Iot_Simulator.api_server.dependencies import reset_runtime_for_tests
    from Iot_Simulator.api_server.main import app

    FASTAPI_READY = True
except Exception:
    FASTAPI_READY = False


def _client():
    reset_runtime_for_tests()
    return TestClient(app)


@unittest.skipUnless(FASTAPI_READY, "FastAPI not available")
class TestActivityLabel(unittest.TestCase):
    def setUp(self):
        self.client = _client()

    def test_schema_has_activity_label(self):
        from Iot_Simulator.api_server.schemas import VitalsSample

        self.assertIn("activityLabel", VitalsSample.model_fields)
        self.assertIn("motionTag", VitalsSample.model_fields)

    def test_api_returns_activity_label(self):
        d = self.client.post("/api/sim/devices", json={"name": "T", "type": "smartwatch"}).json()
        s = self.client.post("/api/sim/sessions", json={"device_ids": [d["id"]], "speed": 1}).json()
        self.client.post(f"/api/sim/sessions/{s['id']}/start")
        r = self.client.get("/api/sim/vitals/latest", params={"deviceId": d["id"]}).json()
        self.assertIn("activityLabel", r)
        self.assertEqual(r["activityLabel"], r["motionTag"])

    def test_fall_event_sets_activity_label_falling(self):
        d = self.client.post("/api/sim/devices", json={"name": "F", "type": "smartwatch"}).json()
        s = self.client.post("/api/sim/sessions", json={"device_ids": [d["id"]], "speed": 1}).json()
        self.client.post(f"/api/sim/sessions/{s['id']}/start")
        self.client.post("/api/sim/scenarios/apply", json={"device_id": d["id"], "scenario_id": "fall_high_confidence"})
        r = self.client.get("/api/sim/vitals/latest", params={"deviceId": d["id"]}).json()
        self.assertEqual(r["activityLabel"], "falling")


class TestClinicalProfiles(unittest.TestCase):
    BOUNDS = {
        "normal_rest": {"heart_rate": (48, 95), "spo2": (95, 100), "respiratory_rate": (10, 20)},
        "tachycardia_warning": {"heart_rate": (90, 132), "spo2": (91, 100), "respiratory_rate": (14, 28)},
        "hypoxia_critical": {"heart_rate": (92, 148), "spo2": (78, 94), "respiratory_rate": (18, 35)},
        "good_sleep_night": {"heart_rate": (40, 70), "spo2": (92, 100), "respiratory_rate": (9, 18)},
        "high_risk_cardiac": {"heart_rate": (100, 158), "spo2": (78, 96), "respiratory_rate": (16, 32)},
    }

    def _snap(self, scenario_id):
        from Iot_Simulator.api_server.dependencies import SimulatorRuntime

        payload = {
            "device_id": "t",
            "vitals": {},
            "emitted_at": "2026-01-01T00:00:00+00:00",
            "state": {},
            "persona_config": {},
        }
        SimulatorRuntime._apply_scenario_overrides(payload, scenario_id)
        return payload["vitals"]

    def test_all_scenarios_in_clinical_bounds(self):
        for scenario_id, bounds in self.BOUNDS.items():
            with self.subTest(scenario=scenario_id):
                vitals = self._snap(scenario_id)
                for param, (lo, hi) in bounds.items():
                    value = vitals.get(param, -999)
                    self.assertTrue(lo <= value <= hi, f"{scenario_id}.{param}={value:.1f} not in [{lo},{hi}]")

    def test_two_devices_differ(self):
        from Iot_Simulator.api_server.dependencies import SimulatorRuntime

        ts = "2026-06-01T12:00:00+00:00"
        p1 = {"device_id": "aaa", "vitals": {}, "emitted_at": ts, "state": {}, "persona_config": {}}
        p2 = {"device_id": "zzz", "vitals": {}, "emitted_at": ts, "state": {}, "persona_config": {}}
        SimulatorRuntime._apply_scenario_overrides(p1, "normal_rest")
        SimulatorRuntime._apply_scenario_overrides(p2, "normal_rest")
        self.assertNotEqual(p1["vitals"]["heart_rate"], p2["vitals"]["heart_rate"])


class TestFallArchitecture(unittest.TestCase):
    def _snap(self, activity, scenario="normal_rest"):
        from Iot_Simulator.api_server.dependencies import SimulatorRuntime

        payload = {
            "device_id": "f",
            "vitals": {},
            "emitted_at": "2026-01-01T00:00:00+00:00",
            "state": {"activity_state": activity},
            "persona_config": {},
        }
        SimulatorRuntime._apply_scenario_overrides(payload, scenario)
        return payload["vitals"]

    def _sev(self, hr, spo2, sys, dia):
        from Iot_Simulator.api_server.dependencies import SimulatorRuntime

        return SimulatorRuntime._to_vitals(
            {
                "heart_rate": hr,
                "spo2": spo2,
                "blood_pressure_sys": sys,
                "blood_pressure_dia": dia,
            },
            False,
        ).severity

    def test_fall_surge_hr(self):
        self.assertGreater(self._snap("fall")["heart_rate"] - self._snap("resting")["heart_rate"], 20)

    def test_fall_surge_spo2_drops(self):
        self.assertLess(self._snap("fall")["spo2"], self._snap("resting")["spo2"])

    def test_severity_spo2_85_critical(self):
        self.assertEqual(self._sev(95, 85, 120, 78), "critical")

    def test_severity_dbp_112_critical(self):
        self.assertEqual(self._sev(88, 97, 155, 112), "critical")

    def test_severity_bp_140_90_warning(self):
        self.assertEqual(self._sev(82, 97, 140, 90), "warning")

    def test_severity_normal_vitals_normal(self):
        self.assertEqual(self._sev(72, 98, 115, 75), "normal")


class TestFallDuration(unittest.TestCase):
    def test_fall_persists_min_ticks(self):
        from Iot_Simulator.simulator_core.persona_engine import Persona, PersonaEngine

        engine = PersonaEngine(persona=Persona())
        engine.inject_event("fall_detected", "fall_1")

        for i in range(engine.FALL_DURATION_TICKS - 1):
            self.assertIn(engine.tick().activity_state, {"fall", "recovery"}, f"tick {i + 1}")

    def test_fall_to_recovery_to_standing(self):
        from Iot_Simulator.simulator_core.persona_engine import Persona, PersonaEngine

        engine = PersonaEngine(persona=Persona())
        engine.inject_event("fall_detected")

        for _ in range(engine.FALL_DURATION_TICKS + 1):
            engine.tick()
        self.assertEqual(engine.state.activity_state, "recovery")

        for _ in range(engine.RECOVERY_DURATION_TICKS + 1):
            engine.tick()
        self.assertEqual(engine.state.activity_state, "standing")


class TestPersonaVitals(unittest.TestCase):
    def _v(self, age, w, h):
        from Iot_Simulator.api_server.dependencies import SimulatorRuntime

        payload = {
            "device_id": "p45",
            "vitals": {},
            "emitted_at": "2026-06-01T12:00:00+00:00",
            "state": {"activity_state": "resting"},
            "persona_config": {"age": age, "weight_kg": w, "height_cm": h},
        }
        SimulatorRuntime._apply_scenario_overrides(payload, "normal_rest")
        return payload["vitals"]

    def test_elderly_bp_higher_than_young(self):
        self.assertGreater(
            self._v(72, 68, 168)["blood_pressure_sys"],
            self._v(25, 58, 165)["blood_pressure_sys"],
        )

    def test_elderly_spo2_lower_than_young(self):
        self.assertLess(
            self._v(72, 68, 168)["spo2"],
            self._v(25, 58, 165)["spo2"],
        )

    def test_obese_hr_higher_than_normal(self):
        self.assertGreater(
            self._v(45, 105, 170)["heart_rate"],
            self._v(45, 75, 175)["heart_rate"],
        )

    def test_obese_bp_higher_than_normal(self):
        self.assertGreater(
            self._v(45, 105, 170)["blood_pressure_sys"],
            self._v(45, 75, 175)["blood_pressure_sys"],
        )


class TestInterSignalCouplings(unittest.TestCase):
    FIXED_TS = "2026-01-01T00:00:00+00:00"
    PROFILES = {
        "normal_rest": (65.0, 4.0, 97.5, 0.7, 36.6, 0.15, 115.0, 75.0, 5.0, 3.5, 15.0),
        "hypoxia_critical": (118.0, 10.0, 88.0, 1.5, 37.5, 0.25, 148.0, 94.0, 9.0, 6.0, 26.0),
        "high_risk_cardiac": (128.0, 12.0, 91.0, 1.8, 38.0, 0.30, 165.0, 104.0, 12.0, 8.0, 24.0),
    }

    def _clamp(self, value, lower, upper):
        return max(lower, min(upper, value))

    def _wave(self, phase, device_offset, scale, shift=0.0):
        return (
            math.sin((phase + shift + device_offset) / 9.0) * scale
            + math.cos((phase + shift + device_offset) / 13.0) * (scale * 0.4)
        )

    def _snap(self, scenario_id, *, state=None, persona_config=None, device_id="coupling-test"):
        from Iot_Simulator.api_server.dependencies import SimulatorRuntime

        payload = {
            "device_id": device_id,
            "vitals": {},
            "emitted_at": self.FIXED_TS,
            "state": state or {},
            "persona_config": persona_config or {},
        }
        SimulatorRuntime._apply_scenario_overrides(payload, scenario_id)
        return payload["vitals"]

    def _pre_coupling(self, scenario_id, *, state=None, persona_config=None, device_id="coupling-test"):
        state = state or {}
        persona_config = persona_config or {}
        phase = datetime.fromisoformat(self.FIXED_TS).timestamp()
        device_offset = float(hash(device_id) % 97)
        (hr_base, hr_amp, spo2_base, spo2_amp, temp_base, temp_amp,
         bp_sys_base, bp_dia_base, bp_sys_amp, bp_dia_amp, rr_base) = self.PROFILES.get(
            scenario_id, self.PROFILES["normal_rest"]
        )

        heart_rate = self._clamp(hr_base + self._wave(phase, device_offset, hr_amp, 0.0), 40, 190)
        spo2 = self._clamp(spo2_base + self._wave(phase, device_offset, spo2_amp, 3.0), 78, 100)
        temperature = self._clamp(temp_base + self._wave(phase, device_offset, temp_amp, 7.0), 34.5, 41.5)
        blood_pressure_sys = self._clamp(
            bp_sys_base + self._wave(phase, device_offset, bp_sys_amp, 11.0), 85, 225
        )
        blood_pressure_dia = self._clamp(
            bp_dia_base + self._wave(phase, device_offset, bp_dia_amp, 15.0), 50, 140
        )
        respiratory_rate = self._clamp(rr_base + self._wave(phase, device_offset, 1.5, 5.0), 4.0, 35.0)

        fall_activity = str(state.get("activity_state") or "")
        fall_variant = str(state.get("fall_variant") or "fall_generic")
        if fall_activity == "fall":
            if fall_variant == "fall_no_response":
                heart_rate = self._clamp(heart_rate - 10.0, 40, 220)
                spo2 = self._clamp(spo2 - 14.0, 78, 100)
                blood_pressure_sys = self._clamp(blood_pressure_sys - 22.0, 85, 225)
                blood_pressure_dia = self._clamp(blood_pressure_dia - 12.0, 50, 140)
                respiratory_rate = self._clamp(respiratory_rate - 8.0, 4, 35)
            elif fall_variant == "fall_brief":
                heart_rate = self._clamp(heart_rate + 15.0, 40, 220)
                spo2 = self._clamp(spo2 - 2.0, 78, 100)
                blood_pressure_sys = self._clamp(blood_pressure_sys + 8.0, 85, 225)
            else:
                heart_rate = self._clamp(heart_rate + 32.0, 40, 220)
                spo2 = self._clamp(spo2 - 6.0, 78, 100)
                blood_pressure_sys = self._clamp(blood_pressure_sys + 22.0, 85, 225)
        elif fall_activity == "recovery":
            heart_rate = self._clamp(heart_rate + 15.0, 40, 220)
            spo2 = self._clamp(spo2 - 3.0, 78, 100)
            blood_pressure_sys = self._clamp(blood_pressure_sys + 10.0, 85, 225)

        stress_state = str(state.get("stress_state") or "")
        if stress_state == "stress":
            heart_rate = self._clamp(heart_rate + 12.0, 40, 220)
            blood_pressure_sys = self._clamp(blood_pressure_sys + 10.0, 85, 225)
            blood_pressure_dia = self._clamp(blood_pressure_dia + 7.0, 50, 140)
            temperature = self._clamp(temperature + 0.2, 34.5, 41.5)

        age = float(persona_config.get("age", 70.0))
        weight_kg = float(persona_config.get("weight_kg", 65.0))
        height_m = float(persona_config.get("height_cm", 165.0)) / 100.0
        bmi = max(10.0, min(70.0, weight_kg / (height_m ** 2) if height_m > 0 else 22.0))

        hr_age = max(0.0, age - 40.0) * 0.25
        spo2_age = -(max(0.0, age - 50.0) * 0.03)
        sys_age = max(0.0, age - 30.0) * 0.6
        dia_age = (min(age, 55.0) - 30.0) * 0.3 - max(0.0, age - 55.0) * 0.2
        tmp_age = -(max(0.0, age - 40.0) * 0.01)
        rr_age = max(0.0, (age - 50.0) * 0.1)

        if bmi > 25.0:
            excess = bmi - 25.0
            hr_bmi, sys_bmi, dia_bmi = excess * 0.5, excess * 1.0, excess * 0.6
            spo2_bmi, tmp_bmi = -(excess * 0.08), excess * 0.015
        elif bmi < 18.5:
            deficit = 18.5 - bmi
            hr_bmi, sys_bmi, dia_bmi = deficit * 0.4, -(deficit * 0.7), -(deficit * 0.4)
            spo2_bmi, tmp_bmi = 0.0, -(deficit * 0.01)
        else:
            hr_bmi = sys_bmi = dia_bmi = spo2_bmi = tmp_bmi = 0.0

        heart_rate = self._clamp(heart_rate + hr_age + hr_bmi, 40, 220)
        spo2 = self._clamp(spo2 + spo2_age + spo2_bmi, 78, 100)
        temperature = self._clamp(temperature + tmp_age + tmp_bmi, 34.5, 41.5)
        blood_pressure_sys = self._clamp(blood_pressure_sys + sys_age + sys_bmi, 85, 225)
        blood_pressure_dia = self._clamp(blood_pressure_dia + dia_age + dia_bmi, 50, 140)
        respiratory_rate = self._clamp(respiratory_rate + rr_age, 4, 35)

        return {
            "heart_rate": heart_rate,
            "spo2": spo2,
            "temperature": temperature,
            "blood_pressure_sys": blood_pressure_sys,
            "blood_pressure_dia": blood_pressure_dia,
            "respiratory_rate": respiratory_rate,
        }

    def test_hypoxia_adds_rr_coupling_bonus(self):
        pre = self._pre_coupling("hypoxia_critical")
        actual = self._snap("hypoxia_critical")
        expected_rr = round(pre["respiratory_rate"] + ((95.0 - pre["spo2"]) * 0.5), 1)
        self.assertLess(pre["spo2"], 95.0)
        self.assertEqual(actual["respiratory_rate"], expected_rr)

    def test_fever_adds_hr_coupling_bonus(self):
        fever_persona = {"age": 40, "weight_kg": 65.0, "height_cm": 165.0}
        pre = self._pre_coupling("high_risk_cardiac", persona_config=fever_persona)
        actual = self._snap("high_risk_cardiac", persona_config=fever_persona)
        expected_hr = round(pre["heart_rate"] + ((pre["temperature"] - 37.5) * 10.0), 2)
        self.assertGreater(pre["temperature"], 37.5)
        self.assertEqual(actual["heart_rate"], expected_hr)

    def test_fall_hypoxia_applies_rr_bonus_after_spo2_drop(self):
        pre = self._pre_coupling("normal_rest", state={"activity_state": "fall", "fall_variant": "fall_1"})
        actual = self._snap("normal_rest", state={"activity_state": "fall", "fall_variant": "fall_1"})
        expected_rr = round(pre["respiratory_rate"] + ((95.0 - pre["spo2"]) * 0.5), 1)
        self.assertLess(pre["spo2"], 95.0)
        self.assertEqual(actual["respiratory_rate"], expected_rr)


if __name__ == "__main__":
    unittest.main()
