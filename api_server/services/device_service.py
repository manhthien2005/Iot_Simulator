"""DeviceService — extracted from SimulatorRuntime (Task 3.1).

Owns all device CRUD, bind/unbind, admin-DB-device lifecycle helpers,
and the ``_db_device_active_cache`` that tracks which DB devices have
a running simulator session.

Thread-safety: every public method acquires ``self._lock`` (the *same*
``threading.RLock`` instance shared with ``SimulatorRuntime``).
"""

from __future__ import annotations

import collections
import time
from threading import RLock
from typing import TYPE_CHECKING, Any, Protocol
from uuid import uuid4

# Dual import path: supports both package-level execution
#   (`python -m Iot_Simulator.api_server.main`)
# and direct execution from the project root
#   (`uvicorn api_server.main:app`).
try:
    from Iot_Simulator.api_server.backend_admin_client import BackendAdminClient
    from Iot_Simulator.api_server.db import session_scope
    from Iot_Simulator.api_server.schemas import CreateDeviceRequest, SimulatedDevice
    from Iot_Simulator.api_server.sim_admin_service import SimAdminService
    from Iot_Simulator.api_server.utils import _utc_now_iso
except ModuleNotFoundError:
    from api_server.backend_admin_client import BackendAdminClient
    from api_server.db import session_scope
    from api_server.schemas import CreateDeviceRequest, SimulatedDevice
    from api_server.sim_admin_service import SimAdminService
    from api_server.utils import _utc_now_iso

if TYPE_CHECKING:
    from api_server.dependencies import DeviceRecord, EventRecord, SessionRecord


# ---------------------------------------------------------------------------
# Minimal protocol so DeviceService can call back into SimulatorRuntime
# for session-management operations without a hard circular import.
# ---------------------------------------------------------------------------

class _RuntimeSessionOps(Protocol):
    """Subset of SimulatorRuntime used by DeviceService for session ops."""

    def create_session(self, device_ids: list[str], speed: int) -> dict[str, Any]: ...
    def start_session(self, session_id: str) -> None: ...
    def stop_session(self, session_id: str) -> None: ...


def _build_db_device_persona(device_info: dict[str, Any], db_device_id: int) -> dict[str, Any]:
    """Import and delegate to the module-level helper in dependencies."""
    # Dual import path — see module-level comment above.
    try:
        from Iot_Simulator.api_server.dependencies import _build_db_device_persona as _helper
    except ModuleNotFoundError:
        from api_server.dependencies import _build_db_device_persona as _helper
    return _helper(device_info, db_device_id)



