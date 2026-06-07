# Proposal: Master Plan — NetPlan Pendiente Completo

## Intent

Organizar TODO el trabajo pendiente de NetPlan en una secuencia de cambios SDD accionables. El proyecto tiene backend al ~40%, frontend al 0%, DB sin aplicar, y código sin commiteo. Necesitamos un roadmap que priorice desbloqueo de working tree → backend core → frontend → deploy.

## Scope

### In Scope
- **Roadmap completo**: T-01-03 a T-03-04 del `tasks.md`
- **Rescue**: código backend no commiteado (nodes, edges, excel_service, main.py, schema.sql)
- **Infraestructura**: DB schema aplicar, requirements.txt limpiar, pytest bootstrap, deploy

### Out of Scope
- Features post-MVP (multi-idioma, SSO, graph visualizer)
- Optimizaciones de performance para >10k nodos
- Monorepo CI/CD (GitHub Actions)

## Capabilities

### New Capabilities
- `project-management`: Roadmap como conjunto de cambios SDD encadenados
- `code-rescue`: Working tree rescue + commit atómico de código existente
- `db-setup`: Aplicar schema Supabase + seed org default

### Modified Capabilities
- None (proyecto nuevo sin specs existentes)

## Approach

Organizar como **6 cambios SDD encadenados**, ejecutados secuencialmente. Cada cambio tiene su propio ciclo propose → spec → design → tasks → apply → verify → archive.

| # | Change | Depende de | Esfuerzo |
|---|--------|-----------|----------|
| 1 | **rescue-working-tree**: commit código no commiteado + limpiar requirements | — | S |
| 2 | **supabase-db-setup**: aplicar schema SQL + org default + Auth config | — | S |
| 3 | **pytest-bootstrap**: crear tests/, conftest.py, pytest.ini | #1 | S |
| 4 | **mst-calculation-endpoint** (T-01-05): MST service + router + tests | #1, #2, #3 | M |
| 5 | **backend-export** (T-01-06): Excel/PDF export + router | #4 | M |
| 6 | **frontend-complete** (T-02-01 a T-02-08): auth, pages, map, planner, export | #2, #4, #5 | XL |
| 7 | **deploy-integration** (T-03-01 a T-03-04): E2E test, error audit, deploy | #6 | M |
| 8 | **projects-crud-fixes**: fix `name` min_length + PATCH nulls + tests | — | S |

## Affected Areas

| Area | Impact | Descripción |
|------|--------|-------------|
| `backend/app/` | Modify | Todos los cambios #1, #4, #5 |
| `frontend/src/` | New | Cambio #6 (todo el frontend) |
| `supabase-schema.sql` | Apply | Cambio #2 |
| `backend/requirements.txt` | Modify | Cambio #1 (cleanup) |
| `backend/tests/` | New | Cambios #3, #4, #5 |
| `openspec/specs/` | New | Se crea con cada cambio |

## Risks

| Riesgo | Prob. | Mitigación |
|--------|-------|------------|
| Código sin commiteo se pierde | Baja | Rescue es el primer cambio |
| Schema SQL conflictos con Supabase actual | Baja | Schema nunca aplicado antes |
| Frontend scope muy grande (XL) | Media | Dividir #6 en 3 PRs: auth+pages → map+forms → planner+export |
| Sin tests, bugs no detectados | Alta | pytest bootstrap es cambio #3, antes de lógica core |
| MST algoritmo incorrecto | Media | TDD estricto sobre core puro sin IO |

## Rollback Plan

Cada cambio es independiente y reversible:
- **Rescue**: `git revert <commit>` — working tree vuelve a estado pre-rescue
- **DB**: Dropear schema via Supabase SQL editor
- **Backend/frontend**: `git revert` del cambio correspondiente
- **Full revert**: Restaurar commit `02ca3e7` (initial) y re-aplicar solo projects CRUD

## Dependencies

- Supabase project ya creado (link en `.env`)
- FastAPI skeleton + Projects CRUD ✅ commiteados
- Vite + Tailwind scaffold ✅

## Success Criteria

- [ ] Todos los archivos sin commiteo están rescatados en `main`
- [ ] `pip install -r requirements.txt` funciona sin deps AI/Azure
- [ ] Schema SQL aplicado a Supabase + RLS activo + org default existente
- [ ] `pytest -x` corre <2s con todos los tests verdes
- [ ] Backend: Projects + Nodes + Edges + MST + Export routers funcionales
- [ ] Frontend: auth, map, planner, export operativos en Vercel
- [ ] Deploy: `healthz` ok, login/create/MST/export flow completo
