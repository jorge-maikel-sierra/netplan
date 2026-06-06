# Proposal: Projects CRUD Router

## Intent

Implement the Projects CRUD router (T-01-02) with 5 endpoints per `design.md §3.1` to enable tenant-scoped project management. This is the first business logic router in the backend and establishes patterns for all subsequent routers (nodes, edges, mst, export).

## Scope

### In Scope
- `app/routers/projects.py` — 5 endpoints: `GET /projects`, `POST /projects`, `GET /projects/{id}`, `PATCH /projects/{id}`, `DELETE /projects/{id}`
- Mount router in `app/main.py` at `/api/v1`
- Extend `app/schemas/project.py` with `ProjectListResponse` and `ProjectDetailResponse` (nested nodes, edges, last_result)
- Free tier enforcement: 3 projects max for `organizations.plan = 'free'`

### Out of Scope
- Frontend integration (T-02-03)
- Nodes/Edges/MST/Export routers (T-01-03 through T-01-06)
- Database migrations (already in design.md §2)
- RLS policy application (defense-in-depth only)

## Capabilities

### New Capabilities
- `projects-crud`: Tenant-scoped project lifecycle (create, list, get-detail, update, delete) with free-tier limit enforcement

### Modified Capabilities
- None (no existing capabilities modified at spec level)

## Approach

Follow established patterns from `dependencies.py`, `supabase_client.py`, and `schemas/`:
- Use `get_current_user` dependency for JWT validation + `org_id` resolution
- Use singleton `get_supabase_client()` (service role) for all DB operations
- Manual tenant scoping: every query filters `.eq("organization_id", org_id)`
- Cross-tenant access returns 404 (not 403) to avoid existence leakage
- `GET /projects/{id}` executes 3 separate queries (nodes, edges, mst_results) and merges in response — Supabase JOIN limitations make single-query approach unreliable
- Free tier check in `POST /projects`: count existing projects for org, return 403 `FREE_TIER_LIMIT` if ≥3 and plan='free'

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/routers/projects.py` | New | 5 endpoints with tenant scoping, free-tier check, nested detail response |
| `app/main.py` | Modified | Mount router at `/api/v1/projects` |
| `app/schemas/project.py` | Modified | Add `ProjectListResponse`, `ProjectDetailResponse`, `ProjectCreate`, `ProjectUpdate` |
| `app/db/supabase_client.py` | None | Reuse existing singleton |
| `app/dependencies.py` | None | Reuse `get_current_user` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Service role key bypasses RLS — missing `organization_id` filter leaks cross-tenant data | High | Mandatory code review checklist: every query MUST include `.eq("organization_id", org_id)`; add linter rule |
| Supabase JOIN limitations cause N+1 or incomplete data in `GET /{id}` | Medium | Use 3 separate indexed queries; accept slight latency for correctness |
| Free tier limit race condition (concurrent creates) | Low | Use DB-level check: `SELECT COUNT(*) FROM projects WHERE organization_id = ? FOR UPDATE` in transaction |
| `DELETE /projects/{id}` cascade not removing child nodes/edges/results | Medium | Verify DB `ON DELETE CASCADE` on FKs (design.md §2); add integration test |

## Rollback Plan

1. Remove router mount from `app/main.py`
2. Delete `app/routers/projects.py`
3. Revert `app/schemas/project.py` to pre-change state (keep only `ProjectResponse`)
4. No DB changes required (migrations are separate)

## Dependencies

- T-01-01 complete: `get_current_user` dependency, `get_supabase_client`, FastAPI app with CORS
- Supabase schema applied (design.md §2): `organizations`, `profiles`, `projects` tables with RLS
- `organizations` table has `plan` column (T-03-03, can be added before or alongside)

## Success Criteria

- [ ] `POST /api/v1/projects` creates project scoped to JWT's `organization_id`
- [ ] `GET /api/v1/projects` returns only projects for that tenant
- [ ] `GET /api/v1/projects/{id}` returns 404 for other tenants' projects (not 403)
- [ ] `GET /api/v1/projects/{id}` response includes `nodes[]`, `edges[]`, `last_result` (or null)
- [ ] `PATCH /api/v1/projects/{id}` updates name/description for own tenant only
- [ ] `DELETE /api/v1/projects/{id}` cascades to nodes, edges, mst_results
- [ ] Free tier org (plan='free') gets 403 `FREE_TIER_LIMIT` on 4th project creation
- [ ] All endpoints return error format `{error, code, detail}` per design.md §3