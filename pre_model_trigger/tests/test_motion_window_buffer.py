"""Tests for :class:`pre_model_trigger.motion_window_buffer.MotionWindowBuffer`.

Covers FIFO behaviour, capacity rollover, multi-device isolation,
input-shape flexibility (flat ``accel_x`` vs nested ``{"accel": ...}``),
serialisation contract (matches the model-api's ``SensorSample`` shape),
and the ``require_full`` gate.
"""

from __future__ import annotations

import math

import pytest

from pre_model_trigger.motion_window_buffer import (
    DEFAULT_CAPACITY,
    MotionWindowBuffer,
)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestMotionWindowBufferConstruction:
    def test_default_capacity_matches_model_api_minimum(self) -> None:
        # Backend's fall_min_sequence_samples is 50; the buffer's default
        # MUST match so a buffer that just filled up always produces a
        # backend-acceptable window without further sizing logic.
        assert DEFAULT_CAPACITY == 50

    def test_rejects_zero_capacity(self) -> None:
        with pytest.raises(ValueError):
            MotionWindowBuffer(capacity=0)

    def test_rejects_negative_capacity(self) -> None:
        with pytest.raises(ValueError):
            MotionWindowBuffer(capacity=-5)

    def test_rejects_zero_sampling_rate(self) -> None:
        with pytest.raises(ValueError):
            MotionWindowBuffer(sampling_rate_hz=0)


# ---------------------------------------------------------------------------
# FIFO + multi-device isolation
# ---------------------------------------------------------------------------


class TestPushAndSize:
    def test_push_increments_size(self) -> None:
        buffer = MotionWindowBuffer(capacity=10)
        for i in range(7):
            buffer.push("dev-A", {"accel_x": 0.1 * i, "accel_y": 0.0, "accel_z": 1.0})
        assert buffer.size("dev-A") == 7
        assert buffer.is_full("dev-A") is False

    def test_capacity_rollover_keeps_last_n(self) -> None:
        buffer = MotionWindowBuffer(capacity=3)
        for i in range(5):
            # Distinct accel_x so we can tell which samples survived.
            buffer.push("dev-A", {"accel_x": float(i), "accel_y": 0.0, "accel_z": 0.0})
        assert buffer.size("dev-A") == 3
        assert buffer.is_full("dev-A") is True
        # The last three pushed values were i=2, 3, 4.
        window = buffer.to_imu_window_data("dev-A")
        assert window is not None
        assert [s["accel"]["x"] for s in window] == [2.0, 3.0, 4.0]

    def test_devices_are_isolated(self) -> None:
        buffer = MotionWindowBuffer(capacity=4)
        buffer.push("dev-A", {"accel_x": 1.0, "accel_y": 0.0, "accel_z": 0.0})
        buffer.push("dev-B", {"accel_x": 2.0, "accel_y": 0.0, "accel_z": 0.0})
        buffer.push("dev-B", {"accel_x": 3.0, "accel_y": 0.0, "accel_z": 0.0})
        assert buffer.size("dev-A") == 1
        assert buffer.size("dev-B") == 2

    def test_size_returns_zero_for_unknown_device(self) -> None:
        buffer = MotionWindowBuffer()
        assert buffer.size("never-seen") == 0
        assert buffer.is_full("never-seen") is False


# ---------------------------------------------------------------------------
# Input shape flexibility
# ---------------------------------------------------------------------------


class TestInputShapeFlexibility:
    def test_accepts_flat_accel_keys(self) -> None:
        buffer = MotionWindowBuffer(capacity=2)
        buffer.push("dev", {"accel_x": 1.0, "accel_y": 2.0, "accel_z": 3.0,
                            "gyro_x": 4.0, "gyro_y": 5.0, "gyro_z": 6.0})
        buffer.push("dev", {"accel_x": 1.0, "accel_y": 2.0, "accel_z": 3.0})
        window = buffer.to_imu_window_data("dev")
        assert window is not None
        first = window[0]
        assert first["accel"] == {"x": 1.0, "y": 2.0, "z": 3.0}
        assert first["gyro"] == {"x": 4.0, "y": 5.0, "z": 6.0}

    def test_accepts_nested_accel_dict(self) -> None:
        buffer = MotionWindowBuffer(capacity=2)
        buffer.push("dev", {"accel": {"x": 0.1, "y": 0.2, "z": 0.3},
                            "gyro": {"x": 1.0, "y": 2.0, "z": 3.0}})
        buffer.push("dev", {"accel": {"x": 0.1, "y": 0.2, "z": 0.3}})
        window = buffer.to_imu_window_data("dev")
        assert window is not None
        first = window[0]
        assert first["accel"] == {"x": 0.1, "y": 0.2, "z": 0.3}
        assert first["gyro"] == {"x": 1.0, "y": 2.0, "z": 3.0}

    def test_missing_keys_default_to_zero_not_crash(self) -> None:
        # Defensive — partial samples must not abort the simulator tick.
        buffer = MotionWindowBuffer(capacity=2)
        buffer.push("dev", {"random_garbage": 42})
        buffer.push("dev", {"accel_x": "not a number"})
        window = buffer.to_imu_window_data("dev")
        assert window is not None
        for sample in window:
            assert sample["accel"] == {"x": 0.0, "y": 0.0, "z": 0.0}
            assert sample["gyro"] == {"x": 0.0, "y": 0.0, "z": 0.0}


