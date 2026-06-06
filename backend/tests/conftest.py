"""Shared pytest fixtures for netplan backend tests.

This conftest provides:
- mock_supabase_client: a MagicMock that mimics the supabase-py Client chain
  (table().select().eq()...).execute())
- test_user_token: a pre-baked unsigned JWT (HS256, secret "test-secret") with
  the `sub` and `organization_id` claims used by get_current_user and the
  rate-limit key function.
- test_app: a FastAPI app instance with get_current_user and
  get_supabase_client dependency-overridden so tests run in-process with
  no network IO and a stable user.
- client: an httpx AsyncClient bound to test_app via ASGI transport.
- sample_uuids: a dict of stable UUIDs used across tests for projects,
  organizations, nodes, and edges.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.dependencies import get_current_user
from app.db.supabase_client import get_supabase_client


# Stable UUIDs reused across tests so assertions are predictable.
SAMPLE_UUIDS: Dict[str, uuid.UUID] = {
    "org_id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "user_id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
    "project_id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
    "node_a": uuid.UUID("44444444-4444-4444-4444-444444444444"),
    "node_b": uuid.UUID("55555555-5555-5555-5555-555555555555"),
    "node_c": uuid.UUID("66666666-6666-6666-6666-666666666666"),
    "node_d": uuid.UUID("77777777-7777-7777-7777-777777777777"),
    "edge_ab": uuid.UUID("88888888-8888-8888-8888-888888888888"),
    "edge_bc": uuid.UUID("99999999-9999-9999-9999-999999999999"),
    "edge_ac": uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
}


def _build_test_token() -> str:
    """Build an unsigned (HS256) JWT with sub + organization_id claims.

    The token is NOT signature-verified anywhere in tests because
    get_current_user is dependency-overridden; this token is used by
    tests that exercise the rate-limit key function (which calls
    jwt.get_unverified_claims).
    """
    claims = {
        "sub": str(SAMPLE_UUIDS["user_id"]),
        "organization_id": str(SAMPLE_UUIDS["org_id"]),
    }
    return jwt.encode(claims, "test-secret-not-used-for-verification", algorithm="HS256")


@pytest.fixture
def sample_uuids() -> Dict[str, uuid.UUID]:
    """Stable UUIDs for tests."""
    return dict(SAMPLE_UUIDS)


@pytest.fixture
def test_user_token() -> str:
    """A pre-baked JWT string used to exercise JWT-decoding code paths."""
    return _build_test_token()


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """A MagicMock that mimics the supabase-py fluent chain.

    Usage pattern in tests:
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [...]
    """
    return MagicMock(name="supabase_client")


@pytest.fixture
def test_app(mock_supabase_client: MagicMock) -> FastAPI:
    """A FastAPI app with get_current_user and supabase client overridden.

    Routers that need to be present must be included by the test via
    `app.include_router(...)` or by mounting the full app.dependency_overrides
    in their own conftest. The default fixture returns a clean app with
    dependency overrides set so any router mounted later picks them up.
    """
    from app.main import app as real_app  # local import to avoid heavy side effects

    # Reset the slowapi rate limiter so each test starts with an empty
    # bucket. The limiter is a module-level singleton on
    # app.core.rate_limit, so without this reset, the second test in
    # a session would already see the 5/min bucket partially full.
    from app.core.rate_limit import limiter
    if hasattr(limiter, "_storage") and limiter._storage is not None:
        try:
            limiter._storage.reset()
        except Exception:
            pass

    real_app.dependency_overrides[get_current_user] = lambda: {
        "user_id": str(SAMPLE_UUIDS["user_id"]),
        "org_id": str(SAMPLE_UUIDS["org_id"]),
    }
    real_app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client

    # Patch get_supabase_client at the module level in routers that call it
    # directly (not via Depends). The MST router uses Depends, but projects,
    # nodes, edges, and export routers call get_supabase_client() as a plain function.
    from app.routers import projects as _projects_rtr
    from app.routers import nodes as _nodes_rtr
    from app.routers import edges as _edges_rtr
    from app.routers import export as _export_rtr
    _router_patches = [
        patch.object(_projects_rtr, "get_supabase_client", return_value=mock_supabase_client),
        patch.object(_nodes_rtr, "get_supabase_client", return_value=mock_supabase_client),
        patch.object(_edges_rtr, "get_supabase_client", return_value=mock_supabase_client),
        patch.object(_export_rtr, "get_supabase_client", return_value=mock_supabase_client),
    ]
    for _p in _router_patches:
        _p.start()

    yield real_app

    # Cleanup patches and DI overrides.
    for _p in _router_patches:
        _p.stop()
    real_app.dependency_overrides.clear()


@pytest.fixture
def sample_project(sample_uuids) -> dict:
    """A sample project dict keyed from sample_uuids."""
    return {
        "id": str(sample_uuids["project_id"]),
        "organization_id": str(sample_uuids["org_id"]),
        "created_by": str(sample_uuids["user_id"]),
        "name": "Test Project",
        "description": "A project for testing",
        "created_at": "2026-06-06T00:00:00+00:00",
        "updated_at": "2026-06-06T00:00:00+00:00",
    }


@pytest.fixture
def sample_node(sample_uuids) -> dict:
    """A sample node dict keyed from sample_uuids."""
    return {
        "id": str(sample_uuids["node_a"]),
        "project_id": str(sample_uuids["project_id"]),
        "name": "Node A",
        "type": "city",
        "lat": 0.0,
        "lng": 0.0,
        "created_at": "2026-06-06T00:00:00+00:00",
    }


@pytest.fixture
async def client(test_app: FastAPI) -> AsyncClient:
    """An httpx AsyncClient bound to test_app via ASGI transport."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
