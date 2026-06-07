# Spec: Export Domain

## Purpose

The export domain allows users to download project data (nodes, edges, MST results) in Excel and PDF formats. Excel export is server-generated using `openpyxl`. PDF export requires a base64-encoded map image from the frontend and is rendered server-side using `reportlab`.

## Requirements

### REQ-EXPORT-001: Excel export — nodes + MST edges

The system MUST generate a valid `.xlsx` file via `GET /api/v1/projects/{id}/export/excel` containing project nodes and, if an MST result exists, the MST edges.

#### Scenario: Full export with both sheets
- **GIVEN** project P has nodes and a recent MST result
- **AND** the requester is authenticated and owns the project
- **WHEN** the requester GETs `/api/v1/projects/{id}/export/excel`
- **THEN** the response is 200 with `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- **AND** `Content-Disposition: attachment; filename="project-{name}-{id-short}.xlsx"`
- **AND** the workbook contains sheet "Nodos" with columns `[nombre, latitud, longitud, tipo]` and sheet "Aristas MST" with columns `[nodo_a, nodo_b, costo, tipo_restriccion]`
- **AND** "Aristas MST" includes a summary row with `total_cost` in the last row

#### Scenario: Export without MST result
- **GIVEN** project P has nodes but NO MST result
- **WHEN** the requester GETs `/api/v1/projects/{id}/export/excel`
- **THEN** the response is 200 with a valid `.xlsx`
- **AND** "Nodos" sheet contains all nodes
- **AND** "Aristas MST" sheet contains header only (no data rows, no error)

### REQ-EXPORT-002: PDF export — map + summary table

The system MUST generate a PDF via `POST /api/v1/projects/{id}/export/pdf` containing project info, optional map image, summary table, and MST edge list.

#### Scenario: Export with map image
- **GIVEN** project P has nodes, MST result, and a valid `map_image_base64` PNG
- **WHEN** the requester POSTs `{"map_image_base64": "<base64-data>"}` to `/api/v1/projects/{id}/export/pdf`
- **THEN** the response is 200 with `Content-Type: application/pdf`
- **AND** `Content-Disposition: attachment; filename="project-{name}-report.pdf"`
- **AND** the PDF contains: title, embedded map image, cost summary row, and edge list table
- **AND** the PDF is at most 2 pages

#### Scenario: Export without map image
- **GIVEN** project P has nodes and MST result
- **WHEN** the requester POSTs `{"map_image_base64": ""}` to `/api/v1/projects/{id}/export/pdf`
- **THEN** the response is 200 with a valid PDF
- **AND** the PDF omits the map section but still includes summary + edge table

#### Scenario: Invalid base64 image
- **GIVEN** a valid project with MST result
- **WHEN** the requester POSTs `{"map_image_base64": "not-valid-base64-data"}` to `/api/v1/projects/{id}/export/pdf`
- **THEN** the response is 422 with `error: "INVALID_MAP_IMAGE"`
- **AND** `detail` describes the decoding error

### REQ-EXPORT-003: Auth and tenant isolation

The system MUST reject unauthenticated requests with 401 and cross-tenant requests with 404, following the same pattern as other routers.

#### Scenario: Unauthenticated Excel export
- **WHEN** a request without `Authorization` header hits `GET /api/v1/projects/{id}/export/excel`
- **THEN** the response is 401 with `error: "NOT_AUTHENTICATED"`

#### Scenario: Cross-tenant Excel export
- **GIVEN** user U1 from org O1 requests project P owned by org O2
- **WHEN** U1 GETs `/api/v1/projects/P/export/excel` with their valid JWT
- **THEN** the response is 404 with `error: "PROJECT_NOT_FOUND"`
- **AND** the body does NOT reveal existence of the project or cross-tenant access

#### Scenario: Unauthenticated PDF export
- **WHEN** a request without `Authorization` header hits `POST /api/v1/projects/{id}/export/pdf`
- **THEN** the response is 401

#### Scenario: Cross-tenant PDF export
- **GIVEN** user U1 from org O1 requests project P owned by org O2
- **WHEN** U1 POSTs to `/api/v1/projects/P/export/pdf` with their valid JWT
- **THEN** the response is 404

### REQ-EXPORT-004: Graceful error on missing project

Both endpoints MUST return 404 when the project does not exist or is not owned by the caller's organization.

#### Scenario: Project not found
- **GIVEN** project ID that does not exist
- **WHEN** any export request is made
- **THEN** the response is 404 with `error: "PROJECT_NOT_FOUND"`
