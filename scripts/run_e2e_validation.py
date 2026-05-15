#!/usr/bin/env python3
"""E2E Clinical Accuracy Validation - VSmartwatch IoT Simulator."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


BASE = "http://127.0.0.1:8799/api/v1/sim"
REPORT = Path(__file__).resolve().parents[2] / "validation_report.md"

PERSONAS = [
    {"label": "young", "name": "Young (25F)", "age": 25, "weight_kg": 58.0, "height_cm": 165.0, "seed": 11},
    {"label": "mid", "name": "Mid-Age (50M)", "age": 50, "weight_kg": 80.0, "height_cm": 175.0, "seed": 22},
    {"label": "elderly", "name": "Elderly (72M)", "age": 72, "weight_kg": 68.0, "height_cm": 168.0, "seed": 33},
    {"label": "obese", "name": "Obese (45M)", "age": 45, "weight_kg": 105.0, "height_cm": 170.0, "seed": 44},
    {"label": "under", "name": "Under (22F)", "age": 22, "weight_kg": 46.0, "height_cm": 165.0, "seed": 55},
]

VITALS_SCENARIOS = [
    "normal_rest",
    "tachycardia_warning",
    "hypoxia_critical",
    "hypertension_moderate",
    "good_sleep_night",
    "fragmented_sleep",
    "high_risk_cardiac",
    "medium_risk_general",
]

REFS = {
    "normal_rest": {"heartRate": (48, 100), "spo2": (92, 100), "bloodPressureSys": (90, 175), "respiratoryRate": (9, 21)},
    "tachycardia_warning": {"heartRate": (88, 140), "spo2": (89, 100), "bloodPressureSys": (105, 188), "respiratoryRate": (13, 30)},
    "hypoxia_critical": {"heartRate": (88, 158), "spo2": (76, 95), "bloodPressureSys": (112, 208), "respiratoryRate": (16, 38)},
    "hypertension_moderate": {"heartRate": (60, 112), "spo2": (89, 100), "bloodPressureSys": (122, 220), "respiratoryRate": (10, 24)},
    "good_sleep_night": {"heartRate": (38, 78), "spo2": (90, 100), "bloodPressureSys": (80, 150), "respiratoryRate": (8, 18)},
    "fragmented_sleep": {"heartRate": (60, 105), "spo2": (86, 100), "bloodPressureSys": (98, 190), "respiratoryRate": (11, 26)},
    "high_risk_cardiac": {"heartRate": (95, 175), "spo2": (76, 100), "bloodPressureSys": (128, 228), "respiratoryRate": (14, 35)},
    "medium_risk_general": {"heartRate": (70, 125), "spo2": (86, 100), "bloodPressureSys": (110, 210), "respiratoryRate": (12, 28)},
}
FALL_REFS = {"heartRate": (85, 220), "spo2": (74, 98)}


def api(method: str, path: str, **kwargs):
    response = getattr(requests, method)(f"{BASE}{path}", timeout=10, **kwargs)
    if response.status_code == 204:
        return {}
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code}: {response.text}")
    return response.json()


def chk(val: float, lo: float, hi: float):
    return (True, "✅") if lo <= val <= hi else (False, f"⚠️ {'LOW' if val < lo else 'HIGH'} {val:.1f}")


def run():
    results = []
    total = 0
    passed = 0

    for persona in PERSONAS:
        bmi = persona["weight_kg"] / (persona["height_cm"] / 100) ** 2
        dev = api(
            "post",
            "/devices",
            json={
                "name": persona["name"],
                "type": "smartwatch",
                "persona_config": {
                    "age": persona["age"],
                    "weight_kg": persona["weight_kg"],
                    "height_cm": persona["height_cm"],
                    "seed": persona["seed"],
                },
            },
        )
        ses = api("post", "/sessions", json={"device_ids": [dev["id"]], "speed": 1})
        api("post", f"/sessions/{ses['id']}/start")
        time.sleep(0.4)

        rows = []
        for scenario_id in VITALS_SCENARIOS:
            api("post", "/scenarios/apply", json={"device_id": dev["id"], "scenario_id": scenario_id})
            time.sleep(0.4)
            vitals = api("get", "/vitals/latest", params={"deviceId": dev["id"]})
            row = {"sid": scenario_id, "v": vitals, "checks": {}, "ok": True}
            for key, (lo, hi) in REFS.get(scenario_id, {}).items():
                value = float(vitals.get(key, 0))
                ok, msg = chk(value, lo, hi)
                row["checks"][key] = (ok, msg, value, lo, hi)
                total += 1
                passed += 1 if ok else 0
                if not ok:
                    row["ok"] = False
            rows.append(row)

        api(
            "post",
            "/events",
            json={"device_id": dev["id"], "event_type": "fall_detected", "variant": "fall_1"},
        )
        time.sleep(0.4)
        fall_vitals = api("get", "/vitals/latest", params={"deviceId": dev["id"]})
        fall_row = {"sid": "FALL_EVENT", "v": fall_vitals, "checks": {}, "ok": True}
        for key, (lo, hi) in FALL_REFS.items():
            value = float(fall_vitals.get(key, 0))
            ok, msg = chk(value, lo, hi)
            fall_row["checks"][key] = (ok, msg, value, lo, hi)
            total += 1
            passed += 1 if ok else 0
            if not ok:
                fall_row["ok"] = False
        rows.append(fall_row)

        api("post", f"/sessions/{ses['id']}/stop")
        results.append({"p": persona, "bmi": round(bmi, 1), "rows": rows})

    return results, total, passed


def build(results, total, passed):
    pct = 100 * passed / total if total else 0
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# VSmartwatch Clinical Accuracy Validation",
        f"**{ts}** | Checks: {total} | Pass: {passed} | Fail: {total - passed} | Rate: **{pct:.1f}%**",
        "---",
    ]

    for pr in results:
        p = pr["p"]
        lines.append(f"\n## 👤 {p['name']} | Age {p['age']} | {p['weight_kg']}kg | BMI {pr['bmi']}")
        for row in pr["rows"]:
            icon = "✅" if row["ok"] else "❌"
            lines.append(
                f"\n### {icon} `{row['sid']}`\n| Parameter | Value | Range | Status |\n|---|---|---|---|"
            )
            for akey, (ok, msg, val, lo, hi) in row["checks"].items():
                lines.append(f"| {akey} | {val:.1f} | {lo}–{hi} | {msg} |")
            v = row["v"]
            lines.append(f"> severity=`{v.get('severity', '?')}` activityLabel=`{v.get('activityLabel', '?')}`")

    lines.append(f"\n---\n## Summary\nPass rate: **{pct:.1f}%** — {'✅ CLINICALLY PLAUSIBLE' if pct >= 80 else '⚠️ REVIEW REQUIRED'}")
    return "\n".join(lines)


if __name__ == "__main__":
    try:
        api("get", "/health")
    except Exception:
        print(f"ERROR: Cannot reach {BASE}")
        sys.exit(1)

    print("Running E2E validation...")
    results, total, passed = run()
    text = build(results, total, passed)
    REPORT.write_text(text, encoding="utf-8")
    print(f"Saved: {REPORT}\nResult: {passed}/{total} ({100 * passed / total:.1f}%)")
