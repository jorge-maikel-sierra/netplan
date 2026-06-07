# Proposal: MST Calculation Endpoint (T-01-05) + Code Rescue

## Why (intent)

El backend tiene todo el andamiaje (T-01-01 a T-01-04) listo pero **sin commitear** — `main.py`, `routers/nodes.py`, `routers/edges.py`, `services/excel_service.py` y `supabase-schema.sql` viven en el working tree. Antes de poder construir T-01-05 (MST calculation) necesitamos **rescatar ese trabajo en un commit atómico** para tener un baseline limpio. Y el MST en sí es la pieza que destapa el valor del producto: sin él, los nodos y edges son datos huérfanos.

## What changes

### Phase 0 — Code rescue (pre-requisito)

- Commit atómico de todo lo uncommitted: `backend/app/main.py`, `backend/app/routers/nodes.py`, `backend/app/routers/edges.py`, `backend/app/services/excel_service.py`, `supabase-schema.sql`.
- Mensaje: `chore(rescue): commit uncommitted T-01-03/T-01-04 work (nodes, edges, excel, schema)`.
- **No se revisa como código nuevo** — ya existe y se auto-revisó. Es solo `git add` + commit.
- **Acción de borde**: el folder `openspec/changes/backend-nodes-edges/` queda en el disco como orphan. **No se toca, no se archiva, no se re-verifica** — solo se acknowledge.

### Phase 1 — Requirements cleanup

- `backend/requirements.txt` está contaminado (~18 deps de AI/Azure: `apm-cli`, `azure-ai-inference`, `openai`, `sentry-sdk`, `llm`, `sqlite-utils`, `fastar`, `pydantic-extra-types`, `passlib`, etc.).
- **Remover** todas las deps que no son del proyecto. **Agregar** las que faltan y están en `design.md`: `networkx`, `openpyxl`, `reportlab`.
- Verificar con `pip install -r requirements.txt` en venv limpio.
- Commit: `chore(deps): clean requirements.txt and add missing networkx/openpyxl/reportlab`.

### Phase 2 — TDD bootstrap

- `pytest==9.0.3` ya está instalado pero `backend/tests/` no existe.
- Crear: `backend/tests/__init__.py`, `backend/tests/unit/__init__.py`, `backend/tests/integration/__init__.py`, `backend/tests/conftest.py` con fixtures (`mock_supabase_client`, `test_app`, `test_user_token`, `mock_jwt_decode`).
- Agregar `backend/pytest.ini` con `testpaths = tests` y `asyncio_mode = auto`.
- Verificar `pytest -x` corre con 0 tests en <0.1s.
- Commit: `test(backend): bootstrap pytest structure and conftest fixtures`.

### Phase 3 — MST service (T-01-05 core)

- Crear `backend/app/services/mst_service.py` con:
  - Jerarquía de errores: `MSTServiceError` → `InsufficientNodes`, `DisconnectedGraph`.
  - Core puro (sync) `def _run_kruskal(nodes, mandatory_edges, optional_edges, forbidden_edges) -> MSTResult` — fácil de testear sin mocks.
  - Wrapper async `async def calculate_mst(supabase, project_id, org_id) -> MSTCalculateResult` que: carga nodes/edges tenant-scoped, separa mandatory/forbidden/normal, llama al core puro, persiste a `mst_results`, retorna el `MSTCalculateResponse`.
  - Algoritmo: `networkx.minimum_spanning_tree` con manejo explícito de mandatory (force-included) y forbidden (excluidos del grafo).
  - Validación previa: <2 nodos → `InsufficientNodes` (mapea a 422 `INSUFFICIENT_NODES`).
  - Verificación de conectividad post-MST: si `len(mst_edges) < n - 1` → `DisconnectedGraph` con `unreachable_nodes` (componentes conexas vía `networkx.connected_components`).
- **Unit tests** del core puro (mocks zero, 100% determinístico):
  - `test_calculate_mst_kruskal_basic` — triángulo, escoge los 2 edges más baratos.
  - `test_calculate_mst_with_mandatory_edges` — un mandatory fuerza su inclusión.
  - `test_calculate_mst_with_forbidden_edges` — un forbidden nunca aparece en el MST.
  - `test_calculate_mst_mandatory_creates_cycle_is_rejected` — guard contra ciclos.
  - `test_calculate_mst_disconnected_returns_422_payload` — con `unreachable_nodes` exacto.
  - `test_calculate_mst_insufficient_nodes_raises` — 0 y 1 nodo.
- Commit: `feat(mst): add MST service with NetworkX Kruskal + mandatory/forbidden handling`.

### Phase 4 — MST router (T-01-05 HTTP)

