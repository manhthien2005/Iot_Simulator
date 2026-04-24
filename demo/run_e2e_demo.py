from __future__ import annotations

import argparse
import json
import time
from typing import Any

import requests


def _print_json(label: str, payload: dict[str, Any]) -> None:
    print(f"{label}: {json.dumps(payload, indent=2)}")


def run(base_url: str, tick_count: int) -> int:
    base = base_url.rstrip("/")
    timeout = 8

    print(f"Using API base: {base}")

    device = requests.post(
        f"{base}/devices",
        json={"name": "Demo Watch A1", "type": "smartwatch", "persona_config": {"age": 37, "weight_kg": 72, "height_cm": 174, "seed": 11}},
        timeout=timeout,
    )
    device.raise_for_status()
    device_payload = device.json()
    device_id = device_payload["id"]
    _print_json("Created device", device_payload)

    session = requests.post(f"{base}/sessions", json={"device_ids": [device_id], "speed": 1}, timeout=timeout)
    session.raise_for_status()
    session_payload = session.json()
    session_id = session_payload["id"]
    _print_json("Created session", session_payload)

    started = requests.post(f"{base}/sessions/{session_id}/start", timeout=timeout)
    started.raise_for_status()
    print(f"Session started: {session_id}")

    for index in range(tick_count):
        time.sleep(1.0)
        vitals = requests.get(f"{base}/vitals/latest", params={"deviceId": device_id}, timeout=timeout)
        vitals.raise_for_status()
        vitals_payload = vitals.json()
        print(
            f"tick {index + 1:02d}: HR={vitals_payload.get('heartRate')} "
            f"SpO2={vitals_payload.get('spo2')} Severity={vitals_payload.get('severity')}"
        )

    injected = requests.post(
        f"{base}/events/fall",
        json={"device_id": device_id, "event_type": "fall_detected", "variant": "left_standing"},
        timeout=timeout,
    )
    injected.raise_for_status()
    print("Fall injected.")

    risk_trigger = requests.post(f"{base}/analytics/risk/trigger", json={"device_id": device_id}, timeout=timeout)
    risk_trigger.raise_for_status()
    risk = requests.get(f"{base}/analytics/risk", params={"deviceId": device_id}, timeout=timeout)
    risk.raise_for_status()
    _print_json("Risk snapshot", risk.json())

    sleep = requests.get(f"{base}/analytics/sleep", params={"deviceId": device_id}, timeout=timeout)
    sleep.raise_for_status()
    sleep_payload = sleep.json()
    print(f"Sleep fallback mode: {sleep_payload.get('realismMode')} with {len(sleep_payload.get('phases', []))} phases")

    verification = requests.get(f"{base}/verification/latest", params={"sessionId": session_id}, timeout=timeout)
    verification.raise_for_status()
    _print_json("Verification", verification.json())

    stopped = requests.post(f"{base}/sessions/{session_id}/stop", timeout=timeout)
    stopped.raise_for_status()
    print("Session stopped. Demo complete.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run IoT simulator E2E demo flow")
    parser.add_argument("--base-url", default="http://localhost:8090/api/sim")
    parser.add_argument("--ticks", type=int, default=5)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    return run(args.base_url, max(1, args.ticks))


if __name__ == "__main__":
    raise SystemExit(main())
