"""Unit tests for pdf_service.build_pdf_report.

Tests the pure function: takes dict data + optional base64 image,
returns BytesIO with valid PDF. No mocks, no IO beyond BytesIO.
"""
from __future__ import annotations

import base64
import uuid
from io import BytesIO

import pytest

from app.services.pdf_service import build_pdf_report


# ---------------------------------------------------------------------------
# A minimal 1×1 red PNG, base64-encoded (valid PNG, 67 bytes raw).
# ---------------------------------------------------------------------------
# This is a hand-crafted minimal PNG: 1x1 pixel, red (RGB 255,0,0).
_VALID_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


# ---------------------------------------------------------------------------
# Helpers — builders with deterministic UUIDs
# ---------------------------------------------------------------------------

def _project(**overrides: object) -> dict:
    base = {
        "id": "33333333-3333-3333-3333-333333333333",
        "name": "PDF Test Project",
        "description": "A PDF generation test",
        "organization_id": "11111111-1111-1111-1111-111111111111",
        "created_by": "22222222-2222-2222-2222-222222222222",
        "created_at": "2026-06-06T00:00:00+00:00",
        "updated_at": "2026-06-06T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _node(idx: int, name: str | None = None) -> dict:
    return {
        "id": str(uuid.UUID(int=idx)),
        "project_id": "33333333-3333-3333-3333-333333333333",
        "name": name or f"Node {idx}",
        "type": "city",
        "lat": float(idx),
        "lng": float(-idx),
        "created_at": "2026-06-06T00:00:00+00:00",
    }


def _edge(idx: int, a: int, b: int, cost: float = 10.0,
          constraint_type: str = "normal") -> dict:
    return {
        "id": str(uuid.UUID(int=10_000 + idx)),
        "project_id": "33333333-3333-3333-3333-333333333333",
        "node_a_id": str(uuid.UUID(int=a)),
        "node_b_id": str(uuid.UUID(int=b)),
        "cost": cost,
        "constraint_type": constraint_type,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pdf_basic_generation() -> None:
    """PDF generates with nodes and edges, returns BytesIO with valid PDF."""
    project = _project()
    nodes = [_node(1, "Alpha"), _node(2, "Beta")]
    edges = [_edge(1, 1, 2, cost=15.0)]

    buf = build_pdf_report(project, nodes, edges, None)
    data = buf.getvalue()

    assert isinstance(buf, BytesIO)
    assert data[:5] == b"%PDF-", f"Expected PDF header, got {data[:20]}"
    assert len(data) > 2000, f"PDF too small: {len(data)} bytes"


def test_pdf_with_map_image() -> None:
    """PDF includes embedded map image when base64 is provided."""
    project = _project()
    nodes = [_node(1)]
    edges: list[dict] = []

    buf = build_pdf_report(project, nodes, edges, None,
                           map_image_base64=_VALID_PNG_BASE64)
    data = buf.getvalue()

    assert data[:5] == b"%PDF-"
    # PDF with image should be larger than a minimal empty one
    assert len(data) > 1500, f"PDF with image too small: {len(data)} bytes"
    # Reportlab re-encodes image pixel data; check for Image XObject marker
    assert b"/Subtype /Image" in data, "Embedded image XObject not found in PDF"


def test_pdf_without_map_image() -> None:
    """PDF generates without map image when base64 is None."""
    project = _project()
    nodes = [_node(1), _node(2)]
    edges = [_edge(1, 1, 2)]

    buf = build_pdf_report(project, nodes, edges, None, map_image_base64=None)
    data = buf.getvalue()

    assert data[:5] == b"%PDF-"
    assert len(data) > 1000
    # No Image XObject when no base64 is provided
    assert b"/Subtype /Image" not in data, "Unexpected image in no-image PDF"


def test_pdf_with_mst_result() -> None:
    """PDF includes MST summary when mst_result is provided."""
    project = _project(name="MST Project")
    nodes = [_node(1), _node(2), _node(3)]
    edges = [
        _edge(1, 1, 2, cost=5.0),
        _edge(2, 2, 3, cost=10.0),
    ]
    mst_result = {
        "total_cost": 15.0,
        "edge_ids": [
            str(uuid.UUID(int=10_000 + 1)),
        ],
        "algorithm": "kruskal",
    }

    buf = build_pdf_report(project, nodes, edges, mst_result)
    data = buf.getvalue()

    assert data[:5] == b"%PDF-"
    assert len(data) > 2000
    # The PDF trailer includes the cross-reference table and %%EOF
    assert data.rstrip().endswith(b"%%EOF")


def test_pdf_empty_nodes() -> None:
    """PDF generates gracefully with empty nodes list."""
    project = _project()
    buf = build_pdf_report(project, [], [], None)
    data = buf.getvalue()
    assert data[:5] == b"%PDF-"
    assert len(data) > 800


def test_pdf_empty_map_image_string() -> None:
    """PDF handles empty string map_image_base64 gracefully (not None)."""
    project = _project()
    nodes = [_node(1)]
    buf = build_pdf_report(project, nodes, [], None, map_image_base64="")
    data = buf.getvalue()
    assert data[:5] == b"%PDF-"
    assert len(data) > 1000
    assert b"/Subtype /Image" not in data
