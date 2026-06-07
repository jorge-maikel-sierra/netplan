# Spec: Testing Infrastructure (pytest-bootstrap)

## Purpose

Provide a repeatable, fast (<2s) test harness for the backend that mocks all Supabase IO, enforces coverage, and validates basic app bootstrap. Every backend change after this SHALL pass `pytest` before commit.

## Requirements

### REQ-TEST-001: Test infrastructure

The system MUST have a working pytest setup with async support (`asyncio_mode = auto`) and code coverage reporting.

#### Scenario: pytest discovers all tests

- GIVEN the `backend/tests/` directory tree with `test_*.py` files
- WHEN `pytest --collect-only --quiet` runs from `backend/`
- THEN all test functions/coroutines are collected
- AND the count is ≥ 20 (current: 9 unit + 11 integration)

#### Scenario: Coverage report generates

- GIVEN pytest-cov is installed
- WHEN `pytest --cov=app --cov-report=term` runs
- THEN a coverage table prints with per-module percentages
- AND the command exits 0

#### Scenario: Tests complete in <2s

- GIVEN the full test suite
- WHEN `pytest -q` runs
- THEN wall-clock time is under 2 seconds
- AND all tests pass

### REQ-TEST-002: Shared fixtures

The system MUST provide a `conftest.py` at `backend/tests/` with reusable fixtures that eliminate IO in tests.

#### Scenario: mock_supabase_client fixture

- GIVEN a test requires database access
- WHEN the test requests `mock_supabase_client`
- THEN a `MagicMock` is injected that mimics the supabase-py fluent chain (`.table().select().eq().execute().data`)
- AND no real network calls are made

#### Scenario: test_app with dependency overrides

- GIVEN a test requires the full FastAPI app
- WHEN the test requests `test_app`
- THEN `get_current_user` returns a dict with `user_id` and `org_id` from `SAMPLE_UUIDS`
- AND `get_supabase_client` returns the `mock_supabase_client` mock

#### Scenario: test_user_token fixture

- GIVEN a test needs a JWT string
- WHEN the test requests `test_user_token`
- THEN a signed HS256 JWT is returned with `sub` and `organization_id` claims matching `SAMPLE_UUIDS`

#### Scenario: sample_uuids fixture

- GIVEN any test
- WHEN the test requests `sample_uuids`
- THEN a stable dict of UUIDs is returned for org, user, project, nodes, and edges
- AND values are deterministic across test runs

#### Scenario: client fixture for HTTP calls

- GIVEN a test needs to make HTTP requests
- WHEN the test requests `client`
- THEN an `httpx.AsyncClient` bound to `test_app` via ASGI transport is yielded
- AND the transport avoids any real networking

### REQ-TEST-003: Smoke tests for app bootstrap

The system MUST have smoke tests that prove the FastAPI app boots correctly and all routers are registered. These tests SHALL run with zero configuration (no `.env` required).

#### Scenario: Health endpoint returns 200

- GIVEN the `test_app` fixture
- WHEN a GET request is sent to `/healthz`
- THEN the response is 200
- AND the body is `{"status": "ok"}`

#### Scenario: Protected endpoint returns 401 without auth

- GIVEN the `test_app` fixture with `get_current_user` overridden to raise 401
- WHEN a GET request is sent to `/api/v1/projects`
- THEN the response is 401
- AND the body contains `error: "INVALID_TOKEN"`

#### Scenario: All routers are registered

- GIVEN the `test_app` fixture
- WHEN inspecting `app.routes`
- THEN routes exist for: `/api/v1/projects`, `/api/v1/projects/{id}/nodes`, `.../edges`, `.../mst/calculate`, `.../mst/latest`
- AND the `/healthz` route also exists outside the API prefix

### REQ-TEST-004: Dependency management

The system MUST declare all test dependencies explicitly in `requirements.txt`.

#### Scenario: pytest-cov is listed

- GIVEN the `requirements.txt` file
- WHEN checked for `pytest-cov`
- THEN it MUST be present
- AND `pip install` succeeds

## Out of Scope

- Full integration tests against real Supabase (use mocked conftest)
- Frontend tests (no vitest installed; separate change)
- E2E tests or Playwright (separate change)
- Testing every endpoint in detail (covered by per-domain specs)
