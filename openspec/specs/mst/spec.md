# Spec: MST Calculation Domain

## Purpose
El dominio MST existe para transformar la topología cruda de un proyecto (nodos y edges) en una red de costo mínimo que respeta las restricciones declaradas por el usuario. Sin él, los nodos y edges de T-01-03/T-01-04 son datos huérfanos sin valor de producto: este endpoint destapa el output que el cliente consume. Resuelve tres problemas concretos: elegir qué aristas construir, forzar inclusion/exclusion de aristas (mandatory/forbidden), y reportar cuando el grafo es inválido para una red real (incompleto, subgrafos aislados).

## Requirements

### REQ-MST-001: Calculate MST for a project
The system SHALL calculate a Minimum Spanning Tree for a project's graph using Kruskal's algorithm via NetworkX.

#### Scenario: Happy path with simple triangle
- **GIVEN** a project with 3 nodes (A, B, C) and 3 edges (A-B cost 1, B-C cost 2, A-C cost 3)
- **AND** the requester is authenticated and owns the project
- **WHEN** the requester POSTs to `/api/v1/projects/{id}/mst/calculate`
- **THEN** the response is 200 with `total_cost: 3` and `mst_edges` containing exactly [A-B, B-C] (the two cheapest)
- **AND** a new row is inserted in `mst_results` with `edge_ids` = [A-B-id, B-C-id]

#### Scenario: Mandatory edges are force-included
- **GIVEN** a project where edge X-Y (cost 100) is marked as `constraint_type: mandatory`
- **AND** the optimal MST without constraints would NOT include X-Y (cheaper alternatives exist)
- **WHEN** the requester calculates MST
- **THEN** the response includes X-Y in `mst_edges`
- **AND** the total cost is HIGHER than the unconstrained optimal MST

#### Scenario: Mandatory edges forming a cycle are rejected
- **GIVEN** a project where 3 mandatory edges form a cycle (A-B, B-C, C-A all marked mandatory)
- **WHEN** the requester calculates MST
- **THEN** the response is 422 with `error: "MANDATORY_CYCLE"`
- **AND** `detail` lists the conflicting edge IDs that form the cycle

#### Scenario: Forbidden edges are excluded
- **GIVEN** a project where edge X-Y (cost 0.01, cheapest) is marked as `constraint_type: forbidden`
- **WHEN** the requester calculates MST
- **THEN** X-Y is NOT in `mst_edges` under any circumstance
- **AND** if X-Y was the only connection to a subgraph, the graph becomes disconnected (see REQ-MST-002)

#### Scenario: Empty project (0 nodes)
- **GIVEN** a project with 0 nodes
- **WHEN** the requester calculates MST
- **THEN** the response is 422 with `error: "INSUFFICIENT_NODES"`
- **AND** `detail` is "Se requieren al menos 2 nodos para calcular el MST"

#### Scenario: Single node project (1 node)
- **GIVEN** a project with exactly 1 node
- **WHEN** the requester calculates MST
- **THEN** the response is 422 with `error: "INSUFFICIENT_NODES"`
- **AND** `detail` is "Se requieren al menos 2 nodos para calcular el MST"

#### Scenario: Two nodes, one edge
- **GIVEN** a project with 2 nodes and 1 edge of cost 5
- **WHEN** the requester calculates MST
- **THEN** the response is 200 with `total_cost: 5` and `mst_edges` containing exactly 1 entry

### REQ-MST-002: Disconnected graph detection
The system SHALL detect when a graph is disconnected and return the unreachable nodes without persisting any result.

#### Scenario: Two disconnected subgraphs
- **GIVEN** a project with 4 nodes (A, B connected by 1 edge; C, D connected by 1 edge; NO edges between the two groups)
- **WHEN** the requester calculates MST
- **THEN** the response is 422 with `error: "DISCONNECTED_GRAPH"`
- **AND** `unreachable_nodes` is a list of UUIDs containing exactly the IDs of C and D (or A and B — implementation consistent)
- **AND** `detail` mentions "el grafo tiene subgrafos no conectados"
- **AND** NO row is inserted in `mst_results`

