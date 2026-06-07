# Verify Report: MST Calculation Endpoint (T-01-05)

**Verdict**: PASS_WITH_WARNINGS

**Generated**: 2026-06-06

## Test Results
- Total: 20
- Passed: 20
- Failed: 0
- Duration: 0.36s

## App Imports
- `from app.main import app` → app OK
- `from app.routers.mst import router` → router OK
- `from app.services.mst_service import calculate_mst, ProjectNotFound` → service OK
- `from app.core.mst_algorithm import calculate, NodeDict, EdgeDict, MSTResult, InsufficientNodesError, MandatoryCycleError, DisconnectedGraphError` → core OK

## Spec Coverage

| REQ | Spec requirement | Tests covering it |
|---|---|---|
| REQ-MST-001 | Calculate MST (Kruskal) with happy path, mandatory, forbidden, cycle, empty/single/two nodes | `test_calculate_simple_triangle`, `test_calculate_mandatory_force_included`, `test_calculate_mandatory_cycle_rejected`, `test_calculate_forbidden_excluded`, `test_calculate_insufficient_nodes_zero`, `test_calculate_insufficient_nodes_one`, `test_calculate_two_nodes_one_edge`, `test_calculate_endpoint_happy_path`, `test_calculate_endpoint_insufficient_nodes_returns_422`, `test_calculate_endpoint_mandatory_cycle_returns_422` |
| REQ-MST-002 | Disconnected graph detection with unreachable_nodes | `test_calculate_disconnected_returns_unreachable`, `test_calculate_endpoint_disconnected_returns_422` |
| REQ-MST-003 | Cross-tenant isolation (404, no 403) + unauthenticated 401 | `test_calculate_endpoint_tenant_isolation`, `test_calculate_endpoint_unauthenticated_returns_401`, `test_latest_endpoint_cross_tenant_returns_404` |
| REQ-MST-004 | Latest MST result, 404 when no result | `test_latest_endpoint_returns_most_recent`, `test_latest_endpoint_no_result_returns_404` |
| REQ-MST-005 | Rate limit 5/min per org_id, 6th → 429 | **NOT COVERED** — no integration test exists; `test_mst_router.py` line 4 only mentions it in a docstring. Service has the limiter wired in `app/routers/mst.py` and the conftest resets the limiter between tests, but no test asserts the 6th request returns 429. |
| REQ-MST-006 | Persist on success, NO persist on failure | `test_calculate_endpoint_persists_on_success`, `test_calculate_endpoint_no_persist_on_failure`, `test_calculate_disconnected_no_partial_result` (core level) |
| REQ-MST-007 | Tenant-scoped loading (org_id filter) | Covered transitively via `test_calculate_endpoint_tenant_isolation` (404 when project is from a different org). `mst_service.py` line 81 uses `.eq("organization_id", str(org_id))` on the projects check, which is the primary enforcement. **No dedicated assertion** that the supabase chain contains `organization_id`. |

## Smoke Test
- `/healthz`: `{"status":"ok"}` (200)
- `POST /mst/calculate` no auth: **401**
- `GET /mst/latest` no auth: **401**

## Findings

### CRITICAL
None

### WARNING
1. **REQ-MST-005 (rate limit) has no automated test.** The slowapi limiter is wired in `app/routers/mst.py:78` and `app/core/rate_limit.py` decodes the JWT org_id. The conftest resets the limiter between tests, suggesting the test infra was prepared for a rate-limit test, but no test asserting the 6th request returns 429 was written. The behavior is verifiable manually but is not regression-protected. Recommended action: add `test_calculate_endpoint_rate_limited` that issues 6 requests and asserts the 6th is 429.
2. **REQ-MST-007 (tenant filter on supabase query) is not directly asserted.** The `service.mst_service.calculate_mst` does filter by `organization_id` on the project lookup (line 81), and the cross-tenant integration test proves end-to-end isolation, but no test asserts that the supabase mock received `.eq("organization_id", org_id)`. The defense is in code review, not the test suite.

### SUGGESTION
1. The `mst_service.py:171` and `:311` fallbacks to `datetime.now(tz=timezone.utc)` when the inserted row has no `calculated_at` are defensive code paths that should never trigger with a real Supabase backend. They are harmless but indicate the contract between service and DB is not strictly typed. Consider raising on missing timestamp instead of silent fallback.
2. `rate_limit_exceeded_handler` accepts an unused `response: Any = None` parameter for slowapi version compatibility. Consider removing once the slowapi version is pinned and the call signature is stable.
3. The `headers_enabled=False` setting on the `Limiter` (rate_limit.py:87) intentionally disables `X-RateLimit-*` response headers because the endpoints return Pydantic models. Documented inline but worth a note in `AGENTS.md` for future maintainers.

## Ready for Archive
YES
