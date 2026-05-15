"""Smoke test for ADR-021 endpoint prefix migration — IoT Simulator side.

Verifies that the simulator API is mounted at /api/v1/sim/* (canonical)
and that the legacy /api/sim/* prefix is no longer served.

Related: XR-001 (topology drift), Phase 7 slice S1 (IoT sub-tasks).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api_server.main import app

    return TestClient(app)


class TestCanonicalSimPrefix:
    """ADR-021: canonical simulator API surface is /api/v1/sim/*."""

    def test_canonical_health_returns_200(self, client):
        resp = client.get("/api/v1/sim/health")
        assert resp.status_code == 200, resp.text

    def test_canonical_devices_returns_200(self, client):
        resp = client.get("/api/v1/sim/devices")
        assert resp.status_code == 200, resp.text


class TestLegacySimPrefixGone:
    """ADR-021: legacy /api/sim/* prefix is no longer served."""

    def test_legacy_health_returns_404(self, client):
        resp = client.get("/api/sim/health")
        assert resp.status_code == 404

    def test_legacy_devices_returns_404(self, client):
        resp = client.get("/api/sim/devices")
        assert resp.status_code == 404


class TestOpenApiPaths:
    """ADR-021: every simulator path declared in the OpenAPI spec starts
    with /api/v1/sim — no orphan legacy mount remaining."""

    def test_openapi_paths_use_canonical_prefix(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        sim_paths = [
            p for p in spec.get("paths", {}).keys() if "/sim" in p
        ]
        assert sim_paths, "OpenAPI spec must declare at least one /sim path"
        for path in sim_paths:
            assert path.startswith("/api/v1/sim"), (
                f"OpenAPI path {path!r} does not match the canonical /api/v1/sim prefix"
            )
