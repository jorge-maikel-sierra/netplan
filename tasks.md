# Tasks — Sistema SaaS de Planificación de Infraestructura de Red

> **Format:** Each task has an ID, layer (FE/BE/DB/INFRA), estimated effort (S/M/L), and explicit acceptance test.  
> **Order:** Follow top to bottom. DB and INFRA tasks must complete before dependent FE/BE tasks.

---

## Phase 0 — Project Bootstrap

### T-00-01 · Initialize monorepo structure
**Layer:** INFRA | **Effort:** S

1. Create root directory `netplan/` with two sub-directories: `frontend/` and `backend/`.
2. Initialize `frontend/` with Vite + React:
   ```bash
   npm create vite@latest frontend -- --template react
   cd frontend && npm install
   ```
3. Install frontend dependencies:
   ```bash
   npm install tailwindcss @tailwindcss/vite leaflet react-leaflet axios @supabase/supabase-js react-router-dom
   npm install -D prettier eslint eslint-plugin-react
   ```
4. Configure Tailwind in `vite.config.js` (plugin-based, Tailwind v4 style).
5. Initialize `backend/` as a Python project:
   ```bash
   mkdir backend && cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install fastapi uvicorn[standard] networkx openpyxl supabase pydantic-settings python-multipart python-jose reportlab
   pip freeze > requirements.txt
   ```
6. Add `.gitignore` at root covering `node_modules/`, `.venv/`, `.env`, `dist/`, `__pycache__/`.
7. Add `.env.example` files in both `frontend/` and `backend/`.

**Acceptance test:** `cd frontend && npm run dev` starts dev server. `cd backend && uvicorn app.main:app` starts API with no errors.

---

### T-00-02 · Supabase project setup
**Layer:** DB | **Effort:** S

1. Create a new Supabase project in the dashboard.
2. Run the full SQL schema from `design.md §2` in the Supabase SQL editor in this exact order:
   - `organizations`
   - `profiles`
   - `projects`
   - `nodes`
   - `edges`
   - `mst_results`
3. Apply RLS policy to each table (template in `design.md §2`).
4. Copy `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` into the respective `.env` files.
5. Enable email/password authentication in Supabase Auth dashboard.

**Acceptance test:** From the Supabase dashboard, insert one row into `organizations` and verify it appears. Attempt to query from a client with `anon` key without a valid JWT and confirm it returns 0 rows (RLS working).

---

## Phase 1 — Backend Core

### T-01-01 · FastAPI app skeleton with CORS and JWT dependency
**Layer:** BE | **Effort:** S

1. Create `app/main.py`:
   ```python
   from fastapi import FastAPI
   from fastapi.middleware.cors import CORSMiddleware
   from app.config import settings

   app = FastAPI(title="NetPlan API", version="1.0.0")
   app.add_middleware(
       CORSMiddleware,
       allow_origins=[settings.allowed_origins],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```
2. Create `app/config.py` using `pydantic-settings`:
   - Fields: `supabase_url`, `supabase_service_role_key`, `allowed_origins`.
   - Reads from `.env` automatically.
3. Create `app/dependencies.py` with `get_current_user(token: str)`:
   - Validates Supabase JWT using `python-jose`.
   - Extracts `sub` (user UUID) and fetches `organization_id` from `profiles` table.
   - Returns `{"user_id": str, "org_id": str}`.
   - Raises `HTTPException(401)` on invalid/expired token.
4. Create `app/db/supabase_client.py`:
   - Single `supabase` client instance using service role key.

**Acceptance test:** `GET /healthz` returns `{"status": "ok"}`. `GET /projects` without a token returns 401.

---

### T-01-02 · Projects CRUD router
**Layer:** BE | **Effort:** M

1. Create `app/schemas/project.py` with Pydantic v2 models: `ProjectCreate`, `ProjectUpdate`, `ProjectResponse`.
2. Create `app/routers/projects.py` implementing all 5 endpoints from `design.md §3.1`.
3. All queries must filter by `organization_id` from the resolved user context.
4. `GET /projects/{id}` must JOIN and return `nodes`, `edges`, and `last_result` in a single response.
5. Mount router in `main.py` at `/api/v1`.

