# Requirements — Sistema SaaS de Planificación de Infraestructura de Red

## 1. Overview

**Product name:** NetPlan (working title)  
**Type:** SaaS web application — multi-tenant, freemium model  
**Goal:** Allow engineering teams and companies to plan, optimize, and save network infrastructure layouts using Minimum Spanning Tree (MST) algorithms, visualized on an interactive map.

---

## 2. User Stories

### US-01 · Ingresar nodos manualmente
**As** a network engineer,  
**I want** to enter network nodes (cities, towers, data centers) with a name, coordinates, and connection cost,  
**so that** I can plan my infrastructure topology without needing to prepare a file.

**Acceptance criteria:**
- Form accepts: name (string, max 80 chars), latitude, longitude (decimal degrees, validated range), connection cost (positive number).
- At minimum 2 nodes required before triggering MST calculation.
- Nodes are immediately rendered as markers on the Leaflet map after entry.
- Input is validated client-side before submission; errors shown inline.

---

### US-02 · Importar nodos desde Excel
**As** a user with existing network data,  
**I want** to upload an `.xlsx` file,  
**so that** I can bulk-import nodes and edges without manual entry.

**Acceptance criteria:**
- Accepted format: `.xlsx` only. Max file size: 5 MB.
- Required columns: `nombre`, `latitud`, `longitud`, `costo` (case-insensitive).
- The backend validates column names and data types; returns a structured error list if invalid rows are found.
- On success: nodes are loaded and rendered on the map.
- The UI shows a preview table of imported rows before final confirmation.

---

### US-03 · Definir restricciones de conexiones
**As** a planner,  
**I want** to mark specific connections as "mandatory" or "forbidden" before running the algorithm,  
**so that** the calculated tree respects real-world constraints (e.g., contractual routes or restricted areas).

**Acceptance criteria:**
- User can select any pair of nodes from a dropdown/map interaction.
- Each pair can be tagged as: `normal` (default), `mandatory`, or `forbidden`.
- Mandatory edges are always included in the MST output regardless of cost.
- Forbidden edges are removed from the graph before Kruskal/Prim runs.
- Restrictions panel shows a list of all tagged connections with ability to remove them.

---

### US-04 · Calcular árbol de expansión mínima
**As** a user with nodes loaded,  
**I want** to trigger MST calculation with a single action,  
**so that** I get the optimal (minimum cost) connected network.

**Acceptance criteria:**
- Backend endpoint `POST /api/v1/mst/calculate` receives node list, edge list, and constraints.
- Algorithm: Kruskal (default). If graph is disconnected after removing forbidden edges, return a descriptive error (not a 500).
- Response includes: list of selected edges (node_a, node_b, cost), total cost, algorithm used.
- Calculation completes in < 3 s for graphs up to 500 nodes / 10,000 edges.
- Results are shown on the map as colored lines connecting the selected nodes.

---

### US-05 · Visualizar resultados en mapa
**As** a user,  
**I want** to see the MST result overlaid on an interactive map,  
**so that** I can understand the topology visually.

**Acceptance criteria:**
- Map uses Leaflet.js with OpenStreetMap tiles (no API key required).
- Nodes: circular markers, color-coded by type (city = blue, tower = orange, data center = red).
- MST edges: polylines in a distinct color (e.g., green) with tooltip showing cost on hover.
- Non-selected edges: shown as faded gray lines.
- Map auto-fits bounds to all nodes after calculation.

---

### US-06 · Ver resumen de resultados
**As** a user,  
**I want** to see a summary panel with total cost, number of connections, and list of nodes,  
**so that** I can validate the result before saving or exporting.

**Acceptance criteria:**
- Summary panel shows: total cost, number of MST edges, number of nodes connected, algorithm used, calculation timestamp.
- Expandable list of all MST edges with per-edge cost.
- Panel is visible alongside the map (sidebar or collapsible drawer).

---

### US-07 · Exportar resultados
**As** a user,  
**I want** to export the MST results as PDF or Excel,  
**so that** I can share them with my team or include them in a report.

**Acceptance criteria:**
- **Excel export:** one sheet "nodes" (name, lat, lng, type), one sheet "MST edges" (node_a, node_b, cost), summary row with total cost.
- **PDF export:** rendered in the backend with the map screenshot (canvas export via Leaflet) + summary table. Max 2 pages.
- Both exports are triggered by a single button and delivered as a file download.
- Export is available only after a successful MST calculation.

---

### US-08 · Autenticación y multi-tenancy
**As** a company user,  
**I want** to log in and have my projects isolated from other companies,  
**so that** my infrastructure data is private.

**Acceptance criteria:**
- Authentication via Supabase Auth (email/password; OAuth optional in v2).
- Each user belongs to one organization (tenant).
- All DB queries are scoped by `organization_id`; users cannot access other tenants' data.
- Session handled via Supabase JWT; token validated on every backend request.
- Row-Level Security (RLS) enabled in Supabase for all tables.

---

### US-09 · Guardar y recuperar proyectos
**As** a returning user,  
**I want** to save my current project and reload it later,  
**so that** I don't have to re-enter data every time.

**Acceptance criteria:**
- "Save project" button persists: project metadata, node list, edge list (with constraints), and last MST result.
- "My projects" page lists all saved projects with name, date, and node count.
- Loading a project restores the full state: nodes on map, constraints panel, last result.
- Project can be renamed or deleted.

---

## 3. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-01 | API response time (calculation) | < 3 s for 500 nodes |
| NFR-02 | API response time (CRUD) | < 500 ms p95 |
| NFR-03 | Frontend bundle size | < 500 KB gzipped |
| NFR-04 | HTTPS enforced | All environments |
| NFR-05 | RLS enforced | All Supabase tables |
| NFR-06 | Input validation | Both client and server |
| NFR-07 | Error responses | Structured JSON `{error, code, detail}` |
| NFR-08 | CORS | Backend allows only frontend origin |
| NFR-09 | Free tier limits | ≤ 3 saved projects per free user |

---

## 4. Out of Scope (v1)

- Real-time collaboration
- OAuth / SSO login
- Mobile native app
- Drag-and-drop node repositioning on map
- Custom map tile providers
- Billing / payment integration (freemium enforced manually in v1)
