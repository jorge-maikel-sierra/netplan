# Design: MST Calculation Endpoint

POST `/projects/{id}/mst/calculate` + GET `/projects/{id}/mst/latest` — rate-limited, tenant-scoped MST via Kruskal.

## Audit Summary

| Area | Status |
|------|--------|
| Contract match (POST + GET) | ✅ Complete |
| Error format `{error, code, detail}` | ✅ Consistent |
| Core algorithm + constraint handling | ✅ Pure function, correct |
| Tenant isolation | ✅ `organization_id` on every query |
| Persistence on success only (REQ-MST-006) | ✅ Implemented |
| Schemas match spec | ✅ |
| Rate limiting decorator + 429 handler | ✅ Wired |
| **Rate limit key function** | ❌ **Production bug** |
| **Test coverage** | ❌ Gaps below |

## Gaps Found

### 1. Rate limit key function broken in production

`rate_limit.py::get_org_id_from_jwt_payload()` extracts `organization_id` from the unsigned JWT. **This claim does not exist in default Supabase JWTs** — it lives in the `profiles` table. Every request falls back to key `"anonymous"`, so ALL orgs share one bucket. Effective per-org rate limiting requires a [Custom Access Token Hook](https://supabase.com/docs/guides/auth/auth-hooks/custom-access-token-hook) to copy `profiles.organization_id` into JWT `app_metadata`.

**Fix**: Change key to extract `sub` (user_id) — always present in valid Supabase JWTs. Per-user vs per-org is a pragmatic tradeoff:

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `sub` from JWT | Per-user bucket, works now, no infra change | ✅ **Chosen** |
| Custom Access Token Hook | Per-org bucket, matches spec exactly | Out of scope |
| No rate limiting | No protection on expensive endpoint | ❌ |

### 2. Missing test coverage

| Gap | What's untested |
|-----|----------------|
| 429 rate-limit response | slowapi returns `RATE_LIMITED` + `retry_after` |
| Key function behavior | JWT with/without `sub`, malformed header, missing header |
| `get_latest_mst` enrichment | Edge-skipping on deleted edges, `source_node_name` resolution |
| `_enrich_disconnected_detail` | 0 and 1 unreachable node edge cases |

### 3. Minor: 401 test leaks DI override

`test_calculate_endpoint_unauthenticated_returns_401` installs `dependency_overrides[get_current_user]` without cleanup. Works because conftest clears it at teardown, but fragile. Refactor to use conftest's override mechanism.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/core/rate_limit.py` | Modify | Key function now extracts `sub`; update module docstring + comments |
| `backend/tests/unit/test_rate_limit.py` | Create | Unit tests for key function: valid JWT, missing header, malformed JWT, missing `sub` |
| `backend/tests/integration/test_mst_router.py` | Modify | Add 429 test, latest-enrichment test, edge-skipping test; refactor 401 test DI |

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit | Key function (new `test_rate_limit.py`) | Direct calls to `get_org_id_from_jwt_payload` with crafted JWTs, empty headers, garbage |
| Integration | 429 response | 6th POST to calculate with conftest DI; assert `RATE_LIMITED`, `retry_after` |
| Integration | Latest enrichment | Mock mst_results + edges + nodes; verify `source_node_name` and correct ordering |
| Integration | Edge-skipping | Mock mst_results referencing a deleted edge; verify it's absent from response |

## Migration / Rollout

No migration. Code-only change — no DB, no env vars, no feature flag.

## Open Questions

None.
