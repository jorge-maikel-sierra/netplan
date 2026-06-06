# Tasks: Backend Export Endpoints

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 500–570 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Service layer → PR 2: Router + Tests |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Service layer: schemas, excel_service, pdf_service, deps | PR 1 | ~350 lines; verifiable via unit tests |
| 2 | Router: export routes, main.py wiring, integration tests | PR 2 | ~210 lines; depends on PR 1 |

## Phase 1: Foundation ✅

- [x] 1.1 Add `reportlab` to `backend/requirements.txt`
- [x] 1.2 Extend `backend/app/schemas/export.py` — add `PDFExportResponse` model

## Phase 2: Service Layer ✅

- [x] 2.1 Add `build_export_workbook()` to `backend/app/services/excel_service.py` — styled 3-sheet workbook (Project Info, Nodes, Edges & MST), `BytesIO` return
- [x] 2.2 Create `backend/app/services/pdf_service.py` — `build_pdf_report()` with reportlab: header, nodes table, edges table, MST summary, embedded map image (optional), `BytesIO` return

## Phase 3: Router & Wiring (PR 2)

- [ ] 3.1 Create `backend/app/routers/export.py` — `GET /projects/{id}/export/excel` (StreamingResponse .xlsx) + `POST /projects/{id}/export/pdf` (StreamingResponse .pdf with `PDFExportRequest` body); auth via `get_current_user`, tenant-scoped project fetch, consistent error format
- [ ] 3.2 Register `export.router` in `backend/app/main.py` with prefix `/api/v1`

## Phase 4: Testing ✅

- [x] 4.1 Create `backend/tests/unit/test_excel_service.py` — unit tests: workbook structure, cell values per sheet, header styling, 0 nodes case
- [x] 4.2 Create `backend/tests/unit/test_pdf_service.py` — unit tests: PDF generation with/without map image, empty image string, file size > minimum
- [ ] 4.3 Create `backend/tests/routers/test_export.py` — integration tests: full Excel/PDF flows (200), unauthenticated (401), cross-tenant (404), project not found (404), empty project valid export

## Verification Criteria

Each task verifiable by:
- 1.1: `pip install -r requirements.txt` succeeds, `import reportlab` works
- 1.2: schema imports without error, `PDFExportRequest` + `PDFExportResponse` defined
- 2.1: `build_export_workbook()` returns valid `.xlsx` with 3 sheets, readable by openpyxl
- 2.2: `build_pdf_report()` returns valid PDF > 1KB, with/without image
- 3.1: `GET /export/excel` returns `Content-Type: application/vnd.openxmlformats...`, `POST /export/pdf` returns `Content-Type: application/pdf`; auth/tenant errors match spec
- 3.2: `GET /healthz` still responds, export routes accessible
- 4.1–4.3: `pytest` passes all tests
