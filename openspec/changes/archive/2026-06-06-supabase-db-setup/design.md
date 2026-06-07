# Design: Supabase Database Setup

## Technical Approach

Delta migrations applied via `supabase_apply_migration` — the base schema was already partially applied (all 6 tables + RLS exist). Design covers the **missing pieces**: `plan` column on organizations, auto-profile trigger, seed data, FK indexes, and RLS initplan optimization.

## Discovery: Actual vs. Schema State

| Asset | `schema.sql` Expects | Actual (probed) | Delta |
|-------|---------------------|-----------------|-------|
| Tables (6) | CREATE TABLE | ✅ All exist | None |
| `organizations.plan` | `TEXT DEFAULT 'free'` | ❌ Missing | ADD COLUMN |
| `handle_new_user()` function | CREATE FUNCTION | ❌ Missing | CREATE |
| `on_auth_user_created` trigger | CREATE TRIGGER | ❌ Missing | CREATE |
| Seed "Default Organization" | INSERT | ❌ Only "Test Org" exists | INSERT |
| FK indexes | (implied) | ❌ 7 unindexed FKs per advisor | CREATE INDEX |
| RLS initplan | `auth.uid()` | ⚠️ Causing re-eval warnings | Rewrite to `(select auth.uid())` |

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| Migration granularity | 5 separate migrations | Single monolithic | Idempotent, reversible, reviewable per logical domain |
| RLS initplan fix | `(select auth.uid())` wrapper | Leave as-is | Supabase docs confirm wrapper avoids per-row re-evaluation |
| Index strategy | B-tree on every FK column | Composite covering indexes | FK joins are the hot path for tenant queries; simple B-tree is optimal |
| Seed org slug | `'default'` as suffix | First-org-wins, config-driven | Matches AGENTS.md contract; slug is UNIQUE so ON CONFLICT DO NOTHING is safe |

## Migration Plan

### M001: Add `plan` column + indexes

```sql
ALTER TABLE organizations ADD COLUMN IF NOT EXISTS plan TEXT NOT NULL DEFAULT 'free'
  CHECK (plan IN ('free', 'premium'));

CREATE INDEX IF NOT EXISTS idx_profiles_organization_id ON profiles(organization_id);
CREATE INDEX IF NOT EXISTS idx_projects_organization_id ON projects(organization_id);
CREATE INDEX IF NOT EXISTS idx_projects_created_by ON projects(created_by);
CREATE INDEX IF NOT EXISTS idx_nodes_project_id ON nodes(project_id);
CREATE INDEX IF NOT EXISTS idx_edges_project_id ON edges(project_id);
CREATE INDEX IF NOT EXISTS idx_edges_node_a_id ON edges(node_a_id);
CREATE INDEX IF NOT EXISTS idx_edges_node_b_id ON edges(node_b_id);
CREATE INDEX IF NOT EXISTS idx_mst_results_project_id ON mst_results(project_id);
```

### M002: Trigger function + trigger

```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.profiles (id, organization_id, display_name, role)
  VALUES (
    NEW.id,
    (SELECT id FROM organizations WHERE slug = 'default' LIMIT 1),
    NEW.raw_user_meta_data->>'display_name',
    'member'
  );
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

### M003: Optimize RLS initplan

Rewrite each `tenant_isolation` policy to wrap `auth.uid()` in a subquery:

```sql
-- Before (per row re-evaluation):
-- USING (id = (SELECT organization_id FROM profiles WHERE id = auth.uid()))

-- After:
DROP POLICY IF EXISTS tenant_isolation ON organizations;
CREATE POLICY tenant_isolation ON organizations
  USING (id = (SELECT organization_id FROM profiles WHERE id = (select auth.uid())));
```

Apply the same pattern to all 6 tables.

### M004: Seed data

```sql
INSERT INTO organizations (name, slug, plan) VALUES ('Default Organization', 'default', 'free')
ON CONFLICT (slug) DO NOTHING;
```

### M005: Verify

Run after all migrations — see verification strategy below.

## Verification Strategy

| Check | SQL / Tool | Expected |
|-------|-----------|----------|
| Tables exist | `SELECT table_name FROM information_schema.tables WHERE table_schema='public'` | 6 tables |
| RLS enabled | `SELECT relname, relrowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace` | All true |
| Trigger exists | `SELECT tgname FROM pg_trigger WHERE tgrelid='auth.users'::regclass` | `on_auth_user_created` |
| Function exists | `SELECT proname FROM pg_proc WHERE proname='handle_new_user'` | 1 row |
| `plan` column | `SELECT column_name FROM information_schema.columns WHERE table_name='organizations'` | Includes `plan` |
| Indexes cover FKs | `SELECT indexname FROM pg_indexes WHERE tablename='edges'` | `idx_edges_node_a_id`, `idx_edges_node_b_id`, etc. |
| Advisors | `supabase_get_advisors(security)` + `(performance)` | No unindexed FK warnings, no initplan warnings |
| Seed data | `SELECT count(*) FROM organizations WHERE slug='default'` | 1 |
| Trigger simulation | Not possible directly (auth.users insert requires Supabase Auth); accept as post-deploy smoke test via signup |

## Rollback Plan

```sql
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.handle_new_user();
ALTER TABLE organizations DROP COLUMN IF EXISTS plan;
DROP INDEX IF EXISTS idx_profiles_organization_id;
DROP INDEX IF EXISTS idx_projects_organization_id;
DROP INDEX IF EXISTS idx_projects_created_by;
DROP INDEX IF EXISTS idx_nodes_project_id;
DROP INDEX IF EXISTS idx_edges_project_id;
DROP INDEX IF EXISTS idx_edges_node_a_id;
DROP INDEX IF EXISTS idx_edges_node_b_id;
DROP INDEX IF EXISTS idx_mst_results_project_id;
DELETE FROM organizations WHERE slug = 'default';
```

## Files Affected

| File | Action | Description |
|------|--------|-------------|
| `supabase-schema.sql` | None (read-only reference) | Already committed; design tracks actual delta |
| `openspec/changes/supabase-db-setup/design.md` | Create | This file |

No code changes — pure database migrations.

## Open Questions

None — all gaps confirmed via live probing.