class DeviceService:
    """Manages simulated devices, binding, admin-DB-device lifecycle."""

    def __init__(
        self,
        *,
        devices: dict[str, "DeviceRecord"],
        sessions: dict[str, "SessionRecord"],
        device_scenarios: dict[str, str],
        risk_snapshots: dict[str, Any],
        risk_history: dict[str, list],
        tick_buffer: dict[str, list[dict[str, Any]]],
        event_history: collections.deque["EventRecord"],
        dashboard_cache_ref: list,  # mutable container: [DashboardSummary | None]
        db_device_active_cache: dict[int, bool],
        lock: RLock,
        admin_client: BackendAdminClient,
        record_event_fn: Any,  # callable(**kwargs) -> None
        publish_device_log_fn: Any,  # callable(sim_device_id, *, level, message, timestamp) -> None
        # HIGH #6 fix: additional dicts that must be cleaned up on device delete
        sleep_phase_tracker: dict[str, Any] | None = None,
        bp_last_observed: dict[str, float] | None = None,
        last_alert_pushes: dict[tuple, float] | None = None,
    ) -> None:
        # Shared mutable state — same object references as SimulatorRuntime
        self.devices = devices
        self.sessions = sessions
        self.device_scenarios = device_scenarios
        self.risk_snapshots = risk_snapshots
        self.risk_history = risk_history
        self._tick_buffer = tick_buffer  # type: ignore[assignment]  # now dict[device_id, list]
        self.event_history = event_history
        self._dashboard_cache_ref = dashboard_cache_ref
        self._db_device_active_cache = db_device_active_cache
        self._lock = lock
        self.admin_client = admin_client
        self._record_event = record_event_fn
        self._publish_device_log = publish_device_log_fn
        # HIGH #6 fix: references for cleanup on device deletion
        self._sleep_phase_tracker = sleep_phase_tracker or {}
        self._bp_last_observed = bp_last_observed or {}
        self._last_alert_pushes = last_alert_pushes or {}

        # Set later via set_runtime_session_ops() to avoid circular init
        self._runtime_session_ops: _RuntimeSessionOps | None = None

    def set_runtime_session_ops(self, ops: _RuntimeSessionOps) -> None:
        """Inject session-management callbacks (called once after runtime init)."""
        self._runtime_session_ops = ops

    # ------------------------------------------------------------------
    # Device CRUD
    # ------------------------------------------------------------------

    def list_devices(self) -> list[SimulatedDevice]:
        with self._lock:
            return [
                device.to_schema(current_scenario_id=self.device_scenarios.get(device.id))
                for device in self.devices.values()
            ]

    def create_device(self, request: CreateDeviceRequest) -> SimulatedDevice:
        try:
            from Iot_Simulator.api_server.dependencies import DeviceRecord
        except ModuleNotFoundError:
            from api_server.dependencies import DeviceRecord

        with self._lock:
            device_id = uuid4().hex
            serial = f"SIM-{device_id[:8].upper()}"
            mqtt_client = f"sim-client-{device_id[:8]}"
            device = DeviceRecord(
                id=device_id,
                name=request.name,
                serial_number=serial,
                mqtt_client_id=mqtt_client,
                device_type=request.type,
                persona_config=request.persona_config.model_dump(),
                data_binding=request.data_binding.model_dump() if request.data_binding else None,
            )
            self.devices[device_id] = device
            self.device_scenarios[device_id] = "normal_rest"
            return device.to_schema(current_scenario_id=self.device_scenarios.get(device_id))

    def delete_device(self, device_id: str) -> None:
        with self._lock:
            self.devices.pop(device_id, None)
            self.device_scenarios.pop(device_id, None)
            self.risk_snapshots.pop(device_id, None)
            self.risk_history.pop(device_id, None)
            # HIGH #6 fix: clean up tracker/observation dicts that were
            # previously missed, preventing stale entries from leaking.
            self._sleep_phase_tracker.pop(device_id, None)
            self._bp_last_observed.pop(device_id, None)
            # _last_alert_pushes is keyed by (device_id, event_type, severity)
            # tuples — remove all entries for this device_id.
            stale_keys = [
                key for key in self._last_alert_pushes
                if key[0] == device_id
            ]
            for key in stale_keys:
                self._last_alert_pushes.pop(key, None)
            self._tick_buffer.pop(device_id, None)
            self._refresh_pending_sync_flags()
            for session in self.sessions.values():
                if device_id in session.device_ids:
                    session.device_ids = [item for item in session.device_ids if item != device_id]
            self._rebuild_db_device_active_cache_locked()
            self._record_event(
                device_id=device_id,
                event_type="device_deleted",
                severity="offline",
                message="Device removed from simulator runtime",
            )

    def bind_device(self, sim_device_id: str, db_device_id: int) -> "DeviceRecord":
        with self._lock:
            device = self._require_device(sim_device_id)
            device.bound_db_device_id = db_device_id
            device.bind_status = "bound"
            if device.state in {"draft", "provisioned", "bindable", "bound"}:
                device.state = "bound"
            self._rebuild_db_device_active_cache_locked()
            return device

    def unbind_device(self, sim_device_id: str) -> "DeviceRecord":
        with self._lock:
            device = self._require_device(sim_device_id)
            device.bound_db_device_id = None
            device.bind_status = "unbound"
            if device.state == "bound":
                device.state = "bindable"
            self._tick_buffer.pop(sim_device_id, None)
            self._refresh_pending_sync_flags()
            self._rebuild_db_device_active_cache_locked()
            return device

    # ------------------------------------------------------------------
    # Validation helper
    # ------------------------------------------------------------------

    def _require_device(self, device_id: str) -> "DeviceRecord":
        if device_id not in self.devices:
            raise KeyError(f"Device not found: {device_id}")
        return self.devices[device_id]

    # ------------------------------------------------------------------
    # DB-device active cache
    # ------------------------------------------------------------------

    def list_running_db_device_ids(self) -> set[int]:
        with self._lock:
            return set(self._db_device_active_cache)

    def is_db_device_sim_running(self, db_device_id: int) -> bool:
        with self._lock:
            return self._db_device_active_cache.get(db_device_id, False)

    def _rebuild_db_device_active_cache_locked(self) -> None:
        active_db_device_ids: dict[int, bool] = {}
        for record in self.sessions.values():
            if record.status != "running":
                continue
            for sim_id in record.device_ids:
                device = self.devices.get(sim_id)
                if device is None or device.bound_db_device_id is None:
                    continue
                active_db_device_ids[device.bound_db_device_id] = True
        self._db_device_active_cache.clear()
        self._db_device_active_cache.update(active_db_device_ids)

    def _refresh_pending_sync_flags(self) -> None:
        pending_ids: set[str] = set()
        for device_id, buffer in self._tick_buffer.items():
            if not buffer:
                continue
            for payload in buffer:
                if payload.get("db_device_id") is not None:
                    pending_ids.add(device_id)
                    break
        for device_id, device in self.devices.items():
            device.has_pending_sync = device_id in pending_ids

    # ------------------------------------------------------------------
    # Admin helpers
    # ------------------------------------------------------------------

    def _find_sim_id_for_db_device(self, db_device_id: int) -> str | None:
        for sim_id, device in self.devices.items():
            if device.bound_db_device_id == db_device_id:
                return sim_id
        return None

    def _find_running_session_for_sim_device(self, sim_id: str) -> "SessionRecord | None":
        for record in self.sessions.values():
            if sim_id in record.device_ids and record.status == "running":
                return record
        return None

    # ------------------------------------------------------------------
    # DB-device lifecycle (activate / deactivate / ensure / stop)
    # ------------------------------------------------------------------

    def _ensure_sim_session_for_db_device(self, db_device_id: int, device_info: dict[str, Any]) -> None:
        """Create or re-use a SimDevice + session for an activated DB device."""
        assert self._runtime_session_ops is not None, "runtime session ops not injected"

        same_user_other_db_device_ids: set[int] = set()
        user_id_raw = device_info.get("user_id")
        try:
            user_id = int(user_id_raw) if user_id_raw is not None else None
        except (TypeError, ValueError):
            user_id = None

        if user_id is not None:
            with session_scope() as db:
                same_user_devices = SimAdminService.list_all_devices(db, user_id=user_id)
            same_user_other_db_device_ids = {
                int(device["id"])
                for device in same_user_devices
                if int(device["id"]) != db_device_id
            }

        persona = _build_db_device_persona(device_info, db_device_id)

        session_id_to_start: str | None = None
        with self._lock:
            # Step 1: Stop running sessions of OTHER devices belonging to same user
            for sim_id_other, dev_record in list(self.devices.items()):
                bound_db_device_id = dev_record.bound_db_device_id
                if bound_db_device_id is None or bound_db_device_id not in same_user_other_db_device_ids:
                    continue
                running = self._find_running_session_for_sim_device(sim_id_other)
                if running is not None:
                    self._runtime_session_ops.stop_session(running.id)

            # Step 2: Find or create SimDevice
            sim_id = self._find_sim_id_for_db_device(db_device_id)
            if sim_id is None:
                request = CreateDeviceRequest(
                    name=str(device_info.get("device_name") or f"DBDevice-{db_device_id}"),
                    type=str(device_info.get("device_type") or "smartwatch"),
                    persona_config=persona,
                )
                sim_device_schema = self.create_device(request)
                sim_id = sim_device_schema.id
                sim_record = self.bind_device(sim_id, db_device_id)
            else:
                sim_record = self._require_device(sim_id)
                if sim_record.bound_db_device_id != db_device_id:
                    sim_record = self.bind_device(sim_id, db_device_id)

            sim_record.persona_config = dict(persona)

            # Step 3: Start session if none running
            if self._find_running_session_for_sim_device(sim_id) is None:
                session = self._runtime_session_ops.create_session([sim_id], speed=5)
                session_id_to_start = session.get("id")
                if session_id_to_start is None:
                    raise RuntimeError(f"Khong the tao session cho db_device_id={db_device_id}")

        if session_id_to_start is not None:
            self._runtime_session_ops.start_session(session_id_to_start)

    def _stop_sim_session_for_db_device(self, db_device_id: int) -> None:
        """Stop running simulator session for a given DB device."""
        assert self._runtime_session_ops is not None, "runtime session ops not injected"

        with self._lock:
            sim_id = self._find_sim_id_for_db_device(db_device_id)
            if sim_id is None:
                return
            session_ids = [
                record.id
                for record in self.sessions.values()
                if sim_id in record.device_ids and record.status == "running"
            ]
            for session_id in session_ids:
                self._runtime_session_ops.stop_session(session_id)

    # ------------------------------------------------------------------
    # Admin client wrappers
    # ------------------------------------------------------------------

    def admin_list_db_devices(self) -> list[dict[str, Any]]:
        return self.admin_client.list_devices()

    def admin_find_user(self, email: str) -> dict[str, Any] | None:
        return self.admin_client.find_user_by_email(email)

    def admin_create_db_device(
        self,
        device_name: str,
        device_type: str = "smartwatch",
        serial_number: str | None = None,
        user_email: str | None = None,
    ) -> dict[str, Any]:
        suffix = str(int(time.time()))[-6:]
        safe_name = "".join(ch if ch.isalnum() else "-" for ch in device_name.lower()).strip("-") or "device"
        auto_mqtt = f"sim-{safe_name}-{suffix}"
        auto_serial = serial_number or f"SIM-{auto_mqtt.upper()[:12]}"
        return self.admin_client.create_device(
            device_name=device_name,
            device_type=device_type,
            serial_number=auto_serial,
            mqtt_client_id=auto_mqtt,
            user_email=user_email,
        )

    def admin_assign_db_device(self, device_id: int, user_email: str) -> dict[str, Any]:
        return self.admin_client.assign_device(device_id, user_email)

    def admin_activate_db_device(self, device_id: int) -> dict[str, Any]:
        result = self.admin_client.activate_device(device_id)
        self._ensure_sim_session_for_db_device(device_id, result)
        return result

    def admin_deactivate_db_device(self, device_id: int) -> dict[str, Any]:
        result = self.admin_client.deactivate_device(device_id)
        self._stop_sim_session_for_db_device(device_id)
        return result

    def admin_delete_db_device(self, device_id: int) -> None:
        self._stop_sim_session_for_db_device(device_id)
        self.admin_client.delete_device(device_id)