# ---------------------------------------------------------------------------
# Serialisation contract
# ---------------------------------------------------------------------------


class TestSerialisationShape:
    def test_to_imu_window_data_matches_sensor_sample_keys(self) -> None:
        buffer = MotionWindowBuffer(capacity=1)
        buffer.push("dev", {"accel_x": 0.0, "accel_y": 0.0, "accel_z": 1.0})
        window = buffer.to_imu_window_data("dev")
        assert window is not None
        assert len(window) == 1
        sample = window[0]
        # Top-level keys per the model-api SensorSample schema.
        assert set(sample.keys()) == {
            "timestamp", "accel", "gyro", "orientation", "environment",
        }
        assert set(sample["accel"]) == {"x", "y", "z"}
        assert set(sample["gyro"]) == {"x", "y", "z"}
        assert set(sample["orientation"]) == {"pitch", "roll", "yaw"}
        assert set(sample["environment"]) == {
            "floor_vibration", "room_occupancy", "pressure_mat",
        }

    def test_timestamps_are_monotonic_at_sampling_rate(self) -> None:
        buffer = MotionWindowBuffer(capacity=4, sampling_rate_hz=50)
        for _ in range(4):
            buffer.push("dev", {"accel_x": 0.1, "accel_y": 0.0, "accel_z": 1.0})
        window = buffer.to_imu_window_data("dev")
        assert window is not None
        # 50 Hz -> 20 ms interval.
        assert [s["timestamp"] for s in window] == [0, 20, 40, 60]

    def test_yaw_is_always_zero_no_magnetometer(self) -> None:
        buffer = MotionWindowBuffer(capacity=1)
        buffer.push("dev", {"accel_x": 0.5, "accel_y": 0.5, "accel_z": 0.5})
        window = buffer.to_imu_window_data("dev")
        assert window is not None
        assert window[0]["orientation"]["yaw"] == 0.0

    def test_flat_z_gives_near_zero_pitch_and_roll(self) -> None:
        buffer = MotionWindowBuffer(capacity=1)
        buffer.push("dev", {"accel_x": 0.0, "accel_y": 0.0, "accel_z": 1.0})
        window = buffer.to_imu_window_data("dev")
        assert window is not None
        orientation = window[0]["orientation"]
        assert math.isclose(orientation["pitch"], 0.0, abs_tol=1e-9)
        assert math.isclose(orientation["roll"], 0.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# require_full gate
# ---------------------------------------------------------------------------


class TestRequireFullGate:
    def test_returns_none_when_buffer_under_capacity_default(self) -> None:
        buffer = MotionWindowBuffer(capacity=10)
        for _ in range(5):
            buffer.push("dev", {"accel_x": 0.1, "accel_y": 0.0, "accel_z": 1.0})
        # Default require_full=True -> no point sending under-sized window.
        assert buffer.to_imu_window_data("dev") is None

    def test_returns_partial_when_require_full_disabled(self) -> None:
        buffer = MotionWindowBuffer(capacity=10)
        for _ in range(5):
            buffer.push("dev", {"accel_x": 0.1, "accel_y": 0.0, "accel_z": 1.0})
        window = buffer.to_imu_window_data("dev", require_full=False)
        assert window is not None
        assert len(window) == 5

    def test_returns_none_for_completely_empty_device(self) -> None:
        buffer = MotionWindowBuffer()
        assert buffer.to_imu_window_data("never-seen") is None
        assert buffer.to_imu_window_data("never-seen", require_full=False) is None


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_one_device_keeps_others(self) -> None:
        buffer = MotionWindowBuffer(capacity=4)
        buffer.push("dev-A", {"accel_x": 0.0, "accel_y": 0.0, "accel_z": 1.0})
        buffer.push("dev-B", {"accel_x": 0.0, "accel_y": 0.0, "accel_z": 1.0})
        buffer.clear("dev-A")
        assert buffer.size("dev-A") == 0
        assert buffer.size("dev-B") == 1

    def test_clear_all_drops_every_device(self) -> None:
        buffer = MotionWindowBuffer()
        buffer.push("dev-A", {"accel_x": 0.0, "accel_y": 0.0, "accel_z": 1.0})
        buffer.push("dev-B", {"accel_x": 0.0, "accel_y": 0.0, "accel_z": 1.0})
        buffer.clear()
        assert buffer.size("dev-A") == 0
        assert buffer.size("dev-B") == 0
