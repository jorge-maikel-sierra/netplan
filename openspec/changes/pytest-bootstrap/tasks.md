# Tasks: pytest-bootstrap

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~210 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |

Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

## Phase 1: Dependencies

- [x] 1.1 Add `pytest-asyncio>=0.24.0` and `pytest-cov>=5.0.0` to `backend/requirements.txt`
- [x] 1.2 Run `pip install -r requirements.txt` to verify install

## Phase 2: Shared Fixtures

- [x] 2.1 Add `sample_project` fixture to `backend/tests/conftest.py` returning a dict with id, organization_id, created_by, name, description, created_at, updated_at — all keyed from `sample_uuids`
- [x] 2.2 Add `sample_node` fixture to `backend/tests/conftest.py` returning a dict with id, project_id, name, type, lat, lng, created_at — keyed from `sample_uuids`

## Phase 3: Smoke Tests

- [x] 3.1 Create `backend/tests/test_health.py` with:
  - `test_healthz`: GET `/healthz` → 200 + `{"status": "ok"}`
- [x] 3.2 Create `backend/tests/test_projects.py` with:
  - `test_list_projects_empty`: empty mock → 200 + `[]`
  - `test_list_projects_populated`: mock with sample → 200 + list
  - `test_create_project`: POST → 201 + created project
  - `test_get_project_found`: mock returns project → 200
  - `test_get_project_404`: mock returns None → 404
  - `test_update_project`: PATCH → 200
  - `test_delete_project`: DELETE → 204
  - `test_free_tier_limit`: mock raises `FREE_TIER_LIMIT` → 403
- [x] 3.3 Create `backend/tests/test_nodes.py` with:
  - `test_create_node`: POST `/projects/{id}/nodes` → 201
  - `test_list_nodes`: GET → 200
  - `test_update_node`: PATCH → 200
  - `test_delete_node`: DELETE → 204
  - `test_node_404`: bad project/node → 404
- [x] 3.4 Create `backend/tests/test_edges.py` with:
  - `test_upsert_edge`: POST `/projects/{id}/edges` → 201
  - `test_delete_edge`: DELETE → 204
  - `test_update_constraint`: PATCH → 200
  - `test_create_edge_missing_node`: 422
  - `test_edge_404`: bad edge → 404

## Phase 4: Configuration & Verification

- [x] 4.1 Add `--cov=app --cov-report=term-missing` to `backend/pytest.ini` `addopts`
- [x] 4.2 Run `pytest --collect-only --quiet` from `backend/` — verify count ≥ 24
- [x] 4.3 Run `pytest --cov=app --cov-report=term` from `backend/` — verify exit 0 and coverage table
- [x] 4.4 Run `pytest -q` — verify all tests pass under 2s (completed in 1.00s)

## Implementation Order

Phase 1 first (deps), then Phase 2 (fixtures other tasks depend on), then Phase 3 (test files — health is simplest, then projects, then nodes, then edges), then Phase 4 (config + verification). Phases 1–2 are blocking; files in Phase 3 are independent of each other.
