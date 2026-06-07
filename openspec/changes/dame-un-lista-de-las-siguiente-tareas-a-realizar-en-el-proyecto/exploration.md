# Exploration: Auditoría de Tareas Pendientes — NetPlan

## Executive Summary

El proyecto NetPlan tiene **el backend parcialmente implementado** (proyectos CRUD commitado, nodes/edges routers sin commiteo, MST/export sin empezar) y el **frontend completamente en estado Vite scaffold** — cero código de aplicación. La base de datos tiene el schema SQL listo pero **nunca fue aplicado a Supabase**. Hay ~7 archivos clave sin commiteo, requirements.txt contaminado con ~30 deps de AI/Azure, y test suite inexistente. En resumen: backend al ~40%, frontend al 0%, infraestructura al 10%.

---

## 1. Completed (Implementado y Commiteado)

| Tarea | Estado | Notas |
|-------|--------|-------|
| T-00-01 Monorepo structure | ✅ | `frontend/` + `backend/` con Vite, Tailwind, FastAPI |
| T-00-02 Supabase schema (SQL file) | ✅ | `supabase-schema.sql` listo **pero sin aplicar** |
| T-01-01 FastAPI skeleton (CORS, JWT, config) | ✅ | `main.py`, `config.py`, `dependencies.py`, `db/supabase_client.py` |
| T-01-02 Projects CRUD router | ✅ | 5 endpoints en `projects.py` — archived como completado |
| Schemas (Pydantic v2) | ✅ | `project.py`, `node.py`, `edge.py`, `mst.py`, `export.py` |
| `.env.example` files | ✅ | En `frontend/` y `backend/` |
| Vite + Tailwind config | ✅ | `vite.config.js` con plugin de Tailwind v4 |
| Dependencies installed (JS) | ✅ | `@supabase/supabase-js`, `axios`, `leaflet`, `react-router-dom`, `tailwindcss` |

---

## 2. In Progress (Creado pero Sin Commiteo ni Verificado)

| Archivo | Estado | Commiteado? |
|---------|--------|-------------|
| `backend/app/routers/nodes.py` | CRUD completo (4 endpoints + import) | ❌ Sin commiteo |
| `backend/app/routers/edges.py` | CRUD completo (3 endpoints + upsert + constraint) | ❌ Sin commiteo |
| `backend/app/services/excel_service.py` | `parse_nodes_xlsx()` con validación | ❌ Sin commiteo |
| `backend/app/main.py` | Con mounts de nodes/edges routers | ❌ Modificado sin commiteo |
| `supabase-schema.sql` | Schema completo con RLS + trigger | ❌ Sin commiteo |
| `.atl/skill-registry.md` | Registro de skills del proyecto | ❌ Sin commiteo |
| `openspec/changes/` | Artifacts SDD de cambios activos | ❌ Sin commiteo |

### Cambios SDD Activos (openspec)

| Change | Estado | Próximo Paso |
|--------|--------|-------------|
| `projects-crud` (archive/) | ✅ Archivado con warnings (12/14 tasks OK) | — |
| `backend-nodes-edges` | ❌ **FAIL** en verify. Código existe pero sin commiteo. Propuesta OK. | Rescatar y re-verificar |
| `mst-calculation-endpoint` | ⏸️ Propuesta creada. Sin spec/design/tasks/apply. | Continuar pipeline SDD |

---

## 3. Pending (Especificado pero Sin Empezar)

### Backend — T-01-05 y T-01-06

| Tarea | Archivos Necesarios | Estado |
|-------|--------------------|--------|
| T-01-05 MST Service | `services/mst_service.py` (~150 LOC) | ❌ No existe |
| T-01-05 MST Router | `routers/mst.py` (~120 LOC) + mount en `main.py` | ❌ No existe |
| T-01-06 Excel Export | Extender `excel_service.py` con `generate_mst_xlsx()` | ❌ No existe |
| T-01-06 PDF Service | `services/pdf_service.py` con reportlab | ❌ No existe |
| T-01-06 Export Router | `routers/export.py` (~100 LOC) + mount | ❌ No existe |

