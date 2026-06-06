"""Smoke tests for the health endpoint.

Verifies the FastAPI app boots correctly and /healthz returns 200.
Zero dependencies required — no mock setup needed.
"""
from __future__ import annotations


async def test_healthz(client) -> None:
    """GET /healthz returns 200 + {"status": "ok"}.

    Covers REQ-TEST-003: Health endpoint returns 200.
    """
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
