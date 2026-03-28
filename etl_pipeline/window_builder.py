from __future__ import annotations

import math
from itertools import groupby
from typing import Any


def _accel_mag(sample: dict[str, float | None]) -> float | None:
    values = [value for value in sample.values() if value is not None]
    if len(values) != 3:
        return None
    return round(math.sqrt(sum(value * value for value in values)), 6)


def _resample_indices(length: int, target_length: int) -> list[int]:
    if length <= 1:
        return [0] * target_length
    return [round(index * (length - 1) / (target_length - 1)) for index in range(target_length)]


def _timestamp_sort_key(value: Any) -> tuple[int, float | str]:
    if value is None:
        return (2, "")
    if isinstance(value, float) and math.isnan(value):
        return (2, "")
    if isinstance(value, (int, float)):
        return (0, float(value))
    return (1, str(value))


def _sort_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value)


def build_motion_windows(
    rows: list[dict[str, Any]],
    *,
    target_length: int = 100,
    stride: int = 25,
) -> list[dict[str, Any]]:
    """Build fixed-length windows grouped by subject/dataset/activity/fall variant."""
    if not rows:
        return []

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            _sort_text(row.get("subject_id")),
            _sort_text(row.get("source_dataset")),
            _sort_text(row.get("activity_label")),
            _sort_text(row.get("fall_variant")),
            _timestamp_sort_key(row.get("timestamp")),
        ),
    )
    windows: list[dict[str, Any]] = []
    window_counter = 0

    group_key = lambda row: (
        row.get("subject_id"),
        row.get("source_dataset"),
        row.get("activity_label"),
        row.get("fall_variant"),
    )
    for key, grouped in groupby(sorted_rows, key=group_key):
        group_rows = list(grouped)
        if len(group_rows) < target_length:
            continue
        for start in range(0, len(group_rows) - target_length + 1, stride):
            raw_window = group_rows[start : start + target_length]
            indices = _resample_indices(len(raw_window), target_length)
            sampled = [raw_window[index] for index in indices]
            window_counter += 1
            windows.append(
                {
                    "window_id": f"window_{window_counter:06d}",
                    "subject_id": key[0],
                    "dataset": key[1],
                    "activity_label": key[2],
                    "fall_variant": key[3],
                    "start_ts": sampled[0]["timestamp"],
                    "end_ts": sampled[-1]["timestamp"],
                    "accel_x": [row["accel_mps2"]["x"] for row in sampled],
                    "accel_y": [row["accel_mps2"]["y"] for row in sampled],
                    "accel_z": [row["accel_mps2"]["z"] for row in sampled],
                    "gyro_x": [row["gyro_radps"]["x"] for row in sampled],
                    "gyro_y": [row["gyro_radps"]["y"] for row in sampled],
                    "gyro_z": [row["gyro_radps"]["z"] for row in sampled],
                    "accel_mag": [_accel_mag(row["accel_mps2"]) for row in sampled],
                    "metadata_extra": {
                        "raw_window_size": len(raw_window),
                        "resampled_to": target_length,
                    },
                }
            )
    return windows
