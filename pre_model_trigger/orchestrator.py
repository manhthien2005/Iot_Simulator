"""Trigger orchestrator — central coordinator for pre-model evaluation.

Aggregates results from :class:`RuleEngine`, :class:`FallPreTrigger`, and
optionally the :class:`HealthGuardAPIClient`, then post-processes via
:class:`ResponseHandler` before returning ``list[TriggerActionItem]`` to
the caller (``SimulatorRuntime``).

Architecture reference: plans/alert-threshold-architecture-plan.md §5.1
"""
from __future__ import annotations

import logging
from typing import Any, Sequence

from pre_model_trigger.fall_pre_trigger import FallPreTrigger
from pre_model_trigger.healthguard_client import HealthGuardAPIClient
from pre_model_trigger.normalization import (
    available_metrics,
    normalize_vitals_for_rules,
    validate_data_quality,
)
from pre_model_trigger.response_handler import ResponseHandler
from pre_model_trigger.rule_engine import RuleEngine
from pre_model_trigger.settings_provider import SystemSettingsProvider
from pre_model_trigger.types import PersonaProfile, TriggerActionItem
from pre_model_trigger.vitals_buffer import VitalsHistoryBuffer

logger = logging.getLogger(__name__)

# Severity values that qualify an action for model escalation.
_MODEL_ESCALATION_SEVERITIES: frozenset[str] = frozenset({
    "SEND_TO_RISK_MODEL",
    "URGENT",
})


