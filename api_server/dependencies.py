"""DI wiring + backward-compat re-exports.

Single source of truth for get_runtime() + all legacy imports that
external callers (routers, tests) still use from this module.
"""
from __future__ import annotations

from api_server.runtime import SimulatorRuntime, _PRE_MODEL_TRIGGER_ENABLED  # noqa: F401
from api_server.models import (  # noqa: F401
    DeviceRecord,
    DevicePublishStatus,
    SessionRecord,
    SessionSideEffects,
    PendingDevicePublish,
    PendingHeartbeatUpdate,
    PendingAlertCall,
    PreparedAlertPush,
    EventRecord,
    RiskSnapshot,
)
from api_server.log_hub import LogHub  # noqa: F401
from api_server.fall_policy import (  # noqa: F401
    FallVariantPolicy as _FallVariantPolicy,
    FALL_VARIANT_POLICIES as _FALL_VARIANT_POLICIES,
    FALL_VARIANT_TO_PERSONA as _FALL_VARIANT_TO_PERSONA,
)
from api_server.services.vitals_service import DAYTIME_THRESHOLDS, SLEEP_THRESHOLDS  # noqa: F401
# Backward compat: tests monkey-patch these via `dependencies_module.session_scope/httpx`
import httpx  # noqa: F401
from api_server.db import session_scope  # noqa: F401


class _RuntimeHolder:
    """Singleton holder — allows test override via set_runtime / app.dependency_overrides."""

    __slots__ = ("instance",)

    def __init__(self) -> None:
        self.instance: SimulatorRuntime | None = None

    def get(self) -> SimulatorRuntime:
        if self.instance is None:
            self.instance = SimulatorRuntime()
            self.instance.start_background_tick()
        return self.instance

    def set(self, runtime: SimulatorRuntime) -> None:  # noqa: A003
        self.instance = runtime

    def reset(self) -> SimulatorRuntime:
        if self.instance is not None:
            self.instance.shutdown()
        self.instance = SimulatorRuntime()
        return self.instance


_holder = _RuntimeHolder()


def get_runtime() -> SimulatorRuntime:
    """FastAPI dependency — returns the running :class:`SimulatorRuntime`.

    Override in tests::

        from api_server.dependencies import get_runtime

        app.dependency_overrides[get_runtime] = lambda: my_mock_runtime
    """
    return _holder.get()


def set_runtime(runtime: SimulatorRuntime) -> None:
    """Explicitly install a runtime instance (e.g. during app lifespan)."""
    _holder.set(runtime)


def reset_runtime_for_tests() -> None:
    """Tear down & recreate the singleton — kept for backward compat."""
    _holder.reset()
