# Design: Deploy Integration Verification & Production Readiness

## Technical Approach

This change produces a **verification checklist** rather than new code. The design documents the criteria and methods to validate that the NetPlan SaaS is production-ready across build, config, security, and integration dimensions. Each checklist item maps to an existing implementation that must be confirmed working.

## Architecture Decisions

### Decision: Checklist Format Over Test Suite

**Choice**: Markdown checklist with pass/fail per item
**Alternatives considered**: Automated integration test suite, CI pipeline gates
**Rationale**: Greenfield project with no existing test infrastructure; checklist is faster to execute manually and serves as audit trail for stakeholders. Can be automated incrementally later.

### Decision: No New Code Unless Broken

**Choice**: Verify existing implementation only
**Alternatives considered**: Add missing features during verification
**Rationale**: Scope is "readiness verification" — adding features mid-verification creates moving targets. Broken items become follow-up tasks.

## Verification Checklist

| # | Area | Item | Verification Method | Expected Result | Pass/Fail |
|---|------|------|---------------------|-----------------|-----------|
| 1 | Build | Backend installs deps | `cd backend && pip install -r requirements.txt` | No errors | ☐ |
| 2 | Build | Backend starts | `uvicorn app.main:app --reload` | Server starts on :8000 | ☐ |
| 3 | Build | Frontend builds | `cd frontend && npm run build` | `dist/` created, no errors | ☐ |
| 4 | Env | Backend .env exists | Check `backend/.env` | All 3 vars present | ☐ |
| 5 | Env | Frontend .env exists | Check `frontend/.env` | All 3 vars present | ☐ |
| 6 | Env | No secrets in repo | `git ls-files | grep -E '\.env$'` | Only `.env.example` files | ☐ |
| 7 | CORS | ALLOWED_ORIGINS set | Check backend `.env` | Matches Vercel prod URL | ☐ |
| 8 | CORS | Preflight works | `curl -X OPTIONS https://api.netplan.app/api/v1/projects` | 200/204 with CORS headers | ☐ |
| 9 | Rate Limit | MST endpoint limited | 6 rapid POST to `/projects/{id}/mst/calculate` | 5th request → 429 | ☐ |
| 10 | Rate Limit | slowapi active | Check `app/main.py` middleware | `slowapi` middleware registered | ☐ |
| 11 | Free Tier | 4th project blocked | Create 4 projects as free org | 4th returns 403 FREE_TIER_LIMIT | ☐ |
| 12 | Free Tier | Plan default | Check `organizations` table | `plan` defaults to `'free'` | ☐ |
| 13 | Error Format | Consistent envelope | Call any endpoint with error | `{error, code, detail}` | ☐ |
| 14 | Error Format | No raw exceptions | Trigger 500 (e.g., DB down) | Formatted error, no traceback | ☐ |
| 15 | Error Format | Cross-tenant = 404 | Access other org's project | 404 (not 403) | ☐ |
| 16 | Health | GET /healthz | `curl https://api.netplan.app/healthz` | 200 `{"status": "ok"}` | ☐ |
| 17 | Auth | Login flow | Supabase Auth UI → redirect to `/projects` | Session established | ☐ |
| 18 | Auth | JWT validation | Call protected endpoint with token | 200 with org-scoped data | ☐ |
| 19 | Auth | Token refresh | Wait for expiry + call API | New token acquired silently | ☐ |

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `openspec/changes/deploy-integration/design.md` | Create | This verification checklist document |

**No application code changes required** — this is a verification artifact.

## Interfaces / Contracts

No new interfaces. Verification targets existing contracts:

- **API Base**: `https://api.netplan.app/api/v1`
- **Auth**: `Authorization: Bearer <supabase_jwt>`
- **Error Envelope**: `{ "error": "CODE", "code": 422, "detail": "message" }`
- **Health**: `GET /healthz` → `{"status": "ok"}`

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Build | Dependency install + server start | Manual commands in clean env |
| Config | Env var presence + CORS | File inspection + curl preflight |
| Security | Rate limit + free tier + cross-tenant | Scripted API calls with timing |
| Integration | Auth flow end-to-end | Browser + Supabase Auth UI |
| Contract | Error format consistency | Automated curl matrix against error cases |

## Migration / Rollout

No migration required. This change produces documentation only.

## Open Questions

- [ ] Should checklist be automated in CI/CD pipeline (GitHub Actions)?
- [ ] Do we need load testing for MST endpoint before launch?
- [ ] Is 5 req/min rate limit appropriate for premium tier too?

---

**Next Step**: Execute verification manually, mark pass/fail, create follow-up tasks for any failures.