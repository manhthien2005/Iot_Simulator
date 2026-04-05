"""Tests for DatasetRegistry — validates data normalization, index building,
stress baseline computation, and helper methods.

Uses a temporary directory with fake artifacts to test logic without
requiring the real multi-GB datasets.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from Iot_Simulator.simulator_core.dataset_registry import DatasetRegistry, normalize_stress_state


# ---------------------------------------------------------------------------
# Helpers: Create temporary artifacts for testing
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Write records as JSONL file."""
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _create_test_artifacts(tmp_dir: Path) -> None:
    """Create minimal artifact files for DatasetRegistry to load."""

    # vitals_stream.jsonl
    vitals_records = [
        {
            "subject_id": "S001",
            "dataset": "TestDS",
            "heart_rate": 72.0,
            "spo2": 98.0,
            "temperature": 36.7,
            "blood_pressure_sys": 120.0,
            "blood_pressure_dia": 80.0,
            "activity_label": "resting",
            "timestamp": "2025-01-01T00:00:00Z",
        },
        {
            "subject_id": "S001",
            "dataset": "TestDS",
            "heart_rate": 95.0,
            "spo2": 97.0,
            "temperature": 37.0,
            "blood_pressure_sys": 130.0,
            "blood_pressure_dia": 85.0,
            "activity_label": "walking",
            "timestamp": "2025-01-01T00:01:00Z",
        },
        {
            "subject_id": "S002",
            "dataset": "VitalDB",
            "heart_rate": 68.0,
            "spo2": 99.0,
            "temperature": None,
            "blood_pressure_sys": 115.0,
            "blood_pressure_dia": 75.0,
            "activity_label": "resting",
            "timestamp": "2025-01-01T00:00:00Z",
        },
    ]
    _write_jsonl(tmp_dir / "vitals_stream.jsonl", vitals_records)

    # motion_windows.jsonl
    motion_records = [
        {
            "accel_x": [0.1, 0.2],
            "accel_y": [0.0, 0.1],
            "accel_z": [9.8, 9.8],
            "activity_label": "resting",
            "dataset": "UCI_HAR",
        },
        {
            "accel_x": [0.5, 8.5, -1.0],
            "accel_y": [0.2, -7.0, 1.0],
            "accel_z": [9.8, 2.0, 9.5],
            "activity_label": "fall",
            "fall_variant": "fall_1",
            "dataset": "SisFall",
        },
    ]
    _write_jsonl(tmp_dir / "motion_windows.jsonl", motion_records)

    # event_catalog.jsonl
    event_records = [
        {
            "event_type": "fall_detected",
            "fall_variant": "fall_1",
            "confidence": 0.95,
            "impact_g": 5.2,
            "dataset": "SisFall",
        },
        {
            "event_type": "fall_detected",
            "fall_variant": "fall_brief",
            "confidence": 0.45,
            "impact_g": 2.1,
            "dataset": "SisFall",
        },
    ]
    _write_jsonl(tmp_dir / "event_catalog.jsonl", event_records)

    # stress_stream.jsonl
    stress_records = [
        {"heart_rate": 70.0, "stress_state": "baseline"},
        {"heart_rate": 72.0, "stress_state": "neutral"},
        {"heart_rate": 74.0, "stress_state": "baseline"},
        {"heart_rate": 90.0, "stress_state": "stress"},
        {"heart_rate": 85.0, "stress_state": "stress"},
        {"heart_rate": 88.0, "stress_state": "amusement"},
    ]
    _write_jsonl(tmp_dir / "stress_stream.jsonl", stress_records)

    # respiration_stream.jsonl
    respiration_records = [
        {"respiration_rate": 16.0, "activity_label": "resting", "dataset": "BIDMC"},
        {"respiration_rate": 22.0, "activity_label": "walking", "dataset": "BIDMC"},
    ]
    _write_jsonl(tmp_dir / "respiration_stream.jsonl", respiration_records)


@pytest.fixture
def real_registry(tmp_path: Path) -> DatasetRegistry:
    """Create a DatasetRegistry backed by real temporary artifacts."""
    _create_test_artifacts(tmp_path)
    return DatasetRegistry(tmp_path)


# ---------------------------------------------------------------------------
# Tests: normalize_stress_state
# ---------------------------------------------------------------------------


