from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=_json_default)
