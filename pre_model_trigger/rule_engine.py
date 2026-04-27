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
        """Escalate WATCH → SEND_TO_RISK_MODEL for high-sensitivity profiles."""
        if not persona.is_high_sensitivity:
            return actions

        escalation_rules = self._profile_rules.get("watch_to_send_if_profile_high_sensitivity", [])
        escalation_codes: set[str] = set()
        for rule in escalation_rules:
            code = rule.get("reason_code", "")
            if code:
                escalation_codes.add(code)

        result: list[TriggerActionItem] = []
        for action in actions:
            if (
                action.severity == "WATCH"
                and any(rc in escalation_codes for rc in action.reason_codes)
            ):
                # Escalate: create new action with higher severity
                result.append(TriggerActionItem(
                    action_type="model_call",
                    severity="SEND_TO_RISK_MODEL",
                    message=f"{action.message} (escalated: high-sensitivity profile)",
                    source="rule_engine",
                    metadata={**action.metadata, "escalated_from": "WATCH"},
                    reason_codes=action.reason_codes,
                ))
            else:
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
                if direction == "above" and all(v > threshold for v in recent):
                    reason_code = cond.get("reason_code", f"drift_{metric}_{severity_key}")
                    actions.append(TriggerActionItem(
                        action_type="model_call",
                        severity=severity_key.upper(),
                        message=f"{metric} persistently {direction} {threshold} for {len(recent)} ticks",
                        source="rule_engine",
                        metadata={"metric": metric, "window": str(len(recent))},
                        reason_codes=[reason_code],
                    ))
                elif direction == "below" and all(v < threshold for v in recent):
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

    def reload_config(self) -> None:
        """Hot-reload the rules configuration from disk."""
        self._config = _load_rules_config()
        self._instant_rules = self._config.get("instant_rules", {})
        self._profile_rules = self._config.get("profile_adjusted_rules", {})
        self._severity_order = self._config.get("severity", {}).get("order", _SEVERITY_ORDER)


__all__ = ["RuleEngine"]
