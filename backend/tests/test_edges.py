"""Smoke tests for the edges CRUD router.

Covers upsert, delete, constraint update, 422 for missing nodes,
and 404 for missing edge.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from httpx import AsyncClient

from app.dependencies import get_current_user


async def _setup_project_verify(
    mock: MagicMock,
    project_id: str,
) -> None:
    """Helper: set up the project ownership check mock chain to succeed."""
    mock.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": project_id}


_SAMPLE_EDGE = {
    "id": "88888888-8888-8888-8888-888888888888",
    "project_id": "33333333-3333-3333-3333-333333333333",
    "node_a_id": "44444444-4444-4444-4444-444444444444",
    "node_b_id": "55555555-5555-5555-5555-555555555555",
    "cost": 1.0,
    "constraint_type": "normal",
    "created_at": "2026-06-06T00:00:00+00:00",
}


async def test_upsert_edge(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """POST /projects/{id}/edges creates/upserts an edge (201)."""
    project_id = sample_project["id"]
    await _setup_project_verify(mock_supabase_client, project_id)
    # _verify_nodes_exist: both nodes found
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .in_.return_value \
        .execute.return_value.data = [
            {"id": "44444444-4444-4444-4444-444444444444"},
            {"id": "55555555-5555-5555-5555-555555555555"},
        ]
    # Edge upsert
    mock_supabase_client.table.return_value \
        .upsert.return_value \
        .execute.return_value.data = [_SAMPLE_EDGE]

    response = await client.post(
        f"/api/v1/projects/{project_id}/edges",
        json={
            "node_a_id": "44444444-4444-4444-4444-444444444444",
            "node_b_id": "55555555-5555-5555-5555-555555555555",
            "cost": 1.0,
            "constraint_type": "normal",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["cost"] == 1.0
    assert data["constraint_type"] == "normal"


async def test_delete_edge(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """DELETE /projects/{id}/edges/{edge_id} returns 204."""
    project_id = sample_project["id"]
    edge_id = "88888888-8888-8888-8888-888888888888"
    await _setup_project_verify(mock_supabase_client, project_id)
    # Edge existence check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": edge_id}

    response = await client.delete(
        f"/api/v1/projects/{project_id}/edges/{edge_id}"
    )

    assert response.status_code == 204


async def test_update_constraint(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """PATCH /projects/{id}/edges/{edge_id}/constraint updates constraint (200)."""
    project_id = sample_project["id"]
    edge_id = "88888888-8888-8888-8888-888888888888"
    await _setup_project_verify(mock_supabase_client, project_id)
    # Edge existence check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": edge_id}
    # Constraint update
    updated = dict(_SAMPLE_EDGE)
    updated["constraint_type"] = "mandatory"
    mock_supabase_client.table.return_value \
        .update.return_value \
        .eq.return_value \
        .execute.return_value.data = [updated]

    response = await client.patch(
        f"/api/v1/projects/{project_id}/edges/{edge_id}/constraint",
        json={"constraint_type": "mandatory"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["constraint_type"] == "mandatory"


async def test_create_edge_missing_node(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """POST /projects/{id}/edges with one missing node returns 422."""
    project_id = sample_project["id"]
    await _setup_project_verify(mock_supabase_client, project_id)
    # _verify_nodes_exist: only 1 of 2 nodes found → len != 2 → 422
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .in_.return_value \
        .execute.return_value.data = [
            {"id": "44444444-4444-4444-4444-444444444444"},
        ]

    response = await client.post(
        f"/api/v1/projects/{project_id}/edges",
        json={
            "node_a_id": "44444444-4444-4444-4444-444444444444",
            "node_b_id": "55555555-5555-5555-5555-555555555555",
            "cost": 1.0,
            "constraint_type": "normal",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"] == "NODES_NOT_FOUND"


async def test_edge_404(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """Operations on a non-existent project return 404."""
    project_id = sample_project["id"]
    # Project ownership check returns None → 404
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.delete(
        f"/api/v1/projects/{project_id}/edges/88888888-8888-8888-8888-888888888888"
    )

    assert response.status_code == 404
    assert response.json()["error"] == "NOT_FOUND"