### Frontend — Fase 2 Completa (T-02-01 a T-02-08)

| Tarea | Archivos Necesarios | Estado |
|-------|--------------------|--------|
| T-02-01 Router + Auth | `App.jsx`, `hooks/useAuth.js`, `services/api.js`, `services/supabaseClient.js`, `ProtectedRoute` | ❌ App.jsx es scaffold Vite |
| T-02-02 Home + Login | `pages/HomePage.jsx`, `pages/LoginPage.jsx` | ❌ No existe `pages/` |
| T-02-03 Projects list | `pages/ProjectsPage.jsx` | ❌ No existe |
| T-02-04 Map view | `components/MapView.jsx` | ❌ No existe `components/` |
| T-02-05 Node form + import | `components/NodeForm.jsx`, `components/ImportButton.jsx` | ❌ No existe |
| T-02-06 Edge form + constraints | `components/EdgeForm.jsx`, `components/ConstraintsPanel.jsx` | ❌ No existe |
| T-02-07 MST trigger + results | `PlannerPage.jsx`, `components/ResultsSummary.jsx`, `hooks/useMst.js` | ❌ No existe |
| T-02-08 Export buttons | `components/ExportButton.jsx` | ❌ No existe |

### Base de Datos

| Ítem | Estado |
|------|--------|
| Aplicar schema a Supabase | ❌ No ejecutado |
| Crear organización default (`INSERT INTO organizations`) | ❌ No ejecutado |
| Activar Auth (email/password) en Supabase dashboard | ❌ No configurado |
| Verificar RLS policies funcionando | ❌ No probado |

### Infraestructura — Fase 3

| Tarea | Estado |
|-------|--------|
| T-03-01 E2E integration test | ❌ No empezado |
| T-03-02 Error handling audit | ⚠️ Backend OK, frontend no existe |
| T-03-03 Free tier enforcement | ⚠️ Backend OK (en projects.py), DB `plan` column existe en schema |
| T-03-04 Deployment (Vercel + Render) | ❌ No configurado |

---

## 4. Issues / Gaps / Technical Debt

### 🔴 Critical

1. **requirements.txt contaminado** — ~30 dependencias de AI/Azure que no pertenecen al proyecto (`azure-ai-inference`, `openai`, `sentry-sdk`, `llm`, `sqlite-utils`, `passlib`, etc.). Faltan `networkx`, `openpyxl`, `reportlab`.
2. **Ninguna tabla creada en Supabase** — el schema SQL existe en archivo pero nunca se ejecutó contra el proyecto de Supabase.
3. **Sin test suite** — `tests/` no existe en backend, `pytest.ini` no existe. No hay forma de verificar nada automáticamente.
4. **Frontend es scaffold Vite** — App.jsx muestra el template "Get started" de Vite. No hay routing, auth, pages, components, hooks, services.

### 🟡 Warning

5. **Código backend sin commiteo** — `nodes.py`, `edges.py`, `excel_service.py`, `main.py` modificado, `supabase-schema.sql`. El working tree necesita rescue urgente.
6. **openspec/config.yaml no existe** — el skill registry lo referencia pero nunca se creó.
7. **openspec/specs/ no existe** — el directorio de specs principal nunca se inicializó.
8. **`backend-nodes-edges` stuck** — verify FAIL, código existe pero no commiteado. Necesita rescue o re-proposal.
9. **`mst-calculation-endpoint` incompleto** — tiene proposal pero ningún otro artifact SDD.
10. **Sin `backend/.gitignore` ni `backend/tests/`** — estructura de proyecto incompleta.
11. **`ProjectCreate.name` sin `min_length=1`** — reportado en verify de projects-crud y no corregido.

