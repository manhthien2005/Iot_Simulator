"""S6 — IoT sim HTTP vitals publisher (ADR-020 part 1).

Phase 7 slice 6 migrates ``_execute_pending_tick_publish`` from the
legacy DB-direct ``INSERT INTO vitals`` path to an HTTP POST against
``/api/v1/mobile/telemetry/ingest`` on the mobile backend so the BE
auto-trigger pipeline (OQ5) actually fires when the simulator runs.

Tests live at the runtime-method level so they exercise the real
``_publish_vitals_http`` payload assembly + response parsing without
booting a live mobile BE. ``httpx.post`` is patched per-test.

Pinned by ``vitals_ingest.md`` (Phase 7 contract) — failures here mean
the simulator is producing a request shape the BE will reject.
"""

from __future__ import annotations

import json
import os
import unittest
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock, patch

try:
    from Iot_Simulator.api_server import dependencies as dependencies_module
    from Iot_Simulator.api_server.dependencies import PendingDevicePublish, SimulatorRuntime
    from Iot_Simulator.api_server.schemas import CreateDeviceRequest
except ModuleNotFoundError:
    from api_server import dependencies as dependencies_module
    from api_server.dependencies import PendingDevicePublish, SimulatorRuntime
    from api_server.schemas import CreateDeviceRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _runtime_with_running_session(device_db_id: int = 303) -> tuple[SimulatorRuntime, Any, str]:
    runtime = SimulatorRuntime()
    created = runtime.create_device(
        CreateDeviceRequest(name="HTTP Watch", type="smartwatch")
    )
    runtime.bind_device(created.id, device_db_id)
    session = runtime.create_session([created.id], speed=1)
    record = runtime.sessions[session["id"]]
    record.status = "running"
    return runtime, record, created.id


def _pending_tick(*, device_db_id: int = 303, count: int = 1, sim_device_id: str = "sim-dev") -> PendingDevicePublish:
    messages: list[dict[str, Any]] = []
    for i in range(count):
        messages.append(
            {
                "db_device_id": device_db_id + i,
                "emitted_at": f"2026-05-15T22:30:{i:02d}Z",
                "vitals": {
                    "heart_rate": 72.0 + i,
                    "spo2": 98.0,
                    "temperature": 36.7,
                    "blood_pressure_sys": 118.0,
                    "blood_pressure_dia": 76.0,
                    "respiratory_rate": 16.0,
                    "hrv": 45.0,
                },
            }
        )
    return PendingDevicePublish(device_id=sim_device_id, messages=messages, clear_count=count)


def _mock_http_response(*, status_code: int, body: dict[str, Any]) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = body
    return response


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


class TestUseHttpVitalsPublishFlag(unittest.TestCase):
    """``USE_HTTP_VITALS_PUBLISH`` controls HTTP vs legacy DB-direct path.

    Default is HTTP (S6 ships HTTP-first). The DB-direct path remains as
    a transitional fallback until S7 disposes it.
    """

    def setUp(self) -> None:
        self._original = os.environ.get("USE_HTTP_VITALS_PUBLISH")

    def tearDown(self) -> None:
        if self._original is None:
            os.environ.pop("USE_HTTP_VITALS_PUBLISH", None)
        else:
            os.environ["USE_HTTP_VITALS_PUBLISH"] = self._original

    def test_defaults_to_http_when_env_absent(self) -> None:
        os.environ.pop("USE_HTTP_VITALS_PUBLISH", None)
        self.assertTrue(SimulatorRuntime._use_http_vitals_publish())

    def test_explicit_true_keeps_http(self) -> None:
        for value in ("true", "TRUE", "1", "yes", "on"):
            os.environ["USE_HTTP_VITALS_PUBLISH"] = value
            self.assertTrue(
                SimulatorRuntime._use_http_vitals_publish(),
                f"value {value!r} must enable HTTP path",
            )

    def test_explicit_false_disables_http(self) -> None:
        for value in ("false", "FALSE", "0", "no", "off"):
            os.environ["USE_HTTP_VITALS_PUBLISH"] = value
            self.assertFalse(
                SimulatorRuntime._use_http_vitals_publish(),
                f"value {value!r} must disable HTTP path",
            )


# ---------------------------------------------------------------------------
# HTTP path — happy path
# ---------------------------------------------------------------------------