class TriggerOrchestrator:
    """Coordinate pre-model trigger evaluation across all sub-engines.

    Parameters
    ----------
    settings_provider:
        Provides vitals thresholds (DB-backed with fallbacks).
    rule_engine:
        Evaluates instant / profile / time-series rules from ``rules_config.json``.
    fall_pre_trigger:
        Stage-1 fall detection from ``fall_pipeline_wrist_config.json``.
    api_client:
        HTTP client for requesting ML predictions from Health Backend.
    response_handler:
        **Class** (not instance) with static post-processing methods.
    vitals_buffer:
        Per-device ring buffer for time-series evaluation.
    enable_model_calls:
        When *True*, actions with ``severity >= SEND_TO_RISK_MODEL`` trigger
        an HTTP call to Health Backend for ML prediction.  When *False*
        (shadow mode), only local rule evaluation runs.
    """

    def __init__(
        self,
        *,
        settings_provider: SystemSettingsProvider,
        rule_engine: RuleEngine,
        fall_pre_trigger: FallPreTrigger,
        api_client: HealthGuardAPIClient,
        response_handler: type[ResponseHandler],
        vitals_buffer: VitalsHistoryBuffer,
        enable_model_calls: bool = False,
    ) -> None:
        self._settings = settings_provider
        self._rule_engine = rule_engine
        self._fall_pre_trigger = fall_pre_trigger
        self._api_client = api_client
        self._response_handler = response_handler
        self._vitals_buffer = vitals_buffer
        self._enable_model_calls = enable_model_calls

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_tick(
        self,
        device_id: str,
        vitals: dict[str, Any],
        motion: dict[str, Any] | None,
        state: dict[str, Any],
        persona: PersonaProfile,
    ) -> list[TriggerActionItem]:
        """Run the full pre-model evaluation pipeline for one tick.

        1. Push vitals into the per-device ring buffer.
        2. Evaluate vitals rules (instant + profile + time-series).
        3. Evaluate fall pre-trigger (if motion data present).
        4. If any action reaches SEND_TO_RISK_MODEL / URGENT and
           ``enable_model_calls`` is *True*, request ML prediction.
        5. Post-process via ``ResponseHandler``.

        Returns
        -------
        list[TriggerActionItem]
            Actionable items sorted by severity (most urgent first).
        """
        # Step 0 — normalize field names and compute derived metrics (Fix #1 #2)
        normalized_vitals = normalize_vitals_for_rules(vitals)

        # Step 0b — data quality gate (Fix #3, P0-5 relaxed 2026-05-18).
        # ``validate_data_quality`` now flips ``is_valid`` only on FATAL
        # issues: missing both critical fields (HR + SpO2), non-numeric
        # values, sensor_error_flag, or signal-quality below threshold.
        # Soft-field absences (BP/temp/RR) are reported in errors but
        # ``is_valid`` stays True, and the rule engine skips per-metric
        # via :func:`available_metrics` instead of dropping every rule.
        _dq_ok, _dq_errors = validate_data_quality(normalized_vitals)
        present_metrics = available_metrics(normalized_vitals)
        if not _dq_ok:
            logger.warning(
                "Data quality gate SUPPRESSED vitals rules for device=%s errors=%s "
                "(fatal: missing both HR+SpO2 / non-numeric / sensor error / "
                "low signal quality). Soft-field absences alone no longer "
                "block evaluation — see P0-5.",
                device_id,
                _dq_errors,
            )
            actions: list[TriggerActionItem] = [
                TriggerActionItem(
                    action_type="log",
                    severity="normal",
                    message=f"Data quality check failed: {', '.join(_dq_errors)}",
                    source="orchestrator",
                    metadata={"device_id": device_id, "errors": str(_dq_errors)},
                )
            ]
            # Still evaluate fall trigger — motion-based, not vitals-dependent
            if motion is not None:
                fall_actions = self._fall_pre_trigger.evaluate(motion=motion)
                actions.extend(fall_actions)
            return self._response_handler.process(actions, device_id=device_id)

        # Log soft-field absences once per tick at INFO level so ops can
        # see how often partial vitals payloads arrive without polluting
        # WARN logs.
        if _dq_errors:
            logger.info(
                "Partial vitals tick for device=%s — evaluating rules on %s "
                "(soft-field absences: %s)",
                device_id,
                sorted(present_metrics),
                _dq_errors,
            )

        # Step 1 — buffer normalized vitals for time-series analysis
        self._vitals_buffer.push(device_id, normalized_vitals)
        history = self._vitals_buffer.get_history(device_id)

        # Step 2 — vitals rule evaluation
        actions = self._rule_engine.evaluate(
            vitals=normalized_vitals,
            persona=persona,
            history=history,
        )

        # Step 3 — fall pre-trigger (only when motion data is present)
        if motion is not None:
            fall_actions = self._fall_pre_trigger.evaluate(motion=motion)
            actions.extend(fall_actions)

        # Step 4 — optional model escalation
        if self._enable_model_calls and self._should_escalate_to_model(actions):
            model_actions = self._request_model_prediction(
                device_id=device_id,
                vitals=normalized_vitals,
                persona=persona,
            )
            actions.extend(model_actions)

        # Step 5 — post-process (dedup, filter, enrich, sort)
        return self._response_handler.process(actions, device_id=device_id)

    def force_health_prediction(
        self,
        device_id: str,
        vitals: dict[str, Any],
        persona: PersonaProfile,
    ) -> list[TriggerActionItem]:
        """Bypass rule evaluation and directly request ML prediction.

        Originally invoked by ``trigger_risk_calculation`` (disposed in
        ADR-020 Phase 7 S7). Currently retained for ad-hoc shadow-mode
        diagnostics — the production risk path now lives on the mobile
        BE auto-trigger after ``/telemetry/ingest``. Always calls the API
        regardless of ``enable_model_calls`` setting.
        """
        model_actions = self._request_model_prediction(
            device_id=device_id,
            vitals=vitals,
            persona=persona,
        )
        return self._response_handler.process(model_actions, device_id=device_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_escalate_to_model(self, actions: Sequence[TriggerActionItem]) -> bool:
        """Check if any action warrants sending data to the ML model."""
        return any(
            action.severity in _MODEL_ESCALATION_SEVERITIES
            for action in actions
        )

    def _request_model_prediction(
        self,
        device_id: str,
        vitals: dict[str, Any],
        persona: PersonaProfile,
    ) -> list[TriggerActionItem]:
        """Call the HealthGuard API for ML prediction, handling errors."""
        try:
            return self._api_client.request_prediction(
                device_id=device_id,
                vitals=vitals,
                persona=persona,
            )
        except Exception as exc:
            logger.warning(
                "Model prediction request failed for %s: %s",
                device_id,
                exc,
            )
            return [
                TriggerActionItem(
                    action_type="log",
                    severity="normal",
                    message=f"Model prediction failed: {exc}",
                    source="orchestrator",
                    metadata={"error": str(exc)},
                ),
            ]
