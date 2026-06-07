from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from uuid import UUID
from typing import List
from app.dependencies import get_current_user
from app.db.supabase_client import get_supabase_client
from app.schemas.edge import EdgeCreate, EdgeUpdate, EdgeConstraintUpdate, EdgeResponse, EdgeImportResult
from app.services.excel_service import parse_edges_xlsx

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


@router.get("/{project_id}/edges", response_model=List[EdgeResponse])
async def list_edges(project_id: UUID, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    response = supabase.table("edges").select("*").eq("project_id", str(project_id)).execute()
    edges = response.data or []
    
    # Convert UUIDs to strings for JSON serialization
    for edge in edges:
        for key in ['id', 'project_id', 'node_a_id', 'node_b_id']:
            if key in edge and edge[key] is not None:
                edge[key] = str(edge[key])
    return edges


@router.post("/{project_id}/edges", response_model=EdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_edge(project_id: UUID, edge: EdgeCreate, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    # Verify both nodes exist and belong to this project
    if not await _verify_nodes_exist(edge.node_a_id, edge.node_b_id, project_id, supabase):
        raise _error_response("NODES_NOT_FOUND", 422, "One or both nodes not found in this project")
    
    data = edge.model_dump()
    data["project_id"] = str(project_id)
    data["node_a_id"] = str(data["node_a_id"])
    data["node_b_id"] = str(data["node_b_id"])
    
    # Upsert using unique constraint (project_id, node_a_id, node_b_id)
    response = supabase.table("edges").upsert(
        data,
        on_conflict="project_id,node_a_id,node_b_id"
    ).execute()
    
    # Convert UUIDs to strings for JSON serialization
    result = response.data[0]
    for key in ['id', 'project_id', 'node_a_id', 'node_b_id']:
        if key in result and result[key] is not None:
            result[key] = str(result[key])
    return result


@router.delete("/{project_id}/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_edge(project_id: UUID, edge_id: UUID, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    existing = supabase.table("edges").select("id").eq("id", str(edge_id)).eq("project_id", str(project_id)).single().execute()
    if not existing.data:
        raise _error_response("NOT_FOUND", 404, "Edge not found")
    
    supabase.table("edges").delete().eq("id", str(edge_id)).execute()


@router.post("/{project_id}/edges/import", response_model=EdgeImportResult)
async def import_edges(project_id: UUID, file: UploadFile = File(...), user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    # Validate MIME type
    allowed_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if file.content_type != allowed_mime:
        raise _error_response("INVALID_FILE_TYPE", 422, "Only .xlsx files are supported")
    
    file_bytes = await file.read()
    
    # Parse edges
    valid_rows, errors = parse_edges_xlsx(file_bytes)
    
    if not valid_rows and not errors:
        raise _error_response("EMPTY_FILE", 422, "No valid data found in file")
    
    # Fetch existing nodes in this project to map names to IDs
    node_resp = supabase.table("nodes").select("id, name").eq("project_id", str(project_id)).execute()
    nodes = node_resp.data or []
    node_name_to_id = {n["name"]: n["id"] for n in nodes}
    
    imported = 0
    for row in valid_rows:
        row_num = row.get("row_num", "?")
        origen_name = row["origen"]
        destino_name = row["destino"]
        
        # Validate node references
        if origen_name not in node_name_to_id:
            errors.append({"row": row_num, "field": "origen", "message": f"Node '{origen_name}' not found in project"})
            continue
        if destino_name not in node_name_to_id:
            errors.append({"row": row_num, "field": "destino", "message": f"Node '{destino_name}' not found in project"})
            continue
        
        node_a_id = str(node_name_to_id[origen_name])
        node_b_id = str(node_name_to_id[destino_name])
        
        edge_data = {
            "project_id": str(project_id),
            "node_a_id": node_a_id,
            "node_b_id": node_b_id,
            "cost": row["costo"],
            "constraint_type": row["tipo_restriccion"],
        }
        
        try:
            supabase.table("edges").upsert(
                edge_data,
                on_conflict="project_id,node_a_id,node_b_id"
            ).execute()
            imported += 1
        except Exception:
            errors.append({"row": row_num, "field": "general", "message": "Failed to insert edge"})
    
    return EdgeImportResult(
        imported=imported,
        skipped=len(errors),
        errors=errors
    )


@router.patch("/{project_id}/edges/{edge_id}/constraint", response_model=EdgeResponse)
async def update_edge_constraint(project_id: UUID, edge_id: UUID, constraint: EdgeConstraintUpdate, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    existing = supabase.table("edges").select("id").eq("id", str(edge_id)).eq("project_id", str(project_id)).single().execute()
    if not existing.data:
        raise _error_response("NOT_FOUND", 404, "Edge not found")
    
    response = supabase.table("edges").update({"constraint_type": constraint.constraint_type}).eq("id", str(edge_id)).execute()
    
    result = response.data[0]
    for key in ['id', 'project_id', 'node_a_id', 'node_b_id']:
        if key in result and result[key] is not None:
            result[key] = str(result[key])
    return result