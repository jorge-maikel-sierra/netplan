# AGENTS.md — NetPlan SaaS

## Project Overview
Multi-tenant SaaS for network infrastructure planning using MST algorithms.
- **Frontend**: React + Vite + TailwindCSS + Leaflet.js (deployed on Vercel)
- **Backend**: FastAPI (Python) + NetworkX + OpenPyXL + supabase-py (deployed on Render)
- **Database**: Supabase PostgreSQL with Auth + RLS + Storage

## Architecture Rules (CRITICAL)
1. **Frontend ↔ Supabase**: ONLY for authentication (signIn, signOut, session refresh). **No direct DB calls from frontend.**
2. **Frontend ↔ Backend**: REST JSON over HTTPS. Backend owns ALL business logic.
3. **Backend ↔ Supabase**: Uses `supabase-py` with **service role key** (bypasses RLS at library level). Manual tenant scoping via `organization_id` in every query.
4. **RLS**: Enabled on all tables as defense-in-depth, NOT primary enforcement.

## Developer Commands

### Frontend (`frontend/`)
```bash
npm run dev          # Start dev server
npm run build        # Production build (output: dist/)
npm run lint         # ESLint
npm run format       # Prettier
```

### Backend (`backend/`)
```bash
source .venv/bin/activate
uvicorn app.main:app --reload    # Dev server
uvicorn app.main:app --host 0.0.0.0 --port $PORT  # Production (Render)
pip freeze > requirements.txt    # Update deps
```

### Database
```bash
# Run migrations via Supabase SQL editor (see design.md §2)
# RLS policies must be applied to each table after creation
```

## Key Files & Entry Points

| Layer | Entry Point | Purpose |
|-------|-------------|---------|
| Frontend | `frontend/src/main.jsx` | App bootstrap, router, providers |
| Frontend | `frontend/src/App.jsx` | Route definitions |
| Frontend | `frontend/src/services/api.js` | Axios instance + JWT interceptor |
| Frontend | `frontend/src/services/supabaseClient.js` | Supabase JS client (auth ONLY) |
| Backend | `backend/app/main.py` | FastAPI app, CORS, router mounting |
| Backend | `backend/app/config.py` | Pydantic-settings from `.env` |
| Backend | `backend/app/dependencies.py` | JWT validation + tenant resolution |
| Backend | `backend/app/db/supabase_client.py` | Service role supabase-py client |
| Backend | `backend/app/services/mst_service.py` | NetworkX MST algorithm (Kruskal) |

## Database Schema (from design.md §2)
- `organizations` — tenant container
- `profiles` — extends `auth.users`, links to `organization_id`, has `role` (admin/member)
- `projects` — scoped to `organization_id`
- `nodes` — scoped to `project_id`, has `type` (city/tower/datacenter), lat/lng
- `edges` — scoped to `project_id`, has `cost`, `constraint_type` (normal/mandatory/forbidden), unique per project node pair
- `mst_results` — stores calculation history with `edge_ids` array

**All queries MUST filter by `organization_id` from decoded JWT.**

## API Contract (design.md §3)
- Base URL: `https://api.netplan.app/api/v1`
- Auth: `Authorization: Bearer <supabase_jwt>` on protected endpoints
- Error format: `{ "error": "CODE", "code": 422, "detail": "message" }`

### Key Endpoints
| Method | Path | Notes |
|--------|------|-------|
| GET/POST | `/projects` | List/create projects (tenant-scoped) |
| GET/PATCH/DELETE | `/projects/{id}` | Single project with nodes/edges/last_result |
| POST | `/projects/{id}/nodes` | Add node |
| POST | `/projects/{id}/nodes/import` | Bulk import from `.xlsx` (max 10k rows) |
| POST/PATCH/DELETE | `/projects/{id}/edges` | Edge CRUD + constraint upsert |
| POST | `/projects/{id}/mst/calculate` | Runs MST, returns 422 if disconnected |
| GET | `/projects/{id}/mst/latest` | Latest saved result |
| GET | `/projects/{id}/export/excel` | Downloads `.xlsx` |
| POST | `/projects/{id}/export/pdf` | Generates PDF with map image |