- Crear `backend/app/routers/mst.py`:
  - `POST /projects/{id}/mst/calculate` — rate-limited (5 req/min por org via `slowapi` o custom token bucket en `dependencies.py`), llama al service, mapea errores.
  - `GET /projects/{id}/mst/latest` — `SELECT * FROM mst_results WHERE project_id = ? ORDER BY calculated_at DESC LIMIT 1` con tenant scoping via `select("id").eq("organization_id", org_id).eq("id", project_id).maybe_single()`.
  - 404 (no 403) para cross-tenant.
  - Error mapping centralizado: `InsufficientNodes` → 422 `INSUFFICIENT_NODES`, `DisconnectedGraph` → 422 `DISCONNECTED_GRAPH` con `unreachable_nodes` en `detail`.
- Mount en `backend/app/main.py` (1 línea).
- Commit: `feat(mst): add MST router with rate-limited calculate + latest endpoints`.

### Phase 5 — Integration tests (TDD continued)

- `backend/tests/integration/test_mst_router.py` con `httpx.AsyncClient` + `TestClient`:
  - `test_calculate_happy_path` — proyecto con 3 nodos y 3 edges → 200 + `total_cost` correcto + `mst_results` row creada.
  - `test_calculate_tenant_isolation` — JWT de org A + project_id de org B → 404.
  - `test_calculate_insufficient_nodes` — 1 nodo → 422 `INSUFFICIENT_NODES`.
  - `test_calculate_disconnected` — 2 componentes → 422 `DISCONNECTED_GRAPH` con `unreachable_nodes`.
  - `test_calculate_unauthorized` — sin JWT → 401.
  - `test_calculate_rate_limited` — 6 requests rápidas → última devuelve 429.
  - `test_latest_returns_most_recent` — 2 calculations → latest devuelve la segunda.
  - `test_latest_no_history_returns_404` — proyecto sin results → 404 con `error: "NO_RESULTS"`.
- `backend/tests/integration/test_mst_service_persistence.py`:
  - `test_service_persists_to_mst_results` — con `mock_supabase_client`, verificar `.insert()` llamado con shape correcto.
  - `test_service_tenant_filters_nodes_and_edges` — verificar que la query incluye `.eq("organization_id", org_id)`.
- Commit: `test(mst): integration tests for router and service (10 tests)`.

### Phase 6 — Manual smoke + verify

- `GET /healthz` → 200.
- `POST /projects/{id}/mst/calculate` con proyecto válido → 200 + `total_cost` + `mst_edges[]`.
- `POST .../calculate` con 1 nodo → 422 `INSUFFICIENT_NODES`.
- `POST .../calculate` con grafo disconexo → 422 `DISCONNECTED_GRAPH` con `unreachable_nodes`.
- `GET /projects/{id}/mst/latest` → último resultado persistido.
- Cross-tenant: token de org A sobre project de org B → 404.
- Rate limit: 6° request en 1 min → 429.
- Log en `openspec/changes/mst-calculation-endpoint/smoke-log.md` (no commit necesario).

## Scope

### In scope

- Code rescue de T-01-03/T-01-04 (Phase 0).
- Cleanup de `requirements.txt` + agregar deps faltantes (Phase 1).
- Bootstrap de `pytest` con `conftest.py` y fixtures (Phase 2).
- MST service (Phase 3) + unit tests.
- MST router con rate limiting (Phase 4) + integration tests (Phase 5).
- Mount del router en `main.py`.
- Smoke test manual documentado (Phase 6).
- Persistencia de resultados en `mst_results` con `edge_ids` array.

### Out of scope

- **T-01-06** (PDF export) — próximo change separado.
- **Frontend** (todo T-02-XX) — change separado después de solid backend.
- **T-03-XX** (billing edge cases, auth refinements) — futuro.
- **Re-verificar o archivar** el orphan `openspec/changes/backend-nodes-edges/`. Se acknowledge, no se toca.
- **NetworkX para >10k nodos** — el import ya limita a 10k filas, MST no se optimiza más allá.
- **Tests E2E frontend** — no aplica acá.

## Impact

### Archivos tocados (estimado)

| Tipo | Path | LOC est. |
|------|------|----------|
| New | `backend/app/services/mst_service.py` | ~150 |
| New | `backend/app/routers/mst.py` | ~120 |
| New | `backend/tests/conftest.py` | ~80 |
| New | `backend/tests/unit/test_mst_service.py` | ~200 |
| New | `backend/tests/integration/test_mst_router.py` | ~200 |
| New | `backend/tests/integration/test_mst_service_persistence.py` | ~80 |
| New | `backend/pytest.ini` | ~10 |
| Mod  | `backend/app/main.py` | +1 (mount) |
| Mod  | `backend/requirements.txt` | -15 / +3 |

**Total ~850 LOC** (code-only ~350, test ~560, config ~10).

### Risk

- **Medio**. MST es core de producto: si el algoritmo elige mal un edge o ignora un mandatory, los números que ve el cliente son incorrectos.
- **Mitigación**: TDD estricto sobre el core puro (sin IO), `networkx` battle-tested, unit tests cubren todos los caminos del constraint handling (mandatory, forbidden, cycle, disconnect).

