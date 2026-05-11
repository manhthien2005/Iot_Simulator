"""Pre-model trigger package — Threshold 1 rule engine for IoT Simulator.

This package evaluates vitals against configurable rules *before* sending
data to the ML risk model (Threshold 2 on Health Backend).  It produces
``TriggerActionItem`` instances that the ``SimulatorRuntime`` translates
into alerts, events, or model-call requests.

Architecture reference: plans/alert-threshold-architecture-plan.md §5.1
"""
from __future__ import annotations

from pre_model_trigger.fall_pre_trigger import FallPreTrigger
from pre_model_trigger.healthguard_client import HealthGuardAPIClient
from pre_model_trigger.normalization import normalize_vitals_for_rules, validate_data_quality
from pre_model_trigger.orchestrator import TriggerOrchestrator
from pre_model_trigger.response_handler import ResponseHandler
from pre_model_trigger.rule_engine import RuleEngine
from pre_model_trigger.settings_provider import (
    SystemSettingsProvider,
    _FALLBACK_DAYTIME,
    _FALLBACK_SLEEP,
)
from pre_model_trigger.types import PersonaProfile, TriggerActionItem
from pre_model_trigger.vitals_buffer import VitalsHistoryBuffer

__all__ = [
    "FallPreTrigger",
    "HealthGuardAPIClient",
    "PersonaProfile",
    "ResponseHandler",
    "RuleEngine",
    "SystemSettingsProvider",
    "TriggerActionItem",
    "TriggerOrchestrator",
    "VitalsHistoryBuffer",
    "normalize_vitals_for_rules",
    "validate_data_quality",
    "_FALLBACK_DAYTIME",
    "_FALLBACK_SLEEP",
]
