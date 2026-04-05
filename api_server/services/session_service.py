"""SessionService — extracted from SimulatorRuntime (Task 3.2).

Owns session CRUD (create / list / start / stop) and session state queries.

Orchestration-heavy methods like ``_tick_session_locked``, ``tick_active``,
``set_device_scenario``, and ``inject_event`` remain in ``SimulatorRuntime``
because they coordinate across multiple services (vitals, sleep, alerts).

Thread-safety: every public method acquires ``self._lock`` (the *same*
``threading.RLock`` instance shared with ``SimulatorRuntime``).
"""

from __future__ import annotations

from threading import RLock
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

# Dual import path: supports both package-level execution
#   (`python -m Iot_Simulator.api_server.main`)
# and direct execution from the project root
#   (`uvicorn api_server.main:app`).
try:
    from Iot_Simulator.api_server.schemas import DataBindingConfig
    from Iot_Simulator.simulator_core.dataset_registry import DatasetRegistry
    from Iot_Simulator.simulator_core.session import (
        DataBinding as SimDataBinding,
        SimulatorSession,
        build_device,
    )
except ModuleNotFoundError:
    from api_server.schemas import DataBindingConfig
    from simulator_core.dataset_registry import DatasetRegistry
    from simulator_core.session import (
        DataBinding as SimDataBinding,
        SimulatorSession,
        build_device,
    )

if TYPE_CHECKING:
    from api_server.dependencies import DeviceRecord, SessionRecord, SessionSideEffects


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class SessionService:
    """Manages session CRUD and lifecycle (create / list / start / stop)."""

    def __init__(
        self,
        *,
        devices: dict[str, "DeviceRecord"],
        sessions: dict[str, "SessionRecord"],
        lock: RLock,
        registry: DatasetRegistry,
        record_event_fn: Any,
        rebuild_db_device_active_cache_fn: Callable[[], None],
        tick_session_locked_fn: Callable[["SessionRecord", bool], "SessionSideEffects"],
        run_session_side_effects_fn: Callable[["SessionSideEffects"], None],
    ) -> None:
        # Shared mutable state — same object references as SimulatorRuntime
        self.devices = devices
        self.sessions = sessions
        self._lock = lock
        self.registry = registry
        self._record_event = record_event_fn
        self._rebuild_db_device_active_cache_locked = rebuild_db_device_active_cache_fn
        self._tick_session_locked = tick_session_locked_fn
        self._run_session_side_effects = run_session_side_effects_fn

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def _require_session(self, session_id: str) -> "SessionRecord":
        if session_id not in self.sessions:
            raise KeyError(f"Session not found: {session_id}")
        return self.sessions[session_id]

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "id": session.id,
                    "deviceIds": list(session.device_ids),
                    "speed": session.speed,
                    "status": session.status,
                    "createdAt": session.created_at,
                    "lastTickAt": session.last_tick_at,
                }
                for session in self.sessions.values()
            ]

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def create_session(self, device_ids: list[str], speed: int) -> dict[str, Any]:
        try:
            from Iot_Simulator.api_server.dependencies import SessionRecord
        except ModuleNotFoundError:
            from api_server.dependencies import SessionRecord

        with self._lock:
            missing = [device_id for device_id in device_ids if device_id not in self.devices]
            if missing:
                raise KeyError(f"Unknown device ids: {', '.join(missing)}")
            contexts = []
            source_modes: dict[str, str] = {}
            for device_id in device_ids:
                device = self.devices[device_id]
                config = dict(device.persona_config)
                raw_binding = device.data_binding or None
                sim_binding: SimDataBinding | None = None
                source_mode = "synthetic"
                if raw_binding:
                    subject_id = str(raw_binding.get("subject_id") or "")
                    dataset = str(raw_binding.get("dataset") or "")
                    source_mode = str(raw_binding.get("source_mode") or "synthetic")
                    sim_binding = SimDataBinding(
                        subject_id=subject_id,
                        dataset=dataset,
                        source_mode=source_mode,
                        loop=bool(raw_binding.get("loop", True)),
                        speed_factor=float(raw_binding.get("speed_factor", 1.0)),
                    )
                    if source_mode == "replay":
                        timeline = self.registry.get_vitals_timeline(subject_id, dataset)
                        if not timeline:
                            raise KeyError(
                                f"subject_id={subject_id} dataset={dataset} not found in artifact registry"
                            )
                        get_case_demographics = getattr(self.registry, "get_case_demographics", None)
                        if callable(get_case_demographics):
                            demographics = get_case_demographics(subject_id, dataset)
                            if demographics:
                                config.update(demographics)
                                device.persona_config = dict(config)
                source_modes[device_id] = source_mode
                contexts.append(
                    build_device(
                        device_id,
                        age=int(config.get("age", 35)),
                        weight_kg=float(config.get("weight_kg", 70.0)),
                        height_cm=float(config.get("height_cm", 170.0)),
                        gender=str(config.get("gender")) if config.get("gender") is not None else None,
                        seed=int(config.get("seed", 7)),
                        data_binding=sim_binding,
                    )
                )
            session_id = uuid4().hex
            simulator = SimulatorSession(self.registry, contexts)
            record = SessionRecord(
                id=session_id,
                device_ids=list(device_ids),
                speed=speed,
                simulator=simulator,
                source_modes=source_modes,
            )
            self.sessions[session_id] = record
            return {
                "id": record.id,
                "deviceIds": list(record.device_ids),
                "speed": record.speed,
                "status": record.status,
                "createdAt": record.created_at,
                "lastTickAt": record.last_tick_at,
            }

    def start_session(self, session_id: str) -> None:
        try:
            from Iot_Simulator.api_server.dependencies import SessionSideEffects
        except ModuleNotFoundError:
            from api_server.dependencies import SessionSideEffects

        effects = SessionSideEffects()
        with self._lock:
            record = self._require_session(session_id)
            record.simulator.start()
            record.status = "running"
            for device_id in record.device_ids:
                if device_id in self.devices:
                    self.devices[device_id].state = "streaming"
                    self.devices[device_id].is_online = True
            self._rebuild_db_device_active_cache_locked()
            self._record_event(
                device_id=record.device_ids[0] if record.device_ids else "system",
                event_type="session_started",
                severity="normal",
                message=f"Session {record.id} started",
            )
            effects = self._tick_session_locked(record, True)
        self._run_session_side_effects(effects)

    def stop_session(self, session_id: str) -> None:
        with self._lock:
            record = self._require_session(session_id)
            record.simulator.stop()
            record.status = "stopped"
            for device_id in record.device_ids:
                if device_id in self.devices:
                    self.devices[device_id].state = (
                        "bound" if self.devices[device_id].bound_db_device_id is not None else "bindable"
                    )
                    self.devices[device_id].is_online = False
            self._rebuild_db_device_active_cache_locked()
            self._record_event(
                device_id=record.device_ids[0] if record.device_ids else "system",
                event_type="session_stopped",
                severity="warning",
                message=f"Session {record.id} stopped",
            )