### Dependencies

- **Requiere**: T-01-03 (nodes) ✅ implemented, T-01-04 (edges) ✅ implemented — ambos uncommitted, rescue en Phase 0.
- **Bloquea**: T-01-06 (PDF export), todos los T-02-XX (frontend).
- **Externas**: `networkx`, `openpyxl`, `reportlab` (ya están en `design.md` como deps requeridas).

## Review workload forecast

- Code LOC: ~350
- Test LOC: ~560
- Total changed: ~850 (incluye deps cleanup: ~30 líneas de diff en `requirements.txt`)
- **`chained-pr` recomendado**: **SÍ** — supera 400 LOC. Auto-chain (estrategia de sesión) honored.
- **`400-line budget risk`**: **High**.
- **`Decision needed before apply`**: **No** — auto-chain strategy ya está resuelta por el orchestrator.

**Plan de PRs encadenados** (3 PRs, cada uno con scope autónomo + verify + rollback claro):

| PR | Scope | LOC est. | Reviewer focus |
|----|-------|----------|----------------|
| **PR #1** | Phase 0 (rescue) + Phase 1 (deps cleanup) | ~30 líneas diff en archivos existentes | "¿Se commitea exactamente lo que ya está revisado, sin cambios furtivos?" |
| **PR #2** | Phase 2 (TDD bootstrap) + Phase 3 (MST service + unit tests) | ~430 LOC | "¿El core de Kruskal con mandatory/forbidden es correcto? ¿Los tests cubren todos los branches?" |
| **PR #3** | Phase 4 (MST router + rate limit) + Phase 5 (integration tests) + Phase 6 (smoke) | ~410 LOC | "¿Tenant isolation es hermética? ¿El rate limit es por org_id? ¿Error mapping cubre los 4 codes?" |

Cada PR apunta a una branch feature intermedia (`feat/mst-pr1-rescue`, `feat/mst-pr2-service`, `feat/mst-pr3-router`); PR #2 y #3 target la branch del PR anterior hasta que se merge todo a main.

## Alternatives considered

1. **Saltear TDD bootstrap, escribir tests inline** → rechazado. TDD discipline es project standard (ver `.atl/skill-registry.md`); bootstrap da fundación limpia para todos los routers futuros.
2. **Incluir T-01-06 (PDF export) en el mismo change** → rechazado. Distinto concern (MST math vs. PDF rendering), merece su propio ciclo.
3. **Usar Prim en vez de Kruskal** → rechazado. `AGENTS.md` y `design.md` especifican Kruskal via NetworkX explícitamente.
4. **No rescatar el código uncommitted, pedirle al usuario que revierta y re-commitee** → rechazado. El código ya está auto-revisado y testeado a mano; perderlo es tirar trabajo. Rescue es la opción honesta.
5. **Hacer un solo PR con todo** → rechazado. Auto-chain strategy está activa y 850 LOC >> budget de 400.
6. **Mockear NetworkX en vez de testear el core puro directo** → rechazado. El core puro es una función determinística sin IO — testearla con mocks agregaría complejidad sin valor. Los tests del wrapper async sí mockean supabase.

## Rollback Plan

- **PR #1** (rescue): `git revert <commit>` — main queda en el estado anterior al rescue, working tree no se toca.
- **PR #2** (service): `git revert <commit>` + borrar `backend/app/services/mst_service.py` y tests. MST endpoints quedan sin service pero el router no existe todavía (PR #3 no aplicado).
- **PR #3** (router): `git revert <commit>` + quitar la línea de mount en `main.py`. Backend queda con `nodes`/`edges`/`projects` routers funcionando, MST no expuesto.
- **Recovery completo**: las 3 reversions dejan el repo en el estado pre-cambio (después del rescue, pero con código MST 100% removido). `mst_results` queda vacía (no se insertó nada).

## Success Criteria

- [ ] Working tree limpio después del rescue (Phase 0).
- [ ] `pip install -r requirements.txt` en venv limpio funciona sin warnings de AI/Azure deps.
- [ ] `pytest -x` corre la suite completa en <2s, todos los 10+ tests verdes.
- [ ] `POST /projects/{id}/mst/calculate` con 3 nodos triangulares retorna 200 + `total_cost` = suma de los 2 edges más baratos.
- [ ] `POST .../calculate` con 1 nodo retorna 422 + `error: "INSUFFICIENT_NODES"`.
- [ ] `POST .../calculate` con grafo disconexo retorna 422 + `error: "DISCONNECTED_GRAPH"` + `detail.unreachable_nodes` poblado.
- [ ] `GET /projects/{id}/mst/latest` retorna el resultado más reciente o 404 si no hay historial.
- [ ] Token de org A sobre project de org B retorna 404 (no 403, no leak de existencia).
- [ ] Rate limit: 6° `POST .../calculate` en <60s retorna 429.
- [ ] Cada commit tiene mensaje conventional, sin `Co-Authored-By` AI.
