# Tasks: MST Calculation Endpoint

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~190 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Delivery strategy | single-pr |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

## Phase 1: Fix Rate Limit Key Function

- [x] **T-01-01**: Change `get_org_id_from_jwt_payload` in `rate_limit.py` to extract `sub` claim instead of `organization_id`; update module docstring and inline comment to reflect per-user keying.
  - **Files**: `backend/app/core/rate_limit.py`
  - **Verify**: Valid JWT → returns `sub` string; missing `sub` → `"anonymous"`; no header → `"anonymous"`; malformed → `"anonymous"`

## Phase 2: Unit Tests for Key Function

- [x] **T-02-01**: Create `test_rate_limit.py` with 5 test cases (+2 triangulation): valid JWT with `sub`, missing `sub` claim, missing Authorization header, malformed JWT, empty token, empty string `sub`, non-string `sub`.
  - **Files**: `backend/tests/unit/test_rate_limit.py` (new)
  - **Verify**: `pytest tests/unit/test_rate_limit.py -v` — 7 passed

## Phase 3: Integration Tests and Cleanup

- [x] **T-03-01**: Add 429 rate-limit integration test: fire 6 POSTs to `/projects/{id}/mst/calculate`, expect 5th returns 200 and 6th returns 429 with `RATE_LIMITED` error and `retry_after` integer field.
  - **Files**: `backend/tests/integration/test_mst_router.py`
  - **Verify**: `pytest tests/integration/test_mst_router.py -v` — 429 + `retry_after` confirmed

- [x] **T-03-02**: Add latest enrichment integration tests: (a) edge-skipping — mst_results references a deleted edge, verify it's absent from response; (b) `source_node_name` resolution from loaded nodes.
  - **Files**: `backend/tests/integration/test_mst_router.py`
  - **Verify**: Skipped edge absent from response `mst_edges`; correct `source_node_name` mapping

- [x] **T-03-03**: Add disconnected detail message tests for n=1 unreachable node (singular message). Refactor `test_calculate_endpoint_unauthenticated_returns_401` to use save/restore DI pattern.
  - **Files**: `backend/tests/integration/test_mst_router.py`
  - **Verify**: Correct Spanish detail for 1 unreachable node; 401 test cleans up via explicit save/restore

## Summary

| Task | File(s) | LOC | Verification |
|------|---------|-----|-------------|
| T-01-01 | `rate_limit.py` | ~30 | Key function returns `sub` |
| T-02-01 | `test_rate_limit.py` (new) | ~100 | 7 unit tests pass |
| T-03-01 | `test_mst_router.py` | ~45 | 429 + `retry_after` |
| T-03-02 | `test_mst_router.py` | ~80 | Edge-skipped + correct name |
| T-03-03 | `test_mst_router.py` | ~60 | Singular message + DI cleanup |
| **Total** | **3 files** | **~315** | **40→51 tests** |

## Next Step

Ready for implementation (sdd-apply). Single PR, no chaining needed.