**Acceptance test:** Create a project via `POST /api/v1/projects`. Verify it appears in `GET /api/v1/projects`. Attempt to access it from a different tenant's token and confirm 404 (not 403, to avoid leaking existence).

---

### T-01-03 · Nodes router with Excel import
**Layer:** BE | **Effort:** M

1. Create `app/schemas/node.py`.
2. Create `app/routers/nodes.py` with single-node CRUD endpoints.
3. Create `app/services/excel_service.py`:
   - `parse_nodes_xlsx(file_bytes) -> tuple[list[dict], list[dict]]`: returns `(valid_rows, errors)`.
   - Required columns: `nombre`, `latitud`, `longitud` (cost column is per-edge, not per-node).
   - Validates: column presence, numeric types, lat range [-90, 90], lng range [-180, 180].
   - Max rows: 10,000. If exceeded, reject with structured error.
4. `POST /projects/{id}/nodes/import` uses `excel_service.parse_nodes_xlsx`, inserts valid rows, returns import summary.

**Acceptance test:** Upload a valid `.xlsx` with 5 rows — confirm 5 nodes created. Upload one with an invalid lat value — confirm error returned with row number and field name. Upload a `.csv` file — confirm 422 with "unsupported file type".

---

### T-01-04 · Edges router with constraint support
**Layer:** BE | **Effort:** S

1. Create `app/schemas/edge.py`.
2. Create `app/routers/edges.py` with endpoints from `design.md §3.3`.
3. Upsert logic: if an edge between `node_a_id` and `node_b_id` already exists in the project, update it instead of creating duplicate (DB `UNIQUE` constraint guides this).
4. `PATCH /edges/{id}/constraint` only updates the `constraint_type` field.

**Acceptance test:** Add an edge between two nodes. Attempt to add the same edge again — confirm it updates rather than errors. Set constraint to `"forbidden"` — confirm value persists in DB.

---

### T-01-05 · MST calculation endpoint
**Layer:** BE | **Effort:** M

1. Create `app/services/mst_service.py` as designed in `design.md §5`.
2. Create `app/routers/mst.py`:
   - `POST /projects/{id}/mst/calculate`:
     - Fetch all nodes and non-forbidden-only edges from DB.
     - Call `mst_service.calculate_mst(nodes, edges)`.
     - On success: persist result to `mst_results` table; return result.
     - On `DISCONNECTED_GRAPH` ValueError: return 422 with structured error (list disconnected nodes).
   - `GET /projects/{id}/mst/latest`: return the most recent `mst_results` row.
3. Validate that the project has at least 2 nodes before running. Return 422 if not.

**Acceptance test:** Create 3 nodes and 3 edges forming a triangle. Run calculate — confirm only 2 edges returned. Mark one edge as `forbidden`, re-run — confirm the remaining 2 edges are used. Remove all edges and run — confirm 422 with appropriate error message.

---

### T-01-06 · Export endpoints
**Layer:** BE | **Effort:** M

1. Create `app/services/excel_service.py` (extend existing):
   - `generate_mst_xlsx(project, nodes, mst_edges) -> bytes`: returns `.xlsx` bytes with two sheets.
2. Create `app/services/pdf_service.py`:
   - `generate_mst_pdf(project, nodes, mst_edges, map_image_bytes) -> bytes` using `reportlab`.
   - Layout: title, map image (if provided), summary table, edge list table.
3. Create `app/routers/export.py` with both endpoints from `design.md §3.5`.
4. Both endpoints return the file as a streaming response with correct `Content-Disposition` header.

**Acceptance test:** Call Excel export — download is valid `.xlsx` openable in LibreOffice. Call PDF export with a base64 map image — PDF contains two pages max, map renders visibly.

---

## Phase 2 — Frontend Core

### T-02-01 · Router and auth shell
**Layer:** FE | **Effort:** S

1. Set up React Router v6 in `App.jsx`:
   - `/` → `HomePage`
   - `/login` → `LoginPage`
   - `/projects` → `ProjectsPage` (protected)
   - `/projects/:id` → `PlannerPage` (protected)
2. Create `src/hooks/useAuth.js`:
   - Wraps Supabase `onAuthStateChange`.
   - Exposes `{ user, session, signIn, signOut, loading }`.
