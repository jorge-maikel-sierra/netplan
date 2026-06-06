"""Export router — Excel and PDF project export endpoints.

Endpoints:
  GET  /projects/{project_id}/export/excel  → .xlsx download
  POST /projects/{project_id}/export/pdf    → .pdf download
"""
import base64
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.dependencies import get_current_user
from app.db.supabase_client import get_supabase_client
from app.schemas.export import PDFExportRequest
from app.services.excel_service import build_export_workbook
from app.services.pdf_service import build_pdf_report

router = APIRouter(prefix="/projects/{project_id}/export", tags=["export"])


def _error_response(code: str, status_code: int, detail: str) -> HTTPException:
    """Return a consistent error format: { error, code, detail }."""
    return HTTPException(
        status_code=status_code,
        detail={"error": code, "code": status_code, "detail": detail},
    )


def _load_project_data(project_id: UUID, org_id: str, supabase):
    """Fetch project, nodes, edges, and latest MST result.

    Returns:
        tuple[dict, list[dict], list[dict], dict | None]

    Raises 404 (PROJECT_NOT_FOUND) if the project does not exist or
    belongs to a different organization.
    """
    # Fetch project (tenant-scoped)
    project_resp = (
        supabase.table("projects")
        .select("*")
        .eq("id", str(project_id))
        .eq("organization_id", org_id)
        .single()
        .execute()
    )
    if project_resp.data is None:
        raise _error_response("PROJECT_NOT_FOUND", 404, "Project not found")

    project = project_resp.data

    # Fetch nodes
    nodes_resp = (
        supabase.table("nodes")
        .select("*")
        .eq("project_id", str(project_id))
        .execute()
    )
    nodes = nodes_resp.data or []

    # Fetch edges
    edges_resp = (
        supabase.table("edges")
        .select("*")
        .eq("project_id", str(project_id))
        .execute()
    )
    edges = edges_resp.data or []

    # Fetch latest MST result
    mst_resp = (
        supabase.table("mst_results")
        .select("*")
        .eq("project_id", str(project_id))
        .order("calculated_at", desc=True)
        .limit(1)
        .execute()
    )
    mst_result = mst_resp.data[0] if mst_resp.data else None

    return project, nodes, edges, mst_result


@router.get("/excel")
async def export_excel(
    project_id: UUID,
    user: dict = Depends(get_current_user),
):
    """Download project data as an .xlsx workbook.

    The workbook contains three sheets: Project Info, Nodes, and Edges & MST.
    """
    supabase = get_supabase_client()
    org_id = user["org_id"]

    project, nodes, edges, mst_result = _load_project_data(
        project_id, org_id, supabase,
    )

    buf = build_export_workbook(project, nodes, edges, mst_result)
    name = project.get("name", "export")
    filename = f"project-{name}-export.xlsx"

    return StreamingResponse(
        buf,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/pdf")
async def export_pdf(
    request: PDFExportRequest,
    project_id: UUID,
    user: dict = Depends(get_current_user),
):
    """Generate and download a PDF report with optional embedded map image."""
    supabase = get_supabase_client()
    org_id = user["org_id"]

    project, nodes, edges, mst_result = _load_project_data(
        project_id, org_id, supabase,
    )

    # Validate base64 if a non-empty value was provided
    map_image_base64 = request.map_image_base64
    if map_image_base64:
        try:
            base64.b64decode(map_image_base64, validate=True)
        except (base64.binascii.Error, ValueError, TypeError):
            raise _error_response(
                "INVALID_MAP_IMAGE",
                422,
                "Invalid base64-encoded image data",
            )

    buf = build_pdf_report(
        project, nodes, edges, mst_result, map_image_base64,
    )
    name = project.get("name", "export")
    filename = f"project-{name}-report.pdf"

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
