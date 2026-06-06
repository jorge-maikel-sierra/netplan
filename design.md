# Design — Sistema SaaS de Planificación de Infraestructura de Red

## 1. System Architecture

```
┌──────────────────────────────┐
│  Frontend (React + Vite)     │  Vercel  →  https://netplan.vercel.app
│  TailwindCSS · Leaflet.js    │
└────────────┬─────────────────┘
             │ HTTPS REST + Supabase JS SDK
┌────────────▼─────────────────┐
│  Backend (FastAPI / Python)  │  Render/Railway  →  https://api.netplan.app
│  NetworkX · OpenPyXL         │
└────────────┬─────────────────┘
             │ supabase-py (service role)
┌────────────▼─────────────────┐
│  Supabase (PostgreSQL)       │  Hosted Supabase project
│  Auth · RLS · Storage        │
└──────────────────────────────┘
```

**Communication rules:**
- Frontend ↔ Backend: REST JSON over HTTPS. Backend owns all business logic.
- Frontend ↔ Supabase: ONLY for authentication (signIn, signOut, session refresh). No direct DB calls from the frontend.
- Backend ↔ Supabase: All DB operations use `supabase-py` with service role key (bypasses RLS at the library level but applies manual tenant scoping in every query).

> **Why no direct frontend DB calls?** Keeps business logic centralized and simplifies RLS reasoning. Supabase RLS remains as a defense-in-depth layer, not the primary enforcement mechanism.

---

## 2. Database Schema