3. Create a `ProtectedRoute` component that redirects to `/login` if `!user`.
4. Create `src/services/supabaseClient.js` using `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
5. Create `src/services/api.js` (Axios instance):
   - Base URL from `VITE_API_BASE_URL`.
   - Request interceptor: attaches `Authorization: Bearer <session.access_token>`.
   - Response interceptor: on 401, call `supabase.auth.signOut()` and redirect to `/login`.

**Acceptance test:** Navigate to `/projects` without being logged in — redirect to `/login`. Log in with a valid Supabase test account — redirect to `/projects`. Sign out — redirect to `/login`.

---

### T-02-02 · Home page and login page
**Layer:** FE | **Effort:** S

1. `HomePage.jsx`: static page with project description, feature highlights, and a CTA button "Iniciar sesión / Probar gratis" linking to `/login`.
2. `LoginPage.jsx`: email/password form using Supabase Auth.
   - On success: redirect to `/projects`.
   - Show error message for invalid credentials.
   - Use Tailwind for styling; no third-party auth UI library.

**Acceptance test:** Home page renders without console errors. Login with wrong password shows error. Login with correct credentials redirects.

---

### T-02-03 · Projects list page
**Layer:** FE | **Effort:** S

1. `ProjectsPage.jsx`:
   - On mount: fetch `GET /api/v1/projects`.
   - Display project cards: name, description, date, node count.
   - "Nuevo proyecto" button: opens modal with `ProjectCreate` form (name + description).
   - Clicking a project card navigates to `/projects/:id`.
   - Delete button on each card with confirmation prompt.
2. Handle empty state ("No tienes proyectos aún. Crea uno para comenzar.").
3. Handle loading and error states.

**Acceptance test:** Create a project from the modal — appears in list. Delete it — disappears. Navigate to a project — loads `PlannerPage`.

---

### T-02-04 · Map view component
**Layer:** FE | **Effort:** M

1. Create `src/components/MapView.jsx`:
   - Initializes Leaflet map in a `useEffect` with `useRef` to prevent re-init.
   - Default center: Colombia (4.5709, -74.2973), zoom 6.
   - Tile layer: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`.
   - Accepts props: `nodes: []`, `allEdges: []`, `mstEdgeIds: []`.
   - Renders node markers (color by type: city=blue, tower=orange, datacenter=red).
   - Renders all edges as faded gray polylines.
   - Renders MST edges as green polylines (thicker stroke).
   - MST edge polylines have a tooltip showing cost.
   - On `nodes` change: `map.fitBounds()` to include all markers.
2. Export a `getMapImageBase64()` function using Leaflet's canvas export (via `leaflet-image` or manual canvas approach).

**Acceptance test:** Load 3 nodes at Colombian coordinates — markers appear. After MST calculation, green lines appear between MST pairs. Hover over a green line — tooltip shows cost.

---

### T-02-05 · Node form and import
**Layer:** FE | **Effort:** M

1. `NodeForm.jsx`: form with fields: name, type (select), lat, lng.
   - Client-side validation (lat range, lng range, required fields).
   - On submit: `POST /api/v1/projects/:id/nodes`.
   - On success: notify parent to refresh node list.
2. `ImportButton.jsx`:
   - File picker accepting `.xlsx` only.
   - On file select: `POST /api/v1/projects/:id/nodes/import`.
   - Show a preview table of parsed rows before confirming.
   - After confirmation, show import summary (imported count, errors with row numbers).

**Acceptance test:** Submit form with lat=999 — show inline error. Submit valid node — appears on map without page reload. Import `.xlsx` — preview table shows before confirm. Import with invalid row — error shown per row.

---

### T-02-06 · Edge form and constraints panel
**Layer:** FE | **Effort:** M

1. `EdgeForm.jsx`:
   - Two dropdowns for selecting node A and node B (populated from project nodes).
   - Cost input (numeric).
   - Constraint type selector: Normal / Mandatory / Forbidden.
   - On submit: `POST /api/v1/projects/:id/edges`.
