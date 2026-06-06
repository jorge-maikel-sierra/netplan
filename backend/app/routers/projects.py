from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from typing import List

from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectDetailResponse
from app.dependencies import get_current_user
from app.db.supabase_client import get_supabase_client

router = APIRouter(prefix="/projects", tags=["projects"])


def _error_response(error: str, code: int, detail: str) -> HTTPException:
    """Returns a consistent error format: { error, code, detail }"""
    return HTTPException(
        status_code=code,
        detail={"error": error, "code": code, "detail": detail},
    )


@router.get("", response_model=List[ProjectResponse])
async def list_projects(user: dict = Depends(get_current_user)):
    """
    List all projects for the current tenant.
    """
    supabase = get_supabase_client()
    org_id = user["org_id"]

    response = (
        supabase.table("projects")
        .select("*")
        .eq("organization_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )

    return response.data or []


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    user: dict = Depends(get_current_user),
):
    """
    Create a new project for the current tenant.
    Enforces free-tier limit (max 3 projects for free plan).
    """
    supabase = get_supabase_client()
    org_id = user["org_id"]
    user_id = user["user_id"]

    # Check free-tier limit
    org_response = (
        supabase.table("organizations")
        .select("plan")
        .eq("id", org_id)
        .single()
        .execute()
    )

    if org_response.data is None:
        raise _error_response("ORG_NOT_FOUND", 404, "Organization not found")

    plan = org_response.data.get("plan", "free")

    if plan == "free":
        count_response = (
            supabase.table("projects")
            .select("id", count="exact")
            .eq("organization_id", org_id)
            .execute()
        )

        project_count = count_response.count or 0
        if project_count >= 3:
            raise _error_response(
                "FREE_TIER_LIMIT",
                403,
                "Free tier allows maximum 3 projects. Upgrade to premium to create more.",
            )

    # Create project
    project_payload = {
        "organization_id": org_id,
        "created_by": user_id,
        "name": project_data.name,
        "description": project_data.description,
    }

    response = supabase.table("projects").insert(project_payload).execute()

    if not response.data:
        raise _error_response("CREATE_FAILED", 500, "Failed to create project")

    return response.data[0]


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: UUID,
    user: dict = Depends(get_current_user),
):
    """
    Get project detail with nodes, edges, and last MST result.
    Returns 404 if project doesn't exist or belongs to another tenant.
    """
    supabase = get_supabase_client()
    org_id = user["org_id"]

    # Fetch project (tenant-scoped)
    project_response = (
        supabase.table("projects")
        .select("*")
        .eq("id", str(project_id))
        .eq("organization_id", org_id)
        .single()
        .execute()
    )

    if project_response.data is None:
        raise _error_response("PROJECT_NOT_FOUND", 404, "Project not found")

    project = project_response.data

    # Fetch nodes
    nodes_response = (
        supabase.table("nodes")
        .select("*")
        .eq("project_id", str(project_id))
        .execute()
    )
    nodes = nodes_response.data or []

    # Fetch edges
    edges_response = (
        supabase.table("edges")
        .select("*")
        .eq("project_id", str(project_id))
        .execute()
    )
    edges = edges_response.data or []

    # Fetch latest MST result
    mst_response = (
        supabase.table("mst_results")
        .select("*")
        .eq("project_id", str(project_id))
        .order("calculated_at", desc=True)
        .limit(1)
        .execute()
    )
    last_result = mst_response.data[0] if mst_response.data else None

    return {
        "id": project["id"],
        "name": project["name"],
        "description": project["description"],
        "nodes": nodes,
        "edges": edges,
        "last_result": last_result,
    }


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    user: dict = Depends(get_current_user),
):
    """
    Update project name or description.
    Returns 404 if project doesn't exist or belongs to another tenant.
    """
    supabase = get_supabase_client()
    org_id = user["org_id"]

    # Check ownership first (tenant isolation)
    check_response = (
        supabase.table("projects")
        .select("id")
        .eq("id", str(project_id))
        .eq("organization_id", org_id)
        .single()
        .execute()
    )

    if check_response.data is None:
        raise _error_response("PROJECT_NOT_FOUND", 404, "Project not found")

    # Build update payload (only non-None fields)
    update_payload = {}
    if project_data.name is not None:
        update_payload["name"] = project_data.name
    if project_data.description is not None:
        update_payload["description"] = project_data.description

    if not update_payload:
        raise _error_response("NO_FIELDS_TO_UPDATE", 422, "No valid fields provided for update")

    response = (
        supabase.table("projects")
        .update(update_payload)
        .eq("id", str(project_id))
        .eq("organization_id", org_id)
        .execute()
    )

    return response.data[0]


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    user: dict = Depends(get_current_user),
):
    """
    Delete a project and all its children (nodes, edges, mst_results cascade).
    Returns 404 if project doesn't exist or belongs to another tenant.
    """
    supabase = get_supabase_client()
    org_id = user["org_id"]

    # Check ownership first
    check_response = (
        supabase.table("projects")
        .select("id")
        .eq("id", str(project_id))
        .eq("organization_id", org_id)
        .single()
        .execute()
    )

    if check_response.data is None:
        raise _error_response("PROJECT_NOT_FOUND", 404, "Project not found")

    # Delete project (cascades to nodes, edges, mst_results via FK)
    supabase.table("projects").delete().eq("id", str(project_id)).eq("organization_id", org_id).execute()