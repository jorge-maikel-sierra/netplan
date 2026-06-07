# Design: Rescue Working Tree

## Technical Approach

Clean-commit the uncommitted backend code (nodes router, edges router, excel service, main.py update, supabase-schema.sql) in logical reviewable units, then sanitize `requirements.txt` by removing AI/Azure cruft and pinning only the project's real dependencies.

This is a pure Git + dependency hygiene change — no new features, no architecture changes.

## Architecture Decisions

### Decision: Commit Strategy — logical slices, not one big commit

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Single commit all files | Simplest, but loses semantic grouping and makes future `git bisect` harder | ❌ Rejected |
| One commit per file | Clean diffs but fragments related work (schema + code that depends on it) | ❌ Rejected |
| **Three logical commits** | Groups by reviewable unit: (1) schema + gitignore, (2) models/services, (3) routers + wiring | ✅ **Chosen** |

**Rationale**: The schema is the foundation that routers depend on. Services are consumed by routers. Wiring (`main.py`) is the final integration step. Three commits follow a natural dependency chain and let each be reviewed independently.

### Decision: Requirements rebuild — start clean, not edit

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Edit the contaminated file | Risk of missing a cruft dependency; fragile | ❌ Rejected |
| **Regenerate via `pip freeze` from a clean `.venv`** | Guarantees only what's actually installed; matches standard workflow | ✅ **Chosen** |

**Rationale**: The current `.venv` already has the contamination installed. We need to create a fresh virtual environment, install only the real deps, then `pip freeze` into a clean `requirements.txt`. This is the only way to guarantee no residual AI/Azure libraries leak through.

### Decision: `.atl/` goes to `.gitignore`

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Track `.atl/` in repo | Pollutes the project with AI agent artifacts | ❌ Rejected |
| **Add `.atl/` to `.gitignore`** | Keeps agent tooling local to each developer's machine | ✅ **Chosen** |

## Git Strategy

```
Commit 1: Database schema + gitignore
  Files: supabase-schema.sql, .gitignore (add .atl/ entry)
  Message: feat: Add database schema and gitignore cleanup

Commit 2: Services (Excel import logic)
  Files: backend/app/services/excel_service.py
  Message: feat: Add Excel node import service with validation

Commit 3: Routers + wiring
  Files: backend/app/routers/nodes.py, backend/app/routers/edges.py,
         backend/app/main.py
  Message: feat: Add nodes and edges CRUD routers with tenant isolation
```

No amend, no force-push. If a commit fails, create a new one.

## Dependency Cleanup Plan

1. Create a temp virtual environment: `python -m venv /tmp/netplan-clean-venv`
2. Activate and install real deps only:

```
fastapi==0.136.1
uvicorn[standard]
pydantic
pydantic-settings
supabase-py
python-jose[cryptography]
python-multipart
openpyxl
bcrypt
passlib[bcrypt]
httpx
pytest
```

3. Run `pip freeze > backend/requirements.txt`
4. Destroy temp venv
5. Verify: `pip install -r backend/requirements.txt` installs cleanly

**Real deps identified** (from codebase analysis):

| Dependency | Usage | File |
|-----------|-------|------|
| `fastapi` | Framework | routers, main.py |
| `uvicorn[standard]` | ASGI server | dev/runtime |
| `pydantic` | Schema models | schemas/*.py |
| `pydantic-settings` | Config/env loading | config.py |
| `supabase-py` | DB client | db/supabase_client.py |
| `python-jose[cryptography]` | JWT validation | dependencies.py |
| `python-multipart` | File upload support | nodes.py (UploadFile) |
| `openpyxl` | Excel parsing | excel_service.py |
| `bcrypt` / `passlib[bcrypt]` | Auth (profile handling) | dependencies.py |
| `httpx` | HTTP client (testing) | — |
| `pytest` | Test runner | — |

**Libraries to exclude** (contamination): `azure-*`, `openai`, `langchain`, `llm`, `llm-github-models`, `torch`, `transformers`, `tqdm`, `sentry-sdk`, `tabulate`, `GitPython`, `aiohttp`, `rich`, `typer`, `sqlite-utils`, `apm-cli`, `fastapi-cloud-cli`, `smmap`, `gitdb`, `toml`, `python-frontmatter`, `rignore`, `fastar`, `shellingham`, `puremagic`, `condense-json`, `python-ulid`, `click-default-group`, `rich-toolkit`, `annotated-doc`, `packaging`, `markdown-it-py`, `Pygments`, `mdurl`, `rich-click`, `sqlite-fts4`, `sqlite-migrate`, `python-dateutil`, `sqlite-utils`, `setuptools`.

## Verification

| Step | Command | Expected |
|------|---------|----------|
| 1. Clean install | `pip install -r backend/requirements.txt` | Succeeds, no errors |
| 2. App starts | `uvicorn app.main:app --port 9999` (in `.venv`) | Starts, `/healthz` returns 200 |
| 3. No residual cruft | `pip list \| grep -i -E "azure\|openai\|langchain\|torch\|transformers"` | Empty output |
| 4. Git log | `git log --oneline -5` | 3 new commits visible |

## Rollback Plan

| Scenario | Action |
|----------|--------|
| App fails to start | `git reset --soft HEAD~3` to uncommit but keep changes; `git restore backend/requirements.txt` from backup |
| requirements.txt is wrong | `git checkout HEAD~1 -- backend/requirements.txt` to restore previous version |
| Contamination persists | Re-run the clean venv process with explicit version pins |

## Open Questions

- None. The scope is well-understood: commit orphaned code, clean requirements, no new behavior.
