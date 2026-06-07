# Design: pytest-bootstrap

## Technical Approach

Extend the existing test scaffold — which already has `conftest.py`, `pytest.ini`, and MST router/algorithm tests — to cover the three CRUD routers (projects, nodes, edges) and a health smoke test. Add missing dependencies (`pytest-asyncio`, `pytest-cov`), add two sample-data fixtures to `conftest.py`, and create four test files that follow the dependency-override + MagicMock pattern already established by the MST integration tests.

No structural changes to the app code. Zero test changes to existing MST tests.

## Architecture Decisions

| Decision | Choice | Alternatives | Why |
|----------|--------|-------------|-----|
| Mock strategy | `dependency_overrides` to swap `get_supabase_client` | Patching the module directly | FastAPI native, used by existing MST tests, no import-order issues |
| Auth | `dependency_overrides` to swap `get_current_user` | Generating real JWTs | Already done in conftest, avoids Supabase JWT signing dependency |
| Sample data fixtures | Add to `conftest.py` | Per-test inline dicts | Reused across all router tests, keeps tests DRY, matches existing `sample_uuids` pattern |
| Test file location | `tests/test_*.py` (root level) | `tests/integration/` subdir | Spec explicitly requests root level; router tests are integration-ish but simpler than existing MST integration tests |
| Supabase mock depth | Plain `MagicMock` for CRUD | `_Chain`/`_ExecuteResult` (MST pattern) | CRUD only uses `.table().insert()`, `.table().select().eq()` — MagicMock handles this. `_Chain` is needed only when validating query structure (MST) |

## Data Flow

```
TestClient ──POST/GET──→ FastAPI App
                            │
                    dependency_overrides
                     ┌──────┴──────┐
                     │              │
              get_current_user   get_supabase_client
              (returns fake)    (returns MagicMock)
                                   │
                              mock.table("projects")
                              mock.table("nodes")
                              mock.table("edges")
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/tests/test_health.py` | Create | Smoke test: `GET /healthz` returns `{"status": "ok"}` |
| `backend/tests/test_projects.py` | Create | List, create, get, update, delete projects; free-tier limit; 404 on cross-tenant |
| `backend/tests/test_nodes.py` | Create | Create, list, update, delete nodes; verify project ownership check |
| `backend/tests/test_edges.py` | Create | Create/upsert edge, delete, update constraint; verify both nodes exist |
| `backend/tests/conftest.py` | Modify | Add `sample_project` and `sample_node` fixtures |
| `backend/requirements.txt` | Modify | Add `pytest-asyncio`, `pytest-cov` |

## Interfaces / Contracts

### Fixture additions to `conftest.py`

```python
@pytest.fixture
def sample_project(sample_uuids) -> dict:
    return {
        "id": str(sample_uuids["project_id"]),
        "organization_id": str(sample_uuids["org_id"]),
        "created_by": str(sample_uuids["user_id"]),
        "name": "Test Project",
        "description": "A project for testing",
        "created_at": "2026-06-06T00:00:00+00:00",
        "updated_at": "2026-06-06T00:00:00+00:00",
    }

@pytest.fixture
def sample_node(sample_uuids) -> dict:
    return {
        "id": str(sample_uuids["node_a"]),
        "project_id": str(sample_uuids["project_id"]),
        "name": "Node A",
        "type": "city",
        "lat": 0.0,
        "lng": 0.0,
        "created_at": "2026-06-06T00:00:00+00:00",
    }
```

### Test patterns

Each router test follows two patterns:

**Pattern A — success (mock returns data):**
```python
async def test_list_projects(client, mock_supabase_client, sample_project):
    mock_supabase_client.table.return_value.select.return_value \
        .eq.return_value.order.return_value.execute.return_value.data = [sample_project]
    response = await client.get("/api/v1/projects")
    assert response.status_code == 200
```

**Pattern B — not-found (mock returns no data):**
```python
async def test_get_project_404(client, mock_supabase_client):
    mock_supabase_client.table.return_value.select.return_value \
        .eq.return_value.eq.return_value.single.return_value.execute.return_value.data = None
    response = await client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert response.status_code == 404
```

### `requirements.txt` additions

```
pytest-asyncio>=0.24.0
pytest-cov>=5.0.0
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Smoke | `GET /healthz` | Assert 200 + `{"status": "ok"}`. No dependencies needed. |
| Routes | Projects CRUD | 7 tests: list (empty + populated), create, get (found + 404), update, delete, free-tier limit. |
| Routes | Nodes CRUD | 5 tests: create, list, update, delete, 404 on bad project/node. |
| Routes | Edges CRUD | 5 tests: create/upsert, delete, update constraint, 422 on missing nodes, 404 on bad edge. |
| Code style | `test_*.py` | Each function takes `client`, `mock_supabase_client`, and any sample data fixtures — all from conftest. No raw imports of FastAPI test client. |

Coverage target: `--cov=app --cov-report=term-missing` enforced in `pytest.ini`, baseline ~12% (existing MST tests already contribute ~7%).

## Migration / Rollout

No migration required. New test files are additive. The only production file changed is `requirements.txt`.

## Open Questions

None. The design is grounded in existing codebase patterns.
