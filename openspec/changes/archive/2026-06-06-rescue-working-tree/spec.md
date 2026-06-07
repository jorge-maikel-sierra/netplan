# code-rescue Specification

## Purpose

Commit uncommitted backend source code and sanitize `requirements.txt` to remove AI/Azure contamination, ensuring the working tree is clean and the project dependency manifest reflects only what NetPlan actually needs to run.

## Requirements

### Requirement: Git working tree rescue

The uncommitted backend files MUST be committed to `main` in logical work units. The user MAY choose between interactive commit workflow or automated staging.

| File | Status | Lines |
|------|--------|-------|
| `backend/app/routers/nodes.py` | New | 106 |
| `backend/app/routers/edges.py` | New | 74 |
| `backend/app/services/excel_service.py` | New | 136 |
| `backend/app/main.py` | Modified | +3/-1 |
| `supabase-schema.sql` | New | 120 |

#### Scenario: Clean working tree after rescue

- GIVEN uncommitted backend files as shown above
- WHEN the code is staged and committed
- THEN `git status --short` shows no entries for those files
- AND all source lines are preserved in the commit history

#### Scenario: No-op when tree already clean

- GIVEN a clean working tree with no uncommitted files
- WHEN the rescue process runs
- THEN no commit is created
- AND the process reports nothing to rescue

### Requirement: requirements.txt sanitization

The `requirements.txt` MUST be rewritten to contain ONLY packages that the project's Python code directly imports or that are required transitive dependencies for runtime. Packages from the `azure-*`, `openai`, `llm-*` families MUST be removed.

The minimum essential set MUST include:

| Package | Reason |
|---------|--------|
| `fastapi`, `uvicorn`, `starlette` | Web framework |
| `pydantic`, `pydantic-settings` | Schema/validation |
| `supabase` | Database client |
| `openpyxl` | Excel import parsing |
| `python-jose` | JWT token validation |
| `python-multipart` | File upload support |
| `httpx` | HTTP client (supabase dependency) |
| `cryptography` | JWT signing (python-jose dependency) |
| `python-dotenv` | Environment loading |
| `networkx` | MST algorithm (future, already installed) |

#### Scenario: Successful pip install after cleanup

- GIVEN a sanitized requirements.txt with only essential packages
- WHEN `pip install -r requirements.txt` is executed in a clean environment
- THEN the command exits with code 0
- AND no dependency conflict errors appear

#### Scenario: No AI/Azure packages remain

- GIVEN the sanitized requirements.txt
- WHEN checked for `azure-`, `openai`, `llm-`, `jiter` patterns
- THEN zero matches are found

### Requirement: Backend startup verification

After requirements cleanup and re-install, the FastAPI application MUST start without import errors.

#### Scenario: Server starts without ImportError

- GIVEN a clean virtualenv with the sanitized requirements installed
- WHEN `uvicorn app.main:app --host 0.0.0.0 --port 8000` is launched
- THEN the server logs indicate startup without any `ImportError` or `ModuleNotFoundError`
- AND `GET /healthz` returns `{"status": "ok"}` with HTTP 200

#### Scenario: All routers register correctly

- GIVEN the server is running after rescue
- WHEN `GET /api/v1/projects` is called (without auth token for schema check only)
- THEN the server returns 401 (not 500 or 404), proving the projects, nodes, and edges routers are all registered

## Out of Scope

- Running unit or integration tests (no test suite exists yet)
- Applying `supabase-schema.sql` to the database (separate change: `supabase-db-setup`)
- Any functional changes to the rescued code
- Database schema validation or seed data
- Frontend code rescue (none exists yet beyond scaffold)
- Performance optimization or refactoring of rescued code
