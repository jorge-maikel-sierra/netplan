# Delta for projects-crud

## ADDED Requirements

### Requirement: Project name minimum length validation

The system **MUST** enforce a minimum length of 3 characters for project names on creation and update.

#### Scenario: Create project with name shorter than 3 chars → 422

- GIVEN an authenticated user with valid JWT
- WHEN POST /projects with name "AB" (2 chars)
- THEN response is 422 with error code "VALIDATION_ERROR"
- AND detail indicates "Project name must be at least 3 characters"

#### Scenario: Create project with name exactly 3 chars → 201

- GIVEN an authenticated user with valid JWT
- WHEN POST /projects with name "ABC" (3 chars)
- THEN response is 201 with created project

#### Scenario: Update project name to shorter than 3 chars → 422

- GIVEN an existing project owned by the user
- WHEN PATCH /projects/{id} with name "XY" (2 chars)
- THEN response is 422 with error code "VALIDATION_ERROR"

### Requirement: Validation error messages in Spanish

The system **MUST** return validation error messages in Spanish for all project endpoints.

#### Scenario: Validation error returns Spanish message

- GIVEN any project endpoint with invalid input
- WHEN validation fails
- THEN error detail is in Spanish (e.g., "El nombre del proyecto debe tener al menos 3 caracteres")

## MODIFIED Requirements

### Requirement: Update project ignores null fields

The system **MUST** ignore null fields in PATCH /projects/{id} and only update provided non-null values. If all fields are null, return 422.

(Previously: PATCH ignored nulls but returned 422 with "NO_FIELDS_TO_UPDATE" when no valid fields provided; behavior unchanged, now explicit in spec)

#### Scenario: PATCH with null name and valid description → 200 updates description only

- GIVEN an existing project owned by the user
- WHEN PATCH /projects/{id} with { "name": null, "description": "New desc" }
- THEN response is 200
- AND project description is updated
- AND project name remains unchanged

#### Scenario: PATCH with both fields null → 422

- GIVEN an existing project owned by the user
- WHEN PATCH /projects/{id} with { "name": null, "description": null }
- THEN response is 422 with error code "NO_FIELDS_TO_UPDATE"
- AND detail "No valid fields provided for update"

#### Scenario: PATCH with valid name and null description → 200 updates name only

- GIVEN an existing project owned by the user
- WHEN PATCH /projects/{id} with { "name": "New Name", "description": null }
- THEN response is 200
- AND project name is updated
- AND project description remains unchanged

### Requirement: Organization not found returns clean 404

The system **MUST** return a clean 404 with error code "ORG_NOT_FOUND" when the user's organization does not exist.

(Previously: ORG_NOT_FOUND returned 404 but error detail was generic; now standardized)

#### Scenario: Create project when org doesn't exist → 404 ORG_NOT_FOUND

- GIVEN an authenticated user whose organization was deleted
- WHEN POST /projects with valid data
- THEN response is 404 with error code "ORG_NOT_FOUND"
- AND detail "Organization not found"

#### Scenario: Any project endpoint with missing org → 404 ORG_NOT_FOUND

- GIVEN an authenticated user whose organization was deleted
- WHEN GET /projects or GET /projects/{id} or PATCH /projects/{id} or DELETE /projects/{id}
- THEN response is 404 with error code "ORG_NOT_FOUND"

## ADDED Requirements

### Requirement: Integration test coverage for projects CRUD edge cases

The system **SHOULD** have automated tests covering all error paths and edge cases for project endpoints.

#### Scenario: Test suite covers min-length validation

- GIVEN test environment with authenticated user
- WHEN running tests for project creation/update
- THEN tests verify 422 for names < 3 chars
- AND tests verify 201/200 for names ≥ 3 chars

#### Scenario: Test suite covers PATCH null handling

- GIVEN test environment with existing project
- WHEN running PATCH tests
- THEN tests verify null fields are ignored
- AND tests verify 422 when all fields null

#### Scenario: Test suite covers ORG_NOT_FOUND

- GIVEN test environment with user without organization
- WHEN running project endpoint tests
- THEN tests verify 404 ORG_NOT_FOUND on all endpoints

#### Scenario: Test suite covers cross-tenant 404

- GIVEN two organizations with projects
- WHEN user from org A accesses project from org B
- THEN tests verify 404 (not 403) on GET/PATCH/DELETE

#### Scenario: Test suite covers free tier limit

- GIVEN free tier org with 3 existing projects
- WHEN attempting to create 4th project
- THEN tests verify 403 FREE_TIER_LIMIT