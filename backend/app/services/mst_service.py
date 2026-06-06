"""Async service wrapper for MST calculation.

This module owns ALL database IO for the MST domain. The pure core
(app.core.mst_algorithm.calculate) handles the math; this service
handles:

  - tenant-scoped reads (project, nodes, edges)
  - dataclass conversion (Supabase rows -> NodeDict/EdgeDict)
  - persistence (insert into mst_results on success ONLY)
  - enrichment (resolve source_node_name from loaded nodes)
  - error surfacing (ProjectNotFound for cross-tenant; core exceptions
    are re-raised for the router to map)

The router (app.routers.mst) calls into this service. Exceptions
raised here are mapped to HTTP status codes by the router; this
service does not know about HTTP.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from supabase import Client

from app.core.mst_algorithm import (
    DisconnectedGraphError,
    EdgeDict,
    InsufficientNodesError,
    MandatoryCycleError,
    MSTResult,
    NodeDict,
    calculate as core_calculate,
)
from app.schemas.mst import (
    MSTCalculateResponse,
    MSTEdgeResponse,
    MSTLatestResponse,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ProjectNotFound(Exception):
    """Raised when the project does not exist OR belongs to another
    organization. The router maps this to 404 (no existence leak).
    """


# ---------------------------------------------------------------------------
# Service: POST /mst/calculate
# ---------------------------------------------------------------------------


async def calculate_mst(
    supabase: Client,
    project_id: UUID,
    org_id: UUID,
) -> MSTCalculateResponse:
    """Load the project tenant-scoped, run MST, persist, return enriched.

    Persistence rule (REQ-MST-006): the mst_results row is inserted ONLY
    after the core returns a successful MSTResult. Any exception from
    the core (InsufficientNodes, MandatoryCycle, DisconnectedGraph) is
    re-raised WITHOUT writing to the database.

    Enrichment: source_node_name is resolved from the nodes we already
    loaded, using a dict lookup (O(1) per edge). If a node referenced
    by an edge is missing (deleted between calculate and persist), we
    fall back to a truncated UUID string so the response is never
    inconsistent.
    """
    # 1. Tenant-scoped project existence check.
    project_resp = (
        supabase.table("projects")
        .select("id, organization_id")
        .eq("id", str(project_id))
        .eq("organization_id", str(org_id))
        .maybe_single()
        .execute()
    )
    if project_resp.data is None:
        raise ProjectNotFound(f"Project {project_id} not found for org {org_id}")

    # 2. Load nodes (tenant-scoped via the project_id, which is
    #    already known to belong to the org from step 1).
    nodes_resp = (
        supabase.table("nodes")
        .select("id, name, type, lat, lng")
        .eq("project_id", str(project_id))
        .execute()
    )
    raw_nodes = nodes_resp.data or []

    # 3. Load edges (tenant-scoped).
    edges_resp = (
        supabase.table("edges")
        .select("id, node_a_id, node_b_id, cost, constraint_type")
        .eq("project_id", str(project_id))
        .execute()
    )
    raw_edges = edges_resp.data or []

    # 4. Convert to dataclasses.
    nodes: list[NodeDict] = [
        NodeDict(
            id=UUID(str(n["id"])),
            name=str(n["name"]),
            type=n["type"],  # already validated by Pydantic at insert
        )
        for n in raw_nodes
    ]
    edges: list[EdgeDict] = [
        EdgeDict(
            id=UUID(str(e["id"])),
            node_a_id=UUID(str(e["node_a_id"])),
            node_b_id=UUID(str(e["node_b_id"])),
            cost=float(e["cost"]),
            constraint_type=e["constraint_type"],
        )
        for e in raw_edges
    ]

    # 5. Call the pure core. The core raises typed exceptions on
    #    invalid inputs; we re-raise them after the core returns or
    #    fails so the router can map to HTTP codes.
    result: MSTResult = core_calculate(nodes, edges)

    # 6. Build the parameters echo (REQ-MST-006 audit field).
    parameters: dict[str, Any] = {
        "mandatory_edge_ids": [
            str(e.id) for e in edges if e.constraint_type == "mandatory"
        ],
        "forbidden_edge_ids": [
            str(e.id) for e in edges if e.constraint_type == "forbidden"
        ],
        "node_count": len(nodes),
        "edge_count": len(edges),
    }

    # 7. Persist the result. This happens ONLY on success.
    insert_payload = {
        "project_id": str(project_id),
        "algorithm": "kruskal",
        "total_cost": float(result.total_cost),
        "edge_ids": [str(e.id) for e in result.edges],
        "parameters": parameters,
    }
    insert_resp = (
        supabase.table("mst_results").insert(insert_payload).execute()
    )
    # The response from insert is the inserted row; capture its
    # calculated_at and id for the response envelope.
    if not insert_resp.data:
        # Defensive: PostgREST would normally return the row.
        raise RuntimeError("mst_results insert returned no data")
    persisted = insert_resp.data[0]
    created_at_raw = persisted.get("calculated_at")
    if isinstance(created_at_raw, str):
        # Supabase returns ISO 8601 strings; parse them.
        created_at = datetime.fromisoformat(
            created_at_raw.replace("Z", "+00:00")
        )
    elif isinstance(created_at_raw, datetime):
        created_at = created_at_raw
    else:
        # Fallback: now in UTC. Should not happen with the real client.
        created_at = datetime.now(tz=timezone.utc)

    # 8. Enrich edges with source_node_name. We use the ALREADY LOADED
    #    nodes; no second DB call needed.
    node_name_by_id: dict[UUID, str] = {n.id: n.name for n in nodes}

    def _enrich(edge: EdgeDict) -> MSTEdgeResponse:
        return MSTEdgeResponse(
            edge_id=edge.id,
            cost=float(edge.cost),
            node_a_id=edge.node_a_id,
            node_b_id=edge.node_b_id,
            type=edge.constraint_type,  # type: ignore[arg-type]
            source_node_name=node_name_by_id.get(
                edge.node_a_id, str(edge.node_a_id)[:8]
            ),
        )

    mst_edges = [_enrich(e) for e in result.edges]
    mandatory_edges = [e for e in mst_edges if e.type == "mandatory"]

    return MSTCalculateResponse(
        project_id=project_id,
        total_cost=float(result.total_cost),
        mst_edges=mst_edges,
        mandatory_edges=mandatory_edges,
        parameters=parameters,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Service: GET /mst/latest
# ---------------------------------------------------------------------------


async def get_latest_mst(
    supabase: Client,
    project_id: UUID,
    org_id: UUID,
) -> MSTLatestResponse:
    """Return the most recent mst_results row for a project.

    Raises:
        ProjectNotFound: project does not exist OR belongs to another org.
        NoMSTResult: project has no mst_results yet.
    """
    # 1. Tenant-scoped project check.
    project_resp = (
        supabase.table("projects")
        .select("id, organization_id")
        .eq("id", str(project_id))
        .eq("organization_id", str(org_id))
        .maybe_single()
        .execute()
    )
    if project_resp.data is None:
        raise ProjectNotFound(f"Project {project_id} not found for org {org_id}")

    # 2. Load the latest mst_results row for the project.
    latest_resp = (
        supabase.table("mst_results")
        .select("*")
        .eq("project_id", str(project_id))
        .order("calculated_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = latest_resp.data or []
    if not rows:
        raise NoMSTResult(
            f"No MST results for project {project_id}"
        )
    row = rows[0]

    # 3. Load the edges referenced by the latest result so we can
    #    enrich each one with the ORIGINAL cost / type / node info.
    edge_ids = [str(eid) for eid in row.get("edge_ids", [])]
    edges_resp = (
        supabase.table("edges")
        .select("id, node_a_id, node_b_id, cost, constraint_type")
        .in_("id", edge_ids)
        .execute()
    )
    raw_edges = edges_resp.data or []
    edge_by_id: dict[UUID, dict[str, Any]] = {
        UUID(str(e["id"])): e for e in raw_edges
    }

    # 4. Load the nodes referenced by the loaded edges so we can
    #    enrich source_node_name.
    referenced_node_ids: set[UUID] = set()
    for e in raw_edges:
        referenced_node_ids.add(UUID(str(e["node_a_id"])))
        referenced_node_ids.add(UUID(str(e["node_b_id"])))
    nodes_resp = (
        supabase.table("nodes")
        .select("id, name")
        .in_(
            "id", [str(nid) for nid in referenced_node_ids]
        )
        .execute()
    )
    raw_nodes = nodes_resp.data or []
    node_name_by_id: dict[UUID, str] = {
        UUID(str(n["id"])): str(n["name"]) for n in raw_nodes
    }

    # 5. Build MSTEdgeResponse list in the order persisted.
    mst_edges: list[MSTEdgeResponse] = []
    for eid in row.get("edge_ids", []):
        e = edge_by_id.get(UUID(str(eid)))
        if e is None:
            # Edge was deleted between calculate and latest. Skip it
            # so the caller sees only edges that still exist.
            continue
        mst_edges.append(
            MSTEdgeResponse(
                edge_id=UUID(str(eid)),
                cost=float(e["cost"]),
                node_a_id=UUID(str(e["node_a_id"])),
                node_b_id=UUID(str(e["node_b_id"])),
                type=e["constraint_type"],  # type: ignore[arg-type]
                source_node_name=node_name_by_id.get(
                    UUID(str(e["node_a_id"])),
                    str(e["node_a_id"])[:8],
                ),
            )
        )
    mandatory_edges = [e for e in mst_edges if e.type == "mandatory"]

    # 6. Build the response.
    created_at_raw = row.get("calculated_at")
    if isinstance(created_at_raw, str):
        created_at = datetime.fromisoformat(
            created_at_raw.replace("Z", "+00:00")
        )
    elif isinstance(created_at_raw, datetime):
        created_at = created_at_raw
    else:
        created_at = datetime.now(tz=timezone.utc)

    return MSTLatestResponse(
        result_id=UUID(str(row["id"])),
        project_id=project_id,
        total_cost=float(row["total_cost"]),
        mst_edges=mst_edges,
        mandatory_edges=mandatory_edges,
        parameters=row.get("parameters") or {},
        created_at=created_at,
    )


class NoMSTResult(Exception):
    """Raised when the project has no mst_results yet."""