class TestHttpVitalsPublishHappyPath(unittest.TestCase):
    def setUp(self) -> None:
        self._original = os.environ.get("USE_HTTP_VITALS_PUBLISH")
        os.environ["USE_HTTP_VITALS_PUBLISH"] = "true"

    def tearDown(self) -> None:
        if self._original is None:
            os.environ.pop("USE_HTTP_VITALS_PUBLISH", None)
        else:
            os.environ["USE_HTTP_VITALS_PUBLISH"] = self._original

    def test_sends_post_with_canonical_payload_shape(self) -> None:
        runtime, _record, device_id = _runtime_with_running_session(device_db_id=303)
        pending = _pending_tick(device_db_id=303, count=1, sim_device_id=device_id)

        with patch.object(dependencies_module.httpx, "post") as post_mock:
            post_mock.return_value = _mock_http_response(
                status_code=200,
                body={
                    "ingested": 1,
                    "rejected": 0,
                    "errors": [],
                    "risk_evaluated_devices": [303],
                },
            )
            runtime._execute_pending_tick_publish([pending])

        post_mock.assert_called_once()
        call = post_mock.call_args
        # Endpoint must use ADR-021 canonical prefix.
        self.assertIn("/api/v1/mobile/telemetry/ingest", call.args[0])
        # Headers carry the internal service marker so the BE bypasses
        # the user JWT auth + applies the validator-only gate.
        headers = call.kwargs["headers"]
        self.assertEqual(headers["X-Internal-Service"], "iot-simulator")
        self.assertEqual(headers["Content-Type"], "application/json")
        # Body must be ``VitalIngestRequest`` shape (S5 strict schema).
        body = json.loads(call.kwargs["content"].decode("utf-8"))
        self.assertIn("messages", body)
        self.assertEqual(len(body["messages"]), 1)
        msg = body["messages"][0]
        self.assertEqual(msg["db_device_id"], 303)
        self.assertEqual(msg["emitted_at"], "2026-05-15T22:30:00Z")
        # All known vital keys present (BE schema rejects extras).
        self.assertEqual(msg["vitals"]["heart_rate"], 72.0)
        self.assertEqual(msg["vitals"]["spo2"], 98.0)

    def test_acks_count_comes_from_response_ingested(self) -> None:
        runtime, record, device_id = _runtime_with_running_session(device_db_id=303)
        pending = _pending_tick(device_db_id=303, count=3, sim_device_id=device_id)

        with patch.object(dependencies_module.httpx, "post") as post_mock:
            post_mock.return_value = _mock_http_response(
                status_code=200,
                body={
                    "ingested": 3,
                    "rejected": 0,
                    "errors": [],
                    "risk_evaluated_devices": [303, 304, 305],
                },
            )
            runtime._execute_pending_tick_publish([pending])

        self.assertTrue(record.last_publish_ok)
        self.assertEqual(record.last_publish_ack_count, 3)
        self.assertEqual(record.last_publish_count, 3)
        self.assertIsNone(record.last_publish_error)

    def test_partial_ack_reports_publish_not_ok(self) -> None:
        runtime, record, device_id = _runtime_with_running_session(device_db_id=303)
        pending = _pending_tick(device_db_id=303, count=3, sim_device_id=device_id)

        with patch.object(dependencies_module.httpx, "post") as post_mock:
            post_mock.return_value = _mock_http_response(
                status_code=200,
                body={
                    "ingested": 2,
                    "rejected": 1,
                    "errors": [
                        {
                            "index": 2,
                            "device_id": 305,
                            "emitted_at": "2026-05-15T22:30:02Z",
                            "error_code": "INSUFFICIENT_VITALS",
                            "message": "missing critical fields",
                        }
                    ],
                    "risk_evaluated_devices": [303, 304],
                },
            )
            runtime._execute_pending_tick_publish([pending])

        # publish_ok is True only when ack == count; partial = soft fail
        # so the sim can flag the failure in the dashboard.
        self.assertFalse(record.last_publish_ok)
        self.assertEqual(record.last_publish_ack_count, 2)
        self.assertEqual(record.last_publish_count, 3)
        self.assertIsNotNone(record.last_publish_error)

    def test_does_not_touch_session_scope(self) -> None:
        # ADR-020 S6 dispose: HTTP path MUST NOT open a DB session for
        # the vitals INSERT path. If a future refactor accidentally
        # routes through ``session_scope``, this guard catches it.
        runtime, _record, device_id = _runtime_with_running_session(device_db_id=303)
        pending = _pending_tick(device_db_id=303, count=1, sim_device_id=device_id)

        @contextmanager
        def explode_scope():
            raise AssertionError(
                "HTTP vitals publish must not call session_scope() — "
                "ADR-020 dispose target"
            )
            yield None  # unreachable

        original_scope = dependencies_module.session_scope
        dependencies_module.session_scope = explode_scope  # type: ignore[assignment]
        try:
            with patch.object(dependencies_module.httpx, "post") as post_mock:
                post_mock.return_value = _mock_http_response(
                    status_code=200,
                    body={"ingested": 1, "rejected": 0, "errors": [], "risk_evaluated_devices": [303]},
                )
                runtime._execute_pending_tick_publish([pending])
        finally:
            dependencies_module.session_scope = original_scope  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# HTTP path — failure modes
# ---------------------------------------------------------------------------


