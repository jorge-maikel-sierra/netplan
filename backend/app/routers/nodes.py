from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from uuid import UUID
from typing import List
from app.dependencies import get_current_user
from app.db.supabase_client import get_supabase_client
from app.schemas.node import NodeCreate, NodeUpdate, NodeResponse, NodeImportResult
from app.services.excel_service import parse_nodes_xlsx

router = APIRouter(prefix="/projects", tags=["nodes"])


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


@router.post("/{project_id}/nodes", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(project_id: UUID, node: NodeCreate, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    data = node.model_dump()
    data["project_id"] = str(project_id)
    
    response = supabase.table("nodes").insert(data).execute()
    return response.data[0]


@router.get("/{project_id}/nodes", response_model=List[NodeResponse])
async def list_nodes(project_id: UUID, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    response = supabase.table("nodes").select("*").eq("project_id", str(project_id)).execute()
    return response.data or []


@router.put("/{project_id}/nodes/{node_id}", response_model=NodeResponse)
async def update_node(project_id: UUID, node_id: UUID, node: NodeUpdate, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    # Verify node exists and belongs to project
    existing = supabase.table("nodes").select("id").eq("id", str(node_id)).eq("project_id", str(project_id)).single().execute()
    if not existing.data:
        raise _error_response("NOT_FOUND", 404, "Node not found")
    
    update_data = node.model_dump(exclude_unset=True)
    response = supabase.table("nodes").update(update_data).eq("id", str(node_id)).execute()
    return response.data[0]


@router.delete("/{project_id}/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(project_id: UUID, node_id: UUID, user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    existing = supabase.table("nodes").select("id").eq("id", str(node_id)).eq("project_id", str(project_id)).single().execute()
    if not existing.data:
        raise _error_response("NOT_FOUND", 404, "Node not found")
    
    supabase.table("nodes").delete().eq("id", str(node_id)).execute()


@router.post("/{project_id}/nodes/import", response_model=NodeImportResult)
async def import_nodes(project_id: UUID, file: UploadFile = File(...), user=Depends(get_current_user)):
    supabase = get_supabase_client()
    await _verify_project(project_id, user["org_id"], supabase)
    
    # Validate MIME type
    allowed_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if file.content_type != allowed_mime:
        raise _error_response("INVALID_FILE_TYPE", 422, "Only .xlsx files are supported")
    
    file_bytes = await file.read()
    
    # Parse and validate
    valid_rows, errors = parse_nodes_xlsx(file_bytes)
    
    if not valid_rows and not errors:
        raise _error_response("EMPTY_FILE", 422, "No valid data found in file")
    
    # Insert valid rows
    imported = 0
    for row in valid_rows:
        row["project_id"] = str(project_id)
        try:
            supabase.table("nodes").insert(row).execute()
            imported += 1
        except Exception:
            errors.append({"row": row.get("row_num", "?"), "field": "general", "message": "Failed to insert row"})
    
    return NodeImportResult(
        imported=imported,
        skipped=len(errors),
        errors=errors
    )