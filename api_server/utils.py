"""Shared helper functions used across multiple api_server modules.

Centralised here (MEDIUM #7) to eliminate copy-paste duplication of
``_utc_now_iso``, ``_safe_float``, ``_coerce_date``, ``_normalize_gender``,
and ``_is_sleeping_state`` that previously existed in 2-6 modules each.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _safe_float(value: Any, default: float | None) -> float | None:
    """Convert *value* to float, returning *default* on failure / NaN / Inf."""
    try:
        cast = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(cast) or math.isinf(cast):
        return default
    return cast


def _coerce_date(value: Any) -> date | None:
    """Coerce *value* to a :class:`date`, returning ``None`` on failure."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _normalize_gender(value: Any) -> str | None:
    """Normalise a gender string to ``'male'`` / ``'female'`` or pass through."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"male", "m", "man", "nam"}:
        return "male"
    if normalized in {"female", "f", "woman", "nu", "nữ"}:
        return "female"
    return normalized


def _is_sleeping_state(activity_state: Any) -> bool:
    """Return ``True`` when the activity state represents sleep."""
    return str(activity_state or "").strip().lower() == "sleeping"


def _derive_age(value: Any, default: int = 35) -> int:
    """Derive age in years from a date-of-birth value, falling back to *default*."""
    dob = _coerce_date(value)
    if dob is None:
        return default
    today = datetime.now(timezone.utc).date()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return max(years, 0)
