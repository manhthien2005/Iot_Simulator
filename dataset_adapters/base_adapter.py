from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class SimpleDataFrame:
    """Minimal fallback container when pandas is unavailable."""

    rows: list[dict[str, Any]]

    @property
    def columns(self) -> list[str]:
        if not self.rows:
            return []
        return list(self.rows[0].keys())

    def __len__(self) -> int:
        return len(self.rows)

    def head(self, n: int = 5) -> "SimpleDataFrame":
        return SimpleDataFrame(self.rows[:n])

    def to_dict(self, orient: str = "records") -> list[dict[str, Any]]:
        if orient != "records":
            raise ValueError("SimpleDataFrame only supports orient='records'")
        return list(self.rows)

    def iter_rows(self) -> Iterable[dict[str, Any]]:
        return iter(self.rows)


class DatasetAdapter(ABC):
    @abstractmethod
    def load_subject(self, subject_id: str, session_start: str) -> Any:
        """Load and normalize one subject into a DataFrame-like structure."""

    @abstractmethod
    def list_subjects(self) -> list[str]:
        """List all subject IDs available in the dataset."""

    @abstractmethod
    def validate(self, df: Any) -> dict[str, Any]:
        """Validate canonical output and return a report dict."""

