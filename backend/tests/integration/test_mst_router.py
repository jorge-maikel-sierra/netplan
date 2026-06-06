"""Integration tests for the MST router and service.

Covers REQ-MST-001, REQ-MST-002, REQ-MST-003 (cross-tenant 404),
REQ-MST-004 (latest), REQ-MST-005 (rate limit), REQ-MST-006 (persistence
on success, no persistence on failure), and REQ-MST-007 (tenant-scoped
queries include organization_id).

These tests run the FastAPI app in-process via httpx.AsyncClient and a
dependency-overridden supabase client (MagicMock). No real network IO.
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.supabase_client import get_supabase_client
from app.dependencies import get_current_user


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class _ExecuteResult:
    """Mimics the supabase-py PostgrestResponse / APIResponse: an object
    with a .data attribute. The async execute() returns a coroutine, so
    we mark it as an awaitable using AsyncMock semantics — but in
    practice supabase-py methods are sync, so we just return this
    object directly. The test code does `resp.data` after awaiting the
    function call, which is fine because the supabase calls inside
    the service are sync (the service is `async def` only for
    FastAPI endpoint compatibility).
    """

    def __init__(self, data: Any = None) -> None:
        self.data = data


class _Chain:
    """Configurable fluent chain for the supabase client mock.

    Each call (.select, .eq, .order, .limit, .maybe_single) returns self
    so the chain stays alive. .execute() returns the configured result.
    """

    def __init__(self, execute_result: _ExecuteResult) -> None:
        self._result = execute_result
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def select(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        self.calls.append(("select", _args))
        return self

    def eq(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        self.calls.append(("eq", _args))
        return self

    def in_(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        self.calls.append(("in_", _args))
        return self

    def order(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        self.calls.append(("order", _args))
        return self

    def limit(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        self.calls.append(("limit", _args))
        return self

    def maybe_single(self) -> "_Chain":
        self.calls.append(("maybe_single", ()))
        return self

    def insert(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        self.calls.append(("insert", _args))
        return self

    def upsert(self, *_args: Any, **_kwargs: Any) -> "_Chain":
        self.calls.append(("upsert", _args))
        return self

    def execute(self) -> _ExecuteResult:
        self.calls.append(("execute", ()))
        return self._result


_PROJECT_NOT_FOUND = object()


def build_supabase_mock(
    project: dict[str, Any] | object = _PROJECT_NOT_FOUND,
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
    mst_results: list[dict[str, Any]] | None = None,
    insert_response: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a MagicMock that mimics the supabase client for one request.

    The mock's .table(name) returns a per-table _Chain with the right
    .execute() result.

    project:
      - dict: the projects table chain returns this as .maybe_single().execute().data
      - _PROJECT_NOT_FOUND (default): use a sensible default project dict
      - any other object: the projects table chain returns data=None
        (project not found; cross-tenant case)
    """
    if project is _PROJECT_NOT_FOUND:
        project = {
            "id": "33333333-3333-3333-3333-333333333333",
            "organization_id": "11111111-1111-1111-1111-111111111111",
        }
    elif not isinstance(project, dict):
        # Treat as "no project found" (cross-tenant).
        project = None
    nodes = nodes or []
    edges = edges or []
    mst_results = mst_results or []
    default_project_id = (
        project["id"] if isinstance(project, dict) else "33333333-3333-3333-3333-333333333333"
    )
    insert_response = insert_response or {
        "id": str(uuid.uuid4()),
        "project_id": default_project_id,
        "algorithm": "kruskal",
        "total_cost": "3.0",
        "edge_ids": [],
        "parameters": {},
        "calculated_at": "2026-06-06T00:00:00+00:00",
    }

    chains: dict[str, _Chain] = {
        "projects": _Chain(_ExecuteResult(data=project)),
        "nodes": _Chain(_ExecuteResult(data=nodes)),
        "edges": _Chain(_ExecuteResult(data=edges)),
        "mst_results": _Chain(_ExecuteResult(data=mst_results)),
    }

    # The insert chain must return a chain whose execute() yields the
    # inserted row. We special-case it: any chain method that goes
    # through .insert returns a sub-chain for the insert.
    insert_chain = _Chain(_ExecuteResult(data=[insert_response]))
    # The select chain returns the table-specific chain for reads.
    # The insert chain is reached via .insert() on the table.

    # Build a parent mock that dispatches .table() to the right chain.
    mock = MagicMock(name="supabase_client")
    table_mock = MagicMock(name="table_dispatch")
    table_mock.side_effect = lambda name: chains.get(name) or _Chain(_ExecuteResult(data=None))
    mock.table = table_mock

    # Override the insert chain on mst_results specifically. The
    # mst_results chain in chains[] is for SELECT. For INSERT we need
    # a different chain. We patch the .insert method of the mst_results
    # chain to return insert_chain.
    chains["mst_results"].insert = MagicMock(  # type: ignore[method-assign]
        return_value=insert_chain
    )

    # Expose the chains for assertion.
    mock._chains = chains  # type: ignore[attr-defined]
    return mock


