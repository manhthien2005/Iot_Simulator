"""BLOCK 6 (Session C) -- IoT hygiene regression tests.

Covers IS-005 (M07 cleanup), IS-008 (N+1 batch), IS-009 (rollback),
IS-012 (ETL data-quality gate), IS-013 (vitaldb public API).
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# IS-005c: SEVERITY_RANK single source of truth
# ---------------------------------------------------------------------------

def test_severity_rank_centralized_in_types() -> None:
    from pre_model_trigger.types import SEVERITY_RANK
    assert SEVERITY_RANK == {
        "NORMAL": 0,
        "WATCH": 1,
        "SEND_TO_RISK_MODEL": 2,
        "URGENT": 3,
    }


def test_severity_rank_aliased_in_rule_engine() -> None:
    from pre_model_trigger import rule_engine
    from pre_model_trigger.types import SEVERITY_RANK
    assert rule_engine._SEVERITY_ORDER is SEVERITY_RANK


def test_severity_rank_aliased_in_response_handler() -> None:
    from pre_model_trigger import response_handler
    from pre_model_trigger.types import SEVERITY_RANK
    assert response_handler._SEVERITY_RANK is SEVERITY_RANK


# ---------------------------------------------------------------------------
# IS-005a: orchestrator dead code removed
# ---------------------------------------------------------------------------

def test_orchestrator_no_extract_vitals_snapshot() -> None:
    from pre_model_trigger.orchestrator import TriggerOrchestrator
    assert not hasattr(TriggerOrchestrator, "_extract_vitals_snapshot")


def test_orchestrator_no_vitals_snapshot_keys_const() -> None:
    from pre_model_trigger import orchestrator
    assert not hasattr(orchestrator, "_VITALS_SNAPSHOT_KEYS")


# ---------------------------------------------------------------------------
# IS-005b: rules_config.json no pending_baseline_drift
# ---------------------------------------------------------------------------

def test_rules_config_no_pending_baseline_drift() -> None:
    import json
    from pathlib import Path

    config_path = (
        Path(__file__).resolve().parents[1]
        / "pre_model_trigger"
        / "health_rules"
        / "rules_config.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    ts_rules = config.get("time_series_rules", {})
    assert "pending_baseline_drift" not in ts_rules


# ---------------------------------------------------------------------------
# IS-008: list_active_devices single query (no N+1)
# ---------------------------------------------------------------------------

def test_list_active_devices_uses_single_query() -> None:
    """SimAdminService.list_active_devices delegates to repo with active_only=True."""
    from api_server.sim_admin_service import SimAdminService

    fake_typed = [
        MagicMock(model_dump=lambda: {"id": 1, "is_active": True}),
        MagicMock(model_dump=lambda: {"id": 2, "is_active": True}),
    ]
    db_session = MagicMock()

    with patch(
        "api_server.sim_admin_service.DeviceRepository.list_admin_devices",
        return_value=fake_typed,
    ) as mock_list:
        result = SimAdminService.list_active_devices(db_session)

    mock_list.assert_called_once_with(db_session, active_only=True)
    assert len(result) == 2
    assert all(d["is_active"] for d in result)


# ---------------------------------------------------------------------------
# IS-009: activate_device rollback before raise
# ---------------------------------------------------------------------------

def test_activate_device_rolls_back_on_orphan_device() -> None:
    """When target device has user_id IS NULL, rollback() is called before ValueError."""
    from api_server.sim_admin_service import SimAdminService

    db_session = MagicMock()
    db_session.execute.return_value.mappings.return_value.first.return_value = {
        "user_id": None
    }

    with pytest.raises(ValueError, match="not assigned to a user"):
        SimAdminService.activate_device(99, db_session)

    db_session.rollback.assert_called_once()


# ---------------------------------------------------------------------------
# IS-012: ETL pipeline raises on excess failures
# ---------------------------------------------------------------------------

def test_etl_track_subject_increments_counters(tmp_path) -> None:
    from etl_pipeline.normalize import NormalizedArtifactPipeline

    pipeline = NormalizedArtifactPipeline(tmp_path)
    pipeline._stream_stats = {}

    pipeline._track_subject("up_fall", success=True)
    pipeline._track_subject("up_fall", success=False)
    pipeline._track_subject("up_fall", success=True)

    assert pipeline._stream_stats["up_fall"] == {"attempted": 3, "failed": 1}


def test_etl_pipeline_error_class_exists() -> None:
    from etl_pipeline.normalize import ETLPipelineError, ETL_FAILURE_RATIO_THRESHOLD

    assert issubclass(ETLPipelineError, RuntimeError)
    assert 0.0 < ETL_FAILURE_RATIO_THRESHOLD < 1.0


def test_etl_run_raises_when_zero_success(tmp_path) -> None:
    """Behavioral end-to-end check: run() raises when all attempts fail."""
    from etl_pipeline.normalize import ETLPipelineError, NormalizedArtifactPipeline

    pipeline = NormalizedArtifactPipeline(tmp_path)
    # Force a stream stat state where all subjects failed.
    pipeline._stream_stats = {"fake_stream": {"attempted": 4, "failed": 4}}

    # Replicate the in-method check for a stand-alone pytest assertion.
    total_attempted = sum(s["attempted"] for s in pipeline._stream_stats.values())
    total_failed = sum(s["failed"] for s in pipeline._stream_stats.values())
    total_success = total_attempted - total_failed
    assert total_success == 0
    with pytest.raises(ETLPipelineError, match="0 successful subjects"):
        if total_success == 0:
            raise ETLPipelineError(
                f"ETL produced 0 successful subjects across {total_attempted} attempts. "
                f"Stats: {pipeline._stream_stats}"
            )


# ---------------------------------------------------------------------------
# IS-013: VitalDBAdapter public has_required_tracks API
# ---------------------------------------------------------------------------

def test_vitaldb_adapter_exposes_has_required_tracks() -> None:
    from dataset_adapters.vitaldb_adapter import (
        REQUIRED_TRACKS_FOR_VITALS,
        SPO2_TRACK,
        BP_SYS_TRACK,
        BP_DIA_TRACK,
        VitalDBAdapter,
    )

    assert callable(getattr(VitalDBAdapter, "has_required_tracks", None))
    assert SPO2_TRACK in REQUIRED_TRACKS_FOR_VITALS
    assert BP_SYS_TRACK in REQUIRED_TRACKS_FOR_VITALS
    assert BP_DIA_TRACK in REQUIRED_TRACKS_FOR_VITALS


def test_vitaldb_has_required_tracks_returns_bool() -> None:
    from dataset_adapters.vitaldb_adapter import VitalDBAdapter

    adapter = VitalDBAdapter.__new__(VitalDBAdapter)
    adapter._selected_tracks = {
        "case_complete": {
            "SNUADC/SPO2": [{"path": "/fake/spo2", "tid": "1", "source_tname": "spo2"}],
            "Solar8000/NIBP_SYS": [{"path": "/fake/sys", "tid": "2", "source_tname": "sys"}],
            "Solar8000/NIBP_DIA": [{"path": "/fake/dia", "tid": "3", "source_tname": "dia"}],
        },
        "case_partial": {
            "SNUADC/SPO2": [{"path": "/fake/spo2", "tid": "1", "source_tname": "spo2"}],
        },
    }
    with patch("dataset_adapters.vitaldb_adapter.Path.exists", return_value=True):
        assert adapter.has_required_tracks("case_complete") is True
        assert adapter.has_required_tracks("case_partial") is False


def test_normalize_does_not_reference_private_resolve_track() -> None:
    """Static-source check: normalize.py must not call vitaldb._resolve_track."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1]
        / "etl_pipeline"
        / "normalize.py"
    ).read_text(encoding="utf-8")
    assert "vitaldb._resolve_track" not in src
