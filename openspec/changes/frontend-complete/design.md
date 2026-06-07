# Design: Frontend Complete

## Technical Approach

Build the entire NetPlan frontend on the existing Vite + React 19 + Tailwind 4 scaffold. Follow the architecture from `design.md §4`: React Router v7 for routing, raw Leaflet via `useEffect` + `useRef` for the map, React Context + `useReducer` for project state, Axios for all API calls, and Supabase JS **only** for auth (`signIn`, `signOut`, `onAuthStateChange`).

## Architecture Decisions

### Decision: Raw Leaflet over react-leaflet

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Raw Leaflet + useRef | Full lifecycle control, canvas export works | ✅ **Chosen** — established in `design.md §4` |
| react-leaflet v5 | Cleaner JSX, but re-render issues with canvas export | ❌ Already installed but unused |

### Decision: Context + useReducer for state

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Context + useReducer | Predictable transitions, single project scope | ✅ **Chosen** — no cross-route state needed |
| Zustand | Lightweight, less boilerplate | ❌ Added dep, overkill for this scope |
| Redux | Heavy, not warranted | ❌ |

### Decision: Map canvas export via leaflet-image

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `leaflet-image` npm | Purpose-built, uses Leaflet public API | ✅ **Chosen** (1.1KB gzipped) |
| Private API (`._renderer._canvas`) | Fragile, breaks on Leaflet upgrades | ❌ |
| `html-to-image` | Works but captures UI overlays too | ❌ Unnecessary noise |

### Decision: BrowserRouter over createBrowserRouter

| Option | Tradeoff | Decision |
|--------|----------|----------|
| BrowserRouter | Simpler, matches Vite dev server | ✅ **Chosen** |
| createBrowserRouter (RRv7 data router) | Loaders/actions, but all data is manual via useReducer | ❌ Adds complexity, no benefit |

## Data Flow

```
User → Page → useProjects (reducer dispatch) → api.js (Axios + JWT) → Backend → Supabase
                      │
                      ├──→ MapView ←─ nodes, edges, mstEdgeIds (via props)
                      ├──→ MSTResults ←─ mstResult (from reducer state)
                      └──→ ExportButtons ←─ mstResult (from reducer state)
```

**Auth flow:**
```
Supabase onAuthStateChange → useAuth context → ProtectedRoute redirect
                            ↓
              api.js request interceptor: attach Bearer token
              api.js response interceptor: 401 → signOut → redirect /login
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/main.jsx` | Modify | Wrap with AuthProvider + BrowserRouter |
| `frontend/src/App.jsx` | Rewrite | Route definitions under Layout |
| `frontend/src/App.css` | Delete | Vite boilerplate — Tailwind replaces |
| `frontend/index.html` | Modify | Set `<title>` to "NetPlan" |
| `frontend/src/services/supabaseClient.js` | Create | Supabase JS client init (auth only) |
| `frontend/src/services/api.js` | Create | Axios instance + JWT interceptor |
| `frontend/src/hooks/useAuth.jsx` | Create | Auth context + provider |
| `frontend/src/hooks/useProjects.jsx` | Create | Project state (useReducer + API calls) |
| `frontend/src/pages/LoginPage.jsx` | Create | Email/password login form |
| `frontend/src/pages/SignupPage.jsx` | Create | Signup form with password confirmation |
| `frontend/src/pages/ProjectsPage.jsx` | Create | Project list + create modal |
| `frontend/src/pages/ProjectDetailPage.jsx` | Create | Planner: map + forms + results |
| `frontend/src/components/Layout.jsx` | Create | App shell: Navbar + Outlet |
| `frontend/src/components/Navbar.jsx` | Create | Top bar with logo + logout |
| `frontend/src/components/ProtectedRoute.jsx` | Create | Auth guard, redirects to `/login` |
| `frontend/src/components/ProjectCard.jsx` | Create | Card with name, dates, delete action |
| `frontend/src/components/MapView.jsx` | Create | Leaflet map wrapper (useRef + useEffect) |
| `frontend/src/components/NodeMarkers.jsx` | Create | CircleMarker layer (color by type) |
| `frontend/src/components/EdgeLines.jsx` | Create | Polyline layer (color by constraint, MST highlight) |
| `frontend/src/components/MSTResults.jsx` | Create | Collapsible sidebar: total cost, edge list |
| `frontend/src/components/ExportButtons.jsx` | Create | Excel download + PDF export with map capture |
| `frontend/src/utils/errorMap.js` | Create | API error code → Spanish message mapping |