class TestNormalizeStressState:
    """Verify stress state normalization logic."""

    def test_baseline_normalizes_to_neutral(self):
        assert normalize_stress_state("baseline") == "neutral"

    def test_rest_normalizes_to_neutral(self):
        assert normalize_stress_state("rest") == "neutral"

    def test_neutral_stays_neutral(self):
        assert normalize_stress_state("neutral") == "neutral"

    def test_stress_stays_stress(self):
        assert normalize_stress_state("stress") == "stress"

    def test_amusement_stays_amusement(self):
        assert normalize_stress_state("amusement") == "amusement"

    def test_none_returns_none(self):
        assert normalize_stress_state(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_stress_state("") is None

    def test_unknown_returns_none(self):
        assert normalize_stress_state("unknown_state") is None

    def test_case_insensitive(self):
        assert normalize_stress_state("STRESS") == "stress"
        assert normalize_stress_state("Baseline") == "neutral"


# ---------------------------------------------------------------------------
# Tests: DatasetRegistry initialization
# ---------------------------------------------------------------------------


class TestDatasetRegistryInit:
    """Verify registry initialization and error handling."""

    def test_raises_on_missing_directory(self):
        """Registry should raise FileNotFoundError for non-existent dir."""
        with pytest.raises(FileNotFoundError):
            DatasetRegistry("/nonexistent/path/to/artifacts")

    def test_loads_successfully_with_valid_artifacts(self, real_registry):
        """Registry should load without error from valid artifacts."""
        assert real_registry is not None
        assert real_registry.artifacts_dir.exists()


# ---------------------------------------------------------------------------
# Tests: Vitals baseline retrieval
# ---------------------------------------------------------------------------


class TestDatasetRegistryVitalsBaseline:
    """Verify vitals baseline retrieval logic."""

    def test_baseline_returns_dict(self, real_registry):
        """get_vitals_baseline should return a dict."""
        baseline = real_registry.get_vitals_baseline()
        assert isinstance(baseline, dict)

    def test_baseline_contains_heart_rate(self, real_registry):
        """Baseline should contain heart_rate field."""
        baseline = real_registry.get_vitals_baseline()
        assert "heart_rate" in baseline

    def test_baseline_activity_filter(self, real_registry):
        """Filtering by activity should return matching records."""
        resting = real_registry.get_vitals_baseline(activity="resting")
        assert resting is not None
        assert resting.get("activity_label") == "resting"

    def test_baseline_with_required_fields(self, real_registry):
        """Required fields filter should work."""
        result = real_registry.get_vitals_baseline(
            required_fields=("spo2", "blood_pressure_sys")
        )
        assert result is not None
        assert result.get("spo2") is not None
        assert result.get("blood_pressure_sys") is not None


# ---------------------------------------------------------------------------
# Tests: Motion windows
# ---------------------------------------------------------------------------


class TestDatasetRegistryMotionWindows:
    """Verify motion window retrieval."""

    def test_motion_windows_not_empty(self, real_registry):
        """get_motion_windows should return non-empty list."""
        windows = real_registry.get_motion_windows()
        assert len(windows) > 0

    def test_motion_windows_filter_by_activity(self, real_registry):
        """Filtering by activity should narrow results."""
        resting = real_registry.get_motion_windows(activity="resting")
        assert all(w.get("activity_label") == "resting" for w in resting)

    def test_motion_windows_fall_variant_filter(self, real_registry):
        """Filtering by fall_variant should return matching windows."""
        fall_windows = real_registry.get_motion_windows(fall_variant="fall_1")
        assert len(fall_windows) > 0
        assert all(w.get("fall_variant") == "fall_1" for w in fall_windows)

    def test_motion_window_has_accel_data(self, real_registry):
        """Each motion window should contain accelerometer data."""
        windows = real_registry.get_motion_windows()
        for w in windows:
            assert "accel_x" in w or "accel_y" in w or "accel_z" in w


# ---------------------------------------------------------------------------
# Tests: Fall events
# ---------------------------------------------------------------------------


class TestDatasetRegistryFallEvents:
    """Verify fall event retrieval."""

    def test_get_fall_event_by_variant(self, real_registry):
        """get_fall_event should return event for known variant."""
        event = real_registry.get_fall_event("fall_1")
        assert event is not None
        assert event["fall_variant"] == "fall_1"
        assert event["event_type"] == "fall_detected"

    def test_get_fall_event_unknown_variant(self, real_registry):
        """get_fall_event should return None for unknown variant."""
        event = real_registry.get_fall_event("nonexistent_variant")
        assert event is None

    def test_fall_event_has_confidence(self, real_registry):
        """Fall event should include confidence score."""
        event = real_registry.get_fall_event("fall_1")
        assert "confidence" in event
        assert 0.0 <= event["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Tests: Stress data
# ---------------------------------------------------------------------------


class TestDatasetRegistryStressData:
    """Verify stress data logic."""

    def test_has_stress_data(self, real_registry):
        """Registry with stress records should report has_stress_data=True."""
        assert real_registry.has_stress_data() is True

    def test_stress_source_real(self, real_registry):
        """stress_source should be 'real:WESAD' when stress data exists."""
        assert real_registry.stress_source() == "real:WESAD"

    def test_stress_baseline_mean_is_computed(self, real_registry):
        """Stress baseline mean should be computed from neutral records."""
        mean = real_registry.get_stress_baseline_mean()
        assert mean is not None
        # Our neutral records: 70.0, 72.0, 74.0 → mean = 72.0
        assert abs(mean - 72.0) < 0.01, f"Expected mean ~72.0, got {mean}"

    def test_stress_sample_returns_record(self, real_registry):
        """get_stress_sample should return a dict with heart_rate."""
        sample = real_registry.get_stress_sample("stress")
        assert sample is not None
        assert "heart_rate" in sample

    def test_stress_sample_returns_none_for_invalid(self, real_registry):
        """get_stress_sample should return None for invalid state."""
        sample = real_registry.get_stress_sample("invalid_state")
        assert sample is None


# ---------------------------------------------------------------------------
# Tests: Respiration data
# ---------------------------------------------------------------------------


class TestDatasetRegistryRespiration:
    """Verify respiration sample retrieval."""

    def test_respiration_sample_returns_value(self, real_registry):
        """get_respiration_sample should return a dict with rate."""
        sample = real_registry.get_respiration_sample()
        assert sample is not None
        assert "respiration_rate" in sample

    def test_respiration_sample_by_activity(self, real_registry):
        """Filtering by activity should work."""
        sample = real_registry.get_respiration_sample(activity="resting")
        assert sample is not None


# ---------------------------------------------------------------------------
# Tests: Vitals timeline / replay
# ---------------------------------------------------------------------------


class TestDatasetRegistryTimeline:
    """Verify timeline and replay cursor logic."""

    def test_vitals_timeline_returns_sorted(self, real_registry):
        """get_vitals_timeline should return records sorted by timestamp."""
        timeline = real_registry.get_vitals_timeline("S001", "TestDS")
        assert len(timeline) > 0
        timestamps = [r.get("timestamp", "") for r in timeline]
        assert timestamps == sorted(timestamps)

    def test_vitals_sample_at_wraps_around(self, real_registry):
        """get_vitals_sample_at should wrap around using modulo."""
        timeline = real_registry.get_vitals_timeline("S001", "TestDS")
        n = len(timeline)
        if n > 0:
            # Index beyond length should wrap
            sample_0 = real_registry.get_vitals_sample_at("S001", "TestDS", 0)
            sample_n = real_registry.get_vitals_sample_at("S001", "TestDS", n)
            assert sample_0 == sample_n  # wraps to same index

    def test_vitals_sample_at_empty_returns_none(self, real_registry):
        """get_vitals_sample_at should return None for nonexistent subject."""
        result = real_registry.get_vitals_sample_at("NONEXIST", "NODS", 0)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Activity normalization
# ---------------------------------------------------------------------------


class TestDatasetRegistryActivityNormalization:
    """Verify _normalize_activity helper."""

    def test_none_returns_none(self):
        assert DatasetRegistry._normalize_activity(None) is None

    def test_fall_keywords(self):
        """Anything containing 'fall' should normalize to 'fall'."""
        assert DatasetRegistry._normalize_activity("fall") == "fall"
        assert DatasetRegistry._normalize_activity("Fall Forward") == "fall"
        assert DatasetRegistry._normalize_activity("FALLING") == "fall"

    def test_lowercase_normalization(self):
        assert DatasetRegistry._normalize_activity("WALKING") == "walking"
        assert DatasetRegistry._normalize_activity("  Running  ") == "running"

    def test_resting_unchanged(self):
        assert DatasetRegistry._normalize_activity("resting") == "resting"


# ---------------------------------------------------------------------------
# Tests: Summary and status
# ---------------------------------------------------------------------------


class TestDatasetRegistrySummary:
    """Verify summary/status methods return correct structure."""

    def test_summary_contains_required_fields(self, real_registry):
        """summary() should contain all expected keys."""
        s = real_registry.summary()
        required_keys = [
            "motion_windows",
            "vitals_rows",
            "stress_rows",
            "respiration_rows",
            "events",
            "datasets",
            "activities",
            "event_types",
            "sleep_sessions",
            "stress_source",
        ]
        for key in required_keys:
            assert key in s, f"Missing key in summary: {key}"

    def test_summary_counts_are_correct(self, real_registry):
        """summary() counts should match artifact sizes."""
        s = real_registry.summary()
        assert s["vitals_rows"] == 3
        assert s["motion_windows"] == 2
        assert s["stress_rows"] == 6
        assert s["respiration_rows"] == 2
        assert s["events"] == 2

    def test_list_datasets(self, real_registry):
        """list_datasets should return sorted unique dataset names."""
        datasets = real_registry.list_datasets()
        assert isinstance(datasets, list)
        assert len(datasets) > 0
        assert datasets == sorted(datasets)
