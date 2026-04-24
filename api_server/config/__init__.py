"""Utility helpers for loading configuration files."""

from __future__ import annotations

import operator
from pathlib import Path
from typing import Any, Callable

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent

# ── Operator mapping for structured filter criteria ──────────────────
_OPS: dict[str, Callable[[Any, Any], bool]] = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
}


def _build_filter(criteria: dict[str, Any] | None) -> Callable[[dict], bool] | None:
    """Convert a structured *filter_criteria* dict into a callable predicate.

    Returns ``None`` when *criteria* is ``None`` (no filtering desired).
    """
    if criteria is None:
        return None

    combine = criteria.get("combine", "and")
    conditions = criteria.get("conditions", [])
    if not conditions:
        return None

    def _predicate(session: dict[str, Any]) -> bool:
        summary = session.get("summary") or {}
        results: list[bool] = []
        for cond in conditions:
            field_val = summary.get(cond["field"], cond.get("default", 0))
            op_fn = _OPS.get(cond["op"])
            if op_fn is None:
                results.append(True)
                continue
            results.append(op_fn(field_val, cond["value"]))
        if combine == "or":
            return any(results)
        return all(results)

    return _predicate


# ── Public loader ────────────────────────────────────────────────────

def load_sleep_scenarios(
    *,
    yaml_path: str | Path | None = None,
) -> tuple[dict[str, list[tuple[str, int]]], dict[str, dict[str, Any]]]:
    """Load sleep scenario phases and profiles from a YAML config file.

    Returns
    -------
    (SLEEP_SCENARIO_PHASES, SLEEP_SCENARIO_PROFILES)
        * ``SLEEP_SCENARIO_PHASES`` – ``dict[str, list[tuple[str, int]]]``
        * ``SLEEP_SCENARIO_PROFILES`` – ``dict[str, dict[str, Any]]``
          with a ``"filter"`` key holding a callable or ``None``.
    """
    if yaml_path is None:
        yaml_path = _CONFIG_DIR / "sleep_scenarios.yaml"
    else:
        yaml_path = Path(yaml_path)

    with open(yaml_path, encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh)

    # ── phases ───────────────────────────────────────────────────────
    phases: dict[str, list[tuple[str, int]]] = {}
    for scenario_id, entries in (raw.get("sleep_scenario_phases") or {}).items():
        phases[scenario_id] = [(str(e[0]), int(e[1])) for e in entries]

    # ── profiles ─────────────────────────────────────────────────────
    profiles: dict[str, dict[str, Any]] = {}
    for scenario_id, prof in (raw.get("sleep_scenario_profiles") or {}).items():
        profiles[scenario_id] = {
            "filter": _build_filter(prof.get("filter_criteria")),
            "stats_override": prof.get("stats_override"),
            "phases_pattern_override": prof.get("phases_pattern_override"),
            "disorder_tags": list(prof.get("disorder_tags") or []),
            "description": str(prof.get("description") or ""),
        }

    return phases, profiles