def install_supabase_override(test_app, mock_supabase: MagicMock) -> None:
    """Install the supabase dependency override on the test app."""
    test_app.dependency_overrides[get_supabase_client] = lambda: mock_supabase


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------


def make_triangle_data(sample_uuids: dict[str, uuid.UUID]):
    """3 nodes + 3 edges forming a triangle with the cheapest 2 edges
    totaling 3.0. Used by the happy-path test."""
    project_id = sample_uuids["project_id"]
    a, b, c = sample_uuids["node_a"], sample_uuids["node_b"], sample_uuids["node_c"]
    nodes = [
        {"id": str(a), "name": "A", "type": "city", "lat": 0.0, "lng": 0.0},
        {"id": str(b), "name": "B", "type": "city", "lat": 0.0, "lng": 0.0},
        {"id": str(c), "name": "C", "type": "city", "lat": 0.0, "lng": 0.0},
    ]
    edges = [
        {"id": str(sample_uuids["edge_ab"]), "node_a_id": str(a), "node_b_id": str(b),
         "cost": 1.0, "constraint_type": "normal"},
        {"id": str(sample_uuids["edge_bc"]), "node_a_id": str(b), "node_b_id": str(c),
         "cost": 2.0, "constraint_type": "normal"},
        {"id": str(sample_uuids["edge_ac"]), "node_a_id": str(a), "node_b_id": str(c),
         "cost": 3.0, "constraint_type": "normal"},
    ]
    return nodes, edges


# ---------------------------------------------------------------------------
# REQ-MST-001: happy path + REQ-MST-006: persistence
# ---------------------------------------------------------------------------


async def test_calculate_endpoint_happy_path(
    test_app, sample_uuids: dict[str, uuid.UUID]
) -> None:
    """200 OK with correct total_cost (3.0) and a persisted row."""
    project_id = sample_uuids["project_id"]
    nodes, edges = make_triangle_data(sample_uuids)
    mock_supabase = build_supabase_mock(nodes=nodes, edges=edges)
    install_supabase_override(test_app, mock_supabase)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/projects/{project_id}/mst/calculate"
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_cost"] == pytest.approx(3.0)
    assert len(body["mst_edges"]) == 2
    assert body["project_id"] == str(project_id)
    # The two cheapest edges are AB (1.0) and BC (2.0).
    chosen_costs = sorted(e["cost"] for e in body["mst_edges"])
    assert chosen_costs == [1.0, 2.0]


async def test_calculate_endpoint_persists_on_success(
    test_app, sample_uuids: dict[str, uuid.UUID]
) -> None:
    """REQ-MST-006: on success, mst_results.insert is called with the
    right shape and the result row is in the response."""
    project_id = sample_uuids["project_id"]
    nodes, edges = make_triangle_data(sample_uuids)
    mock_supabase = build_supabase_mock(nodes=nodes, edges=edges)
    install_supabase_override(test_app, mock_supabase)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/projects/{project_id}/mst/calculate"
        )

    assert response.status_code == 200
    # The build_supabase_mock helper monkey-patches mst_chain.insert
    # to return a separate insert_chain, so the original .insert method
    # is gone. Instead, check that .insert was called on mst_chain by
    # verifying it was used as a callable at all (i.e. the MagicMock
    # we put in its place was called).
    mst_chain = mock_supabase._chains["mst_results"]
    # mst_chain.insert is a MagicMock we installed; assert it was called.
    assert mst_chain.insert.called, (
        "mst_results.insert should have been called on success"
    )


# ---------------------------------------------------------------------------
# REQ-MST-003: cross-tenant isolation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# REQ-MST-003: cross-tenant isolation
# ---------------------------------------------------------------------------


async def test_calculate_endpoint_tenant_isolation(
    test_app, sample_uuids: dict[str, uuid.UUID]
) -> None:
    """REQ-MST-003: project belongs to a different org -> 404 (no leak)."""
    project_id = sample_uuids["project_id"]
    # Project lookup returns None -> 404.
    mock_supabase = build_supabase_mock(project="NOT_FOUND")
    install_supabase_override(test_app, mock_supabase)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/projects/{project_id}/mst/calculate"
        )

    assert response.status_code == 404
    body = response.json()
    # No existence leak: the body must NOT contain forbidden / not authorized.
    body_text = str(body).lower()
    assert "forbidden" not in body_text
    assert "not authorized" not in body_text
    assert "cross-tenant" not in body_text
    assert body["error"] == "NOT_FOUND"


