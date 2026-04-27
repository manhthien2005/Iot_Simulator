"""Per-device circular buffer of motion samples.

The fall pre-trigger fires from a single :class:`MotionSnapshot` (one
tick of accel + gyro), but the backend's IMU-window route requires a
50-sample window. This buffer accumulates the last N motion snapshots
per device so that when the trigger fires, we can serialize the recent
history into a ``FallPredictionRequest``-compatible payload.

Architecture reference: plan ``risk-core-final-completion-9ea607.md``
slice 2b — simulator dispatch.

The buffer is intentionally a separate primitive (not bolted onto
:class:`FallPreTrigger`) so:

* The trigger evaluator stays a pure function of the current sample.
* Tests can exercise the buffer in isolation.
* Future scenarios that need IMU windows (e.g. activity classification)
  can reuse the same buffer.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default buffer capacity matches the backend's
#: ``fall_min_sequence_samples = 50`` requirement.
DEFAULT_CAPACITY: int = 50

#: Sampling rate the simulator's runtime tick produces motion snapshots
#: at. Used to synthesise monotonic millisecond timestamps in the
#: serialised window when the source motion dict doesn't carry its own.
DEFAULT_SAMPLING_RATE_HZ: int = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce ``value`` to ``float`` or fall back to ``default``."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _accel_xyz(sample: dict[str, Any]) -> tuple[float, float, float]:
    """Extract ``(accel_x, accel_y, accel_z)`` from a flexible sample dict.

    Accepts either flat keys (``accel_x``/``accel_y``/``accel_z`` —
    matches the simulator's :class:`MotionSnapshot` dataclass field
    names) or a nested ``{"accel": {"x", "y", "z"}}`` shape.
    """
    accel = sample.get("accel")
    if isinstance(accel, dict):
        return (
            _safe_float(accel.get("x")),
            _safe_float(accel.get("y")),
            _safe_float(accel.get("z")),
        )
    return (
        _safe_float(sample.get("accel_x")),
        _safe_float(sample.get("accel_y")),
        _safe_float(sample.get("accel_z")),
    )


def _gyro_xyz(sample: dict[str, Any]) -> tuple[float, float, float]:
    """Extract ``(gyro_x, gyro_y, gyro_z)`` from the same flexible shapes."""
    gyro = sample.get("gyro")
    if isinstance(gyro, dict):
        return (
            _safe_float(gyro.get("x")),
            _safe_float(gyro.get("y")),
            _safe_float(gyro.get("z")),
        )
    return (
        _safe_float(sample.get("gyro_x")),
        _safe_float(sample.get("gyro_y")),
        _safe_float(sample.get("gyro_z")),
    )


def _derive_orientation(
    ax: float, ay: float, az: float
) -> tuple[float, float, float]:
    """Approximate ``(pitch, roll, yaw)`` from the gravity-vector projection.

    The simulator's IMU has no magnetometer field, so yaw stays at
    ``0.0``. Pitch and roll are recoverable from the accelerometer's
    apparent gravity direction:

    * ``pitch = atan2(-ax, sqrt(ay^2 + az^2))``
    * ``roll  = atan2(ay, az)``

    Same formulae used by :mod:`backend.tests.eval.etl_up_fall` so the
    payloads the simulator emits are shape-identical to the harness's
    UP-Fall windows.
    """
    pitch = math.atan2(-ax, math.sqrt(ay * ay + az * az))
    roll = math.atan2(ay, az)
    return pitch, roll, 0.0


# ---------------------------------------------------------------------------
# Buffer
# ---------------------------------------------------------------------------


@dataclass
class _StoredSample:
    """One motion sample as kept in the FIFO."""

    accel_x: float
    accel_y: float
    accel_z: float
    gyro_x: float
    gyro_y: float
    gyro_z: float


class MotionWindowBuffer:
    """Per-device FIFO of the last ``capacity`` motion samples.

    Usage::

        buffer = MotionWindowBuffer()
        for tick in stream:
            buffer.push("device-01", tick.motion_dict)
        window = buffer.to_imu_window_data("device-01")
        if window is not None:
            client.submit_imu_window(device_id="device-01", window=window)

    The buffer is **best-effort**: pushing data that doesn't parse
    cleanly (no accel keys at all) silently appends a zero sample so
    the FIFO stride stays constant. Callers that need strict input
    validation should validate before calling ``push``.

    Thread-safety: not safe for concurrent use across threads. The
    simulator's runtime uses a single tick loop per device so this is
    fine in practice.
    """

    def __init__(
        self,
        *,
        capacity: int = DEFAULT_CAPACITY,
        sampling_rate_hz: int = DEFAULT_SAMPLING_RATE_HZ,
    ) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1; got {capacity}")
        if sampling_rate_hz < 1:
            raise ValueError(
                f"sampling_rate_hz must be >= 1; got {sampling_rate_hz}"
            )
        self._capacity = capacity
        self._sampling_rate_hz = sampling_rate_hz
        self._buffers: dict[str, deque[_StoredSample]] = {}

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def sampling_rate_hz(self) -> int:
        return self._sampling_rate_hz

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push(self, device_id: str, sample: dict[str, Any]) -> None:
        """Append one motion sample to the device's FIFO.

        ``sample`` may be either:

        * A flat dict ``{"accel_x", "accel_y", "accel_z", "gyro_x", ...}``
          (matches :class:`MotionSnapshot` dataclass field names).
        * A nested dict ``{"accel": {"x", "y", "z"}, "gyro": {...}}``
          (matches the simulator's tick-payload format).

        Anything else is treated as an all-zeros sample so the FIFO
        stride stays constant and the trigger evaluation continues to
        work even on partial data.
        """
        ax, ay, az = _accel_xyz(sample)
        gx, gy, gz = _gyro_xyz(sample)
        bucket = self._buffers.setdefault(
            device_id, deque(maxlen=self._capacity)
        )
        bucket.append(
            _StoredSample(accel_x=ax, accel_y=ay, accel_z=az,
                          gyro_x=gx, gyro_y=gy, gyro_z=gz)
        )

    def is_full(self, device_id: str) -> bool:
        bucket = self._buffers.get(device_id)
        return bucket is not None and len(bucket) >= self._capacity

    def size(self, device_id: str) -> int:
        bucket = self._buffers.get(device_id)
        return len(bucket) if bucket is not None else 0

    def clear(self, device_id: str | None = None) -> None:
        """Drop the buffer for one device, or all devices when ``None``."""
        if device_id is None:
            self._buffers.clear()
            return
        self._buffers.pop(device_id, None)

    def to_imu_window_data(
        self, device_id: str, *, require_full: bool = True,
    ) -> list[dict[str, Any]] | None:
        """Serialise the buffer into a ``SensorSample``-shaped list.

        Output is the same shape the model-api's
        ``FallPredictionRequest.data`` expects (and the same shape the
        backend's ``/api/v1/mobile/telemetry/imu-window`` proxies).

        When ``require_full=True`` (default) returns ``None`` if the
        buffer holds fewer than :attr:`capacity` samples — there is no
        point sending an under-sized window because the backend will
        reject it (``fall_min_sequence_samples=50``).

        When ``require_full=False`` returns whatever is in the buffer.
        Useful for diagnostics / flush-on-shutdown paths.
        """
        bucket = self._buffers.get(device_id)
        if bucket is None or not bucket:
            return None
        if require_full and len(bucket) < self._capacity:
            return None
        interval_ms = round(1000 / self._sampling_rate_hz)
        out: list[dict[str, Any]] = []
        for i, s in enumerate(bucket):
            pitch, roll, yaw = _derive_orientation(s.accel_x, s.accel_y, s.accel_z)
            out.append(
                {
                    "timestamp": i * interval_ms,
                    "accel": {"x": s.accel_x, "y": s.accel_y, "z": s.accel_z},
                    "gyro": {"x": s.gyro_x, "y": s.gyro_y, "z": s.gyro_z},
                    "orientation": {"pitch": pitch, "roll": roll, "yaw": yaw},
                    "environment": {
                        "floor_vibration": 0.0,
                        "room_occupancy": 0.0,
                        "pressure_mat": 0.0,
                    },
                }
            )
        return out


__all__ = [
    "DEFAULT_CAPACITY",
    "DEFAULT_SAMPLING_RATE_HZ",
    "MotionWindowBuffer",
]
