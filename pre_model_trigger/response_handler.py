"""Response handler for trigger action post-processing.

``ResponseHandler`` is passed as a **class** (not an instance) to the
``TriggerOrchestrator`` constructor.  The orchestrator calls its static
methods to filter, deduplicate, and format the final action list before
returning it to the caller.

Architecture reference: plans/alert-threshold-architecture-plan.md §5.1
"""
from __future__ import annotations

import logging
import time
from typing import Any

from pre_model_trigger.types import SEVERITY_RANK, TriggerActionItem

logger = logging.getLogger(__name__)

# IS-005c: alias to centralized SEVERITY_RANK in types module (single source of truth).
_SEVERITY_RANK = SEVERITY_RANK


class ResponseHandler:
    """Static utility class for post-processing trigger actions.

    All methods are ``@staticmethod`` so that the class can be passed
    by reference (not instantiated) to the orchestrator.

    Usage in ``dependencies.py``::

        TriggerOrchestrator(
            ...
            response_handler=ResponseHandler,  # class, NOT instance
            ...
        )
    """

    @staticmethod
    def deduplicate(actions: list[TriggerActionItem]) -> list[TriggerActionItem]:
        """Remove duplicate actions, keeping the highest severity per source+metric.

        Two actions are considered duplicates when they share the same
        ``source`` and the same ``metric`` metadata key.
        """
        best: dict[str, TriggerActionItem] = {}

        for action in actions:
            metric = action.metadata.get("metric", action.source or "unknown")
            key = f"{action.source}:{metric}"
            existing = best.get(key)

            if existing is None:
                best[key] = action
            else:
                existing_rank = _SEVERITY_RANK.get(existing.severity.upper(), 0)
                new_rank = _SEVERITY_RANK.get(action.severity.upper(), 0)
                if new_rank > existing_rank:
                    best[key] = action

        return list(best.values())

    @staticmethod
    def filter_actionable(actions: list[TriggerActionItem]) -> list[TriggerActionItem]:
        """Keep only actions that require downstream processing.

        Filters out ``NORMAL`` severity actions which are informational
        only and do not need alert/model-call handling.
        """
        return [
            a for a in actions
            if a.severity.upper() != "NORMAL"
        ]

    @staticmethod
    def sort_by_severity(actions: list[TriggerActionItem]) -> list[TriggerActionItem]:
        """Sort actions by severity descending (most urgent first)."""
        return sorted(
            actions,
            key=lambda a: _SEVERITY_RANK.get(a.severity.upper(), 0),
            reverse=True,
        )

    @staticmethod
    def enrich_metadata(
        actions: list[TriggerActionItem],
        *,
        device_id: str,
        timestamp: float | None = None,
    ) -> list[TriggerActionItem]:
        """Add device_id and timestamp to each action's metadata.

        Returns new ``TriggerActionItem`` instances (does not mutate
        the originals).
        """
        ts = str(timestamp or time.time())
        enriched: list[TriggerActionItem] = []
        for action in actions:
            new_meta = {**action.metadata, "device_id": device_id, "timestamp": ts}
            enriched.append(TriggerActionItem(
                action_type=action.action_type,
                severity=action.severity,
                message=action.message,
                source=action.source,
                metadata=new_meta,
                reason_codes=list(action.reason_codes),
            ))
        return enriched

    @staticmethod
    def process(
        actions: list[TriggerActionItem],
        *,
        device_id: str,
    ) -> list[TriggerActionItem]:
        """Full post-processing pipeline: dedup → filter → enrich → sort.

        This is the main entry point called by the orchestrator.
        """
        result = ResponseHandler.deduplicate(actions)
        result = ResponseHandler.filter_actionable(result)
        result = ResponseHandler.enrich_metadata(result, device_id=device_id)
        result = ResponseHandler.sort_by_severity(result)
        return result


__all__ = ["ResponseHandler"]
