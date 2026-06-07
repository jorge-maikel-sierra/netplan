# SDD Verify Report

**Change**: frontend-complete (re-verification after remediation)
**Version**: `openspec/changes/frontend-complete/{spec,design,tasks}.md`
**Mode**: Standard

## Completeness

| Metric | Value |
|---|---|
| Tasks total | 11 |
| Tasks complete | 10 |
| Tasks incomplete | 1 (`T-03-04`) |

## Build & Runtime Evidence

**Build**: ✅ Passed
```text
Command: npm run build (workdir: frontend/)

vite v8.0.16 building client environment for production...
✓ 141 modules transformed.
dist/index.html                   0.45 kB │ gzip:   0.29 kB
dist/assets/index-BkqTepeA.css   34.26 kB │ gzip:  10.74 kB
dist/assets/index-CnWQnhY5.js   668.17 kB │ gzip: 196.66 kB
✓ built in 306ms
```

**Tests**: ⚠️ No automated FE tests executed (not present for this change)

**Coverage**: ➖ Not available

## Verification Matrix (requested scope)

### 1) Drag + save wiring and endpoint correctness

| Check | Evidence | Result |
|---|---|---|
| Marker drag behavior exists | `frontend/src/components/NodeMarkers.jsx` uses `L.marker(..., { draggable: true })` and `dragstart`/`dragend` handlers | ✅ COMPLIANT |
| Explicit save flow exists | Popup renders `Guardar`/`Cancelar`; save triggers `onNodeDragSave(node.id, pending)` | ✅ COMPLIANT |
| UI wiring to page action exists | `MapView.jsx` forwards `onNodeDragSave`; `ProjectDetailPage.jsx` implements `onNodeDragSave` | ✅ COMPLIANT |
| Backend call for position persistence exists | `useProjects.jsx::updateNodePosition()` calls `PUT /projects/${projectId}/nodes/${nodeId}` | ✅ COMPLIANT |
| Endpoint exists server-side | `backend/app/routers/nodes.py` defines `@router.put("/{project_id}/nodes/{node_id}")` | ✅ COMPLIANT |

### 2) Error mapping leakage risk re-check

| Check | Evidence | Result |
|---|---|---|
| Centralized Spanish mapping present | `frontend/src/utils/errorMap.js` maps required codes and fallbacks | ✅ COMPLIANT |
| 401 silent redirect preserved | `frontend/src/services/api.js` interceptor signs out and redirects to `/login` | ✅ COMPLIANT |
| Raw/non-standard message leakage risk | `ProjectDetailPage.jsx::formatError()` returns `err.message` when present | ⚠️ PARTIAL |

### 3) Tasks status / acceptance gate impact

| Check | Evidence | Result |
|---|---|---|
| Manual acceptance task status | `openspec/changes/frontend-complete/tasks.md` keeps `T-03-04` unchecked and explicitly pending browser execution | ❌ UNTESTED |
| Blocking classification | T-03-04 is the full acceptance gate across all spec scenarios | ❌ BLOCKING |

## Issues Found

**CRITICAL**
1. `T-03-04` remains pending, and it is the only end-to-end acceptance evidence for multiple spec scenarios. Under verify gate rules, pending full acceptance keeps final status blocked.

**WARNING**
1. `ProjectDetailPage.formatError()` can still surface raw `err.message` in some paths, which weakens the “no raw API error to user” guarantee.
2. Spec/tasks still describe drag persistence as PATCH in places, while implementation is PUT (backend-confirmed). Behavior is correct, but docs should be aligned to avoid future false negatives.

**SUGGESTION**
1. Replace `err.message` fallback in `ProjectDetailPage.formatError()` with strict `getErrorMessage()`-first behavior.
2. Update spec/tasks wording from PATCH to PUT for node position persistence to keep contracts consistent.

## Verdict

**FAIL**

Re-remediation fixed the drag + save + persistence wiring (now compliant), but final verification remains blocked by pending full manual acceptance (`T-03-04`).
