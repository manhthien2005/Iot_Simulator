"""Shared data types for the pre-model trigger package.

These dataclasses are the *contract* between ``TriggerOrchestrator`` and the
``SimulatorRuntime`` in ``api_server/dependencies.py``.  Keep them minimal
and serialisation-friendly (no ORM models, no heavy deps).
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# PersonaProfile — user profile snapshot for rule evaluation
# ---------------------------------------------------------------------------

@dataclass
class PersonaProfile:
    """Lightweight user profile consumed by the rule engine.

    Constructed by ``SimulatorRuntime._get_trigger_persona()`` from the
    device's ``persona_config`` dict.
    """

    age: int = 35
    gender: str = "unknown"
    weight_kg: float = 70.0
    height_cm: float = 170.0
    medical_conditions: list[str] = field(default_factory=list)

    # -- derived helpers --------------------------------------------------

    @property
    def bmi(self) -> float:
        """Body-mass index (kg / m²)."""
        height_m = self.height_cm / 100.0
        if height_m <= 0:
            return 0.0
        return self.weight_kg / (height_m * height_m)

    @property
    def is_elderly(self) -> bool:
        return self.age >= 65

    @property
    def is_high_sensitivity(self) -> bool:
        """True when profile-based rules should tighten thresholds."""
        if self.is_elderly:
            return True
        bmi = self.bmi
        if bmi < 18.5 or bmi >= 25:
            return True
        return False


# ---------------------------------------------------------------------------
# TriggerActionItem — output of evaluate_tick / force_health_prediction
# ---------------------------------------------------------------------------

@dataclass
class TriggerActionItem:
    """A single action produced by the trigger engine.

    ``action_type`` determines how ``SimulatorRuntime`` interprets this:
    * ``"alert"``  → create a ``PendingAlertCall``
    * ``"model_call"`` → request ML inference from Health Backend
    * ``"log"``    → publish to device log only (no user-facing action)

    ``severity`` uses the same vocabulary as the simulator event system:
    ``"normal"`` | ``"warning"`` | ``"critical"`` | ``"urgent"``
    """

    action_type: str  # "alert" | "model_call" | "log"
    severity: str = "normal"
    message: str = ""
    source: str | None = None  # e.g. "rule_engine", "fall_pre_trigger"
    metadata: dict[str, str] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# SEVERITY_RANK — single source of truth for severity ordering
# ---------------------------------------------------------------------------
# Higher rank = more severe. Consumed by both `rule_engine` (for sorting
# evaluate() output) and `response_handler` (for dedup keep-highest logic).
# IS-005c cleanup: previously duplicated as `_SEVERITY_ORDER` in rule_engine
# and `_SEVERITY_RANK` in response_handler — drift risk if levels change.
SEVERITY_RANK: dict[str, int] = {
    "NORMAL": 0,
    "WATCH": 1,
    "SEND_TO_RISK_MODEL": 2,
    "URGENT": 3,
}
