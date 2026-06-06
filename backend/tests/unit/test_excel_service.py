"""Unit tests for excel_service.build_export_workbook.

These are pure-function tests: build_export_workbook takes Python dicts
and returns a BytesIO with an openpyxl workbook. No mocks, no IO,
no async.
"""
from __future__ import annotations

import uuid
from io import BytesIO

import openpyxl
import pytest

from app.services.excel_service import build_export_workbook


# ---------------------------------------------------------------------------
# Helpers — builders with deterministic UUIDs
# ---------------------------------------------------------------------------

def _project(**overrides: object) -> dict:
    base = {
        "id": "33333333-3333-3333-3333-333333333333",
        "name": "Test Project",
        "description": "A project for testing",
        "organization_id": "11111111-1111-1111-1111-111111111111",
        "created_by": "22222222-2222-2222-2222-222222222222",
        "created_at": "2026-06-06T00:00:00+00:00",
        "updated_at": "2026-06-06T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _node(idx: int, name: str | None = None, type_: str = "city") -> dict:
    return {
        "id": str(uuid.UUID(int=idx)),
        "project_id": "33333333-3333-3333-3333-333333333333",
        "name": name or f"Node {idx}",
        "type": type_,
        "lat": float(idx * 10),
        "lng": float(-idx * 10),
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


def _mst_result(edge_indices: list[int], total_cost: float = 25.0) -> dict:
    """Build a minimal mst_result dict with edge_ids as strings."""
    return {
        "edge_ids": [str(uuid.UUID(int=10_000 + i)) for i in edge_indices],
        "total_cost": total_cost,
        "algorithm": "kruskal",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_workbook_has_three_sheets() -> None:
    """Sheet names match expected: Project Info, Nodes, Edges & MST."""
    project = _project()
    nodes = [_node(1), _node(2)]
    edges = [_edge(1, 1, 2)]
    buf = build_export_workbook(project, nodes, edges, None)

    wb = openpyxl.load_workbook(BytesIO(buf.getvalue()))
    assert wb.sheetnames == ["Project Info", "Nodes", "Edges & MST"]


def test_workbook_project_info_content() -> None:
    """Project Info sheet contains project name, description, counts."""
    project = _project(name="Alpha", description="Desc A")
    nodes = [_node(1), _node(2), _node(3)]
    edges = [_edge(1, 1, 2, cost=5.0), _edge(2, 2, 3, cost=10.0)]
    mst = _mst_result([1], total_cost=5.0)

    buf = build_export_workbook(project, nodes, edges, mst)
    wb = openpyxl.load_workbook(BytesIO(buf.getvalue()))
    ws = wb["Project Info"]

    # Read all cells as a dict of (row, col) -> value
    info = {}
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row,
                            max_col=ws.max_column, values_only=False):
        key = str(row[0].value) if row[0].value else ""
        val = str(row[1].value) if len(row) > 1 and row[1].value is not None else ""
        info[key.rstrip(":")] = val

    assert info.get("Project Name") == "Alpha"
    assert info.get("Description") == "Desc A"
    assert info.get("Nodes") == "3"
    assert info.get("Edges") == "2"
    assert info.get("Total Cost") == "5.0"


def test_workbook_nodes_sheet_columns_and_data() -> None:
    """Nodes sheet has correct columns and sorted data."""
    project = _project()
    nodes = [
        _node(2, name="Bravo"),
        _node(1, name="Alpha"),
    ]
    buf = build_export_workbook(project, nodes, [], None)
    wb = openpyxl.load_workbook(BytesIO(buf.getvalue()))
    ws = wb["Nodes"]

    # Header row
    headers = [cell.value for cell in ws[1]]
    assert headers == ["Label", "Type", "Latitude", "Longitude"]

    # Data rows — sorted by label
    rows = list(ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True))
    assert len(rows) == 2
    assert rows[0][0] == "Alpha"
    assert rows[0][1] == "city"
    assert rows[1][0] == "Bravo"


def test_workbook_edges_sheet_with_mst_flag() -> None:
    """Edges & MST sheet shows edges with correct MST flag."""
    project = _project()
    nodes = [_node(1, "Node A"), _node(2, "Node B"), _node(3, "Node C")]
    edges = [
        _edge(1, 1, 2, cost=5.0),    # in MST
        _edge(2, 2, 3, cost=10.0),   # in MST
        _edge(3, 1, 3, cost=20.0),   # NOT in MST
    ]
    mst = _mst_result([1, 2], total_cost=15.0)

    buf = build_export_workbook(project, nodes, edges, mst)
    wb = openpyxl.load_workbook(BytesIO(buf.getvalue()))
    ws = wb["Edges & MST"]

    headers = [cell.value for cell in ws[1]]
    assert headers == ["Node A", "Node B", "Cost", "Constraint", "In MST"]

    # Check each edge's MST flag
    edge_rows: dict[str, dict[str, object]] = {}
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
        if row[0] is None:
            continue
        key = f"{row[0]}→{row[1]}"
        edge_rows[key] = {
            "cost": row[2],
            "constraint": row[3],
            "in_mst": row[4],
        }

    assert edge_rows["Node A→Node B"]["in_mst"] == "Yes"
    assert edge_rows["Node B→Node C"]["in_mst"] == "Yes"
    assert edge_rows["Node A→Node C"]["in_mst"] == "No"


def test_workbook_without_mst_result() -> None:
    """All edges have MST flag 'No' when mst_result is None."""
    project = _project()
    nodes = [_node(1, "X"), _node(2, "Y")]
    edges = [_edge(1, 1, 2, cost=7.0)]

    buf = build_export_workbook(project, nodes, edges, None)
    wb = openpyxl.load_workbook(BytesIO(buf.getvalue()))
    ws = wb["Edges & MST"]

    rows = list(ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True))
    assert len(rows) == 1
    assert rows[0][4] == "No"  # In MST column


def test_workbook_empty_nodes() -> None:
    """Empty nodes list produces valid workbook with header-only sheets."""
    project = _project()
    buf = build_export_workbook(project, [], [], None)
    wb = openpyxl.load_workbook(BytesIO(buf.getvalue()))

    ws_nodes = wb["Nodes"]
    headers = [cell.value for cell in ws_nodes[1]]
    assert headers == ["Label", "Type", "Latitude", "Longitude"]
    # No data rows
    assert ws_nodes.max_row == 1 or all(
        cell.value is None for cell in ws_nodes.iter_rows(min_row=2, max_row=2)
    )


def test_workbook_return_type() -> None:
    """Function returns a BytesIO, not written to disk."""
    project = _project()
    result = build_export_workbook(project, [], [], None)
    assert isinstance(result, BytesIO)
    # Must contain valid xlsx signature bytes
    data = result.getvalue()
    assert data[:2] == b"PK"  # xlsx is a ZIP archive


def test_workbook_headers_are_bold() -> None:
    """Header row cells have bold font style."""
    project = _project()
    nodes = [_node(1)]
    buf = build_export_workbook(project, nodes, [], None)
    wb = openpyxl.load_workbook(BytesIO(buf.getvalue()))

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for cell in ws[1]:
            if cell.value is not None:
                assert cell.font and cell.font.bold, \
                    f"Header '{cell.value}' in sheet '{sheet_name}' is not bold"
