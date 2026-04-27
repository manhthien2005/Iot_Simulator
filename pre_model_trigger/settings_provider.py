"""Vitals threshold settings provider for the pre-model trigger system.

Exports two module-level fallback dictionaries (``_FALLBACK_DAYTIME`` and
``_FALLBACK_SLEEP``) that ``dependencies.py`` imports as the single source
of truth for hard-coded threshold defaults.  The ``SystemSettingsProvider``
class wraps these fallbacks and exposes ``get_vitals_thresholds()`` which
the ``TriggerOrchestrator`` calls on every tick.

Architecture reference: plans/alert-threshold-architecture-plan.md §5.1
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Fallback threshold dictionaries — single source of truth
# ---------------------------------------------------------------------------
# Keys follow the naming convention used throughout dependencies.py:
#   hr_critical_low, hr_critical_high, hr_warning_low, hr_warning_high,
#   spo2_critical, spo2_warning, rr_critical_low, rr_critical_high,
#   bp_sys_critical, bp_dia_critical, bp_sys_warning, bp_dia_warning
# Sleep adds: osa_alert_spo2_threshold, nocturnal_tachy_hr, apnea_rr_threshold

_FALLBACK_DAYTIME: dict[str, float] = {
    "hr_critical_low": 50.0,
    "hr_critical_high": 120.0,
    "hr_warning_low": 55.0,
    "hr_warning_high": 110.0,
    "spo2_critical": 90.0,
    "spo2_warning": 94.0,
    "rr_critical_low": 10.0,
    "rr_critical_high": 25.0,
    "bp_sys_critical": 180.0,
    "bp_dia_critical": 120.0,
    "bp_sys_warning": 140.0,
    "bp_dia_warning": 90.0,
}

_FALLBACK_SLEEP: dict[str, float] = {
    "hr_critical_low": 38.0,
    "hr_critical_high": 100.0,
    "hr_warning_low": 42.0,
    "hr_warning_high": 90.0,
    "spo2_critical": 85.0,
    "spo2_warning": 90.0,
    "rr_critical_low": 6.0,
    "rr_critical_high": 25.0,
    "bp_sys_critical": 180.0,
    "bp_dia_critical": 120.0,
    "bp_sys_warning": 160.0,
    "bp_dia_warning": 100.0,
    "osa_alert_spo2_threshold": 88.0,
    "nocturnal_tachy_hr": 120.0,
    "apnea_rr_threshold": 6.0,
}


class SystemSettingsProvider:
    """Provides vitals threshold settings to the trigger pipeline.

    On construction the provider starts with the built-in fallback
    dictionaries.  Call ``update_overrides`` to inject thresholds
    fetched from an external source (e.g. the Health Backend DB).

    Usage in ``dependencies.py``::

        settings_provider = SystemSettingsProvider()
        thresholds = settings_provider.get_vitals_thresholds(is_sleeping=False)
    """

    def __init__(self) -> None:
        self._daytime: dict[str, float] = dict(_FALLBACK_DAYTIME)
        self._sleep: dict[str, float] = dict(_FALLBACK_SLEEP)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_vitals_thresholds(self, *, is_sleeping: bool = False) -> dict[str, float]:
        """Return the active threshold dict for the given context.

        Parameters
        ----------
        is_sleeping:
            When ``True`` return sleep-specific thresholds (wider ranges,
            additional OSA / apnea keys).

        Returns
        -------
        dict[str, float]
            A **copy** of the internal threshold dict so callers cannot
            mutate provider state.
        """
        source = self._sleep if is_sleeping else self._daytime
        return dict(source)

    def update_overrides(self, overrides: dict[str, Any], *, is_sleeping: bool = False) -> None:
        """Merge caller-supplied overrides into the active threshold set.

        Only keys already present in the fallback dict are accepted;
        unknown keys are silently ignored to prevent typo-induced bugs.

        Parameters
        ----------
        overrides:
            Mapping of threshold key → new value.  Values are coerced to
            ``float``; non-numeric values are skipped.
        is_sleeping:
            Target the sleep threshold set when ``True``.
        """
        target = self._sleep if is_sleeping else self._daytime
        for key, value in overrides.items():
            if key not in target:
                continue
            try:
                target[key] = float(value)
            except (TypeError, ValueError):
                continue

    def reset(self) -> None:
        """Restore both threshold sets to built-in fallbacks."""
        self._daytime = dict(_FALLBACK_DAYTIME)
        self._sleep = dict(_FALLBACK_SLEEP)


__all__ = [
    "_FALLBACK_DAYTIME",
    "_FALLBACK_SLEEP",
    "SystemSettingsProvider",
]
