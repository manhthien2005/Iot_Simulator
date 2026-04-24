"""API-key authentication for admin endpoints.

Usage
-----
Apply ``Depends(require_admin_key)`` to any admin endpoint or router:

    from api_server.middleware.auth import require_admin_key

    router = APIRouter(dependencies=[Depends(require_admin_key)])

Behaviour
---------
* If the env-var ``SIM_ADMIN_API_KEY`` is **not set** (or empty), authentication
  is bypassed — this keeps local / dev-mode frictionless.
* When the env-var **is** set, the request must carry a matching
  ``X-Admin-Key`` header.  A mismatch (or missing header) returns **403**.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status


def require_admin_key(
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
) -> None:
    """FastAPI dependency — validates the admin API key when configured."""
    expected = os.environ.get("SIM_ADMIN_API_KEY", "").strip()
    if not expected:
        # Dev mode: no key configured → allow all requests
        return
    if x_admin_key != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key",
        )
