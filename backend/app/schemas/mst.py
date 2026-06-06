"""Pydantic schemas for the MST calculation domain.

These extend / replace the original stubs to match the spec at
`openspec/changes/mst-calculation-endpoint/specs/mst/spec.md`:
- MSTEdgeResponse is enriched with source_node_name (resolved from
  nodes.name at calculation time) and the original `type` literal.
- MSTCalculateResponse is the 200 response for POST /mst/calculate.
- MSTLatestResponse extends MSTCalculateResponse with the persisted
  result_id (the mst_results row id).
"""
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------


ConstraintType = Literal["normal", "mandatory", "forbidden"]


class MSTEdgeResponse(BaseModel):
    """One edge in the MST result.

    `type` is the ORIGINAL constraint_type from the edges table (not
    mutated by the MST run). `source_node_name` is enriched server-side
    from nodes.name to keep the frontend from doing an extra lookup;
    it falls back to a truncated UUID string when the node is missing
    (e.g. node was deleted between calculate and latest).
    """

    edge_id: UUID
    cost: float
    node_a_id: UUID
    node_b_id: UUID
    type: ConstraintType
    source_node_name: str


# ---------------------------------------------------------------------------
# Calculate response (POST /projects/{id}/mst/calculate)
# ---------------------------------------------------------------------------


class MSTCalculateResponse(BaseModel):
    project_id: UUID
    total_cost: float
    mst_edges: list[MSTEdgeResponse]
    # Subset of mst_edges whose original constraint_type == "mandatory".
    mandatory_edges: list[MSTEdgeResponse]
    # Echo of inputs for audit: {mandatory_edge_ids, forbidden_edge_ids,
    # node_count, edge_count}.
    parameters: dict[str, Any]
    created_at: datetime


# ---------------------------------------------------------------------------
# Latest response (GET /projects/{id}/mst/latest)
# ---------------------------------------------------------------------------


class MSTLatestResponse(MSTCalculateResponse):
    """Same as MSTCalculateResponse plus the persisted result id."""

    result_id: UUID
