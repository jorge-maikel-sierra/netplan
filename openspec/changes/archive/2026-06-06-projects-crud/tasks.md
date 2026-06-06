# Tasks: Projects CRUD Router

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 250-350 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Projects CRUD router + schemas + main mount | PR 1 | Single PR; all tasks dependent |

## Phase 1: Foundation — Schemas & Router Setup

- [x] T-01-02-01 Extend `app/schemas/project.py` with `ProjectListResponse`, `ProjectDetailResponse`, nested `NodeResponse`, `EdgeResponse`, `MstResultResponse`
- [x] T-01-02-02 Create `app/routers/projects.py` with router instance and `get_current_user` dependency import
- [x] T-01-02-03 Mount projects router in `app/main.py` at `/api/v1/projects` with prefix and tags

## Phase 2: Core Implementation — 5 Endpoints

- [x] T-01-02-04 Implement `GET /projects` — list projects scoped to `org_id`, return `ProjectListResponse[]`
- [x] T-01-02-05 Implement `POST /projects` — create project with `org_id` and `created_by` from JWT, return `ProjectDetailResponse`
- [x] T-01-02-06 Implement `GET /projects/{id}` — fetch project + nodes + edges + latest mst_result; return 404 if not in tenant; return `ProjectDetailResponse`
- [x] T-01-02-07 Implement `PATCH /projects/{id}` — update name/description for own tenant only; return `ProjectDetailResponse`
- [x] T-01-02-08 Implement `DELETE /projects/{id}` — delete project (cascades via DB FK); return 204

## Phase 3: Business Rules — Free Tier & Error Handling

- [x] T-01-02-09 Add free-tier check in `POST /projects`: count projects for org, if `plan='free'` and count ≥ 3 return 403 `FREE_TIER_LIMIT`
- [x] T-01-02-10 Add consistent error handling: all endpoints return `{error, code, detail}` format per design.md §3; 404 for cross-tenant (not 403)
- [x] T-01-02-11 Add validation: `POST /projects` requires `name` (min 1 char), `PATCH` ignores null fields

## Phase 4: Verification

- [ ] T-01-02-12 Write integration test script `tests/test_projects_crud.py` covering: create/list/get/update/delete, free-tier limit, cross-tenant 404, error format (INCOMPLETE — no test suite)
- [x] T-01-02-13 Manual smoke test: `GET /healthz`, `GET /projects` without token → 401, cross-tenant access → 404 (PARTIAL — healthz & 401 pass)

## Phase 5: Cleanup (Optional)

- [x] T-01-02-14 Add docstrings to all endpoints with example requests/responses