### REQ-MST-003: Cross-tenant isolation
The system SHALL NOT leak data across organizations: any request for a project owned by another org returns 404 (not 403) to avoid existence leak.

#### Scenario: User requests MST of another org's project
- **GIVEN** user U1 belongs to organization O1
- **AND** project P belongs to organization O2
- **WHEN** U1 sends `POST /api/v1/projects/P/mst/calculate` with their own valid JWT
- **THEN** the response is 404
- **AND** the response body MUST NOT contain the words "forbidden", "not authorized", or "cross-tenant" (no existence leak)

#### Scenario: User requests latest MST of another org's project
- **GIVEN** user U1 belongs to org O1
- **AND** project P belongs to org O2
- **WHEN** U1 sends `GET /api/v1/projects/P/mst/latest`
- **THEN** the response is 404

#### Scenario: Unauthenticated request
- **WHEN** a request without `Authorization: Bearer <jwt>` header hits `POST /api/v1/projects/{id}/mst/calculate`
- **THEN** the response is 401
- **AND** the body conforms to the error format `{ "error": "INVALID_TOKEN", "code": 401, "detail": "..." }`

### REQ-MST-004: Retrieve latest MST result
The system SHALL return the most recent MST result for a project, ordered by `created_at` DESC.

#### Scenario: Multiple calculations done
- **GIVEN** MST has been calculated 3 times for project P at timestamps T1 < T2 < T3
- **WHEN** the requester GETs `/api/v1/projects/P/mst/latest`
- **THEN** the response is 200 with the row created at T3
- **AND** the response includes the full enriched `mst_edges` array (with `node_a_name`, `node_b_name`, `cost`, `type`), NOT just `edge_ids`

#### Scenario: No calculations yet
- **GIVEN** project P has never had MST calculated (zero rows in `mst_results`)
- **WHEN** the requester GETs `/api/v1/projects/P/mst/latest`
- **THEN** the response is 404 with `error: "NO_RESULT"`
- **AND** `detail` is "No hay resultados de MST para este proyecto"

### REQ-MST-005: Rate limiting
The system SHALL limit MST calculation requests to 5 requests per 60-second window, keyed by `organization_id` extracted from the JWT (NOT by IP or user_id).

#### Scenario: 6th request in 60 seconds from same org
- **GIVEN** 5 successful POSTs to `/mst/calculate` occurred in the last 60 seconds for org O1
- **WHEN** org O1 makes a 6th POST within that window
- **THEN** the response is 429 with `error: "RATE_LIMITED"`
- **AND** `detail` includes retry-after seconds (e.g., "Demasiadas solicitudes. Reintentá en N segundos")
- **AND** NO row is inserted in `mst_results` for this rejected call

#### Scenario: Different orgs are independent
- **GIVEN** org O1 has already hit the rate limit (5 POSTs in last 60s)
- **WHEN** org O2 makes a POST to calculate MST for its own project
- **THEN** the response succeeds (200 or 422 depending on graph validity) — NOT 429

### REQ-MST-006: Persistence (no organization_id column)
The system SHALL persist every successful MST calculation to `mst_results`, and SHALL NOT persist any failed calculation. Each persisted row SHALL contain `project_id`, `edge_ids`, `total_cost`, `parameters`, and `calculated_at`. There is NO `organization_id` column on `mst_results` — tenant traceability relies on the project's transitive ownership via `projects.organization_id`.

#### Scenario: Successful calculation creates mst_results row
- **GIVEN** a valid MST calculation that returns 200
- **WHEN** the response is sent to the client
- **THEN** a row exists in `mst_results` with: `project_id` (UUID), `edge_ids` (UUID[]), `total_cost` (numeric), `parameters` (JSONB containing `mandatory_edge_ids`, `forbidden_edge_ids`, `node_count`, `edge_count`), `calculated_at` (timestamptz)