### Table: `organizations`
```sql
CREATE TABLE organizations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  slug        TEXT NOT NULL UNIQUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Table: `users` (extends Supabase Auth `auth.users`)
```sql
CREATE TABLE public.profiles (
  id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  organization_id UUID NOT NULL REFERENCES organizations(id),
  display_name    TEXT,
  role            TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Table: `projects`
```sql
CREATE TABLE projects (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id UUID NOT NULL REFERENCES organizations(id),
  created_by      UUID NOT NULL REFERENCES profiles(id),
  name            TEXT NOT NULL,
  description     TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Table: `nodes`
```sql
CREATE TABLE nodes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  type        TEXT NOT NULL DEFAULT 'city' CHECK (type IN ('city', 'tower', 'datacenter')),
  lat         DOUBLE PRECISION NOT NULL,
  lng         DOUBLE PRECISION NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Table: `edges`
```sql
CREATE TABLE edges (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  node_a_id   UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  node_b_id   UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  cost        NUMERIC(12, 2) NOT NULL CHECK (cost >= 0),
  constraint_type TEXT NOT NULL DEFAULT 'normal' CHECK (constraint_type IN ('normal', 'mandatory', 'forbidden')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (project_id, node_a_id, node_b_id)
);
```

### Table: `mst_results`
```sql
CREATE TABLE mst_results (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  algorithm       TEXT NOT NULL DEFAULT 'kruskal',
  total_cost      NUMERIC(14, 2) NOT NULL,
  edge_ids        UUID[] NOT NULL,   -- ordered list of edge IDs included in MST
  calculated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### RLS Policies (apply to all tables)
```sql
-- Example for `projects` (repeat pattern for nodes, edges, mst_results)
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tenant_isolation" ON projects
  USING (
    organization_id = (
      SELECT organization_id FROM profiles WHERE id = auth.uid()
    )
  );
```

---

## 3. API Contract

**Base URL:** `https://api.netplan.app/api/v1`  
**Auth header:** `Authorization: Bearer <supabase_jwt>` on all protected endpoints.  
**Error format:**
```json
{ "error": "VALIDATION_ERROR", "code": 422, "detail": "lat must be between -90 and 90" }
```

---

### 3.1 Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects` | List all projects for tenant |
| POST | `/projects` | Create new project |
| GET | `/projects/{id}` | Get project with nodes, edges, last result |
| PATCH | `/projects/{id}` | Rename or update description |
| DELETE | `/projects/{id}` | Delete project and all children |

**POST /projects — Request body:**
```json
{
  "name": "Red Riohacha Norte",
  "description": "Planificación Q2 2026"
}
```

**GET /projects/{id} — Response:**
```json
{
  "id": "uuid",
  "name": "Red Riohacha Norte",
  "nodes": [ { "id": "uuid", "name": "Torre Centro", "type": "tower", "lat": 11.54, "lng": -72.91 } ],
  "edges": [ { "id": "uuid", "node_a_id": "uuid", "node_b_id": "uuid", "cost": 1500.00, "constraint_type": "normal" } ],
  "last_result": { "total_cost": 4200.00, "algorithm": "kruskal", "edge_ids": ["uuid", "uuid"] }
}
```

---

### 3.2 Nodes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/projects/{id}/nodes` | Add single node |
| PUT | `/projects/{id}/nodes/{node_id}` | Update node |
| DELETE | `/projects/{id}/nodes/{node_id}` | Delete node (cascades edges) |
| POST | `/projects/{id}/nodes/import` | Bulk import from .xlsx |

**POST /projects/{id}/nodes — Request:**
```json
{
  "name": "Torre Centro",
  "type": "tower",
  "lat": 11.5444,
  "lng": -72.9072
}
```

**POST /projects/{id}/nodes/import — Request:** `multipart/form-data`, field `file` (.xlsx).  
**POST /projects/{id}/nodes/import — Response (success):**
```json
{
  "imported": 12,
  "skipped": 1,
  "errors": [
    { "row": 5, "field": "lat", "message": "Value '999' is out of valid range [-90, 90]" }
  ]
}
```

---

### 3.3 Edges & Constraints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/projects/{id}/edges` | Add or update edge between two nodes |
| DELETE | `/projects/{id}/edges/{edge_id}` | Remove edge |
| PATCH | `/projects/{id}/edges/{edge_id}/constraint` | Change constraint type |

**POST /projects/{id}/edges — Request:**
```json
{
  "node_a_id": "uuid",
  "node_b_id": "uuid",
  "cost": 2500.00,
  "constraint_type": "mandatory"
}
```

---

### 3.4 MST Calculation

| Method | Path | Description |
|--------|------|-------------|
| POST | `/projects/{id}/mst/calculate` | Run MST and persist result |
| GET | `/projects/{id}/mst/latest` | Get latest saved result |

**POST /projects/{id}/mst/calculate — Response (success):**
```json
{
  "result_id": "uuid",
  "algorithm": "kruskal",
  "total_cost": 7850.00,
  "mst_edges": [
    { "edge_id": "uuid", "node_a": "Torre Centro", "node_b": "Nodo Puerto", "cost": 1500.00 }
  ],
  "nodes_connected": 8,
  "calculated_at": "2026-06-06T14:22:00Z"
}
```

**POST /projects/{id}/mst/calculate — Response (error, disconnected graph):**
```json
{
  "error": "DISCONNECTED_GRAPH",
  "code": 422,
  "detail": "After applying constraints, nodes [Torre Norte, Nodo Lejano] are unreachable from the main component."
}
```

---

### 3.5 Export

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/{id}/export/excel` | Download .xlsx with nodes + MST edges |
| POST | `/projects/{id}/export/pdf` | Generate and download PDF report |

**POST /projects/{id}/export/pdf — Request:**
```json
{
  "map_image_base64": "<canvas export from Leaflet, base64 PNG>"
}
```
PDF generated server-side using `reportlab` or `weasyprint`. Returns `application/pdf`.

---

## 4. Frontend Structure

```
src/
├── main.jsx
├── App.jsx                     # Router setup
├── pages/
│   ├── HomePage.jsx            # Landing / description
│   ├── LoginPage.jsx           # Supabase Auth UI
│   ├── ProjectsPage.jsx        # Project list
│   └── PlannerPage.jsx         # Main planner (map + panels)
├── components/
│   ├── NodeForm.jsx            # Add/edit node form
│   ├── EdgeForm.jsx            # Add edge + constraint picker
│   ├── ConstraintsPanel.jsx    # List of tagged edges
│   ├── ResultsSummary.jsx      # MST result summary sidebar
│   ├── MapView.jsx             # Leaflet map wrapper
│   ├── ImportButton.jsx        # Excel upload + preview
│   └── ExportButton.jsx        # PDF / Excel export trigger
├── hooks/
│   ├── useProject.js           # Project CRUD + state
│   ├── useMst.js               # MST trigger + result
│   └── useAuth.js              # Supabase session
├── services/
│   ├── api.js                  # Axios instance + interceptors
│   └── supabaseClient.js       # Supabase JS init (auth only)
└── utils/
    └── validators.js           # Shared validation helpers
```

**Key decisions:**
- React Router v6 for routing.
- Axios for API calls; interceptor adds JWT from Supabase session automatically.
- Leaflet instantiated inside `MapView.jsx` via `useEffect`; avoid re-initializing on re-renders (use `useRef` for map instance).
- State management: React Context + `useReducer` for project state (no Redux needed at this scale).

---

## 5. Backend Structure

```
app/
├── main.py                     # FastAPI app init, CORS, routers mount
├── config.py                   # Settings via pydantic-settings (env vars)
├── dependencies.py             # JWT validation, tenant resolution
├── routers/
│   ├── projects.py
│   ├── nodes.py
│   ├── edges.py
│   ├── mst.py
│   └── export.py
├── services/
│   ├── mst_service.py          # NetworkX graph construction + algorithm
│   ├── excel_service.py        # OpenPyXL import/export
│   └── pdf_service.py          # PDF generation
├── schemas/
│   ├── project.py              # Pydantic v2 models
│   ├── node.py
│   ├── edge.py
│   └── mst.py
└── db/
    └── supabase_client.py      # supabase-py client init
```

**MST service logic (`mst_service.py`):**
```python
import networkx as nx

def build_graph(nodes, edges) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from([n["id"] for n in nodes])
    for e in edges:
        if e["constraint_type"] != "forbidden":
            G.add_edge(e["node_a_id"], e["node_b_id"], weight=e["cost"], edge_id=e["id"])
    return G

def apply_mandatory_edges(G, mandatory_edges) -> tuple[nx.Graph, list]:
    # Force-include mandatory edges in result; remove them from graph before MST
    G_reduced = G.copy()
    forced = []
    for e in mandatory_edges:
        G_reduced.remove_edge(e["node_a_id"], e["node_b_id"])
        forced.append(e)
    return G_reduced, forced

def calculate_mst(nodes, edges) -> dict:
    mandatory = [e for e in edges if e["constraint_type"] == "mandatory"]
    G = build_graph(nodes, edges)
    G_reduced, forced = apply_mandatory_edges(G, mandatory)

    if not nx.is_connected(G):
        # Report disconnected nodes in error
        components = list(nx.connected_components(G))
        raise ValueError(f"DISCONNECTED_GRAPH: {components}")

    mst_edges = list(nx.minimum_spanning_edges(G_reduced, algorithm="kruskal", data=True))
    all_edges = forced + [{"edge_id": d["edge_id"], "weight": d["weight"]} for _, _, d in mst_edges]
    total_cost = sum(e.get("cost", e.get("weight", 0)) for e in all_edges)
    return {"mst_edges": all_edges, "total_cost": total_cost, "algorithm": "kruskal"}
```

---

## 6. Environment Variables

### Frontend (.env)
```
VITE_API_BASE_URL=https://api.netplan.app/api/v1
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key>
```

### Backend (.env)
```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service role key>
ALLOWED_ORIGINS=https://netplan.vercel.app
```

> **Never commit these files.** Both repos must include `.env` in `.gitignore`. Provide `.env.example` files.

---

## 7. Deployment

| Layer | Platform | Notes |
|-------|----------|-------|
| Frontend | Vercel (free) | Auto-deploy from `main` branch |
| Backend | Render (free) | Web service, Python, `uvicorn app.main:app` |
| Database | Supabase (free) | Hosted PostgreSQL |

**Render start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`  
**Vercel build command:** `npm run build` / output dir: `dist`

---

## 8. Security Checklist

- [ ] CORS on backend: `allow_origins=[ALLOWED_ORIGINS]`, not `*`
- [ ] JWT validated on every protected endpoint via FastAPI dependency
- [ ] All DB queries scoped by `organization_id` from decoded JWT
- [ ] Supabase RLS enabled on all tables as defense-in-depth
- [ ] File upload: validate MIME type server-side (not just extension)
- [ ] Excel import: max row count enforced (e.g., 10,000 rows)
- [ ] Rate limiting: apply to `/mst/calculate` (expensive endpoint)
- [ ] No secrets in frontend bundle
