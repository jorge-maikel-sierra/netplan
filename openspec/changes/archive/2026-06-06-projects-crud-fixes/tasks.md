# Tasks: projects-crud-fixes

**Change ID**: projects-crud-fixes
**Project**: netplan
**Created**: 2026-06-06

---

## Task Breakdown

### T-01: Add min_length validation to ProjectCreate/ProjectUpdate name fields
**File**: `backend/app/schemas/project.py`
- Add `min_length=3` to `name` in `ProjectCreate` and `ProjectUpdate`
- Add Spanish validation message: `"El nombre debe tener al menos 3 caracteres"`
- Use `Field(min_length=3, description="...")` from pydantic

**Acceptance**: `POST /projects` with `{"name": "ab"}` returns 422 with Spanish error

---

### T-02: Verify/fix PATCH null handling and add org existence check
**File**: `backend/app/routers/projects.py`
- **PATCH null handling**: Already correct (lines 191-198 skip None values, return 422 if all None)
- **Add ORG_NOT_FOUND check to GET/PATCH/DELETE**: Before querying project, verify organization exists (consistent with create_project)
  - GET `/projects/{id}` (line 98): add org check
  - PATCH `/projects/{id}` (line 164): add org check
  - DELETE `/projects/{id}` (line 211): add org check
- Reuse existing `_error_response("ORG_NOT_FOUND", 404, "Organization not found")`

**Acceptance**: Requests for non-existent org return 404 ORG_NOT_FOUND (not 500)

---

### T-03: Add validation tests for name length
**File**: `backend/tests/test_projects.py`
- `test_create_project_name_too_short`: POST with `{"name": "ab"}` → 422
- `test_update_project_name_too_short`: PATCH with `{"name": "ab"}` → 422

**Acceptance**: Both tests pass with Spanish validation message in detail

---

### T-04: Add PATCH null handling tests
**File**: `backend/tests/test_projects.py`
- `test_update_project_with_null_values`: PATCH with `{"name": "New", "description": null}` → 200 (ignores null)
- `test_update_project_all_null`: PATCH with `{"name": null, "description": null}` → 422 NO_FIELDS_TO_UPDATE

**Acceptance**: Both tests pass with correct status codes

---

### T-05: Add org-scoped access tests
**File**: `backend/tests/test_projects.py`
- `test_get_project_missing_org`: GET with mocked org returning None → 404 ORG_NOT_FOUND
- `test_cross_tenant_access`: GET/PATCH/DELETE with project_id from different org → 404 PROJECT_NOT_FOUND (not 403)
- `test_free_tier_limit`: Already exists (line 199), verify it passes

**Acceptance**: All tests pass; cross-tenant returns 404 (security through obscurity)

---

## Execution Order

```
T-01 → T-02 → T-03 → T-04 → T-05
```

Each task is independently verifiable. Run tests after each: `pytest backend/tests/test_projects.py -v`