2. `ConstraintsPanel.jsx`:
   - Lists all edges that are `mandatory` or `forbidden`.
   - Each row shows: node A name → node B name, cost, constraint badge.
   - Remove button calls `DELETE /api/v1/projects/:id/edges/:edge_id`.

**Acceptance test:** Add a mandatory edge — appears in constraints panel with correct badge. Remove it — disappears from panel. Add a forbidden edge and run MST — it is excluded from result.

---

### T-02-07 · MST trigger and results summary
**Layer:** FE | **Effort:** M

1. "Calcular MST" button in `PlannerPage.jsx`:
   - Calls `POST /api/v1/projects/:id/mst/calculate`.
   - Shows loading state on button while request is in flight.
   - On success: updates `mstEdgeIds` in map state and shows `ResultsSummary`.
   - On error: shows error toast with the `detail` field from the API error response.
2. `ResultsSummary.jsx`:
   - Shows: total cost (formatted as currency), algorithm used, number of MST edges, number of nodes connected, timestamp.
   - Expandable list of all MST edges.
   - Positioned as a collapsible sidebar panel.

**Acceptance test:** Click calculate with insufficient nodes — show toast "Se necesitan al menos 2 nodos". Successful calculation — summary panel appears with correct total. Disconnected graph error — toast shows which nodes are unreachable.

---

### T-02-08 · Export buttons
**Layer:** FE | **Effort:** S

1. `ExportButton.jsx`:
   - Two buttons: "Exportar Excel" and "Exportar PDF".
   - Both disabled until an MST result exists.
   - Excel: `GET /api/v1/projects/:id/export/excel` → triggers file download.
   - PDF: captures map canvas (`getMapImageBase64()`), then `POST /api/v1/projects/:id/export/pdf` with base64 body → triggers file download.
   - Show loading spinner during export.

**Acceptance test:** Click Excel export — `.xlsx` downloads with correct content. Click PDF export — `.pdf` downloads and opens in browser. Both buttons disabled before calculation.

---

## Phase 3 — Integration & Polish

### T-03-01 · End-to-end integration test (manual)
**Layer:** INFRA | **Effort:** M

Run this full scenario against the staging environment:
1. Register a new user → verify in Supabase Auth dashboard.
2. Create a project.
3. Add 5 nodes manually.
4. Import 3 more nodes via Excel.
5. Add 3 edges (1 mandatory, 1 forbidden, 1 normal).
6. Run MST → verify result on map and summary panel.
7. Export to Excel → open file and verify node/edge sheets.
8. Export to PDF → verify map image and summary table render.
9. Save project → log out → log in → reload project → verify state restored.
10. Delete project → verify it no longer appears in list.

All 10 steps must pass without console errors or unexpected API 5xx responses.

---

### T-03-02 · Error handling audit
**Layer:** FE + BE | **Effort:** S

1. Every API error response must follow the `{error, code, detail}` schema defined in `design.md §3`.
2. Frontend must never show a raw API error object to the user — always map to a readable Spanish message.
3. Network errors (offline, timeout) must show a toast "Error de conexión. Revisa tu red e intenta de nuevo."
4. 500 errors must show "Error del servidor. Por favor intenta más tarde."

---

### T-03-03 · Free tier enforcement
**Layer:** BE | **Effort:** S

1. In `POST /projects` handler: check count of existing projects for the organization.
2. If count ≥ 3 and the organization is on the free plan: return 403 with error `FREE_TIER_LIMIT`.
3. Add a `plan` field to `organizations` table: `TEXT DEFAULT 'free' CHECK (plan IN ('free', 'premium'))`.
4. Frontend must show a clear upgrade prompt when this error is received.

---

### T-03-04 · Deployment configuration
**Layer:** INFRA | **Effort:** S

**Vercel (Frontend):**
1. Connect `frontend/` directory to Vercel project.
2. Set environment variables in Vercel dashboard: `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
3. Set build command: `npm run build`. Output directory: `dist`.

**Render (Backend):**
1. Connect `backend/` directory to Render web service.
2. Set environment variables: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ALLOWED_ORIGINS`.
3. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Set `ALLOWED_ORIGINS` to the Vercel production URL.

**Acceptance test:** `curl https://api.netplan.app/healthz` returns 200. Frontend at Vercel URL loads and can log in successfully.
