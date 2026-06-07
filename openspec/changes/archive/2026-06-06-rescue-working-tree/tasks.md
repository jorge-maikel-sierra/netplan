# Tasks: Rescue Working Tree

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~555 (460 additions + 95 deletions) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR (code already exists — rescue only) |
| Delivery strategy | ask-on-risk |
| Chain strategy | size-exception |

Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Git rescue (4 commits) + deps cleanup | Single PR | All code exists uncommitted; low cognitive load |
| 2 | Verification | Same PR | Included in same PR as rescue |

## Phase 1: Git Rescue — Commit existing code in logical units

- [x] **T-01-01** — Add `.atl/` entry to `.gitignore` (1 line). Verify: `grep ".atl/" .gitignore` matches
- [x] **T-01-02** — Stage `supabase-schema.sql` + `.gitignore`, commit as `feat: Add database schema and gitignore cleanup`. Verify: `git log --oneline -1` shows the message
- [x] **T-01-03** — Stage `backend/app/services/excel_service.py`, commit as `feat: Add Excel node import service with validation`. Verify: file exists in HEAD
- [x] **T-01-04** — Stage `backend/app/routers/nodes.py`, `backend/app/routers/edges.py`, `backend/app/main.py`, commit as `feat: Add nodes and edges CRUD routers with tenant isolation`. Verify: 3 commits visible

## Phase 2: Dependency Cleanup — Strip AI/Azure cruft

- [x] **T-02-01** — Create temp venv (`/tmp/netplan-clean-venv`), install pinned deps from design.md, `pip freeze > backend/requirements.txt`. Clean up temp venv afterwards
- [x] **T-02-02** — Verify no residual cruft: `grep -i -E "azure-|openai|langchain|torch|transformers|llm" backend/requirements.txt` returns empty
- [x] **T-02-03** — Stage `backend/requirements.txt`, commit as `chore: Strip AI/Azure cruft from requirements.txt to essential deps only`. Verify: 4 commits total in log

## Phase 3: Verification — Prove the tree works

- [x] **T-03-01** — Clean install: `pip install -r backend/requirements.txt` in a fresh venv exits 0 with no errors
- [x] **T-03-02** — App starts: `uvicorn app.main:app --port 9999` logs no ImportError; `GET /healthz` returns `{"status":"ok"}` 200
- [x] **T-03-03** — Router registration: `GET /api/v1/projects` returns 401 (not 500/404), proving projects/nodes/edges routers are wired
- [x] **T-03-04** — Tree clean: `git status --short` shows no uncommitted changes
- [x] **T-03-05** — No residual cruft in installed packages: `pip list | grep -i -E "azure|openai|langchain"` returns empty

## Rollback

If any verification step fails: `git reset --soft HEAD~4` to uncommit all; `git restore backend/requirements.txt` to recover. Re-run the failed phase after fixing.

## Files Affected

| File | Action |
|------|--------|
| `.gitignore` | Modified (+1 line) |
| `supabase-schema.sql` | Created (120 lines) |
| `backend/app/services/excel_service.py` | Created (136 lines) |
| `backend/app/routers/nodes.py` | Created (106 lines) |
| `backend/app/routers/edges.py` | Created (74 lines) |
| `backend/app/main.py` | Modified (+3/-1) |
| `backend/requirements.txt` | Rewritten (~20 lines from ~95) |
