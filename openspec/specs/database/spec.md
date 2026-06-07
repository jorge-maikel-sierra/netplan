# DB Setup Specification

## Purpose

Apply the NetPlan PostgreSQL schema to Supabase, seed the default organization, enable RLS, configure the auth profile trigger, and verify security posture. This establishes the foundational data layer that all backend services depend on.

## Requirements

| ID | Statement | Strength |
|----|-----------|----------|
| R1 | The DDL from `supabase-schema.sql` MUST be applied to the Supabase PostgreSQL database in the correct order (extensions → tables → RLS → functions → triggers) | MUST |
| R2 | A default organization with `slug = 'default'` and `plan = 'free'` MUST be seeded | MUST |
| R3 | The `handle_new_user` trigger MUST auto-create a `profiles` row when a new `auth.users` row is inserted | MUST |
| R4 | RLS policies MUST prevent cross-tenant access by organization | MUST |
| R5 | The security advisor SHOULD return no CRITICAL issues after migration | SHOULD |
| R6 | Re-applying the migration SHALL be idempotent via `IF NOT EXISTS` / `OR REPLACE` guards | SHALL |

### R1: Schema Migration

#### S1: All tables exist after migration

- GIVEN the migration has been applied
- WHEN querying `information_schema.tables` for the `public` schema
- THEN tables `organizations`, `profiles`, `projects`, `nodes`, `edges`, and `mst_results` all exist

#### S2: RLS enabled on all tables

- GIVEN the migration has been applied
- WHEN checking `pg_tables.rowsecurity` for each table
- THEN every table has `rowsecurity = true`
- AND the `uuid-ossp` extension is installed

### R2: Seed Data

#### S3: Default organization exists

- GIVEN the migration has been applied
- WHEN selecting from `organizations` WHERE `slug = 'default'`
- THEN exactly 1 row exists with `name = 'Default Organization'` and `plan = 'free'`

### R3: Auth Trigger

#### S4: Signup creates profile row

- GIVEN a new user signs up via Supabase Auth (email/password)
- WHEN a row is inserted into `auth.users`
- THEN within 1 second a corresponding row exists in `profiles` with `organization_id` pointing to the default org and `role = 'member'`

### R4: RLS Enforcement

#### S5: Cross-tenant query returns empty

- GIVEN user U1 belongs to org O1 and data exists for org O2
- WHEN U1 queries `projects` directly via the Data API
- THEN no rows belonging to O2 are returned

### R5: Security Posture

#### S6: Security advisor returns no CRITICAL issues

- GIVEN all DDL has been applied
- WHEN `supabase_get_advisors(type: "security")` is invoked
- THEN no CRITICAL-severity issues are reported
- AND all findings are LOW or INFO severity

### R6: Migration Idempotency

#### S7: Re-applying migration produces no errors

- GIVEN the schema has been applied once
- WHEN the same DDL statements execute again
- THEN no errors occur (`CREATE EXTENSION IF NOT EXISTS`, `CREATE OR REPLACE FUNCTION`, trigger guards handle duplicates)

## Out of Scope

- Backend or frontend code changes (schema only)
- Data migration of existing auth users
- Performance tuning or index optimization beyond what the schema already defines