### 🟢 Suggestion

12. El `README.md` tiene solo "# netplan" — necesita documentación real.
13. No hay `backend/pytest.ini` para correr tests.
14. No hay hooks de pre-commit ni linters configurados en backend.

---

## 5. Priorized Task List

### Prioridad 1 — Rescue + Baseline (desbloquea todo lo demás)

| # | Tarea | Esfuerzo | Dependencias | Por qué primero |
|---|-------|----------|-------------|-----------------|
| 1 | **Rescue**: commitear código no commiteado (nodes, edges, excel, schema) | S | — | Sin esto, el working tree es frágil y no se puede avanzar |
| 2 | **Clean requirements.txt**: remover deps AI/Azure, agregar `networkx`, `openpyxl`, `reportlab` | S | #1 | Sin deps correctas nada buildéa |
| 3 | **Aplicar schema SQL a Supabase** + crear org default | S | — | Sin DB no funciona nada del backend |
| 4 | **Crear `pytest.ini` + `tests/` bootstrap** con fixtures | S | #1, #2 | Necesitamos poder testear |

### Prioridad 2 — Core Backend (desbloquea frontend)

| # | Tarea | Esfuerzo | Dependencias | Por qué |
|---|-------|----------|-------------|---------|
| 5 | **T-01-05**: MST service + router (NetworkX Kruskal) | M | #1-#4 | Es el corazón del producto |
| 6 | **T-01-06**: Export endpoints (Excel + PDF) | M | #5 | Los usuarios necesitan exportar |

### Prioridad 3 — Frontend (lo que ve el usuario)

| # | Tarea | Esfuerzo | Dependencias | Por qué |
|---|-------|----------|-------------|---------|
| 7 | **T-02-01**: Router + Auth shell (App.jsx, useAuth, api.js) | S | #1 | Base de todo el frontend |
| 8 | **T-02-02**: HomePage + LoginPage | S | #7 | Landing + auth |
| 9 | **T-02-03**: ProjectsPage (lista + crear + eliminar) | S | #7, #8 | Gestión de proyectos |
| 10 | **T-02-04**: MapView (Leaflet) | M | #7 | Visualización backbone |
| 11 | **T-02-05**: NodeForm + ImportButton | M | #7-#10 | CRUD de nodos |
| 12 | **T-02-06**: EdgeForm + ConstraintsPanel | M | #7-#10 | CRUD de edges |
| 13 | **T-02-07**: MST trigger + ResultsSummary | M | #5, #7-#10 | Calcular y ver MST |
| 14 | **T-02-08**: ExportButtons | S | #6, #7 | Exportar resultados |

### Prioridad 4 — Polish + Deploy

| # | Tarea | Esfuerzo | Dependencias |
|---|-------|----------|-------------|
| 15 | T-03-02: Error handling audit (frontend) | S | #7-#14 |
| 16 | T-03-01: E2E integration test | M | #1-#14 |
| 17 | T-03-04: Deploy Vercel + Render | S | #1-#14 |
| 18 | README documentation | S | #1-#14 |

---

## 6. Git Log Context

```
e3198db feat: Implement Projects CRUD Router with 5 endpoints
875f566 feat: Initial commit of design and requirements documentation
02ca3e7 Initial commit
```

Solo 3 commits en total. El proyecto está en etapa muy temprana.

---

## Ready for Proposal

**Sí** — la situación es clara. Recomiendo:

1. **Primero**: Hacer un cambio único de **rescue** que commitee el código no commiteado y limpie requirements.txt. Esto desbloquea el working tree.
2. **Segundo**: Retomar `mst-calculation-endpoint` que ya tiene proposal — continuar spec → design → tasks → apply con MST service + router + tests.
3. **Tercero**: Un cambio de Frontend Bootstrap (T-02-01 y T-02-02) para tener auth funcionando.
4. **Cuarto**: Los cambios restantes de frontend y export en paralelo.
