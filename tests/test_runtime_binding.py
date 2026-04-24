from __future__ import annotations

import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from api_server.dependencies import PendingTickPublish, SimulatorRuntime
from api_server.schemas import CreateDeviceRequest, DataBindingConfig


class RuntimeBindingRegistryStub:
    def __init__(
        self,
        rows_by_binding: dict[tuple[str, str], list[dict[str, object]]],
        demographics_by_binding: dict[tuple[str, str], dict[str, object]] | None = None,
    ) -> None:
        self.rows_by_binding = rows_by_binding
        self.demographics_by_binding = demographics_by_binding or {}

    def get_vitals_timeline(self, subject_id: str, dataset: str) -> list[dict[str, object]]:
        return list(self.rows_by_binding.get((subject_id, dataset), []))

    def get_vitals_sample_at(self, subject_id: str, dataset: str, cursor_index: int) -> dict[str, object] | None:
        rows = self.rows_by_binding.get((subject_id, dataset), [])
        if not rows:
            return None
        return rows[cursor_index % len(rows)]

    def get_case_demographics(self, subject_id: str, dataset: str) -> dict[str, object] | None:
        demographics = self.demographics_by_binding.get((subject_id, dataset))
        return dict(demographics) if demographics else None

    def get_vitals_baseline(self, activity: str | None = None, dataset: str | None = None) -> dict[str, object] | None:
        return {
            "timestamp": "baseline-ts",
            "heart_rate": 72.0,
            "spo2": 98.0,
            "blood_pressure_sys": 120.0,
            "blood_pressure_dia": 80.0,
            "activity_label": activity or "resting",
            "dataset": dataset or "baseline",
        }

    def get_motion_windows(
        self,
        activity: str | None = None,
        activity_label: str | None = None,
        dataset: str | None = None,
        fall_variant: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        return [{"window_id": f"{activity or activity_label or 'rest'}-window", "dataset": dataset or "stub"}]

    def get_fall_event(self, variant: str) -> dict[str, object] | None:
        return {"event_type": "fall_detected", "fall_variant": variant}


class TestRuntimeBinding(unittest.TestCase):
    def test_push_interval_reads_env(self) -> None:
        original = os.environ.get("SIM_PUSH_INTERVAL_SECONDS")
        os.environ["SIM_PUSH_INTERVAL_SECONDS"] = "60"
        try:
            runtime = SimulatorRuntime()
        finally:
            if original is None:
                os.environ.pop("SIM_PUSH_INTERVAL_SECONDS", None)
            else:
                os.environ["SIM_PUSH_INTERVAL_SECONDS"] = original

        self.assertEqual(runtime._push_interval, 60)

    def test_backend_url_reads_env_for_http_ingest(self) -> None:
        original = os.environ.get("HEALTH_BACKEND_URL")
        os.environ["HEALTH_BACKEND_URL"] = "http://backend.example:9000/"
        try:
            runtime = SimulatorRuntime()
        finally:
            if original is None:
                os.environ.pop("HEALTH_BACKEND_URL", None)
            else:
                os.environ["HEALTH_BACKEND_URL"] = original

        self.assertEqual(
            runtime._health_backend_url,
            "http://backend.example:9000",
        )
        self.assertEqual(
            runtime.transport_router.http_publisher.endpoint,
            "http://backend.example:9000/mobile/telemetry/ingest",
        )
        self.assertEqual(
            runtime._telemetry_alert_endpoint(runtime._health_backend_url),
            "http://backend.example:9000/mobile/telemetry/alert",
        )

    def test_push_alert_to_backend_posts_bound_device_payload_once_per_signature(self) -> None:
        runtime = SimulatorRuntime()
        created = runtime.create_device(CreateDeviceRequest(name="Alert Watch", type="smartwatch"))
        runtime.bind_device(created.id, 501)
        sent: list[tuple[str, dict[str, object]]] = []

        def fake_sender(endpoint: str, payload: str) -> int:
            sent.append((endpoint, json.loads(payload)))
            return 202

        runtime._http_sender = fake_sender  # type: ignore[method-assign]

        runtime._push_alert_to_backend(
            created.id,
            event_type="vitals_out_of_range",
            severity="warning",
            metadata={"heart_rate": 118, "timestamp": "2026-03-26T10:00:00Z"},
        )
        runtime._push_alert_to_backend(
            created.id,
            event_type="vitals_out_of_range",
            severity="warning",
            metadata={"heart_rate": 119, "timestamp": "2026-03-26T10:00:05Z"},
        )

        self.assertEqual(len(sent), 1)
        endpoint, payload = sent[0]
        self.assertEqual(endpoint, "http://localhost:8000/mobile/telemetry/alert")
        self.assertEqual(payload["db_device_id"], 501)
        self.assertEqual(payload["event_type"], "vitals_out_of_range")
        self.assertEqual(payload["severity"], "warning")
        self.assertEqual(payload["metadata"]["heart_rate"], 118)

    def test_inject_event_pushes_fall_alert(self) -> None:
        runtime = SimulatorRuntime()
        created = runtime.create_device(CreateDeviceRequest(name="Fall Watch", type="smartwatch"))
        runtime.bind_device(created.id, 88)
        session = runtime.create_session([created.id], speed=1)
        record = runtime.sessions[session["id"]]
        record.status = "idle"
        pushed: list[tuple[str, str, dict[str, object]]] = []

        def fake_push(sim_device_id: str, event_type: str, severity: str, metadata: dict[str, object] | None = None) -> None:
            pushed.append((event_type, severity, dict(metadata or {})))

        runtime._push_alert_to_backend = fake_push  # type: ignore[method-assign]

        runtime.inject_event(created.id, "fall_detected", "fall_1")

        self.assertEqual(len(pushed), 1)
        event_type, severity, metadata = pushed[0]
        self.assertEqual(event_type, "fall_detected")
        self.assertEqual(severity, "critical")
        self.assertEqual(metadata["variant"], "fall_1")

    def test_tick_warning_pushes_threshold_alert(self) -> None:
        runtime = SimulatorRuntime()
        created = runtime.create_device(CreateDeviceRequest(name="Warning Watch", type="smartwatch"))
        runtime.bind_device(created.id, 77)
        runtime.set_device_scenario(created.id, "tachycardia_warning")
        session = runtime.create_session([created.id], speed=1)
        record = runtime.sessions[session["id"]]
        record.status = "running"
        record.simulator.start()
        record.last_tick_monotonic = 0.0
        pushed: list[tuple[str, str, dict[str, object]]] = []

        def fake_push(sim_device_id: str, event_type: str, severity: str, metadata: dict[str, object] | None = None) -> None:
            pushed.append((event_type, severity, dict(metadata or {})))

        runtime._push_alert_to_backend = fake_push  # type: ignore[method-assign]

        effects = runtime._tick_session_locked(record, force=False)
        runtime._run_session_side_effects(effects)

        self.assertTrue(pushed)
        event_type, severity, metadata = pushed[0]
        self.assertEqual(event_type, "vitals_out_of_range")
        self.assertIn(severity, {"warning", "critical"})
        self.assertEqual(metadata["scenario_id"], "tachycardia_warning")

    def test_bind_and_unbind_update_device_state(self) -> None:
        runtime = SimulatorRuntime()
        created = runtime.create_device(CreateDeviceRequest(name="Runtime Watch", type="smartwatch"))

        runtime.bind_device(created.id, 77)
        bound = runtime.list_devices()[0]
        self.assertEqual(bound.boundDbDeviceId, 77)
        self.assertEqual(bound.bindStatus, "bound")
        self.assertEqual(bound.state, "bound")

        runtime.unbind_device(created.id)
        unbound = runtime.list_devices()[0]
        self.assertIsNone(unbound.boundDbDeviceId)
        self.assertEqual(unbound.bindStatus, "unbound")
        self.assertEqual(unbound.state, "bindable")

    def test_tick_buffer_only_keeps_bound_device_vitals(self) -> None:
        runtime = SimulatorRuntime()
        runtime._push_interval = 999999
        runtime._publish_tick_buffer_locked = lambda **kwargs: None  # type: ignore[method-assign]

        bound = runtime.create_device(CreateDeviceRequest(name="Bound Watch", type="smartwatch"))
        unbound = runtime.create_device(CreateDeviceRequest(name="Unbound Watch", type="smartwatch"))
        runtime.bind_device(bound.id, 101)

        session = runtime.create_session([bound.id, unbound.id], speed=1)
        record = runtime.sessions[session["id"]]
        record.status = "running"
        record.simulator.start()
        record.last_tick_monotonic = 0.0

        runtime._tick_session_locked(record, force=False)

        self.assertTrue(runtime._tick_buffer)
        self.assertTrue(all(payload.get("db_device_id") == 101 for payload in runtime._tick_buffer))
        self.assertEqual({payload.get("device_id") for payload in runtime._tick_buffer}, {bound.id})
        self.assertTrue(runtime.devices[bound.id].has_pending_sync)
        self.assertFalse(runtime.devices[unbound.id].has_pending_sync)

    def test_tick_publish_commits_vitals_without_motion_table(self) -> None:
        runtime = SimulatorRuntime()
        created = runtime.create_device(CreateDeviceRequest(name="Persist Watch", type="smartwatch"))
        runtime.bind_device(created.id, 303)
        session = runtime.create_session([created.id], speed=1)
        record = runtime.sessions[session["id"]]
        record.status = "running"

        class RecordingSession:
            def __init__(self) -> None:
                self.statements: list[str] = []
                self.commits = 0

            def execute(self, statement, params=None):  # type: ignore[no-untyped-def]
                self.statements.append(str(statement))
                return None

            def commit(self) -> None:
                self.commits += 1

        fake_session = RecordingSession()

        @contextmanager
        def fake_scope():
            yield fake_session

        pending_publish = PendingTickPublish(
            messages=[
                {
                    "db_device_id": 303,
                    "emitted_at": "2026-01-01T00:00:00Z",
                    "vitals": {
                        "heart_rate": 72.0,
                        "spo2": 98.0,
                        "temperature": 36.7,
                        "blood_pressure_sys": 118.0,
                        "blood_pressure_dia": 76.0,
                        "respiratory_rate": 16.0,
                    },
                    "motion": {"accel_x": [0.1, 0.2, 0.3]},
                }
            ],
            clear_count=1,
        )

        original_scope = None
        from api_server import dependencies as dependencies_module

        original_scope = dependencies_module.session_scope
        dependencies_module.session_scope = fake_scope  # type: ignore[assignment]
        try:
            runtime._execute_pending_tick_publish(pending_publish)
        finally:
            dependencies_module.session_scope = original_scope  # type: ignore[assignment]

        self.assertEqual(fake_session.commits, 1)
        self.assertTrue(any("INSERT INTO vitals" in stmt for stmt in fake_session.statements))
        self.assertTrue(any("UPDATE devices SET last_sync_at = NOW()" in stmt for stmt in fake_session.statements))
        self.assertFalse(any("motion_data" in stmt for stmt in fake_session.statements))
        self.assertTrue(record.last_publish_ok)
        self.assertEqual(record.last_publish_ack_count, 1)
        self.assertEqual(record.last_publish_count, 1)
        self.assertIsNotNone(record.last_publish_latency_ms)

    def test_health_payload_marks_db_down_when_session_scope_fails(self) -> None:
        runtime = SimulatorRuntime()
        from api_server import dependencies as dependencies_module

        original_scope = dependencies_module.session_scope
        original_backend_healthy = runtime._backend_healthy

        def failing_scope():
            raise RuntimeError("database unavailable")

        dependencies_module.session_scope = failing_scope  # type: ignore[assignment]
        runtime._backend_healthy = lambda: False  # type: ignore[method-assign]
        try:
            payload = runtime.health_payload()
        finally:
            dependencies_module.session_scope = original_scope  # type: ignore[assignment]
            runtime._backend_healthy = original_backend_healthy  # type: ignore[method-assign]

        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["backend"], "down")
        self.assertEqual(payload["db"], "down")

    def test_tick_publish_failure_does_not_report_ack(self) -> None:
        runtime = SimulatorRuntime()
        created = runtime.create_device(CreateDeviceRequest(name="Fail Watch", type="smartwatch"))
        runtime.bind_device(created.id, 404)
        session = runtime.create_session([created.id], speed=1)
        record = runtime.sessions[session["id"]]
        record.status = "running"

        class FailingSession:
            def execute(self, statement, params=None):  # type: ignore[no-untyped-def]
                raise RuntimeError("insert failed")

            def commit(self) -> None:
                raise AssertionError("commit should not be reached when insert fails")

        @contextmanager
        def fake_scope():
            yield FailingSession()

        pending_publish = PendingTickPublish(
            messages=[
                {
                    "db_device_id": 404,
                    "emitted_at": "2026-01-01T00:00:00Z",
                    "vitals": {"heart_rate": 65.0, "spo2": 97.0},
                }
            ],
            clear_count=1,
        )

        from api_server import dependencies as dependencies_module

        original_scope = dependencies_module.session_scope
        dependencies_module.session_scope = fake_scope  # type: ignore[assignment]
        try:
            runtime._execute_pending_tick_publish(pending_publish)
        finally:
            dependencies_module.session_scope = original_scope  # type: ignore[assignment]

        self.assertFalse(record.last_publish_ok)
        self.assertEqual(record.last_publish_ack_count, 0)
        self.assertEqual(record.last_publish_count, 1)

    def test_create_device_with_data_binding(self) -> None:
        runtime = SimulatorRuntime()

        created = runtime.create_device(
            CreateDeviceRequest(
                name="Replay Watch",
                data_binding=DataBindingConfig(dataset="VitalDB", subject_id="1", source_mode="replay"),
            )
        )

        self.assertIsNotNone(created.dataBinding)
        self.assertEqual(created.dataBinding.dataset, "VitalDB")
        self.assertEqual(created.dataBinding.subject_id, "1")
        self.assertEqual(runtime.devices[created.id].data_binding, created.dataBinding.model_dump())

    def test_create_session_with_replay_binding(self) -> None:
        runtime = SimulatorRuntime()
        runtime.registry = RuntimeBindingRegistryStub(
            rows_by_binding={
                ("1", "VitalDB"): [
                    {"timestamp": "2024-01-01T00:00:01Z", "heart_rate": 70},
                    {"timestamp": "2024-01-01T00:00:02Z", "heart_rate": 71},
                ]
            },
            demographics_by_binding={
                ("1", "VitalDB"): {"age": 77, "weight_kg": 67.5, "height_cm": 160.2}
            },
        )
        created = runtime.create_device(
            CreateDeviceRequest(
                name="Replay Watch",
                data_binding=DataBindingConfig(dataset="VitalDB", subject_id="1", source_mode="replay"),
            )
        )

        session = runtime.create_session([created.id], speed=1)
        runtime.start_session(session["id"])
        record = runtime.sessions[session["id"]]
        device_context = record.simulator.devices[0]

        self.assertEqual(record.source_modes, {created.id: "replay"})
        self.assertIsNotNone(device_context.data_binding)
        self.assertEqual(device_context.data_binding.subject_id, "1")
        self.assertEqual(device_context.engine.persona.age, 77)
        self.assertEqual(runtime.devices[created.id].persona_config["age"], 77)
        self.assertEqual(record.last_tick_outputs[0]["vitals"]["source_mode"], "replay")

    def test_session_fail_unknown_subject_id(self) -> None:
        runtime = SimulatorRuntime()
        runtime.registry = RuntimeBindingRegistryStub(rows_by_binding={})
        created = runtime.create_device(
            CreateDeviceRequest(
                name="Missing Replay Watch",
                data_binding=DataBindingConfig(dataset="VitalDB", subject_id="NONEXISTENT_9999", source_mode="replay"),
            )
        )

        with self.assertRaises(KeyError):
            runtime.create_session([created.id], speed=1)

    def test_two_devices_independent_cursors(self) -> None:
        runtime = SimulatorRuntime()
        runtime.registry = RuntimeBindingRegistryStub(
            rows_by_binding={
                ("1", "VitalDB"): [
                    {"timestamp": "2024-01-01T00:00:01Z", "heart_rate": 70},
                    {"timestamp": "2024-01-01T00:00:02Z", "heart_rate": 71},
                ],
                ("2", "VitalDB"): [
                    {"timestamp": "2024-02-01T00:00:01Z", "heart_rate": 80},
                    {"timestamp": "2024-02-01T00:00:02Z", "heart_rate": 81},
                ],
            }
        )
        first = runtime.create_device(
            CreateDeviceRequest(
                name="Replay Watch One",
                data_binding=DataBindingConfig(dataset="VitalDB", subject_id="1", source_mode="replay"),
            )
        )
        second = runtime.create_device(
            CreateDeviceRequest(
                name="Replay Watch Two",
                data_binding=DataBindingConfig(dataset="VitalDB", subject_id="2", source_mode="replay"),
            )
        )

        session = runtime.create_session([first.id, second.id], speed=1)
        record = runtime.sessions[session["id"]]
        record.simulator.start()

        first_tick = record.simulator.tick()
        second_tick = record.simulator.tick()

        self.assertEqual(record.source_modes, {first.id: "replay", second.id: "replay"})
        self.assertEqual(first_tick[0]["vitals"]["timestamp"], "2024-01-01T00:00:01Z")
        self.assertEqual(first_tick[1]["vitals"]["timestamp"], "2024-02-01T00:00:01Z")
        self.assertEqual(second_tick[0]["vitals"]["timestamp"], "2024-01-01T00:00:02Z")
        self.assertEqual(second_tick[1]["vitals"]["timestamp"], "2024-02-01T00:00:02Z")

    def test_verification_stays_pending_before_first_publish(self) -> None:
        runtime = SimulatorRuntime()
        created = runtime.create_device(CreateDeviceRequest(name="Pending Watch", type="smartwatch"))
        session = runtime.create_session([created.id], speed=1)
        record = runtime.sessions[session["id"]]
        record.status = "running"
        record.last_tick_outputs = [{"device_id": created.id, "vitals": {"heart_rate": 72}}]
        record.last_tick_at = datetime.now(timezone.utc).isoformat()

        verification = runtime.verification(session["id"])

        self.assertEqual(verification.status, "PENDING")

    def test_verification_marks_running_session_delayed_when_tick_is_stale(self) -> None:
        runtime = SimulatorRuntime()
        created = runtime.create_device(CreateDeviceRequest(name="Delayed Watch", type="smartwatch"))
        session = runtime.create_session([created.id], speed=1)
        record = runtime.sessions[session["id"]]
        record.status = "running"
        record.last_tick_outputs = [{"device_id": created.id, "vitals": {"heart_rate": 68}}]
        record.last_tick_at = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()

        verification = runtime.verification(session["id"])

        self.assertEqual(verification.status, "DELAYED")


if __name__ == "__main__":
    unittest.main()
