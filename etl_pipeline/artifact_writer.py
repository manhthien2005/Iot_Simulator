from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import pandas as pd  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    pd = None

try:
    import pyarrow  # noqa: F401  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    pyarrow = None


class ArtifactWriter:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def can_write_parquet(self) -> bool:
        return pd is not None and pyarrow is not None

    def write_records(self, artifact_name: str, records: list[dict[str, Any]]) -> Path:
        if self.can_write_parquet:
            output_path = self.output_dir / f"{artifact_name}.parquet"
            pd.DataFrame(records).to_parquet(output_path, index=False)
            return output_path

        output_path = self.output_dir / f"{artifact_name}.jsonl"
        with output_path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return output_path