class TestHttpVitalsPublishFailureModes(unittest.TestCase):
    def setUp(self) -> None:
        self._original = os.environ.get("USE_HTTP_VITALS_PUBLISH")
        os.environ["USE_HTTP_VITALS_PUBLISH"] = "true"

    def tearDown(self) -> None:
        if self._original is None:
            os.environ.pop("USE_HTTP_VITALS_PUBLISH", None)
        else:
            os.environ["USE_HTTP_VITALS_PUBLISH"] = self._original

    def test_http_5xx_reports_zero_ack(self) -> None:
        runtime, record, device_id = _runtime_with_running_session(device_db_id=303)
        pending = _pending_tick(device_db_id=303, count=2, sim_device_id=device_id)

        with patch.object(dependencies_module.httpx, "post") as post_mock:
            post_mock.return_value = _mock_http_response(
                status_code=500,
                body={"error": "internal"},
            )
            runtime._execute_pending_tick_publish([pending])

        self.assertFalse(record.last_publish_ok)
        self.assertEqual(record.last_publish_ack_count, 0)
        self.assertEqual(record.last_publish_count, 2)
        self.assertIsNotNone(record.last_publish_error)

    def test_http_422_reports_zero_ack(self) -> None:
        # Pydantic schema rejection at the BE boundary — entire batch
        # fails before any item is inserted.
        runtime, record, device_id = _runtime_with_running_session(device_db_id=303)
        pending = _pending_tick(device_db_id=303, count=1, sim_device_id=device_id)

        with patch.object(dependencies_module.httpx, "post") as post_mock:
            post_mock.return_value = _mock_http_response(
                status_code=422,
                body={"detail": "validation error"},
            )
            runtime._execute_pending_tick_publish([pending])

        self.assertFalse(record.last_publish_ok)
        self.assertEqual(record.last_publish_ack_count, 0)

    def test_network_exception_reports_zero_ack(self) -> None:
        runtime, record, device_id = _runtime_with_running_session(device_db_id=303)
        pending = _pending_tick(device_db_id=303, count=1, sim_device_id=device_id)

        with patch.object(dependencies_module.httpx, "post") as post_mock:
            post_mock.side_effect = ConnectionError("backend down")
            runtime._execute_pending_tick_publish([pending])

        self.assertFalse(record.last_publish_ok)
        self.assertEqual(record.last_publish_ack_count, 0)
        self.assertIsNotNone(record.last_publish_error)

    def test_invalid_response_body_reports_zero_ack(self) -> None:
        runtime, record, device_id = _runtime_with_running_session(device_db_id=303)
        pending = _pending_tick(device_db_id=303, count=1, sim_device_id=device_id)

        response = MagicMock()
        response.status_code = 200
        response.json.side_effect = ValueError("not json")

        with patch.object(dependencies_module.httpx, "post") as post_mock:
            post_mock.return_value = response
            runtime._execute_pending_tick_publish([pending])

        self.assertFalse(record.last_publish_ok)
        self.assertEqual(record.last_publish_ack_count, 0)


# ---------------------------------------------------------------------------
# Feature flag fallback — flag=false routes through DB-direct path
# ---------------------------------------------------------------------------


class TestFeatureFlagFallbackToDbDirect(unittest.TestCase):
    """Flag=false MUST keep the legacy DB-direct path live so an operator
    can toggle off the HTTP path during the migration window without
    redeploying the simulator.
    """

    def setUp(self) -> None:
        self._original = os.environ.get("USE_HTTP_VITALS_PUBLISH")
        os.environ["USE_HTTP_VITALS_PUBLISH"] = "false"

    def tearDown(self) -> None:
        if self._original is None:
            os.environ.pop("USE_HTTP_VITALS_PUBLISH", None)
        else:
            os.environ["USE_HTTP_VITALS_PUBLISH"] = self._original

    def test_http_not_called_when_flag_disabled(self) -> None:
        runtime, _record, device_id = _runtime_with_running_session(device_db_id=303)
        pending = _pending_tick(device_db_id=303, count=1, sim_device_id=device_id)

        class _RecordingSession:
            def __init__(self) -> None:
                self.statements: list[str] = []
                self.commits = 0

            def execute(self, statement, params=None):  # type: ignore[no-untyped-def]
                self.statements.append(str(statement))
                return None

            def commit(self) -> None:
                self.commits += 1

        fake_session = _RecordingSession()

        @contextmanager
        def fake_scope():
            yield fake_session

        original_scope = dependencies_module.session_scope
        dependencies_module.session_scope = fake_scope  # type: ignore[assignment]
        try:
            with patch.object(dependencies_module.httpx, "post") as post_mock:
                runtime._execute_pending_tick_publish([pending])
                post_mock.assert_not_called()
        finally:
            dependencies_module.session_scope = original_scope  # type: ignore[assignment]

        # DB-direct path executed instead — INSERT statement seen.
        self.assertTrue(
            any("INSERT INTO vitals" in stmt for stmt in fake_session.statements),
            "flag=false must route through legacy session_scope INSERT",
        )


if __name__ == "__main__":
    unittest.main()
