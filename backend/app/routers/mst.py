"""HTTP router for MST calculation endpoints.

POST /api/v1/projects/{id}/mst/calculate
  Runs the MST calculation for a project. Rate-limited (5/min per org).
  200: MSTCalculateResponse
  401: invalid token
  404: project not found OR belongs to another org (no leak)
  422: INSUFFICIENT_NODES / MANDATORY_CYCLE / DISCONNECTED_GRAPH

GET /api/v1/projects/{id}/mst/latest
  Returns the most recent mst_results row for the project.
  200: MSTLatestResponse
  401: invalid token
  404: project not found OR no MST result yet
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter

from app.core.mst_algorithm import (
    DisconnectedGraphError,
    InsufficientNodesError,
    MandatoryCycleError,
)
from app.core.rate_limit import limiter
from app.dependencies import get_current_user
from app.db.supabase_client import get_supabase_client
from app.schemas.mst import MSTCalculateResponse, MSTLatestResponse
from app.services import mst_service


router = APIRouter(prefix="/projects", tags=["mst"])


# ---------------------------------------------------------------------------
# Error helpers (consistent project format)
# ---------------------------------------------------------------------------


def _err(error: str, code: int, detail: str) -> HTTPException:
    """Build an HTTPException whose detail conforms to the project error
    format: { error, code, detail }.
    """
    return HTTPException(
        status_code=code,
        detail={"error": error, "code": code, "detail": detail},
    )


def _enrich_disconnected_detail(
    exc: DisconnectedGraphError,
) -> str:
    """Build a Spanish detail message for the disconnected-graph error
    that includes the unreachable node names when available. Falls back
    to a generic message.
    """
    n = len(exc.unreachable_nodes)
    if n == 0:
        return "El grafo tiene subgrafos no conectados."
    if n == 1:
        return "El grafo tiene un nodo no alcanzable desde el resto."
    return f"El grafo tiene {n} nodos no alcanzables desde el componente principal."


# ---------------------------------------------------------------------------
# POST /projects/{id}/mst/calculate
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/mst/calculate",
    response_model=MSTCalculateResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("5/minute")
async def calculate_mst(
    request: Request,  # required by slowapi's decorator
    project_id: UUID,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    """Run MST for a project. Rate-limited (5/min per organization_id)."""
    org_id_str = user["org_id"]
    try:
        org_id = UUID(org_id_str)
    except (ValueError, TypeError):
        # Should never happen if get_current_user is healthy, but if
        # the JWT is somehow malformed we treat it as 401-shaped error.
        raise _err("INVALID_TOKEN", 401, "Token inválido")

    try:
        return await mst_service.calculate_mst(
            supabase=supabase,
            project_id=project_id,
            org_id=org_id,
        )
    except mst_service.ProjectNotFound:
        # No existence leak: 404 with the same message as any other
        # missing project.
        raise _err(
            "NOT_FOUND", 404, "Proyecto no encontrado"
        )
    except InsufficientNodesError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "INSUFFICIENT_NODES",
                "code": 422,
                "detail": exc.message,
            },
        )
    except MandatoryCycleError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "MANDATORY_CYCLE",
                "code": 422,
                "detail": "Los edges mandatory forman un ciclo",
                "conflicting_edge_ids": [
                    str(eid) for eid in exc.conflicting_edge_ids
                ],
            },
        )
    except DisconnectedGraphError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "DISCONNECTED_GRAPH",
                "code": 422,
                "detail": _enrich_disconnected_detail(exc),
                "unreachable_nodes": [
                    str(nid) for nid in exc.unreachable_nodes
                ],
            },
        )


# ---------------------------------------------------------------------------
# GET /projects/{id}/mst/latest
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/mst/latest",
    response_model=MSTLatestResponse,
    status_code=status.HTTP_200_OK,
)
async def get_latest_mst(
    project_id: UUID,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
):
    """Return the most recent MST result for a project."""
    org_id_str = user["org_id"]
    try:
        org_id = UUID(org_id_str)
    except (ValueError, TypeError):
        raise _err("INVALID_TOKEN", 401, "Token inválido")

    try:
        return await mst_service.get_latest_mst(
            supabase=supabase,
            project_id=project_id,
            org_id=org_id,
        )
    except mst_service.ProjectNotFound:
        raise _err(
            "NOT_FOUND", 404, "Proyecto no encontrado"
        )
    except mst_service.NoMSTResult:
        raise _err(
            "NO_RESULT",
            404,
            "No hay resultados de MST para este proyecto",
        )
