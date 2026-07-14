# Session Notes — TaskManager

Last updated: 2026-07-14

## Completed Work

### 2026-07-14 (this session)
- **Full pytest suite**: 165 tests across 6 test files, all passing. Tests skip embedding hooks (crash), manually recreate FTS5/vec0 after drop. Key fixtures: `app`, `client`, `populated_db` (session-scoped, temp SQLite DB).
- **Code review**: Thorough review of entire app (source + templates). Identified 18 issues spanning bugs, tech debt, refactors, and frontend improvements.
- **18 Forgejo issues filed**: #30–#47, properly labeled and milestone'd. Labels created on repo: bug, backend, frontend, refactor, tech-debt, quick-win.

### 2026-07-12 (prior session)
- **#14**: Tag input on task detail
- **#15**: Links on tasks — URL + label pairs
- **#16**: Logs CRUD on projects and tasks
- **#17**: Project nesting with circular ref prevention
- **#19**: CSV export
- **#20**: Dashboard polish
- **#21**: Hybrid search (FTS5 + sqlite-vec)
- **#11**: Board view — Kanban with drag-and-drop

### 2026-07-11 (prior session)
- Initial app scaffolding, models, basic CRUD, dashboard

## Next Actionable Items

1. **Fix #30** — FTS5 keyword search for tasks is dead (register hooks independently of embedding, backfill existing tasks)
2. **Fix #34** — Project edit JS breaks on single quotes in project name (use script tag + tojson pattern)
3. **Fix #32** — Inbox summary bar link points to nonexistent filter
4. **Fix #47** — Log FTS5 inserts use wrong schema
5. **Fix #31** — Add FTS5-based "Related Captures" fallback
6. Work through remaining issues in priority order

## Open Issues (from prior sessions, still not started)
- **#12**: Calendar view
- **#13**: Gantt view
- **#18**: Gantt PDF export
- **#23**: Portable Python packaging

## Test Baseline

- 165 tests passing as of 2026-07-14
- Run: `cd /Volumes/DevEnvironment/projects/TaskManager && source .venv/bin/activate && python -m pytest tests/`
- Tests use a temp SQLite DB, skip embedding hooks, manually recreate FTS5/vec0 virtual tables

## Notes

- **Embedding model crashes Python** — sentence-transformers `warmup_model()` causes crashes. All semantic search features are disabled. This is the #1 blocker for Phase 1 completion.
- **App may be running on port 5000** — kill it: `lsof -ti:5000 | xargs kill -9`
- **Flask debug reloader doesn't watch templates** — touch a Python file or restart manually after template edits
