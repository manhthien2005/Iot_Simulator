#!/usr/bin/env python3
"""E2E Clinical Validation v2 — includes phases 8-11 changes."""
from __future__ import annotations
import sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = "http://127.0.0.1:8799/api/sim"
REPORT = Path(__file__).resolve().parents[2] / "validation_report_v2.md"

PERSONAS = [
    {"label":"young",   "name":"Young (25F)",   "age":25,"weight_kg":58.0, "height_cm":165.0,"seed":11},
    {"label":"mid",     "name":"Mid-Age (50M)",  "age":50,"weight_kg":80.0, "height_cm":175.0,"seed":22},
    {"label":"elderly", "name":"Elderly (72M)",  "age":72,"weight_kg":68.0, "height_cm":168.0,"seed":33},
    {"label":"obese",   "name":"Obese (45M)",    "age":45,"weight_kg":105.0,"height_cm":170.0,"seed":44},
    {"label":"under",   "name":"Under (22F)",    "age":22,"weight_kg":46.0, "height_cm":165.0,"seed":55},
]

# Clinical reference ranges — updated for phase 11 hypertension_moderate fix
VITALS_REFS = {
    "normal_rest":           {"heartRate":(48,95),   "spo2":(91,100),"bloodPressureSys":(90,175), "respiratoryRate":(9,21)},
    "tachycardia_warning":   {"heartRate":(92,142),  "spo2":(88,100),"bloodPressureSys":(110,190),"respiratoryRate":(13,30)},
    "hypoxia_critical":      {"heartRate":(88,158),  "spo2":(76,95), "bloodPressureSys":(110,215),"respiratoryRate":(16,40)},
    "hypertension_moderate": {"heartRate":(58,108),  "spo2":(88,100),"bloodPressureSys":(118,210),"respiratoryRate":(10,24)},
    "good_sleep_night":      {"heartRate":(36,76),   "spo2":(90,100),"bloodPressureSys":(78,155), "respiratoryRate":(8,17)},
    "fragmented_sleep":      {"heartRate":(58,106),  "spo2":(84,100),"bloodPressureSys":(95,195), "respiratoryRate":(11,27)},
    "high_risk_cardiac":     {"heartRate":(95,178),  "spo2":(74,100),"bloodPressureSys":(125,235),"respiratoryRate":(15,40)},
    "medium_risk_general":   {"heartRate":(68,128),  "spo2":(83,100),"bloodPressureSys":(108,220),"respiratoryRate":(11,30)},
}

# Fall variant reference ranges (tested via event injection)
FALL_VARIANT_REFS = {
    "fall_1":           {"heartRate":(85,220),  "spo2":(74,95)},
    "fall_no_response": {"heartRate":(40,80),   "spo2":(68,88)},  # bradycardia + deep hypoxia
    "fall_brief":       {"heartRate":(70,130),  "spo2":(84,98)},
}

def api(m, p, **k):
    r = getattr(requests, m)(f"{BASE}{p}", timeout=12, **k)
    if r.status_code == 204: return {}
    if r.status_code >= 400: raise RuntimeError(f"{r.status_code}: {r.text}")
    return r.json()

def chk(val, lo, hi):
    return (True, "✅") if lo <= val <= hi else (False, f"⚠️ {'LOW' if val < lo else 'HIGH'} {val:.1f}")

