"""Persistence layer for the IoT Simulator's mutable runtime config.

The simulator exposes three knobs over `/api/sim/settings/runtime`:
``tickIntervalSeconds``, ``pushIntervalSeconds`` and ``sleepSpeedFactor``.
Until Phase F these were stored only on the live ``SimulatorRuntime``
instance and in ``os.environ`` — every restart silently reset them to
defaults, which is exactly the kind of "UI lying to the user" failure mode
the UX refactor is targeting (plan §10.2 / 1.2 #4).

This module gives those knobs a real home:

* ``runtime_defaults.json`` is committed and provides the bootstrap values.
* ``runtime.json`` is *gitignored* and written on every successful save.

The loader prefers the runtime file, falls back to defaults if the runtime
file is missing or invalid, and never raises — the simulator always boots
with *some* config so the dashboard hero pill never goes orange because of
a config disk error.

Atomicity: writes go through a temp-file + ``os.replace`` so a crash mid-
write cannot leave a half-flushed JSON document on disk.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PERSISTENCE_SCHEMA_VERSION = "1.0"

PersistenceSource = Literal["file", "defaults"]

_CONFIG_DIR = Path(__file__).resolve().parent / "config"
DEFAULTS_PATH: Path = _CONFIG_DIR / "runtime_defaults.json"
RUNTIME_PATH: Path = _CONFIG_DIR / "runtime.json"


# ---------------------------------------------------------------------------
# Data shape — keep tiny, this is hot-path on every settings GET
# ---------------------------------------------------------------------------


@dataclass
class RuntimeConfigValues:
    """The three persisted runtime knobs. All units in seconds (or factor)."""

    tick_interval_seconds: float = 1.0
    push_interval_seconds: int = 5
    sleep_speed_factor: float = 60.0

    def to_json(self) -> dict[str, Any]:
        return {
            "schemaVersion": PERSISTENCE_SCHEMA_VERSION,
            "tickIntervalSeconds": self.tick_interval_seconds,
            "pushIntervalSeconds": self.push_interval_seconds,
            "sleepSpeedFactor": self.sleep_speed_factor,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "RuntimeConfigValues":
        # Be lenient: silently coerce missing keys to defaults so an older
        # runtime.json from a previous schema does not brick startup.
        defaults = cls()
        return cls(
            tick_interval_seconds=float(payload.get("tickIntervalSeconds", defaults.tick_interval_seconds)),
            push_interval_seconds=int(payload.get("pushIntervalSeconds", defaults.push_interval_seconds)),
            sleep_speed_factor=float(payload.get("sleepSpeedFactor", defaults.sleep_speed_factor)),
        )


@dataclass
class PersistenceState:
    """Result of :func:`load_runtime_config` returned to the runtime.

    Carries the values **plus** observability metadata that ``/sim/settings``
    forwards to the FE so the new persistence indicator can show whether the
    user is looking at saved values or hard-coded defaults.
    """

    values: RuntimeConfigValues
    source: PersistenceSource
    path: Path
    last_saved_at: str | None = None
    last_error: str | None = None
    lock: RLock = field(default_factory=RLock)


# ---------------------------------------------------------------------------
# Loaders / writers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("runtime config: failed to parse %s — %s", path, exc)
        return None


def _file_mtime_iso(path: Path) -> str | None:
    try:
        ts = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def load_runtime_config(
    *,
    runtime_path: Path | None = None,
    defaults_path: Path | None = None,
) -> PersistenceState:
    """Resolve the active runtime config.

    Resolution order:
      1. ``runtime.json`` (file)        → ``source = "file"``
      2. ``runtime_defaults.json``      → ``source = "defaults"``
      3. Hard-coded ``RuntimeConfigValues()`` if even defaults are missing.

    Never raises. Errors are recorded on ``PersistenceState.last_error`` so the
    settings endpoint can surface them.
    """
    runtime_path = runtime_path or RUNTIME_PATH
    defaults_path = defaults_path or DEFAULTS_PATH

    last_error: str | None = None

    file_payload = _read_json(runtime_path)
    if file_payload is not None:
        try:
            values = RuntimeConfigValues.from_json(file_payload)
            return PersistenceState(
                values=values,
                source="file",
                path=runtime_path,
                last_saved_at=_file_mtime_iso(runtime_path),
                last_error=None,
            )
        except (TypeError, ValueError) as exc:
            last_error = f"runtime.json invalid: {exc}"
            logger.warning("runtime config: %s — falling back to defaults", last_error)

    defaults_payload = _read_json(defaults_path)
    if defaults_payload is not None:
        try:
            values = RuntimeConfigValues.from_json(defaults_payload)
            return PersistenceState(
                values=values,
                source="defaults",
                path=defaults_path,
                last_saved_at=None,
                last_error=last_error,
            )
        except (TypeError, ValueError) as exc:
            logger.warning("runtime config: defaults invalid — using hard-coded values: %s", exc)
            last_error = f"defaults invalid: {exc}"

    # Last-resort: hard-coded values so the simulator can always boot.
    return PersistenceState(
        values=RuntimeConfigValues(),
        source="defaults",
        path=defaults_path,
        last_saved_at=None,
        last_error=last_error or "no runtime_defaults.json found",
    )


def save_runtime_config(
    values: RuntimeConfigValues,
    *,
    runtime_path: Path | None = None,
) -> str:
    """Atomically persist ``values`` to ``runtime.json``.

    Returns the ISO-8601 ``lastSavedAt`` timestamp the FE should display.
    Raises ``OSError`` only when the temp-file write itself fails — the
    rename is platform-atomic on POSIX and Windows (Python 3.3+).
    """
    runtime_path = runtime_path or RUNTIME_PATH
    runtime_path.parent.mkdir(parents=True, exist_ok=True)

    payload = values.to_json()
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    # Write to a temp file in the same directory so ``os.replace`` is atomic
    # (cross-device renames would not be).  ``delete=False`` because we hand
    # the path to ``os.replace`` ourselves.
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=".runtime-",
        suffix=".json.tmp",
        dir=str(runtime_path.parent),
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, runtime_path)
    except Exception:
        # Best-effort cleanup; do not mask the original exception.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return _file_mtime_iso(runtime_path) or datetime.now(timezone.utc).isoformat()


def reset_runtime_config(*, runtime_path: Path | None = None) -> PersistenceState:
    """Delete ``runtime.json`` (if any) and return the now-active defaults.

    The "Khôi phục mặc định" button in Settings calls this. The deletion is
    idempotent — calling it twice in a row is fine.
    """
    runtime_path = runtime_path or RUNTIME_PATH
    try:
        runtime_path.unlink()
        logger.info("runtime config: %s removed", runtime_path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("runtime config: failed to remove %s — %s", runtime_path, exc)
        # Fall through; loader will still report the file as the source if
        # the unlink failed silently.

    return load_runtime_config(runtime_path=runtime_path)


__all__ = [
    "PERSISTENCE_SCHEMA_VERSION",
    "PersistenceSource",
    "PersistenceState",
    "RuntimeConfigValues",
    "DEFAULTS_PATH",
    "RUNTIME_PATH",
    "load_runtime_config",
    "save_runtime_config",
    "reset_runtime_config",
]
