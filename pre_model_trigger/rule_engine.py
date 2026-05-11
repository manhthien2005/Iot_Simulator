"""Rule engine that evaluates vitals against ``rules_config.json``.

The ``RuleEngine`` loads the JSON rule configuration at init time and
provides an ``evaluate()`` method that checks a single vitals snapshot
against instant rules, profile-adjusted rules, and (when history is
available) time-series rules.  Each violated rule produces a
``TriggerActionItem``.

Architecture reference: plans/alert-threshold-architecture-plan.md §5.1
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pre_model_trigger.settings_provider import SystemSettingsProvider
from pre_model_trigger.types import PersonaProfile, TriggerActionItem

logger = logging.getLogger(__name__)

# Severity ordering (higher = more severe)
_SEVERITY_ORDER: dict[str, int] = {
    "NORMAL": 0,
    "WATCH": 1,
    "SEND_TO_RISK_MODEL": 2,
    "URGENT": 3,
}

_CONFIG_PATH = Path(__file__).parent / "health_rules" / "rules_config.json"


def _load_rules_config() -> dict[str, Any]:
    """Load and parse the JSON rule configuration file."""
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[no-any-return]
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load rules_config.json: %s — using empty config", exc)
        return {}


def _safe_float(value: Any) -> float | None:
    """Coerce *value* to float or return ``None``."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Regex for a single comparison: ``<number|metric> <op> <number|metric>``
_CMP_RE = re.compile(
    r"(-?\d+(?:\.\d+)?|[a-z_][a-z_0-9]*)\s*(<=|>=|<|>|==|!=)\s*(-?\d+(?:\.\d+)?|[a-z_][a-z_0-9]*)"
)

_OPS: dict[str, Any] = {
    "<": float.__lt__,
    ">": float.__gt__,
    "<=": float.__le__,
    ">=": float.__ge__,
    "==": float.__eq__,
    "!=": float.__ne__,
}

# Mapping from profile-escalation output reason_code → source instant reason_code.
# Used by _apply_profile_adjustments to match actions by their actual reason_code
# rather than the profile-specific output code.
_PROFILE_ESCALATION_SOURCE_MAP: dict[str, str] = {
    "PROFILE_ESCALATED_HR_BORDERLINE": "HR_BORDERLINE_HIGH",
    "PROFILE_ESCALATED_RR_BORDERLINE": "RR_BORDERLINE_HIGH",
    "PROFILE_ESCALATED_DBP_BORDERLINE": "DBP_BORDERLINE_HIGH",
    "PROFILE_ESCALATED_SBP_BORDERLINE": "SBP_BORDERLINE_HIGH",
    "PROFILE_ESCALATED_SPO2_DROP": "SPO2_BORDERLINE_LOW",
}


def _eval_single_cmp(left_raw: str, op: str, right_raw: str, value: float) -> bool:
    """Evaluate one comparison, substituting *value* for any non-numeric token."""
    left_f = _safe_float(left_raw)
    right_f = _safe_float(right_raw)
    left = left_f if left_f is not None else value
    right = right_f if right_f is not None else value
    cmp_fn = _OPS.get(op)
    if cmp_fn is None:
        return False
    return bool(cmp_fn(left, right))


def _eval_multi_metric_condition(condition_str: str, vitals: dict[str, Any]) -> bool:
    """Evaluate a multi-metric condition expression against a vitals snapshot.

    Unlike ``_check_condition`` which operates on a single pre-resolved
    metric value, this function resolves *both* sides of every comparison
    from the *vitals* dict, enabling combination rules such as::

        "heart_rate > 100 and resp_rate >= 20"
        "spo2 <= 94 and resp_rate >= 20"
    """
    parts = [p.strip() for p in condition_str.split(" and ")]
    for part in parts:
        match = _CMP_RE.match(part)
        if match is None:
            logger.warning("Unparseable combination condition fragment: %r", part)
            return False
        left_raw, op, right_raw = match.group(1), match.group(2), match.group(3)

        left_f = _safe_float(left_raw)
        if left_f is None:
            left_f = _safe_float(vitals.get(left_raw))

        right_f = _safe_float(right_raw)
        if right_f is None:
            right_f = _safe_float(vitals.get(right_raw))

        if left_f is None or right_f is None:
            return False

        cmp_fn = _OPS.get(op)
        if cmp_fn is None:
            return False
        if not cmp_fn(left_f, right_f):
            return False
    return True


