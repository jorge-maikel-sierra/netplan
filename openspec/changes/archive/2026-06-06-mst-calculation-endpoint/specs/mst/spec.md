# Delta for MST Calculation Domain

## MODIFIED Requirements

### REQ-MST-006: Persistence (no organization_id column)

The system SHALL persist every successful MST calculation to `mst_results`, and SHALL NOT persist any failed calculation. Each persisted row SHALL contain `project_id`, `edge_ids`, `total_cost`, `parameters`, and `calculated_at`. There is NO `organization_id` column on `mst_results` — tenant traceability relies on the project's transitive ownership via `projects.organization_id`.
(Previously: required organization_id in insert payload, but the table schema has no such column)

#### Scenario: Successful calculation creates mst_results row

- GIVEN a valid MST calculation that returns 200
- WHEN the response is sent to the client
- THEN a row exists in `mst_results` with: `project_id` (UUID), `edge_ids` (UUID[]), `total_cost` (numeric), `parameters` (JSONB containing `mandatory_edge_ids`, `forbidden_edge_ids`, `node_count`, `edge_count`), `calculated_at` (timestamptz)

#### Scenario: Failed calculation does NOT create a row

- GIVEN a graph that returns 422 (any of: `INSUFFICIENT_NODES`, `DISCONNECTED_GRAPH`, `MANDATORY_CYCLE`)
- WHEN the response is sent
- THEN NO new row is inserted in `mst_results`
- AND the database row count for that project's `mst_results` is unchanged from before the call

#### Scenario: Rejected rate-limited call does NOT create a row

- GIVEN org O1 has hit the rate limit
- WHEN O1 makes another POST that returns 429
- THEN NO new row is inserted in `mst_results`

### REQ-MST-007: Tenant-scoped via transitive project validation

The system SHALL validate `organization_id` on the project lookup query as the authoritative tenant gate. Node and edge queries SHALL filter by `project_id` only (the schema has no `organization_id` column on those tables), relying on transitive scoping: the project_id is already known to belong to the caller's org from step 1.
(Previously: required nodes/edges queries to include .eq("organization_id", ...), but neither table has that column)

#### Scenario: Project check is authoritative tenant gate

- GIVEN any MST calculation request
- WHEN the service queries the `projects` table
- THEN the project query includes `.eq("id", project_id)` AND `.eq("organization_id", org_id_from_jwt)`
- AND the service raises `ProjectNotFound` (404) before loading any nodes or edges if no row matches

#### Scenario: Nodes and edges are transitively scoped

- GIVEN the project existence check has passed (organization_id matches)
- WHEN the service queries `nodes` and `edges`
- THEN both queries filter by `project_id` only — there is no `organization_id` column to filter on
- AND any edge from another project is NEVER included in `mst_edges` or persisted `edge_ids` (the project_id filter already guarantees this)
- AND no error is raised to the caller (silent defense, no information disclosure)

### Error response schema

#### Modified: `MSTErrorResponse` (updated fields)

| Field | Condition | Type | Description |
|-------|-----------|------|-------------|
| `conflicting_edge_ids` | `error == "MANDATORY_CYCLE"` | `list[UUID]` | IDs of edges forming the cycle |
| `retry_after` | `error == "RATE_LIMITED"` | `int` | Seconds to wait before retry |
| `unreachable_nodes` | `error == "DISCONNECTED_GRAPH"` | `list[UUID]` | Unreachable node IDs |

(Previously: only `unreachable_nodes` was specified; `conflicting_edge_ids` and `retry_after` were absent)

## Out of scope

Same as main spec: export, frontend, billing, algorithm optimization, E2E tests.