## Interfaces / Contracts

### Project State (useReducer)

```js
const initialState = {
  project: null,         // { id, name, description, created_at }
  nodes: [],             // [{ id, name, type, lat, lng, project_id }]
  edges: [],             // [{ id, node_a_id, node_b_id, cost, constraint_type }]
  mstResult: null,       // { total_cost, algorithm, mst_edges: [{edge_id, cost, node_a, node_b}], calculated_at }
  loading: false,
  error: null,
}

// Action types:
// LOAD_PROJECT | ADD_NODE | UPDATE_NODE | DELETE_NODE
// ADD_EDGE | DELETE_EDGE | UPDATE_EDGE_CONSTRAINT
// CALCULATE_MST | SET_LOADING | SET_ERROR | CLEAR_ERROR
```

### Error Mapping

```js
const ERROR_MAP = {
  PROJECT_NOT_FOUND:  'Proyecto no encontrado',
  FREE_TIER_LIMIT:    'Alcanzaste el límite de proyectos gratuitos. Actualizá tu plan.',
  INSUFFICIENT_NODES: 'Se requieren al menos 2 nodos para calcular el MST',
  DISCONNECTED_GRAPH: null,  // use backend's detail field (already Spanish)
  MANDATORY_CYCLE:    'Las aristas obligatorias forman un ciclo. Revisá las restricciones.',
  RATE_LIMITED:       'Demasiadas solicitudes. Esperá unos segundos y volvé a intentar.',
  INVALID_TOKEN:      'Sesión expirada. Iniciá sesión de nuevo.',
  NETWORK_ERROR:      'Error de conexión. Verificá tu internet e intentá de nuevo.',
}
```

### Map Export Contract

```js
// MapView exposes via useImperativeHandle or ref callback:
getMapBase64() => Promise<string>  // returns data URI without prefix
// Uses leaflet-image: L.map.imageExport(map, callback)
// Where callback receives base64 string of the rendered map canvas
```

## Chained PR Strategy (3 PRs)

| PR | Name | Focus | Est. Lines | Review Risk |
|----|------|-------|-----------|-------------|
| 1 | `feat/auth-pages-shell` | Routing, AuthContext, Login/Signup, Layout, ProjectsPage, ProtectedRoute | ~450 | Low — foundational, no map yet |
| 2 | `feat/map-forms-planner` | MapView, NodeMarkers, EdgeLines, NodeForm, EdgeForm, ConstraintsPanel, useProjects reducer + full ProjectDetailPage plan | ~600 | **Medium** — core interaction |
| 3 | `feat/mst-export-integration` | MST trigger, MSTResults, ExportButtons, errorMap, Polish | ~350 | Low — wires existing pieces |

**Chaining**: PR1 → branch. PR2 → PR1 branch. PR3 → PR2 branch. Each merges into `main` sequentially.

**If PR2 exceeds 600 lines**: split NodeForm + EdgeForm + ConstraintsPanel into a standalone PR 2b. This keeps every PR under the 400-line review budget.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Manual | All auth flows (login, signup, logout, session restore) | Browser smoke test per spec |
| Manual | Map render, markers, edge lines, MST highlight | Visual inspection |
| Manual | Excel/PDF download | File opens correctly |
| E2E | T-03-01 full flow | Manual acceptance test |

No automated FE tests in this change — scope is build-out. Add in a follow-up.

## Rollout

No migration. All new files. Rollback: `git revert` the merged PR(s). For partial rollback, revert individual PRs in reverse order (PR3 → PR2 → PR1).

## Open Questions

- [ ] Does Vercel need a `vercel.json` with `rewrites: [{"source": "/(.*)", "destination": "/index.html"}]` for SPA client-side routing? Common issue: refresh on `/projects/xxx` returns 404 without it.
- [ ] Confirm leaflet-image is compatible with Leaflet 1.9.4. If not, fallback to manual canvas compositing via `html-to-image`.