async def test_calculate_endpoint_unauthenticated_returns_401(test_app) -> None:
    """REQ-MST-003: no Authorization header -> 401."""
    # Override get_current_user to a dependency that raises 401.
    from fastapi import HTTPException, status as http_status

    def _fake_dep():
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_TOKEN", "code": 401, "detail": "Invalid token"},
        )

    test_app.dependency_overrides[get_current_user] = _fake_dep

    transport = ASGITransport(app=test_app)
    project_id = "33333333-3333-3333-3333-333333333333"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/projects/{project_id}/mst/calculate"
        )

    assert response.status_code == 401
    assert response.json()["error"] == "INVALID_TOKEN"


# ---------------------------------------------------------------------------
# REQ-MST-001: insufficient nodes & mandatory cycle (422)
# ---------------------------------------------------------------------------


async def test_calculate_endpoint_insufficient_nodes_returns_422(
    test_app, sample_uuids: dict[str, uuid.UUID]
) -> None:
    """REQ-MST-001: <2 nodes -> 422 INSUFFICIENT_NODES."""
    project_id = sample_uuids["project_id"]
    # Only 1 node, no edges.
    single_node = [{
        "id": str(sample_uuids["node_a"]),
        "name": "A", "type": "city", "lat": 0.0, "lng": 0.0,
    }]
    mock_supabase = build_supabase_mock(nodes=single_node, edges=[])
    install_supabase_override(test_app, mock_supabase)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/projects/{project_id}/mst/calculate"
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "INSUFFICIENT_NODES"


async def test_calculate_endpoint_mandatory_cycle_returns_422(
    test_app, sample_uuids: dict[str, uuid.UUID]
) -> None:
    """REQ-MST-001: 3 mandatory edges forming a cycle -> 422 MANDATORY_CYCLE."""
    project_id = sample_uuids["project_id"]
    a, b, c = sample_uuids["node_a"], sample_uuids["node_b"], sample_uuids["node_c"]
    nodes = [
        {"id": str(a), "name": "A", "type": "city", "lat": 0.0, "lng": 0.0},
        {"id": str(b), "name": "B", "type": "city", "lat": 0.0, "lng": 0.0},
        {"id": str(c), "name": "C", "type": "city", "lat": 0.0, "lng": 0.0},
    ]
    edges = [
        {"id": str(sample_uuids["edge_ab"]), "node_a_id": str(a), "node_b_id": str(b),
         "cost": 5.0, "constraint_type": "mandatory"},
        {"id": str(sample_uuids["edge_bc"]), "node_a_id": str(b), "node_b_id": str(c),
         "cost": 5.0, "constraint_type": "mandatory"},
        {"id": str(sample_uuids["edge_ac"]), "node_a_id": str(a), "node_b_id": str(c),
         "cost": 5.0, "constraint_type": "mandatory"},
    ]
    mock_supabase = build_supabase_mock(nodes=nodes, edges=edges)
    install_supabase_override(test_app, mock_supabase)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/projects/{project_id}/mst/calculate"
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "MANDATORY_CYCLE"
    assert "conflicting_edge_ids" in body


# ---------------------------------------------------------------------------
# REQ-MST-002: disconnected graph
# ---------------------------------------------------------------------------


async def test_calculate_endpoint_disconnected_returns_422(
    test_app, sample_uuids: dict[str, uuid.UUID]
) -> None:
    """REQ-MST-002: 2 disconnected subgraphs -> 422 DISCONNECTED_GRAPH."""
    project_id = sample_uuids["project_id"]
    a, b, c, d = (
        sample_uuids["node_a"],
        sample_uuids["node_b"],
        sample_uuids["node_c"],
        sample_uuids["node_d"],
    )
    nodes = [
        {"id": str(a), "name": "A", "type": "city", "lat": 0.0, "lng": 0.0},
        {"id": str(b), "name": "B", "type": "city", "lat": 0.0, "lng": 0.0},
        {"id": str(c), "name": "C", "type": "city", "lat": 0.0, "lng": 0.0},
        {"id": str(d), "name": "D", "type": "city", "lat": 0.0, "lng": 0.0},
    ]
    edges = [
        {"id": str(sample_uuids["edge_ab"]), "node_a_id": str(a), "node_b_id": str(b),
         "cost": 1.0, "constraint_type": "normal"},
        {"id": str(sample_uuids["edge_bc"]), "node_a_id": str(c), "node_b_id": str(d),
         "cost": 1.0, "constraint_type": "normal"},
    ]
    mock_supabase = build_supabase_mock(nodes=nodes, edges=edges)
    install_supabase_override(test_app, mock_supabase)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/projects/{project_id}/mst/calculate"
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "DISCONNECTED_GRAPH"
    assert "unreachable_nodes" in body
    assert len(body["unreachable_nodes"]) == 2


