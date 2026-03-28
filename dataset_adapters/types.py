from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


SleepStageValue = Literal["awake", "rem", "light", "deep"]


@dataclass
class SleepPhase:
    stage: SleepStageValue
    start: str
    end: str
    duration_s: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SleepSessionRecord:
    subject_id: str
    recording_start: str
    phases: list[SleepPhase]
    summary: dict[str, Any]
    source_dataset: str = "Sleep-EDF"
    realism_mode: str = "real"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["phases"] = [phase.to_dict() for phase in self.phases]
        return payload
