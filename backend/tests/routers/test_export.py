"""Integration tests for the export router.

Covers:
  - Excel export: 200 with correct content-type and disposition
  - PDF export: 200 with correct content-type and disposition
  - PDF export with valid base64 map image
  - PDF export with invalid base64 → 422
  - Unauthenticated requests → 401 (both endpoints)
  - Cross-tenant / not found → 404 (both endpoints)
  - Empty project (no nodes/edges) still exports successfully
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status as http_status
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user

# A minimal valid 1×1 red PNG in base64.
_VALID_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4"
    "nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project_resolved(
    mock: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """Set up mocks so that _load_project_data succeeds with the given project.

    Nodes and edges return empty lists (shared mock chain).
    """
    # Project fetch (tenant-scoped) — .select("*").eq("id").eq(org).single()
    mock.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = sample_project

    # Nodes & edges — both use .select("*").eq("project_id").execute()
    mock.table.return_value \
        .select.return_value \
        .eq.return_value \
        .execute.return_value.data = []

    # MST result — .select("*").eq("project_id").order(...).limit(...).execute()
    mock.table.return_value \
        .select.return_value \
        .eq.return_value \
        .order.return_value \
        .limit.return_value \
        .execute.return_value.data = []


# ===================================================================
# Excel export
# ===================================================================


async def test_export_excel_success(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """GET /projects/{id}/export/excel returns 200 with .xlsx headers."""
    _make_project_resolved(mock_supabase_client, sample_project)

    response = await client.get(
        f"/api/v1/projects/{sample_project['id']}/export/excel",
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    disp = response.headers["content-disposition"]
    assert "attachment;" in disp
    assert 'filename="project-Test Project-export.xlsx"' in disp


async def test_export_excel_401(test_app) -> None:
    """GET /export/excel without auth returns 401."""
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
        response = await ac.get(
            "/api/v1/projects/33333333-3333-3333-3333-333333333333/export/excel",
        )

    assert response.status_code == 401
    assert response.json()["error"] == "INVALID_TOKEN"


async def test_export_excel_404(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """GET /export/excel on non-existent / cross-tenant project returns 404."""
    # Project not found → .single().execute().data = None
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.get(
        f"/api/v1/projects/{sample_project['id']}/export/excel",
    )

    assert response.status_code == 404
    assert response.json()["error"] == "PROJECT_NOT_FOUND"


# ===================================================================
# PDF export
# ===================================================================


async def test_export_pdf_success(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """POST /projects/{id}/export/pdf returns 200 with PDF headers."""
    _make_project_resolved(mock_supabase_client, sample_project)

    response = await client.post(
        f"/api/v1/projects/{sample_project['id']}/export/pdf",
        json={"map_image_base64": ""},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    disp = response.headers["content-disposition"]
    assert "attachment;" in disp
    assert 'filename="project-Test Project-report.pdf"' in disp
    # Verify it's a valid PDF (starts with %PDF)
    assert response.content[:4] == b"%PDF"


async def test_export_pdf_with_image(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """POST /export/pdf with valid base64 map image returns 200 + PDF."""
    _make_project_resolved(mock_supabase_client, sample_project)

    response = await client.post(
        f"/api/v1/projects/{sample_project['id']}/export/pdf",
        json={"map_image_base64": _VALID_PNG_B64},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"
    # PDF with embedded image should be larger than bare-minimum PDF
    assert len(response.content) > 2000


async def test_export_pdf_invalid_base64(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """POST /export/pdf with invalid base64 returns 422."""
    _make_project_resolved(mock_supabase_client, sample_project)

    response = await client.post(
        f"/api/v1/projects/{sample_project['id']}/export/pdf",
        json={"map_image_base64": "not-valid-base64!!!"},
    )

    assert response.status_code == 422
    err = response.json()
    assert err["error"] == "INVALID_MAP_IMAGE"


async def test_export_pdf_401(test_app) -> None:
    """POST /export/pdf without auth returns 401."""
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
        response = await ac.post(
            "/api/v1/projects/33333333-3333-3333-3333-333333333333/export/pdf",
            json={"map_image_base64": ""},
        )

    assert response.status_code == 401
    assert response.json()["error"] == "INVALID_TOKEN"


async def test_export_pdf_404(
    client: AsyncClient,
    mock_supabase_client: MagicMock,
    sample_project: dict[str, Any],
) -> None:
    """POST /export/pdf on non-existent / cross-tenant project returns 404."""
    mock_supabase_client.table.return_value \
        .select.return_value \
        .eq.return_value \
        .eq.return_value \
        .single.return_value \
        .execute.return_value.data = None

    response = await client.post(
        f"/api/v1/projects/{sample_project['id']}/export/pdf",
        json={"map_image_base64": ""},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "PROJECT_NOT_FOUND"