## MST Algorithm (backend/app/services/mst_service.py)
- **Algorithm**: Kruskal via NetworkX
- **Mandatory edges**: Force-included, removed from graph before MST
- **Forbidden edges**: Excluded from graph entirely
- **Disconnected graph**: Returns 422 with list of unreachable nodes
- **Validation**: Minimum 2 nodes required

## Environment Variables

### Frontend (`frontend/.env`)
```
VITE_API_BASE_URL=https://api.netplan.app/api/v1
VITE_SUPABASE_URL=https://<project>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon key>
```

### Backend (`backend/.env`)
```
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service role key>
ALLOWED_ORIGINS=https://netplan.vercel.app
```

**Never commit `.env`. Use `.env.example` templates.**

## Frontend Patterns
- **Routing**: React Router v6 (`/`, `/login`, `/projects`, `/projects/:id`)
- **Auth**: `useAuth.js` hook wraps Supabase `onAuthStateChange`
- **API calls**: Axios instance in `services/api.js` with request/response interceptors
  - Request: attaches `Authorization: Bearer <session.access_token>`
  - Response: 401 → signOut + redirect to `/login`
- **State**: React Context + `useReducer` for project state (no Redux)
- **Leaflet**: `MapView.jsx` uses `useRef` + `useEffect` to prevent re-initialization
- **Map export**: `getMapImageBase64()` via canvas export for PDF generation

## Backend Patterns
- **JWT validation**: `dependencies.py::get_current_user()` validates Supabase JWT, extracts `sub`, fetches `organization_id` from `profiles`
- **Tenant scoping**: Every DB query includes `.eq("organization_id", org_id)`
- **Upsert edges**: Uses DB unique constraint `(project_id, node_a_id, node_b_id)` for upsert logic
- **File upload**: Validates MIME type server-side (not just extension)
- **Rate limiting**: Apply to `/mst/calculate` (expensive endpoint)

## Testing & Verification
- No formal test suite yet (greenfield project)
- Manual acceptance tests defined in `tasks.md` for each task
- Key smoke tests:
  - `GET /healthz` returns `{"status": "ok"}`
  - `GET /projects` without token → 401
  - Cross-tenant access → 404 (not 403, to avoid leaking existence)
  - Excel import: invalid lat/lng returns structured error with row/field

## Deployment
| Layer | Platform | Build/Start Command |
|-------|----------|---------------------|
| Frontend | Vercel | `npm run build` / output: `dist` |
| Backend | Render | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Database | Supabase | Hosted PostgreSQL |

- `ALLOWED_ORIGINS` in backend must match Vercel production URL
- Frontend env vars set in Vercel dashboard
- Backend env vars set in Render dashboard

## Skills Available
- `supabase` — Supabase operations (DB, Auth, Edge Functions, Storage, etc.)
- `supabase-postgres-best-practices` — Postgres performance, RLS, indexing, query optimization

## Free Tier Enforcement (tasks.md T-03-03)
- Max 3 projects per organization on free plan
- `organizations.plan` field: `'free' | 'premium'` (default 'free')
- Backend returns 403 `FREE_TIER_LIMIT` on 4th project creation
- Frontend shows upgrade prompt

## Common Gotchas
1. **Don't call Supabase DB from frontend** — all data goes through backend
2. **Service role key bypasses RLS** — manual `organization_id` scoping is mandatory
3. **Leaflet re-initialization** — use `useRef` in `MapView.jsx`
4. **Edge upsert** — unique constraint handles it, don't double-insert
5. **CORS** — backend `allow_origins=[settings.allowed_origins]`, NOT `*`
6. **Error mapping** — frontend must never show raw API error; map to Spanish user messages
7. **PDF export** — requires `map_image_base64` from frontend canvas capture