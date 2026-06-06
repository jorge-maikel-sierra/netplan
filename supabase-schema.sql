-- NetPlan SaaS Database Schema
-- Run in Supabase SQL Editor in this exact order

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. organizations table
CREATE TABLE organizations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  slug        TEXT NOT NULL UNIQUE,
  plan        TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'premium')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. profiles table (extends auth.users)
CREATE TABLE public.profiles (
  id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id),
  display_name    TEXT,
  role            TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. projects table
CREATE TABLE projects (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  created_by      UUID NOT NULL REFERENCES profiles(id),
  name            TEXT NOT NULL,
  description     TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. nodes table
CREATE TABLE nodes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  type        TEXT NOT NULL DEFAULT 'city' CHECK (type IN ('city', 'tower', 'datacenter')),
  lat         DOUBLE PRECISION NOT NULL,
  lng         DOUBLE PRECISION NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. edges table
CREATE TABLE edges (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  node_a_id       UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  node_b_id       UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  cost            NUMERIC(12, 2) NOT NULL CHECK (cost >= 0),
  constraint_type TEXT NOT NULL DEFAULT 'normal' CHECK (constraint_type IN ('normal', 'mandatory', 'forbidden')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_id, node_a_id, node_b_id)
);

-- 6. mst_results table
CREATE TABLE mst_results (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  algorithm       TEXT NOT NULL DEFAULT 'kruskal',
  total_cost      NUMERIC(14, 2) NOT NULL,
  edge_ids        UUID[] NOT NULL,
  calculated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS Policies (apply to all tables)
-- organizations
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON organizations
  USING (id = (SELECT organization_id FROM profiles WHERE id = auth.uid()));

-- profiles
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON profiles
  USING (organization_id = (SELECT organization_id FROM profiles WHERE id = auth.uid()));

-- projects
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON projects
  USING (organization_id = (SELECT organization_id FROM profiles WHERE id = auth.uid()));

-- nodes
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON nodes
  USING (project_id IN (SELECT id FROM projects WHERE organization_id = (SELECT organization_id FROM profiles WHERE id = auth.uid())));

-- edges
ALTER TABLE edges ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON edges
  USING (project_id IN (SELECT id FROM projects WHERE organization_id = (SELECT organization_id FROM profiles WHERE id = auth.uid())));

-- mst_results
ALTER TABLE mst_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_isolation" ON mst_results
  USING (project_id IN (SELECT id FROM projects WHERE organization_id = (SELECT organization_id FROM profiles WHERE id = auth.uid())));

-- Trigger to auto-create profile on user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
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
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Create a default organization for new users (run once)
-- INSERT INTO organizations (name, slug) VALUES ('Default Organization', 'default')
-- ON CONFLICT (slug) DO NOTHING;