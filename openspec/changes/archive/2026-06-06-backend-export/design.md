# Design: Backend Export Endpoints

## Technical Approach

Add two export endpoints to the existing NetPlan API — Excel and PDF — following the established patterns in the codebase: tenant-scoped reads, service-layer business logic, router for HTTP concerns, and `BytesIO`-based streaming for file downloads. No temp files on disk.

The PDF library [`reportlab`](https://pypi.org/project/reportlab/) (pure Python, no system deps) is chosen over weasyprint (requires libpango/cairo system libs — risky on Render free tier) and fpdf2 (less mature table/image support).

## Architecture Decisions

| Option | Tradeoff | Decision |
|--------|----------|----------|
| reportlab vs weasyprint vs fpdf2 | weasyprint needs system deps (Render free tier risk); fpdf2 lacks mature table API; reportlab is pure Python, battle-tested, handles tables+images | **reportlab** |
| BytesIO vs temp files | Temp files add cleanup complexity and I/O on ephemeral disks | **BytesIO** — stream directly |
| New router vs inject into projects.py | Keeps concerns separate, matches `design.md` §5 structure (routers/export.py) | **New `export.py` router** |
| Extend existing excel_service vs new file | Import parsing and export formatting are separate concerns; but share openpyxl config | **Extend `excel_service.py`** with `build_export_workbook()` |
| Separate pdf_service.py | Clear separation, matches design.md §5 (`services/pdf_service.py`) | **New `pdf_service.py`** |

## Data Flow

```
Excel:
  Client → GET /projects/{id}/export/excel
            → dependencies.get_current_user (JWT) → org_id
            → router: verify project exists & scoped
            → excel_service.build_export_workbook(project, nodes, edges, mst)
            → BytesIO → StreamingResponse(.xlsx, content-disposition)

PDF:
  Client → POST /projects/{id}/export/pdf { map_image_base64 }
            → dependencies.get_current_user (JWT) → org_id
            → router: verify project exists & scoped
            → pdf_service.build_pdf_report(project, nodes, edges, mst, map_image_base64)
            → BytesIO → StreamingResponse(.pdf, content-disposition)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/schemas/export.py` | Modify | Add response schemas (already has `PDFExportRequest`) |
| `backend/app/services/excel_service.py` | Modify | Add `build_export_workbook()` — workbook styling, 3 sheets |
| `backend/app/services/pdf_service.py` | Create | Reportlab PDF generation — tables, map image, headers |
| `backend/app/routers/export.py` | Create | GET export/excel + POST export/pdf; auth + tenant scope |
| `backend/app/main.py` | Modify | Register `export.router` |
| `backend/requirements.txt` | Modify | Add `reportlab` |

## Interfaces / Contracts

### Schema (`schemas/export.py`)

```python
# Already exists:
class PDFExportRequest(BaseModel):
    map_image_base64: str

# Add:
class PDFExportResponse(BaseModel):
    filename: str
    # No response body needed — returns file stream
```

### Services

```python
# excel_service.py — add
def build_export_workbook(
    project: dict,
    nodes: list[dict],
    edges: list[dict],
    mst_result: dict | None,
) -> BytesIO:
    """Build styled .xlsx with Nodes, Edges, MST Result sheets.
    Returns BytesIO ready for StreamingResponse."""

# pdf_service.py — new
def build_pdf_report(
    project: dict,
    nodes: list[dict],
    edges: list[dict],
    mst_result: dict | None,
    map_image_base64: str | None,
) -> BytesIO:
    """Build PDF with reportlab: header, nodes table, edges table,
    MST summary, embedded map image. Returns BytesIO."""
```

### Workbook Structure (Excel)

| Sheet | Columns | Notes |
|-------|---------|-------|
| **Nodos** | name, type, lat, lng | Sorted by name |
| **Enlaces** | node_a_name, node_b_name, cost, constraint_type | Sorted by cost desc; names resolved from nodes |
| **Resultado MST** | total_cost, algorithm, n_edges, calculated_at | Single row summary |
| **Arcos MST** | source_node, target_node, cost, type | Only if mst_result exists; sorted by cost desc |

All sheets: header row **bold**, auto-width columns, light gray borders, frozen header row.

### PDF Structure (reportlab)

```
Page 1:
┌────────────────────────────────────┐
│  NetPlan - Informe de Proyecto     │
│  Proyecto: {name}                  │
│  Fecha: {generated_at}             │
├────────────────────────────────────┤
│  Resumen                           │
│  Nodos: {n} · Enlaces: {m}        │
│  Costo Total MST: ${cost}          │
├────────────────────────────────────┤
│  Tabla de Nodos                    │
│  ┌──────┬──────┬──────┬──────┐    │
│  │ Nombre│ Tipo │ Lat  │ Lng  │    │
│  ├──────┼──────┼──────┼──────┤    │
│  │ ...  │ ...  │ ...  │ ...  │    │
│  └──────┴──────┴──────┴──────┘    │
├────────────────────────────────────┤
│  Tabla de Enlaces                  │
│  (misma estructura)                │
├────────────────────────────────────┤
│  [Mapa de red — imagen]            │
│  (resized to fit page width,       │
│   max 80% page height)             │
└────────────────────────────────────┘
```

Page break logic: if content exceeds one page, tables split naturally via reportlab's `Table` with `repeatRows=1` for header repetition.

### Router (`routers/export.py`)

```python
router = APIRouter(prefix="/projects/{project_id}/export", tags=["export"])

@router.get("/excel")
async def export_excel(
    project_id: UUID,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
) -> StreamingResponse:
    """Download .xlsx with nodes, edges, MST result."""

@router.post("/pdf")
async def export_pdf(
    request: PDFExportRequest,
    project_id: UUID,
    user: dict = Depends(get_current_user),
    supabase=Depends(get_supabase_client),
) -> StreamingResponse:
    """Generate and download PDF report with map image."""
```

**Response headers:**
- Excel: `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- PDF: `Content-Type: application/pdf`
- Both: `Content-Disposition: attachment; filename="proyecto-{slug}-{date}.{ext}"`

**Error handling:**
- Project not found / cross-tenant → 404 (no existence leak, same pattern as `mst_service.ProjectNotFound`)
- No nodes → 422 `NO_NODES` for Excel (empty workbook is valid but we warn)
- Invalid base64 → 422 `INVALID_MAP_IMAGE`
- Empty base64 → PDF generated without map image (graceful degradation)

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `build_export_workbook()` | Create workbook with known data; verify cell values per sheet, header styling, row count |
| Unit | `build_pdf_report()` | Generate PDF with nodes+edges+MST+image; verify file size > minimum, no exceptions. Without image (None) — verify graceful degradation |
| Unit | Base64 decode + embed | Valid PNG base64, invalid base64, oversized image (>10MB) |
| Integration | Excel: full flow | Create project, add nodes+edges, run MST → export Excel → verify content-type, content-disposition, readable by openpyxl |
| Integration | PDF: full flow | Same → export PDF with valid base64 image → verify content-type, content-disposition |
| Integration | Auth: no token → 401 | Both endpoints without Authorization header |
| Integration | Cross-tenant → 404 | Token for org A, project from org B |
| Integration | Empty project | Excel with 0 nodes → valid workbook, 0 data rows |
| Integration | PDF no image | POST without map_image_base64 (or empty) → valid PDF |

**Add to test files:**
- `backend/tests/services/test_excel_service.py` (or extend if exists)
- `backend/tests/services/test_pdf_service.py`
- `backend/tests/routers/test_export.py`

## Migration / Rollout

- Add `reportlab` to `requirements.txt` — installs cleanly, no system deps
- No DB schema changes
- No frontend changes in this task (separate task)
- Rollback: remove the import in `main.py` and the `export` router file

## Open Questions

None.
