# Proposal: backend-nodes-edges

## Intent

Implement the Nodes and Edges REST APIs for the NetPlan backend, enabling project-level CRUD operations for network nodes (with Excel bulk import) and edges (with constraint types: normal/mandatory/forbidden). These APIs are prerequisites for MST calculation and map visualization.

## Scope

### In Scope
- **T-01-03**: Nodes router (`app/routers/nodes.py`) with single-node CRUD + Excel import endpoint
  - `POST /projects/{id}/nodes` — Create single node
  - `PUT /projects/{id}/nodes/{node_id}` — Update node
  - `DELETE /projects/{id}/nodes/{node_id}` — Delete node (cascades edges)
  - `POST /projects/{id}/nodes/import` — Bulk import from `.xlsx` (max 10k rows)
- **T-01-04**: Edges router (`app/routers/edges.py`) with CRUD + constraint endpoints
  - `POST /projects/{id}/edges` — Upsert edge (unique constraint on `project_id, node_a_id, node_b_id`)
  - `DELETE /projects/{id}/edges/{edge_id}` — Remove edge
  - `PATCH /projects/{id}/edges/{edge_id}/constraint` — Update only `constraint_type`
- Excel service (`app/services/excel_service.py`) with `parse_nodes_xlsx()` validating lat/lng ranges
- Tenant scoping via `organization_id` from JWT on all queries
- Cross-tenant access returns 404 (not 403)
- Error format: `{error, code, detail}` per design.md §3

### Out of Scope
- MST calculation endpoints (T-01-05)
- Export endpoints (T-01-06)
- Frontend components (T-02-05, T-02-06)
- Rate limiting on `/mst/calculate` (future task)

## Capabilities

### New Capabilities
- `nodes-crud`: Node CRUD operations scoped to project and tenant
- `nodes-import`: Excel bulk import with validation and error reporting
- `edges-crud`: Edge CRUD with upsert semantics via DB unique constraint
- `edges-constraints`: Constraint type management (normal/mandatory/forbidden)

### Modified Capabilities
- None (these are new capabilities)

## Approach

Follow existing patterns from `app/routers/projects.py`:
1. **Dependencies**: Use `get_current_user` for JWT validation and tenant resolution
2. **Tenant scoping**: Every Supabase query includes `.eq("organization_id", org_id)` (via project join)
3. **Error handling**: Use `_error_response()` helper for consistent `{error, code, detail}` format
4. **Validation**: Leverage Pydantic models in `app/schemas/node.py` and `app/schemas/edge.py` (already created)
5. **Excel parsing**: Use `openpyxl` in `excel_service.parse_nodes_xlsx()` returning `(valid_rows, errors)` tuples
6. **Upsert logic**: Use Supabase `.upsert()` with `on_conflict="project_id,node_a_id,node_b_id"` matching DB unique constraint

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/routers/nodes.py` | New | Nodes CRUD + import endpoints |
| `app/routers/edges.py` | New | Edges CRUD + constraint endpoints |
| `app/services/excel_service.py` | New | `parse_nodes_xlsx()` implementation |
| `app/main.py` | Modified | Mount new routers at `/api/v1` |
| `app/schemas/node.py` | Existing | Already has Pydantic models |
| `app/schemas/edge.py` | Existing | Already has Pydantic models |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Excel parsing edge cases (merged cells, formats) | Medium | Use `openpyxl` with strict column validation; limit to 10k rows |
| Upsert race conditions | Low | DB unique constraint guarantees atomicity |
| Cross-tenant data leakage | Low | All queries filter by `organization_id`; 404 on missing |
| Large file upload memory | Low | Stream file bytes; validate MIME type server-side |

## Rollback Plan

1. Remove router imports from `app/main.py`
2. Delete `app/routers/nodes.py` and `app/routers/edges.py`
3. Delete `app/services/excel_service.py`
4. No database migration needed (tables already exist from T-00-02)

## Dependencies

- T-00-02 (Supabase schema with `nodes` and `edges` tables) — COMPLETE
- T-01-01 (FastAPI skeleton, JWT dependency, Supabase client) — COMPLETE
- T-01-02 (Projects router with tenant scoping patterns) — COMPLETE

## Success Criteria

- [ ] `POST /projects/{id}/nodes` creates node with valid lat/lng
- [ ] `POST /projects/{id}/nodes/import` accepts `.xlsx`, returns summary with per-row errors
- [ ] Import rejects files >10k rows with structured error
- [ ] `POST /projects/{id}/edges` upserts on duplicate `(node_a_id, node_b_id)`
- [ ] `PATCH /edges/{id}/constraint` updates only `constraint_type`
- [ ] Cross-tenant access returns 404 (not 403)
- [ ] All errors follow `{error, code, detail}` format