def run():
    results, total, passed = [], 0, 0
    for p in PERSONAS:
        dev = api("post", "/devices", json={"name": p["name"], "type": "smartwatch",
            "persona_config": {"age": p["age"], "weight_kg": p["weight_kg"],
                                 "height_cm": p["height_cm"], "seed": p["seed"]}})
        ses = api("post", "/sessions", json={"device_ids": [dev["id"]], "speed": 1})
        api("post", f"/sessions/{ses['id']}/start"); time.sleep(1.5)
        rows = []

        # --- Part A: 8 vitals scenarios ---
        for sid, refs in VITALS_REFS.items():
            api("post", "/scenarios/apply", json={"device_id": dev["id"], "scenario_id": sid})
            time.sleep(1.5)
            v = api("get", "/vitals/latest", params={"deviceId": dev["id"]})
            row = {"sid": sid, "v": v, "checks": {}, "ok": True}
            for key, (lo, hi) in refs.items():
                val = float(v.get(key, 0))
                ok, msg = chk(val, lo, hi)
                row["checks"][key] = (ok, msg, val, lo, hi)
                total += 1; passed += (1 if ok else 0)
                if not ok: row["ok"] = False
            rows.append(row)

        # --- Part B: stress event on normal_rest ---
        api("post", "/scenarios/apply", json={"device_id": dev["id"], "scenario_id": "normal_rest"})
        time.sleep(1.5)
        v_base = api("get", "/vitals/latest", params={"deviceId": dev["id"]})
        api("post", "/events/inject", json={"device_id": dev["id"], "event_type": "stress"})
        time.sleep(1.5)
        v_stress = api("get", "/vitals/latest", params={"deviceId": dev["id"]})
        stress_delta = float(v_stress.get("heartRate", 0)) - float(v_base.get("heartRate", 0))
        ok_stress = stress_delta > 5
        total += 1; passed += (1 if ok_stress else 0)
        rows.append({"sid": "STRESS_EVENT", "v": v_stress,
                     "checks": {"heartRate_delta": (ok_stress, f"{'✅' if ok_stress else '⚠️'} +{stress_delta:.1f}bpm", stress_delta, 5, 999)},
                     "ok": ok_stress})

        # --- Part C: fall variants ---
        for variant, refs in FALL_VARIANT_REFS.items():
            api("post", "/scenarios/apply", json={"device_id": dev["id"], "scenario_id": "normal_rest"})
            time.sleep(1.5)
            api("post", "/events/inject", json={"device_id": dev["id"], "event_type": "fall_detected", "variant": variant})
            time.sleep(1.5)
            v = api("get", "/vitals/latest", params={"deviceId": dev["id"]})
            row = {"sid": f"FALL_{variant.upper()}", "v": v, "checks": {}, "ok": True}
            for key, (lo, hi) in refs.items():
                val = float(v.get(key, 0))
                ok, msg = chk(val, lo, hi)
                row["checks"][key] = (ok, msg, val, lo, hi)
                total += 1; passed += (1 if ok else 0)
                if not ok: row["ok"] = False
            rows.append(row)

        api("post", f"/sessions/{ses['id']}/stop")
        results.append({"p": p, "rows": rows})
    return results, total, passed

def build(results, total, passed):
    pct = 100 * passed / total if total else 0
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"# VSmartwatch E2E Validation v2 (Phases 1–11)\n**{ts}** | {total} checks | {passed} pass | {total-passed} fail | **{pct:.1f}%**\n---"]
    for pr in results:
        p = pr["p"]
        lines.append(f"\n## 👤 {p['name']} | Age {p['age']}")
        for row in pr["rows"]:
            icon = "✅" if row["ok"] else "❌"
            lines.append(f"\n### {icon} `{row['sid']}`\n| Parameter | Value | Range | Status |\n|---|---|---|---|")
            for key, (ok, msg, val, lo, hi) in row["checks"].items():
                lines.append(f"| {key} | {val:.1f} | {lo}–{hi} | {msg} |")
            v = row["v"]
            lines.append(f"> severity=`{v.get('severity','?')}` activityLabel=`{v.get('activityLabel','?')}`")
    lines.append(f"\n---\n## Summary\nPass rate: **{pct:.1f}%** — {'✅ CLINICALLY PLAUSIBLE' if pct >= 80 else '⚠️ REVIEW REQUIRED'}")
    return "\n".join(lines)

if __name__ == "__main__":
    try: api("get", "/health")
    except: print(f"ERROR: Cannot reach {BASE}"); sys.exit(1)
    print("Running E2E v2 validation...")
    results, total, passed = run()
    txt = build(results, total, passed)
    REPORT.write_text(txt, encoding="utf-8")
    print(f"Saved: {REPORT}\nResult: {passed}/{total} ({100*passed/total:.1f}%)")
