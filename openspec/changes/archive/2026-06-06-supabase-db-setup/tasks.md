# Tasks: supabase-db-setup

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~45 (pure SQL) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

## Phase 1: Foundation — Schema Migrations

### T-01-01: Add `plan` column + 8 FK indexes
- [x] **What**: `ALTER TABLE organizations ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free','premium'))`. Create `CREATE INDEX IF NOT EXISTS` on all FK columns: `profiles(organization_id)`, `projects(organization_id)`, `projects(created_by)`, `nodes(project_id)`, `edges(project_id)`, `edges(node_a_id)`, `edges(node_b_id)`, `mst_results(project_id)`.
- **Migration**: `supabase_apply_migration(name: "001_add_plan_and_indexes", query: "...")` ✅
- **Verify**: `SELECT column_name FROM information_schema.columns WHERE table_name='organizations' AND column_name='plan'` → 1 row ✅. `SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND indexname LIKE 'idx_%'` → 8 ✅.

## Phase 2: Auth Trigger

### T-02-01: Create `handle_new_user()` function + trigger
- [x] **What**: `CREATE OR REPLACE FUNCTION public.handle_new_user()` (SECURITY DEFINER SET search_path = '', inserts profile linked to default org with `role='member'`). `DROP TRIGGER IF EXISTS` + `CREATE TRIGGER on_auth_user_created ON auth.users AFTER INSERT FOR EACH ROW`.
- **Migration**: `supabase_apply_migration(name: "002_auth_trigger", query: "...")` ✅
- **Verify**: `SELECT proname FROM pg_proc WHERE proname='handle_new_user'` → 1 row ✅. `SELECT tgname FROM pg_trigger WHERE tgrelid='auth.users'::regclass` → `on_auth_user_created` ✅.

## Phase 3: RLS Optimization

### T-03-01: Fix RLS initplan warnings
- [x] **What**: Rewrite all 6 `tenant_isolation` policies (one per table) to wrap `auth.uid()` in `(select auth.uid())` subquery — prevents per-row re-evaluation.
- **Migration**: `supabase_apply_migration(name: "003_rls_initplan_fix", query: "DROP POLICY IF EXISTS ...; CREATE POLICY ... USING (... (select auth.uid()) ...)")` ✅
- **Verify**: `supabase_get_advisors(type: "security")` → no initplan re-evaluation warnings (only LOW/INFO findings) ✅.

## Phase 4: Seed Data

### T-04-01: Seed Default Organization
- [x] **What**: `INSERT INTO organizations (name, slug, plan) VALUES ('Default Organization', 'default', 'free') ON CONFLICT (slug) DO NOTHING`.
- **Migration**: `supabase_apply_migration(name: "004_seed_default_org", query: "...")` ✅
- **Verify**: `SELECT count(*) FROM organizations WHERE slug='default' AND plan='free'` → 1 ✅.

## Phase 5: Verification

### T-05-01: Full smoke check
- [x] **What**: Run security + performance advisors on final state. Verify all tables, trigger, function, indexes.
- **Commands**: `supabase_get_advisors(type: "security")` → no CRITICAL ✅. `supabase_get_advisors(type: "performance")` → no unindexed FK warnings ✅. `SELECT table_name FROM information_schema.tables WHERE table_schema='public'` → 6 tables ✅.
- **Extra**: Added `005_revoke_rpc_handle_new_user` to revoke EXECUTE on `handle_new_user()` from public (only trigger-invoked, never via RPC).
- **Verify**: No CRITICAL security issues; no unindexed FK warnings; 6 tables present; S1–S7 from spec all pass ✅.