def _check_condition(value: float, condition: dict[str, Any]) -> bool:
    """Return ``True`` when *value* satisfies the condition dict.

    Supports two formats:

    1. **String expression** (``"condition"`` key) — parsed from
       ``rules_config.json``.  Examples:
       - ``"heart_rate <= 40"``
       - ``"41 <= heart_rate and heart_rate <= 50"``
       - ``"spo2 == 95"``

    2. **Structured keys** ``lt``, ``gt``, ``lte``, ``gte`` — kept for
       backward compatibility / programmatic use.
    """
    # --- Format 1: string condition expression ---
    expr = condition.get("condition")
    if isinstance(expr, str):
        parts = [p.strip() for p in expr.split(" and ")]
        for part in parts:
            match = _CMP_RE.match(part)
            if match is None:
                logger.warning("Unparseable condition fragment: %r", part)
                return False
            if not _eval_single_cmp(match.group(1), match.group(2), match.group(3), value):
                return False
        return True

    # --- Format 2: structured lt/gt/lte/gte keys (backward compat) ---
    lt = _safe_float(condition.get("lt"))
    gt = _safe_float(condition.get("gt"))
    lte = _safe_float(condition.get("lte"))
    gte = _safe_float(condition.get("gte"))

    has_any = lt is not None or gt is not None or lte is not None or gte is not None
    if not has_any:
        return False

    if lt is not None and not (value < lt):
        return False
    if gt is not None and not (value > gt):
        return False
    if lte is not None and not (value <= lte):
        return False
    if gte is not None and not (value >= gte):
        return False
    return True


