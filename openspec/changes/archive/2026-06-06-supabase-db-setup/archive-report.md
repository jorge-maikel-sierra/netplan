# Archive Report: supabase-db-setup

**Archived**: 2026-06-06
**Status**: PASS

## Summary

The `supabase-db-setup` change completed the foundational Supabase PostgreSQL schema for NetPlan. Live probing revealed 5 gaps between the `schema.sql` reference and the actual database state. All gaps closed via 5 delta migrations (M001-M005) plus 1 hardening migration:

- **M001**: Added `plan` column to `organizations` + 8 FK indexes
- **M002**: Created `handle_new_user()` auth trigger
- **M003**: Rewrote RLS policies to avoid initplan re-evaluation (`(select auth.uid())` wrapper)
- **M004**: Seeded "Default Organization" with slug `default` and plan `free`
- **M005**: Verification (S1-S7 all pass)
- **Hardening**: `REVOKE EXECUTE ON handle_new_user() FROM PUBLIC`

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| database | Created | 6 requirements, 7 scenarios — full spec copied as new domain |

## Archive Contents

- `design.md` ✅ — 5-migration plan with architecture decisions
- `spec.md` ✅ — delta spec (6 requirements, 7 Given/When/Then scenarios)
- `tasks.md` ✅ — 5/5 tasks complete across 5 phases
- `archive-report.md` ✅ — this file

## Verify Findings (preserved)

See Engram observation #60 for full verification report.

| Check | Result |
|-------|--------|
| All 6 tables exist with RLS enabled | ✅ |
| Default org seeded with plan='free' | ✅ |
| Auth trigger function + trigger | ✅ |
| RLS initplan-safe pattern | ✅ |
| Security advisor: 0 CRITICAL | ✅ |
| Performance advisor: 8 INFO (unused indexes — expected greenfield) | ✅ |
| **Overall: 7/7 scenarios, 6/6 requirements** | **PASS** |

## Engram Artifact Traceability

| Artifact | Observation ID | Key |
|----------|---------------|-----|
| Design | #57 | `sdd/supabase-db-setup/design` |
| Tasks | #58 | `sdd/supabase-db-setup/tasks` |
| Apply | #59 | `sdd/supabase-db-setup/apply-progress` |
| Verify | #60 | `sdd/supabase-db-setup/verify-report` |
| Archive | — | `sdd/supabase-db-setup/archive-report` |

## Learnings

- `profiles` table uses `display_name`, not `full_name` — trust design docs over inline task SQL
- `handle_new_user()` needs `SET search_path = ''` + `REVOKE EXECUTE FROM PUBLIC` for security compliance
- `(select auth.uid())` wrapper is Supabase's recommended pattern to avoid per-row RLS re-evaluation
- `ON CONFLICT (slug) DO NOTHING` makes seed data idempotent

## Files in this archive

- `design.md` — 5-migration design with rollback plan
- `spec.md` — delta spec (now synced to main spec at `openspec/specs/database/spec.md`)
- `tasks.md` — task breakdown (5/5 tasks complete)

## Source of Truth Updated

The following specs now reflect the implemented behavior:
- `openspec/specs/database/spec.md` — new domain, 6 requirements