#### Scenario: Failed calculation does NOT create a row
- **GIVEN** a graph that returns 422 (any of: `INSUFFICIENT_NODES`, `DISCONNECTED_GRAPH`, `MANDATORY_CYCLE`)
- **WHEN** the response is sent
- **THEN** NO new row is inserted in `mst_results`
- **AND** the database row count for that project's `mst_results` is unchanged from before the call

#### Scenario: Rejected rate-limited call does NOT create a row
- **GIVEN** org O1 has hit the rate limit
- **WHEN** O1 makes another POST that returns 429
- **THEN** NO new row is inserted in `mst_results`

### REQ-MST-007: Tenant-scoped via transitive project validation
The system SHALL validate `organization_id` on the project lookup query as the authoritative tenant gate. Node and edge queries SHALL filter by `project_id` only (the schema has no `organization_id` column on those tables), relying on transitive scoping: the project_id is already known to belong to the caller's org from step 1.

#### Scenario: Project check is authoritative tenant gate
- **GIVEN** any MST calculation request
- **WHEN** the service queries the `projects` table
- **THEN** the project query includes `.eq("id", project_id)` AND `.eq("organization_id", org_id_from_jwt)`
- **AND** the service raises `ProjectNotFound` (404) before loading any nodes or edges if no row matches

#### Scenario: Nodes and edges are transitively scoped
- **GIVEN** the project existence check has passed (organization_id matches)
- **WHEN** the service queries `nodes` and `edges`
- **THEN** both queries filter by `project_id` only — there is no `organization_id` column to filter on
- **AND** any edge from another project is NEVER included in `mst_edges` or persisted `edge_ids` (the project_id filter already guarantees this)
- **AND** no error is raised to the caller (silent defense, no information disclosure)

## Response Schemas (delta — Pydantic v2)

> These schemas extend the existing stubs in `backend/app/schemas/mst.py`. The proposal adopts the enriched `mst_edges[]` format (Q2 decision) instead of the current `edge_ids`-only stub.

### `MSTCalculateResponse` (200)
- `project_id: UUID`
- `total_cost: float` (≥ 0)
- `mst_edges: list[MSTEdgeResponse]`
- `mandatory_edges: list[MSTEdgeResponse]` (subset of `mst_edges` whose original `constraint_type == "mandatory"`)
- `parameters: dict[str, Any]` (echoes `{mandatory_edge_ids, forbidden_edge_ids, node_count, edge_count}` for audit)
- `created_at: datetime` (server-generated, UTC)

### `MSTEdgeResponse`
- `edge_id: UUID`
- `cost: float` (> 0)
- `node_a_id: UUID`
- `node_b_id: UUID`
- `type: Literal["normal", "mandatory", "forbidden"]` (the ORIGINAL `constraint_type` from the edges table, not mutated by the MST run)
- `source_node_name: str` (enriched from `nodes.name` for UI; falls back to truncated UUID if missing)

### `MSTLatestResponse` (200)
Same as `MSTCalculateResponse` plus:
- `result_id: UUID` (the `mst_results.id`)

### `MSTErrorResponse` (422 / 429)
- `error: Literal["INSUFFICIENT_NODES", "DISCONNECTED_GRAPH", "MANDATORY_CYCLE", "RATE_LIMITED", "NO_RESULT", "NOT_FOUND"]`
- `code: int` (404, 422 or 429 depending on case)
- `detail: str` (human-readable in Spanish for end users)
- `unreachable_nodes: list[UUID]` (ONLY present when `error == "DISCONNECTED_GRAPH"`; omitted otherwise)
- `conflicting_edge_ids: list[UUID]` (ONLY present when `error == "MANDATORY_CYCLE"`; IDs of edges forming the cycle)
- `retry_after: int` (ONLY present when `error == "RATE_LIMITED"`; seconds to wait before retry)

## Out of scope (will NOT be specified here)
- T-01-06 (PDF export) — separate change
- Frontend (T-02-XX) — separate change
- T-03-XX (billing, free-tier edge cases) — separate change
- NetworkX algorithm optimization for >10k nodes
- Re-verification or archival of orphan `backend-nodes-edges` change
- Frontend tests (no vitest installed)
- E2E tests
