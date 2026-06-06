from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List
from app.dependencies import get_current_user
from app.db.supabase_client import get_supabase_client
from app.schemas.edge import EdgeCreate, EdgeUpdate, EdgeConstraintUpdate, EdgeResponse

router = APIRouter(prefix="/projects", tags=["edges"])


def _error_response(code: str, status_code: int, detail: str):
    return HTTPException(
        status_code=status_code,
        detail={"error": code, "code": status_code, "detail": detail}
    )


async def _verify_project(project_id: UUID, org_id: str, supabase) -> dict:
    """Verify project exists and belongs to org. Returns project or raises 404."""
    response = supabase.table("projects").select("id").eq("id", str(project_id)).eq("organization_id", org_id).single().execute()
    if not response.data:
        raise _error_response("NOT_FOUND", 404, "Project not found")
    return response.data


async def _verify_nodes_exist(node_a_id: UUID, node_b_id: UUID, project_id: UUID, supabase) -> bool:
    """Verify both nodes exist and belong to the project."""
    response = supabase.table("nodes").select("id").eq("project_id", str(project_id)).in_("id", [str(node_a_id), str(node_b_id)]).execute()
    return len(response.data or []) == 2


@router.post("/{project_id}/edges", response_model=EdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_edge(project_id: UUID, edge: EdgeCreate, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    # Verify both nodes exist and belong to this project
    if not await _verify_nodes_exist(edge.node_a_id, edge.node_b_id, project_id, supabase):
        raise _error_response("NODES_NOT_FOUND", 422, "One or both nodes not found in this project")
    
    data = edge.model_dump()
    data["project_id"] = str(project_id)
    
    # Upsert using unique constraint (project_id, node_a_id, node_b_id)
    response = supabase.table("edges").upsert(
        data,
        on_conflict="project_id,node_a_id,node_b_id"
    ).execute()
    
    return response.data[0]


@router.delete("/{project_id}/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_edge(project_id: UUID, edge_id: UUID, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    existing = supabase.table("edges").select("id").eq("id", str(edge_id)).eq("project_id", str(project_id)).single().execute()
    if not existing.data:
        raise _error_response("NOT_FOUND", 404, "Edge not found")
    
    supabase.table("edges").delete().eq("id", str(edge_id)).execute()


@router.patch("/{project_id}/edges/{edge_id}/constraint", response_model=EdgeResponse)
async def update_edge_constraint(project_id: UUID, edge_id: UUID, constraint: EdgeConstraintUpdate, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    existing = supabase.table("edges").select("id").eq("id", str(edge_id)).eq("project_id", str(project_id)).single().execute()
    if not existing.data:
        raise _error_response("NOT_FOUND", 404, "Edge not found")
    
    response = supabase.table("edges").update({"constraint_type": constraint.constraint_type}).eq("id", str(edge_id)).execute()
    return response.data[0]