class RuleEngine:
    """Evaluates vitals against the declarative rules in ``rules_config.json``.

    Parameters
    ----------
    settings_provider:
        Used to obtain runtime threshold overrides (currently reserved
        for future use — instant rules come from the JSON config).

    Usage in ``dependencies.py``::

        rule_engine = RuleEngine(settings_provider=settings_provider)
    """

    def __init__(self, *, settings_provider: SystemSettingsProvider) -> None:
        self._settings = settings_provider
        self._config = _load_rules_config()
        self._instant_rules: dict[str, Any] = self._config.get("instant_rules", {})
        self._profile_rules: dict[str, Any] = self._config.get("profile_adjusted_rules", {})
        self._severity_order: dict[str, int] = self._config.get("severity", {}).get("order", _SEVERITY_ORDER)
        self._source_to_profile: dict[str, str] = self._build_source_to_profile_map()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        vitals: dict[str, Any],
        persona: PersonaProfile | None = None,
        *,
        history: list[dict[str, Any]] | None = None,
    ) -> list[TriggerActionItem]:
        """Evaluate *vitals* against all configured rules.

        Parameters
        ----------
        vitals:
            Current vitals snapshot (keys: ``heart_rate``, ``spo2``,
            ``resp_rate``, ``body_temp``, ``sys_bp``, ``dia_bp``, etc.).
        persona:
            Optional patient profile for profile-adjusted rule escalation.
        history:
            Optional list of previous vitals for time-series rules.

        Returns
        -------
        list[TriggerActionItem]
            Actions produced by violated rules, sorted by severity
            (most severe first).
        """
        actions: list[TriggerActionItem] = []

        # Phase 1: instant rules
        actions.extend(self._evaluate_instant_rules(vitals))

        # Phase 2: profile-adjusted escalation
        if persona is not None:
            actions = self._apply_profile_adjustments(actions, persona)

        # Phase 3: time-series rules (if history available)
        if history:
            actions.extend(self._evaluate_time_series_rules(vitals, history))

        # Phase 4: combination rules (Fix #5)
        actions.extend(self._evaluate_combination_rules(vitals))

        # Sort by severity descending
        actions.sort(
            key=lambda a: self._severity_order.get(a.severity.upper(), 0),
            reverse=True,
        )
        return actions

    # ------------------------------------------------------------------
    # Instant rules
    # ------------------------------------------------------------------

    def _evaluate_instant_rules(self, vitals: dict[str, Any]) -> list[TriggerActionItem]:
        """Check each vital metric against its instant rule thresholds."""
        actions: list[TriggerActionItem] = []

        for metric, severity_groups in self._instant_rules.items():
            raw_value = _safe_float(vitals.get(metric))
            if raw_value is None:
                continue

            # Evaluate severity levels from highest to lowest
            for severity_key in ("urgent", "send_to_risk_model", "watch"):
                conditions = severity_groups.get(severity_key, [])
                for cond in conditions:
                    if _check_condition(raw_value, cond):
                        reason_code = cond.get("reason_code", f"{metric}_{severity_key}")
                        action_type = "alert" if severity_key == "urgent" else "model_call"
                        actions.append(TriggerActionItem(
                            action_type=action_type,
                            severity=severity_key.upper(),
                            message=f"{metric}={raw_value:.1f} triggered {severity_key} rule",
                            source="rule_engine",
                            metadata={"metric": metric, "value": str(raw_value)},
                            reason_codes=[reason_code],
                        ))
                        break  # Only highest matching severity per metric

                else:
                    continue
                break  # Exit outer loop once a match is found for this metric

        return actions

    # ------------------------------------------------------------------
    # Profile-adjusted escalation
    # ------------------------------------------------------------------

    def _apply_profile_adjustments(
        self,
        actions: list[TriggerActionItem],
        persona: PersonaProfile,
    ) -> list[TriggerActionItem]:
        """Escalate WATCH → SEND_TO_RISK_MODEL for high-sensitivity profiles.

        Fix #6: uses _PROFILE_ESCALATION_SOURCE_MAP to match actions by their
        *instant rule* reason_code (e.g. HR_BORDERLINE_HIGH) rather than the
        profile output reason_code (e.g. PROFILE_ESCALATED_HR_BORDERLINE) which
        was never present in action.reason_codes.
        """
        if not persona.is_high_sensitivity:
            return actions

        result: list[TriggerActionItem] = []
        for action in actions:
            if action.severity == "WATCH":
                matched_profiles = [
                    self._source_to_profile[rc]
                    for rc in action.reason_codes
                    if rc in self._source_to_profile
                ]
                if matched_profiles:
                    result.append(TriggerActionItem(
                        action_type="model_call",
                        severity="SEND_TO_RISK_MODEL",
                        message=f"{action.message} (escalated: high-sensitivity profile)",
                        source="rule_engine",
                        metadata={**action.metadata, "escalated_from": "WATCH"},
                        reason_codes=action.reason_codes + matched_profiles,
                    ))
                    continue
            result.append(action)

        return result

    # ------------------------------------------------------------------
    # Time-series rules (stub — evaluates persistent drift)
    # ------------------------------------------------------------------

    def _evaluate_time_series_rules(
        self,
        current: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> list[TriggerActionItem]:
        """Evaluate time-series rules using vitals history.

        Currently implements a simplified persistent-drift check:
        if the last N readings all breach a threshold, escalate.
        """
        actions: list[TriggerActionItem] = []
        ts_config = self._config.get("time_series_rules", {})
        drift_rules = ts_config.get("persistent_drift", {})

        for severity_key in ("send_to_risk_model", "watch"):
            conditions = drift_rules.get(severity_key, [])
            for cond in conditions:
                metric = cond.get("metric", "")
                window = cond.get("window", 5)
                direction = cond.get("direction", "")
                threshold = _safe_float(cond.get("threshold"))

                if not metric or threshold is None or not direction:
                    continue

                # Gather recent values for this metric
                recent = []
                for snap in history[-window:]:
                    val = _safe_float(snap.get(metric))
                    if val is not None:
                        recent.append(val)

                if len(recent) < max(2, window // 2):
                    continue  # Not enough data

                # Check if all recent values breach in the specified direction
                # Fix #4: added above_eq / below_eq direction support
                breached = False
                if direction == "above":
                    breached = all(v > threshold for v in recent)
                elif direction == "above_eq":
                    breached = all(v >= threshold for v in recent)
                elif direction == "below":
                    breached = all(v < threshold for v in recent)
                elif direction == "below_eq":
                    breached = all(v <= threshold for v in recent)

                if breached:
                    reason_code = cond.get("reason_code", f"drift_{metric}_{severity_key}")
                    actions.append(TriggerActionItem(
                        action_type="model_call",
                        severity=severity_key.upper(),
                        message=f"{metric} persistently {direction} {threshold} for {len(recent)} ticks",
                        source="rule_engine",
                        metadata={"metric": metric, "window": str(len(recent))},
                        reason_codes=[reason_code],
                    ))

        return actions

    # ------------------------------------------------------------------
    # Combination rules (Fix #5)
    # ------------------------------------------------------------------

    def _evaluate_combination_rules(self, vitals: dict[str, Any]) -> list[TriggerActionItem]:
        """Evaluate multi-metric combination rules from ``rules_config.json``.

        Handles conditions such as::

            "heart_rate > 100 and resp_rate >= 20"
            "spo2 <= 94 and resp_rate >= 20"

        These rules are escalation-only: they can only add actions at the
        configured severity, never downgrade existing actions.
        """
        actions: list[TriggerActionItem] = []
        combo_config = self._config.get("combination_rules", {})

        if not combo_config.get("enabled", False):
            return actions

        for severity_key in ("urgent", "send_to_risk_model", "watch"):
            for rule in combo_config.get(severity_key, []):
                condition_str = rule.get("condition", "")
                if not condition_str:
                    continue
                reason_code = rule.get("reason_code", f"combo_{severity_key}")
                if _eval_multi_metric_condition(condition_str, vitals):
                    action_type = "alert" if severity_key == "urgent" else "model_call"
                    actions.append(TriggerActionItem(
                        action_type=action_type,
                        severity=severity_key.upper(),
                        message=f"Combination rule triggered: {reason_code}",
                        source="rule_engine",
                        metadata={"condition": condition_str, "metric": reason_code},
                        reason_codes=[reason_code],
                    ))

        return actions

    def _build_source_to_profile_map(self) -> dict[str, str]:
        """Build the source_instant_code -> profile_output_code reverse map."""
        result: dict[str, str] = {}
        escalation_rules = self._profile_rules.get("watch_to_send_if_profile_high_sensitivity", [])
        for rule in escalation_rules:
            profile_code = rule.get("reason_code", "")
            if profile_code and profile_code in _PROFILE_ESCALATION_SOURCE_MAP:
                source_code = _PROFILE_ESCALATION_SOURCE_MAP[profile_code]
                result[source_code] = profile_code
        return result

    def reload_config(self) -> None:
        """Hot-reload the rules configuration from disk."""
        self._config = _load_rules_config()
        self._instant_rules = self._config.get("instant_rules", {})
        self._profile_rules = self._config.get("profile_adjusted_rules", {})
        self._severity_order = self._config.get("severity", {}).get("order", _SEVERITY_ORDER)
        self._source_to_profile = self._build_source_to_profile_map()


__all__ = ["RuleEngine"]
