# Tasks: Frontend Complete

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,400 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 → PR2 → PR3 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

```
Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High
```

Three sequential PRs, each merges to `main`. 

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Auth + Layout + Projects CRUD | PR 1 | ~450 lines, base `main` → `main` |
| 2 | Map + Nodes/Edges + MST Planner | PR 2 | ~600 lines, base `main` → `main` |
| 3 | Export + Polish | PR 3 | ~350 lines, base `main` → `main` |

---

## PR 1: Auth + Layout + Projects CRUD

- [x] **T-01-01** — Create `supabaseClient.js`, `api.js`, `useAuth.jsx` (auth context + provider), `useProjects.jsx` (reducer + API), `errorMap.js`
- [x] **T-01-02** — Rewrite `main.jsx` (AuthProvider + BrowserRouter), rewrite `App.jsx` (routes: `/login`, `/signup`, `/projects`, `/projects/:id`), add `ProtectedRoute.jsx`
- [x] **T-01-03** — Create `LoginPage.jsx` (email/password, error messages in Spanish, redirect on success)
- [x] **T-01-04** — Create `SignupPage.jsx` (email + password + confirm, "Revisá tu email" success, password mismatch validation)
- [x] **T-01-05** — Create `Layout.jsx` + `Navbar.jsx` (app shell, logo, logout, back arrow on detail pages, responsive)
- [x] **T-01-06** — Create `ProjectsPage.jsx` (list from API, empty state, project cards) + `ProjectCard.jsx` (name, dates, clickable)
- [x] **T-01-07** — Create project creation modal (name field, validation 3-100 chars, free-tier 403 handling with upgrade prompt)

**Verify**: `npm run dev` → Login/Signup redirection flow works, Projects list loads project cards from API, free-tier error shows upgrade link.

---

## PR 2: Map + Nodes/Edges + MST Planner

- [x] **T-02-01** — Create `MapView.jsx` (Leaflet via useRef + useEffect, OpenStreetMap tiles, auto-fit bounds, `getMapBase64` ref export, `leaflet-image` dep)
- [x] **T-02-02** — Create `NodeMarkers.jsx` (draggable markers, popup with name/type, drag updates coords, "Guardar" button → PATCH)
- [x] **T-02-03** — Create `EdgeLines.jsx` (Leaflet polylines, color by constraint: green/blue/red, MST highlight thicker/cyan)
- [x] **T-02-04** — Create `ProjectDetailPage.jsx` (loads project + nodes + edges + latest MST, wires MapView + NodeMarkers + EdgeLines)
- [x] **T-02-05** — Add node/edge controls to detail page (add node form, add edge with node pair selector, delete edge button)
- [x] **T-02-06** — Create `MSTResults.jsx` (trigger "Calcular MST" button, loading spinner, total cost display, collapsible edge list, disconnected graph error with unreachable nodes)

**Verify**: Project detail page loads map with markers and edge lines. Drag marker shows save option. MST calculates and highlights edges. Disconnected graph shows Spanish error.

---

## PR 3: Export + Polish

- [x] **T-03-01** — Create `ExportButtons.jsx` ("Descargar Excel" via GET blob download, "Descargar PDF" via POST with map base64, loading indicators, error handling)
- [x] **T-03-02** — Wire errorMap.js into Axios response interceptor (map API error codes to Spanish messages, silent 401 redirect, generic fallback)
- [x] **T-03-03** — Polish: loading states on all buttons/spinners, responsive layout check, index.html `<title>`, delete App.css, delete Vite boilerplate assets
- [ ] **T-03-04** — Full manual acceptance test against all spec scenarios (auth, projects, map, MST, export)
  - Estado: **pendiente de ejecución manual en navegador** (no ejecutable íntegramente desde CLI).
  - Evidencia CLI previa completada: `frontend npm run build` ✅.
  - Checklist manual a ejecutar en navegador real:
    1. Auth: login válido redirige a `/projects`; credenciales inválidas muestran error en español; logout vuelve a `/login`; sesión persistida refresca ruta protegida.
    2. Projects: listado renderiza proyectos, empty state correcto, creación válida agrega proyecto, free-tier (403 `FREE_TIER_LIMIT`) muestra mensaje + CTA de upgrade.
    3. Map/Nodes: mapa Leaflet renderiza y no se re-inicializa en re-render; marcadores muestran popup; drag de marcador actualiza lat/lng visible y botón **Guardar** persiste posición vía `PUT /projects/{project_id}/nodes/{node_id}`.
    4. Edges/MST: crear/eliminar aristas funciona; `Calcular MST` muestra loading, resultado y highlight; errores `INSUFFICIENT_NODES` / `DISCONNECTED_GRAPH` se ven en español.
    5. Export: `Descargar Excel` y `Descargar PDF` descargan archivos válidos; PDF incluye mapa capturado (`map_image_base64`) con y sin MST.

**Verify**: Excel/PDF downloads work end-to-end. All errors show Spanish messages. 401 silently redirects to login. All spec scenarios pass manual test.
