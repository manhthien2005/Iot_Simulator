"""Tests for :class:`pre_model_trigger.mobile_telemetry_client.MobileTelemetryClient`.

Covers happy-path POST shaping, transport-failure handling, non-2xx
swallowing, malformed-JSON tolerance, the IMU window endpoint URL, the
sleep-record stub endpoint URL, and the parameter pass-through
(``device_id`` / ``db_device_id`` / ``sampling_rate``).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from pre_model_trigger.mobile_telemetry_client import (
    DEFAULT_TIMEOUT_SECONDS,
    MobileTelemetryClient,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capturing_sender(status: int, body: dict[str, Any] | str | None = None):
    """Return a mock sender that records every call and replies with ``status`` / ``body``."""
    captured: list[dict[str, Any]] = []
    if isinstance(body, dict):
        body_text = json.dumps(body)
    elif body is None:
        body_text = ""
    else:
        body_text = body

    def sender(endpoint: str, payload: str, headers: dict[str, str] | None,
               timeout: float) -> tuple[int, str]:
        captured.append({
            "endpoint": endpoint,
            "payload": payload,
            "headers": dict(headers) if headers else None,
            "timeout": timeout,
        })
        return status, body_text

    return sender, captured


_VALID_WINDOW: list[dict[str, Any]] = [
    {
        "timestamp": i * 20,
        "accel": {"x": 0.0, "y": 0.0, "z": 1.0},
        "gyro": {"x": 0.0, "y": 0.0, "z": 0.0},
        "orientation": {"pitch": 0.0, "roll": 0.0, "yaw": 0.0},
        "environment": {"floor_vibration": 0.0, "room_occupancy": 0.0, "pressure_mat": 0.0},
    }
    for i in range(50)
]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestSubmitImuWindowHappyPath:
    def test_returns_parsed_response_on_2xx(self) -> None:
        response_body = {
            "status": "persisted",
            "fall_event_id": 17,
            "model_request_id": "req-abc-123",
            "predicted_fall": True,
        }
        sender, captured = _capturing_sender(200, response_body)
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
        )

        result = client.submit_imu_window(
            device_id="dev-1",
            window_data=_VALID_WINDOW,
            db_device_id=42,
        )

        assert result == response_body
        assert len(captured) == 1
        call = captured[0]
        # Endpoint URL must hit the backend's mobile-telemetry surface.
        assert call["endpoint"] == "http://backend:8000/api/v1/mobile/telemetry/imu-window"
        # Default timeout propagates.
        assert call["timeout"] == DEFAULT_TIMEOUT_SECONDS
        # Internal-service header must be set so the backend can
        # distinguish simulator traffic from real Flutter clients.
        assert call["headers"] is not None
        assert call["headers"].get("X-Internal-Service") == "iot-simulator"

    def test_payload_includes_db_device_id_and_window(self) -> None:
        sender, captured = _capturing_sender(200, {"status": "persisted"})
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
        )

        client.submit_imu_window(
            device_id="device-99",
            window_data=_VALID_WINDOW,
            db_device_id=7,
            sampling_rate=50,
        )

        body = json.loads(captured[0]["payload"])
        assert body["device_id"] == "device-99"
        assert body["db_device_id"] == 7
        assert body["sampling_rate"] == 50
        assert body["window_size"] == 50
        assert len(body["data"]) == 50
        assert body["data"][0]["accel"] == {"x": 0.0, "y": 0.0, "z": 1.0}

    def test_201_created_is_treated_as_success(self) -> None:
        # Backend may return 201 for newly persisted rows.
        sender, _ = _capturing_sender(201, {"status": "persisted", "fall_event_id": 5})
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
        )
        result = client.submit_imu_window(
            device_id="dev-1", window_data=_VALID_WINDOW, db_device_id=1,
        )
        assert result is not None
        assert result["fall_event_id"] == 5


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------


class TestSubmitImuWindowFailures:
    def test_transport_failure_returns_none(self) -> None:
        # Negative status signals a connection-level failure.
        sender, _ = _capturing_sender(-1, "connection refused")
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
        )
        assert client.submit_imu_window(
            device_id="dev", window_data=_VALID_WINDOW, db_device_id=1,
        ) is None

    def test_http_500_returns_none(self) -> None:
        sender, _ = _capturing_sender(500, "Internal Server Error")
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
        )
        assert client.submit_imu_window(
            device_id="dev", window_data=_VALID_WINDOW, db_device_id=1,
        ) is None

    def test_http_422_validation_error_returns_none(self) -> None:
        # Backend rejects under-sized windows with 422 — that's a caller
        # bug, not a transport failure, but the simulator should still
        # not crash and should return None so the orchestrator can log.
        sender, _ = _capturing_sender(
            422, {"detail": [{"loc": ["body", "data"], "msg": "List should have at least 50 items"}]},
        )
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
        )
        assert client.submit_imu_window(
            device_id="dev", window_data=[], db_device_id=1,
        ) is None

    def test_malformed_json_response_returns_none(self) -> None:
        sender, _ = _capturing_sender(200, "this is not JSON")
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
        )
        assert client.submit_imu_window(
            device_id="dev", window_data=_VALID_WINDOW, db_device_id=1,
        ) is None

    def test_non_object_json_returns_none(self) -> None:
        # Backend should always return an object, but defend against
        # arrays / nulls / scalars just in case.
        sender, _ = _capturing_sender(200, '["not", "an", "object"]')
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
        )
        assert client.submit_imu_window(
            device_id="dev", window_data=_VALID_WINDOW, db_device_id=1,
        ) is None

    def test_sender_raising_returns_none(self) -> None:
        def raising_sender(*args, **kwargs):
            raise ConnectionError("simulated socket error")
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=raising_sender,
        )
        # Must NOT propagate the exception — simulator tick must keep going.
        assert client.submit_imu_window(
            device_id="dev", window_data=_VALID_WINDOW, db_device_id=1,
        ) is None


# ---------------------------------------------------------------------------
# Sleep stub
# ---------------------------------------------------------------------------


class TestSubmitSleepRecordStub:
    def test_endpoint_url_targets_sleep_risk_route(self) -> None:
        sender, captured = _capturing_sender(200, {"status": "persisted", "risk_score_id": 99})
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
        )
        result = client.submit_sleep_record(
            record={"sleep_score": 78.5, "duration_minutes": 420},
            db_device_id=3,
            db_user_id=11,
        )
        assert result is not None
        assert captured[0]["endpoint"] == (
            "http://backend:8000/api/v1/mobile/telemetry/sleep-risk"
        )

    def test_payload_wraps_record_with_db_ids(self) -> None:
        sender, captured = _capturing_sender(200, {"status": "persisted"})
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
        )
        client.submit_sleep_record(
            record={"sleep_score": 50.0},
            db_device_id=7,
            db_user_id=22,
        )
        body = json.loads(captured[0]["payload"])
        assert body["db_device_id"] == 7
        assert body["db_user_id"] == 22
        assert body["record"] == {"sleep_score": 50.0}


# ---------------------------------------------------------------------------
# Constructor edge cases
# ---------------------------------------------------------------------------


class TestConstructor:
    def test_trailing_slash_in_base_url_is_stripped(self) -> None:
        sender, captured = _capturing_sender(200, {"status": "persisted"})
        client = MobileTelemetryClient(
            base_url="http://backend:8000/",
            http_sender=sender,
        )
        client.submit_imu_window(
            device_id="d", window_data=_VALID_WINDOW, db_device_id=1,
        )
        # No double slash in the joined URL.
        assert captured[0]["endpoint"] == (
            "http://backend:8000/api/v1/mobile/telemetry/imu-window"
        )

    def test_custom_timeout_propagates_to_sender(self) -> None:
        sender, captured = _capturing_sender(200, {"status": "persisted"})
        client = MobileTelemetryClient(
            base_url="http://backend:8000",
            http_sender=sender,
            timeout=15.0,
        )
        client.submit_imu_window(
            device_id="d", window_data=_VALID_WINDOW, db_device_id=1,
        )
        assert captured[0]["timeout"] == 15.0
