# Design: projects-crud-fixes

## Technical Approach

This change adds three fixes to the projects CRUD router based on the spec:
1. **Min-length validation** on `name` field (≥3 chars) in `ProjectCreate` and `ProjectUpdate` schemas using Pydantic v2 `Field(min_length=3)`.
2. **PATCH null handling** already works correctly (ignores nulls, returns 422 if all null) — verify and keep.
3. **ORG_NOT_FOUND consistency** — already exists in `create_project`; extend to all endpoints (GET, PATCH, DELETE) by checking org existence before tenant-scoped queries.
4. **Spanish validation errors** — add custom validation in schemas to return Spanish messages.
5. **Tests** — extend `test_projects.py` with new cases for all edge conditions.

## Architecture Decisions

### Decision: Min-length validation location

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Schema-level (Pydantic `Field`) | Declarative, automatic 422, no extra code | **Chosen** — follows existing Pydantic patterns |
| Router-level manual check | More control, but duplicates validation logic | Rejected — violates DRY |

**Rationale**: Pydantic v2 `Field(min_length=3)` on the schema is the idiomatic way. Returns 422 with `VALIDATION_ERROR` automatically. Custom Spanish message via `@field_validator` with `mode="after"`.

### Decision: ORG_NOT_FOUND on all endpoints

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Check org in every endpoint | Consistent, explicit, slight duplication | **Chosen** — clarity over DRY for security boundary |
| Centralize in dependency | DRY, but hides tenant-scoping logic | Rejected — current `get_current_user` only validates JWT + fetches profile; org check is business logic |

**Rationale**: The spec requires ORG_NOT_FOUND on *all* endpoints. Adding `org = supabase.table("organizations").select("plan").eq("id", org_id).single().execute()` at the start of each endpoint ensures consistent 404 before any tenant-scoped query.

### Decision: Spanish validation messages

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Pydantic `@field_validator` with Spanish `ValueError` | Built-in, returns 422 with custom detail | **Chosen** — minimal change, integrates with FastAPI |
| Global exception handler | Centralized, but overkill for one field | Rejected — YAGNI |

## Data Flow

```
POST /projects (create)
    │
    ▼
Validate JWT → get_current_user (org_id, user_id)
    │
    ▼
Check org exists → ORG_NOT_FOUND if missing
    │
    ▼
Check free tier limit → FREE_TIER_LIMIT if exceeded
    │
    ▼
Pydantic validates name min_length=3 → 422 VALIDATION_ERROR (Spanish)
    │
    ▼
Insert project → return 201

PATCH /projects/{id} (update)
    │
    ▼
Validate JWT → get_current_user
    │
    ▼
Check org exists → ORG_NOT_FOUND if missing
    │
    ▼
Check project ownership (tenant-scoped) → PROJECT_NOT_FOUND if not owned
    │
    ▼
Pydantic validates name min_length=3 (if provided) → 422
    │
    ▼
Build payload skipping None fields → 422 if empty (NO_FIELDS_TO_UPDATE)
    │
    ▼
Update project → return 200
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/schemas/project.py` | Modify | Add `Field(min_length=3)` to `name` in `ProjectCreate` and `ProjectUpdate`; add `@field_validator` for Spanish error message |
| `backend/app/routers/projects.py` | Modify | Add org existence check at start of `list_projects`, `get_project`, `update_project`, `delete_project` (consistent with `create_project`) |
| `backend/tests/test_projects.py` | Modify | Add test cases: min-length (create/update), PATCH null handling, ORG_NOT_FOUND on all endpoints, cross-tenant 404, free tier limit |

## Interfaces / Contracts

### Schema Changes (`backend/app/schemas/project.py`)

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class ProjectCreate(BaseModel):
    name: str = Field(min_length=3)
    description: Optional[str] = None

    @field_validator("name", mode="after")
    @classmethod
    def validate_name_spanish(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("El nombre del proyecto debe tener al menos 3 caracteres")
        return v

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3)
    description: Optional[str] = None

    @field_validator("name", mode="after")
    @classmethod
    def validate_name_spanish(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) < 3:
            raise ValueError("El nombre del proyecto debe tener al menos 3 caracteres")
        return v
```

### Router Org Check Pattern (applied to all endpoints)

```python
# At start of each endpoint after getting org_id:
org_response = (
    supabase.table("organizations")
    .select("plan")
    .eq("id", org_id)
    .single()
    .execute()
)

if org_response.data is None:
    raise _error_response("ORG_NOT_FOUND", 404, "Organization not found")

plan = org_response.data.get("plan", "free")
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (schema) | Min-length validation, Spanish messages | Direct Pydantic model instantiation in `test_projects.py` |
| Integration (router) | CREATE: 422 for <3 chars, 201 for ≥3 | Mock supabase, assert status + error code |
| Integration (router) | UPDATE: 422 for <3 chars, 200 for ≥3 | Same pattern with PATCH |
| Integration (router) | PATCH null handling: ignore null, 422 if all null | Existing test `test_update_project` covers happy path; add 3 new cases |
| Integration (router) | ORG_NOT_FOUND on GET/POST/PATCH/DELETE | Mock org lookup returning `None`, assert 404 + error code |
| Integration (router) | Cross-tenant access → 404 (not 403) | Mock ownership check returning `None`, assert 404 |
| Integration (router) | Free tier limit (3 projects) | Existing `test_free_tier_limit` covers; verify still works |

## Migration / Rollout

No migration required. Schema validation is additive (stricter). Router org check adds a query before existing logic — no data changes.

## Open Questions

- [ ] Should `description` also have min-length? Spec only mentions `name`.
- [ ] Confirm Spanish message exact wording: "El nombre del proyecto debe tener al menos 3 caracteres" (from spec) vs Pydantic default.
- [ ] Do we need to handle org check in a shared helper to avoid duplication? (Current decision: inline for clarity; can refactor later if pattern grows)