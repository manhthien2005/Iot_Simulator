"""Fall variant policy table — pure data, no side effects.

Maps each operator-injectable fall variant to a SOS countdown policy +
downstream alert behaviour. See SimulatorRuntime._resolve_fall_policy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FallVariantPolicy:
    countdown_sec: int
    auto_resolve: bool
    allows_cancel: bool
    device_state_on_inject: str   # one of DeviceStateValue
    push_alert: bool
    default_severity: str         # "normal" | "warning" | "critical"
    #: Simulated confidence floor for the alert webhook metadata.
    #: The HealthGuard backend gates SOS escalation on
    #: ``confidence >= FALL_CONFIDENCE_THRESHOLD`` (default 0.7).
    simulated_confidence: float


FALL_VARIANT_POLICIES: dict[str, FallVariantPolicy] = {
    "false_fall": FallVariantPolicy(
        countdown_sec=0,
        auto_resolve=False,
        allows_cancel=False,
        device_state_on_inject="streaming",
        push_alert=False,
        default_severity="normal",
        simulated_confidence=0.10,
    ),
    "slip_recovery": FallVariantPolicy(
        countdown_sec=0,
        auto_resolve=False,
        allows_cancel=False,
        device_state_on_inject="streaming",
        push_alert=False,
        default_severity="normal",
        simulated_confidence=0.20,
    ),
    "fall_brief": FallVariantPolicy(
        countdown_sec=10,
        auto_resolve=True,
        allows_cancel=True,
        device_state_on_inject="fall_countdown",
        push_alert=True,
        default_severity="warning",
        simulated_confidence=0.65,
    ),
    "fall_from_bed": FallVariantPolicy(
        countdown_sec=30,
        auto_resolve=False,
        allows_cancel=True,
        device_state_on_inject="fall_countdown",
        push_alert=True,
        default_severity="critical",
        simulated_confidence=0.85,
    ),
    "confirmed": FallVariantPolicy(
        countdown_sec=30,
        auto_resolve=False,
        allows_cancel=True,
        device_state_on_inject="fall_countdown",
        push_alert=True,
        default_severity="critical",
        simulated_confidence=0.95,
    ),
    "fall_no_response": FallVariantPolicy(
        countdown_sec=30,
        auto_resolve=False,
        allows_cancel=False,
        device_state_on_inject="fall_countdown",
        push_alert=True,
        default_severity="critical",
        simulated_confidence=0.99,
    ),
}

#: Default policy for unknown / legacy variants (backwards compat).
FALL_VARIANT_DEFAULT_POLICY: FallVariantPolicy = FALL_VARIANT_POLICIES["confirmed"]

FALL_VARIANT_TO_PERSONA: dict[str, str] = {
    "false_fall": "false_fall",
    "slip_recovery": "slip_recovery",
    "fall_brief": "fall_brief",
    "fall_from_bed": "fall_from_bed",
    "confirmed": "confirmed",
    "fall_no_response": "fall_no_response",
}
