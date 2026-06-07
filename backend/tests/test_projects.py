"""Smoke tests for the projects CRUD router.

Covers list (empty + populated), create, get, update, delete, and the
free-tier limit. All tests use mock_supabase_client from conftest with
dependency_overrides — no real IO.

Auth-required behaviour is tested via test_list_projects_401 which
overrides get_current_user to raise 401.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user


async def test_list_projects_empty(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
) -> None:
    """GET /api/v1/projects with empty mock returns 200 and [].

    Covers REQ-TEST-003: Protected endpoint returns proper response
    when authorised (the list is empty).
    """
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .order.return_value \
        .execute.return_value.data = []

    response = await client.get("/api/v1/projects")

    assert response.status_code == 200
    assert response.json() == []


async def test_list_projects_populated(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """GET /api/v1/projects returns a list with the sample project."""
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .order.return_value \
        .execute.return_value.data = [sample_project]

    response = await client.get("/api/v1/projects")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Project"


async def test_create_project(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """POST /api/v1/projects creates and returns the project (201)."""
    # Mock org plan lookup (.select("plan").eq("id", org_id).single().execute().data)
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"plan": "free"}
    # Mock project count check (.select("id", count="exact").eq(...).execute().count)
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .execute.return_value.count = 1
    # Mock project insert
    mock_supabase_client.table.return_value \
        .insert.return_value \
        .execute.return_value.data = [sample_project]

    response = await client.post(
        "/api/v1/projects",
        json={"name": "Test Project", "description": "Testing"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"


async def test_get_project_found(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """GET /api/v1/projects/{id} returns project detail."""
    project_id = sample_project["id"]
    # Project lookup (.select("*").eq("id", ...).eq("organization_id", ...).single())
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = sample_project
    # Nodes & edges lookup (both go through .eq(...).execute().data)
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .execute.return_value.data = []
    # MST lookup (.eq(...).order(...).limit(...).execute().data)
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .order.return_value \
        .limit.return_value \
        .execute.return_value.data = []

    response = await client.get(f"/api/v1/projects/{project_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_project["id"])


async def test_get_project_404(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """GET /api/v1/projects/{id} when project not found returns 404."""
    project_id = sample_project["id"]
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.get(f"/api/v1/projects/{project_id}")

    assert response.status_code == 404
    assert response.json()["error"] == "PROJECT_NOT_FOUND"


async def test_update_project(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """PATCH /api/v1/projects/{id} updates and returns the project."""
    project_id = sample_project["id"]
    # Ownership check (.select("id").eq(...).eq(...).single())
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": project_id}
    # Update (.update(...).eq(...).eq(...).execute().data)
    mock_supabase_client.table.return_value \
        .update.return_value \
        .eq.return_value \
        .eq.return_value \
        .execute.return_value.data = [sample_project]

    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Updated"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Project"


async def test_delete_project(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """DELETE /api/v1/projects/{id} returns 204 No Content."""
    project_id = sample_project["id"]
    # Ownership check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": project_id}

    response = await client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 204


async def test_free_tier_limit(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
) -> None:
    """POST /api/v1/projects on free plan with 3 projects → 403."""
    # Org plan check returns free
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"plan": "free"}
    # Count >= 3 triggers FREE_TIER_LIMIT
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .execute.return_value.count = 3

    response = await client.post(
        "/api/v1/projects",
        json={"name": "Fourth Project"},
    )

    assert response.status_code == 403
    assert response.json()["error"] == "FREE_TIER_LIMIT"


# --- T-03: Name validation (min 3 chars) ---

async def test_create_project_name_too_short(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
) -> None:
    """POST /api/v1/projects with name < 3 chars returns 422."""
    # Mock org plan lookup (free)
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"plan": "free"}
    # Mock project count check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .execute.return_value.count = 1

    # Name "ab" is only 2 chars
    response = await client.post(
        "/api/v1/projects",
        json={"name": "ab", "description": "Testing"},
    )

    assert response.status_code == 422
    # FastAPI validation error format
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any("al menos 3 caracteres" in str(e.get("msg", "")) for e in detail)


async def test_create_project_name_whitespace_only(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
) -> None:
    """POST /api/v1/projects with whitespace-only name < 3 chars returns 422."""
    # Mock org plan lookup (free)
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"plan": "free"}
    # Mock project count check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .execute.return_value.count = 1

    response = await client.post(
        "/api/v1/projects",
        json={"name": "  a  ", "description": "Testing"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any("al menos 3 caracteres" in str(e.get("msg", "")) for e in detail)


async def test_update_project_name_too_short(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """PATCH /api/v1/projects/{id} with name < 3 chars returns 422."""
    project_id = sample_project["id"]
    # Org exists
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": "org-id"}
    # Ownership check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": project_id}

    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "xy"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert any("al menos 3 caracteres" in str(e.get("msg", "")) for e in detail)


# --- T-04: PATCH null handling ---

async def test_update_project_null_values_ignored(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """PATCH /api/v1/projects/{id} with null name/description ignores them (200)."""
    project_id = sample_project["id"]
    # Ownership check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": project_id}
    # Update returns the project
    mock_supabase_client.table.return_value \
        .update.return_value \
        .eq.return_value \
        .eq.return_value \
        .execute.return_value.data = [sample_project]

    # Send null for name and description - they should be ignored
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": None, "description": None},
    )

    # Should fail with 422 because no valid fields provided
    assert response.status_code == 422
    assert response.json()["error"] == "NO_FIELDS_TO_UPDATE"


async def test_update_project_partial_null(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """PATCH /api/v1/projects/{id} with null description but valid name updates name (200)."""
    project_id = sample_project["id"]
    updated_project = {**sample_project, "name": "New Name"}
    # Ownership check
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": project_id}
    # Update returns updated project
    mock_supabase_client.table.return_value \
        .update.return_value \
        .eq.return_value \
        .eq.return_value \
        .execute.return_value.data = [updated_project]

    # Send null for description, valid name - should update name only
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "New Name", "description": None},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


# --- T-05: Missing org and cross-tenant ---

async def test_get_project_org_not_found(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """GET /api/v1/projects/{id} when org not found returns 404 ORG_NOT_FOUND."""
    project_id = sample_project["id"]
    # Org lookup returns None
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.get(f"/api/v1/projects/{project_id}")

    assert response.status_code == 404
    assert response.json()["error"] == "ORG_NOT_FOUND"


async def test_update_project_org_not_found(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """PATCH /api/v1/projects/{id} when org not found returns 404 ORG_NOT_FOUND."""
    project_id = sample_project["id"]
    # Org lookup returns None
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Updated Name"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "ORG_NOT_FOUND"


async def test_delete_project_org_not_found(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """DELETE /api/v1/projects/{id} when org not found returns 404 ORG_NOT_FOUND."""
    project_id = sample_project["id"]
    # Org lookup returns None
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 404
    assert response.json()["error"] == "ORG_NOT_FOUND"


async def test_get_project_cross_tenant(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """GET /api/v1/projects/{id} from another tenant returns 404 PROJECT_NOT_FOUND."""
    project_id = sample_project["id"]
    # Org exists
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": "org-id"}
    # Project lookup returns None (cross-tenant or not found)
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.get(f"/api/v1/projects/{project_id}")

    assert response.status_code == 404
    assert response.json()["error"] == "PROJECT_NOT_FOUND"


async def test_update_project_cross_tenant(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """PATCH /api/v1/projects/{id} from another tenant returns 404 PROJECT_NOT_FOUND."""
    project_id = sample_project["id"]
    # Org exists
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": "org-id"}
    # Project ownership check returns None (cross-tenant)
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Updated Name"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "PROJECT_NOT_FOUND"


async def test_delete_project_cross_tenant(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """DELETE /api/v1/projects/{id} from another tenant returns 404 PROJECT_NOT_FOUND."""
    project_id = sample_project["id"]
    # Org exists
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = {"id": "org-id"}
    # Project ownership check returns None (cross-tenant)
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 404
    assert response.json()["error"] == "PROJECT_NOT_FOUND"


async def test_list_projects_401(test_app) -> None:
    """GET /api/v1/projects without auth token returns 401."""
    from fastapi import HTTPException, status as http_status

    def _fake_dep() -> None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "INVALID_TOKEN",
                "code": 401,
                "detail": "Invalid token",
            },
        )

    test_app.dependency_overrides[get_current_user] = _fake_dep
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/projects")

    assert response.status_code == 401
    assert response.json()["error"] == "INVALID_TOKEN"