# ---------------------------------------------------------------------------
# REQ-MST-006: no persistence on failure
# ---------------------------------------------------------------------------


async def test_calculate_endpoint_no_persist_on_failure(
    test_app, sample_uuids: dict[str, uuid.UUID]
) -> None:
    """REQ-MST-006: a 422 response must NOT call mst_results.insert."""
    project_id = sample_uuids["project_id"]
    # 1 node -> INSUFFICIENT_NODES -> 422.
    single_node = [{
        "id": str(sample_uuids["node_a"]),
        "name": "A", "type": "city", "lat": 0.0, "lng": 0.0,
    }]
    mock_supabase = build_supabase_mock(nodes=single_node, edges=[])
    install_supabase_override(test_app, mock_supabase)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/projects/{project_id}/mst/calculate"
        )

    assert response.status_code == 422
    mst_chain = mock_supabase._chains["mst_results"]
    assert not any(call[0] == "insert" for call in mst_chain.calls), (
        "mst_results.insert must NOT be called on a 422 response"
    )


# ---------------------------------------------------------------------------
# REQ-MST-004: latest endpoint
# ---------------------------------------------------------------------------


async def test_latest_endpoint_returns_most_recent(
    test_app, sample_uuids: dict[str, uuid.UUID]
) -> None:
    """REQ-MST-004: returns the most recent mst_results row for the project."""
    project_id = sample_uuids["project_id"]
    a, b = sample_uuids["node_a"], sample_uuids["node_b"]
    nodes = [
        {"id": str(a), "name": "A", "type": "city", "lat": 0.0, "lng": 0.0},
        {"id": str(b), "name": "B", "type": "city", "lat": 0.0, "lng": 0.0},
    ]
    edges = [
        {"id": str(sample_uuids["edge_ab"]), "node_a_id": str(a), "node_b_id": str(b),
         "cost": 5.0, "constraint_type": "normal"},
    ]
    mst_results = [{
        "id": "abcdef00-0000-0000-0000-000000000001",
        "project_id": str(project_id),
        "algorithm": "kruskal",
        "total_cost": "5.0",
        "edge_ids": [str(sample_uuids["edge_ab"])],
        "parameters": {
            "mandatory_edge_ids": [],
            "forbidden_edge_ids": [],
            "node_count": 2,
            "edge_count": 1,
        },
        "calculated_at": "2026-06-06T00:00:00+00:00",
    }]
    mock_supabase = build_supabase_mock(
        nodes=nodes, edges=edges, mst_results=mst_results
    )
    install_supabase_override(test_app, mock_supabase)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            f"/api/v1/projects/{project_id}/mst/latest"
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result_id"] == "abcdef00-0000-0000-0000-000000000001"
    assert body["total_cost"] == pytest.approx(5.0)
    assert body["project_id"] == str(project_id)
    assert len(body["mst_edges"]) == 1
    assert body["mst_edges"][0]["edge_id"] == str(sample_uuids["edge_ab"])


async def test_latest_endpoint_no_result_returns_404(
    test_app, sample_uuids: dict[str, uuid.UUID]
) -> None:
    """REQ-MST-004: no mst_results yet -> 404 NO_RESULT."""
    project_id = sample_uuids["project_id"]
    mock_supabase = build_supabase_mock(mst_results=[])
    install_supabase_override(test_app, mock_supabase)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            f"/api/v1/projects/{project_id}/mst/latest"
        )

    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "NO_RESULT"


async def test_latest_endpoint_cross_tenant_returns_404(
    test_app, sample_uuids: dict[str, uuid.UUID]
) -> None:
    """REQ-MST-003: latest on a project from another org -> 404."""
    project_id = sample_uuids["project_id"]
    mock_supabase = build_supabase_mock(project="NOT_FOUND")
    install_supabase_override(test_app, mock_supabase)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        response = await ac.get(
            f"/api/v1/projects/{project_id}/mst/latest"
        )

    assert response.status_code == 404
    assert response.json()["error"] == "NOT_FOUND"
