"""Smoke tests for the nodes CRUD router.

Covers create, list, update, delete, and 404 for missing project/node.
All tests use mock_supabase_client from conftest.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from httpx import AsyncClient


async def test_create_node(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
    sample_node: dict[str, Any],
) -> None:
    """POST /projects/{id}/nodes creates a node and returns 201."""
    project_id = sample_project["id"]
    # Project ownership check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": project_id}
    # Node insert
    mock_supabase_client.table.return_value \
        .insert.return_value \
        .execute.return_value.data = [sample_node]

    response = await client.post(
        f"/api/v1/projects/{project_id}/nodes",
        json={"name": "Node A", "type": "city", "lat": 0.0, "lng": 0.0},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Node A"


async def test_list_nodes(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
    sample_node: dict[str, Any],
) -> None:
    """GET /projects/{id}/nodes returns list of nodes (200)."""
    project_id = sample_project["id"]
    # Project ownership check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": project_id}
    # Node list query
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .execute.return_value.data = [sample_node]

    response = await client.get(f"/api/v1/projects/{project_id}/nodes")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Node A"


async def test_update_node(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
    sample_node: dict[str, Any],
) -> None:
    """PUT /projects/{id}/nodes/{node_id} updates and returns the node."""
    project_id = sample_project["id"]
    node_id = sample_node["id"]
    # Project ownership check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": project_id}
    # Node existence check (same chain path as project check)
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": node_id}
    # Node update
    mock_supabase_client.table.return_value \
        .update.return_value \
        .eq.return_value \
        .execute.return_value.data = [sample_node]

    response = await client.put(
        f"/api/v1/projects/{project_id}/nodes/{node_id}",
        json={"name": "Updated Node"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Node A"


async def test_delete_node(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
    sample_node: dict[str, Any],
) -> None:
    """DELETE /projects/{id}/nodes/{node_id} returns 204."""
    project_id = sample_project["id"]
    node_id = sample_node["id"]
    # Project ownership check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": project_id}
    # Node existence check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": node_id}

    response = await client.delete(
        f"/api/v1/projects/{project_id}/nodes/{node_id}"
    )

    assert response.status_code == 204


async def test_node_404(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """GET /projects/{id}/nodes when project not found returns 404."""
    project_id = sample_project["id"]
    # Project ownership check returns None → 404 NOT_FOUND
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.get(f"/api/v1/projects/{project_id}/nodes")

    assert response.status_code == 404
    assert response.json()["error"] == "NOT_FOUND"
