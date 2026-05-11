from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api_server.dependencies import (
    DAYTIME_THRESHOLDS,
    SLEEP_THRESHOLDS,
    SimulatorRuntime,
    _PRE_MODEL_TRIGGER_ENABLED,
    get_runtime,
)
from api_server.runtime_persistence import PersistenceState
from api_server.schemas import (
    FeatureFlags,
    RuntimeConfig,
    RuntimeConfigSaveResponse,
    RuntimeConfigUpdate,
    RuntimePersistenceBlock,
    SimulatorSettingsResponse,
    TriggerModeValue,
)

router = APIRouter(tags=["settings"])

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_RULES_CONFIG_PATH = _PROJECT_ROOT / "pre_model_trigger" / "health_rules" / "rules_config.json"
_FALL_CONFIG_PATH = _PROJECT_ROOT / "pre_model_trigger" / "fall" / "fall_pipeline_wrist_config.json"


def _read_json_file(path: Path) -> dict[str, Any] | None:
    """Read a JSON config file, returning None if missing or invalid."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _build_runtime_config(runtime: SimulatorRuntime) -> RuntimeConfig:
    """Extract the live runtime config from the persistence layer.

    Reads the in-memory snapshot kept on ``SimulatorRuntime`` instead of
    ``os.environ``: the persistence file is the source of truth, the env is
    just a mirror for legacy code paths.
    """
    values = runtime.runtime_persistence_snapshot().values
    return RuntimeConfig(
        tick_interval_seconds=values.tick_interval_seconds,
        push_interval_seconds=values.push_interval_seconds,
        sleep_speed_factor=values.sleep_speed_factor,
        health_backend_url=runtime._health_backend_url,
    )


def _persistence_block(state: PersistenceState) -> RuntimePersistenceBlock:
    return RuntimePersistenceBlock(
        source=state.source,
        path=str(state.path),
        last_saved_at=state.last_saved_at,
        last_error=state.last_error,
    )


def _derive_trigger_mode(runtime: SimulatorRuntime) -> tuple[TriggerModeValue, bool]:
    """Compute the canonical ``triggerMode`` + the ``enableModelCalls`` flag.

    The mapping mirrors the truth model in plan §10.4 / §2:

    * ``off``   — feature flag disabled OR orchestrator failed to wire.
    * ``shadow``— flag on, orchestrator wired, but ``enable_model_calls`` False.
    * ``active``— flag on, orchestrator wired, and ``enable_model_calls`` True.
    """
    orchestrator = runtime._trigger_orchestrator
    if not _PRE_MODEL_TRIGGER_ENABLED or orchestrator is None:
        return "off", False

    enable_model_calls = bool(getattr(orchestrator, "_enable_model_calls", False))
    return ("active" if enable_model_calls else "shadow"), enable_model_calls


def _read_db_thresholds(
    runtime: SimulatorRuntime,
) -> tuple[dict[str, float] | None, dict[str, float] | None, str]:
    """Probe the trigger orchestrator's settings provider for DB thresholds."""
    db_daytime: dict[str, float] | None = None
    db_sleep: dict[str, float] | None = None
    try:
        orchestrator = runtime._trigger_orchestrator
        if orchestrator is not None and hasattr(orchestrator, "_settings"):
            settings_provider = orchestrator._settings
            raw_day = settings_provider.get_vitals_thresholds(is_sleeping=False)
            if raw_day is not None:
                db_daytime = {k: float(v) for k, v in raw_day.items()}
            raw_sleep = settings_provider.get_vitals_thresholds(is_sleeping=True)
            if raw_sleep is not None:
                db_sleep = {k: float(v) for k, v in raw_sleep.items()}
    except Exception:
        db_daytime = None
        db_sleep = None

    threshold_source = "db" if (db_daytime is not None or db_sleep is not None) else "fallback"
    return db_daytime, db_sleep, threshold_source


@router.get("/settings", response_model=SimulatorSettingsResponse)
def get_settings(
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> SimulatorSettingsResponse:
    """Return the full simulator settings (runtime + thresholds + configs + flags)."""
    db_daytime, db_sleep, threshold_source = _read_db_thresholds(runtime)
    trigger_mode, enable_model_calls = _derive_trigger_mode(runtime)
    persistence = runtime.runtime_persistence_snapshot()

    return SimulatorSettingsResponse(
        runtime=_build_runtime_config(runtime),
        daytime_thresholds=dict(DAYTIME_THRESHOLDS),
        sleep_thresholds=dict(SLEEP_THRESHOLDS),
        rules_config=_read_json_file(_RULES_CONFIG_PATH),
        fall_config=_read_json_file(_FALL_CONFIG_PATH),
        feature_flags=FeatureFlags(
            use_db_thresholds=os.environ.get("USE_DB_THRESHOLDS", "").lower() in ("1", "true", "yes"),
            pre_model_trigger_enabled=_PRE_MODEL_TRIGGER_ENABLED,
            trigger_mode=trigger_mode,
            enable_model_calls=enable_model_calls,
        ),
        db_daytime_thresholds=db_daytime,
        db_sleep_thresholds=db_sleep,
        threshold_source=threshold_source,
        persistence=_persistence_block(persistence),
    )


@router.put("/settings/runtime", response_model=RuntimeConfigSaveResponse)
def update_runtime_config(
    body: RuntimeConfigUpdate,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> RuntimeConfigSaveResponse:
    """Update mutable runtime configuration values and persist to ``runtime.json``.

    Module F.2: writes survive restart.  Returns the live config plus the
    ``persistence`` block so the FE can render the "Đã lưu lúc HH:MM" arc
    without waiting for the next settings poll.
    """
    if body.tick_interval_seconds is None and body.push_interval_seconds is None and body.sleep_speed_factor is None:
        raise HTTPException(status_code=422, detail="At least one field must be provided")

    try:
        new_state = runtime.apply_and_persist_runtime_config(
            tick_interval_seconds=body.tick_interval_seconds,
            push_interval_seconds=body.push_interval_seconds,
            sleep_speed_factor=body.sleep_speed_factor,
        )
    except OSError as exc:  # disk write failure
        raise HTTPException(
            status_code=500,
            detail=f"Failed to persist runtime config: {exc}",
        ) from exc

    return RuntimeConfigSaveResponse(
        runtime=_build_runtime_config(runtime),
        persistence=_persistence_block(new_state),
    )


@router.post("/settings/runtime/reset", response_model=RuntimeConfigSaveResponse)
def restore_runtime_defaults(
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> RuntimeConfigSaveResponse:
    """Delete ``runtime.json`` (if present) and reload defaults.

    Backs the "Khôi phục mặc định" button in the Settings runtime section
    (Module F.5).  Idempotent — returns the active defaults whether or not
    a runtime file existed.
    """
    new_state = runtime.restore_runtime_defaults()
    return RuntimeConfigSaveResponse(
        runtime=_build_runtime_config(runtime),
        persistence=_persistence_block(new_state),
    )
