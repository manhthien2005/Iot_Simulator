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
    get_runtime,
)
from api_server.schemas import (
    FeatureFlags,
    RuntimeConfig,
    RuntimeConfigUpdate,
    SimulatorSettingsResponse,
)

router = APIRouter(tags=["settings"])

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_RULES_CONFIG_PATH = _PROJECT_ROOT / "pre_model_trigger" / "NguongHeath" / "rules_config.json"
_FALL_CONFIG_PATH = _PROJECT_ROOT / "pre_model_trigger" / "fall" / "fall_pipeline_wrist_config.json"


def _read_json_file(path: Path) -> dict[str, Any] | None:
    """Read a JSON config file, returning None if missing or invalid."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _build_runtime_config(runtime: SimulatorRuntime) -> RuntimeConfig:
    """Extract current runtime config from the SimulatorRuntime singleton."""
    return RuntimeConfig(
        tick_interval_seconds=runtime._background_tick_interval,
        push_interval_seconds=runtime._push_interval,
        sleep_speed_factor=float(os.environ.get("SIM_SLEEP_SPEED_FACTOR", "60")),
        health_backend_url=runtime._health_backend_url,
    )


@router.get("/settings", response_model=SimulatorSettingsResponse)
def get_settings(
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> SimulatorSettingsResponse:
    """Return the full simulator settings (runtime + thresholds + configs + flags)."""
    return SimulatorSettingsResponse(
        runtime=_build_runtime_config(runtime),
        daytime_thresholds=dict(DAYTIME_THRESHOLDS),
        sleep_thresholds=dict(SLEEP_THRESHOLDS),
        rules_config=_read_json_file(_RULES_CONFIG_PATH),
        fall_config=_read_json_file(_FALL_CONFIG_PATH),
        feature_flags=FeatureFlags(
            use_db_thresholds=os.environ.get("USE_DB_THRESHOLDS", "").lower() in ("1", "true", "yes"),
        ),
    )


@router.put("/settings/runtime", response_model=RuntimeConfig)
def update_runtime_config(
    body: RuntimeConfigUpdate,
    runtime: SimulatorRuntime = Depends(get_runtime),
) -> RuntimeConfig:
    """Update mutable runtime configuration values (in-memory only)."""
    if body.tick_interval_seconds is None and body.push_interval_seconds is None and body.sleep_speed_factor is None:
        raise HTTPException(status_code=422, detail="At least one field must be provided")

    if body.tick_interval_seconds is not None:
        runtime._background_tick_interval = body.tick_interval_seconds
        os.environ["SIM_TICK_INTERVAL_SECONDS"] = str(body.tick_interval_seconds)

    if body.push_interval_seconds is not None:
        runtime._push_interval = body.push_interval_seconds
        os.environ["SIM_PUSH_INTERVAL_SECONDS"] = str(body.push_interval_seconds)

    if body.sleep_speed_factor is not None:
        os.environ["SIM_SLEEP_SPEED_FACTOR"] = str(body.sleep_speed_factor)

    return _build_runtime_config(runtime)
