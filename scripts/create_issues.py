#!/usr/bin/env python3
"""Create bug/refactor issues in Forgejo for TaskManager code review findings."""

import json
import os

FORGEJO_TOKEN = os.environ.get("FORGEJO_TOKEN")
FORGEJO_URL = os.environ.get("FORGEJO_URL", "http://10.0.10.30:3000")
BASE = f"{FORGEJO_URL}/api/v1/repos/Chris/TaskManager/issues"

# Label IDs (created earlier)
LABELS = {
    "bug": 13,
    "backend": 11,
    "frontend": 12,
    "refactor": 8,
    "tech-debt": 9,
    "quick-win": 10,
}

# Milestone IDs
MILESTONES = {
    "phase1": 9,   # Phase 1 — Foundation & Core
    "phase2": 10,  # Phase 2 — Views & Organization
    "phase3": 11,  # Phase 3 — Polish & Export
}

ISSUES = [
    {
        "title": "bug: FTS5 keyword search for tasks is dead - index never populated",
        "labels": ["bug", "backend"],
        "milestone": "phase1",
        "body": """## Problem

FTS5 keyword search for tasks is completely dead. The `register_fts5_hooks` function only fires if `create_app()` reaches it, but `register_embedding_hooks` calls `warmup_model()` which crashes before FTS5 hooks are registered. Even if embedding worked, tasks created after a crash wouldn't be indexed.

The search view queries `search_index MATCH ?` for tasks, but nothing ever populates that virtual table with task data.

## Root Cause

- `register_embedding_hooks(app)` calls `warmup_model()` which crashes
- If it doesn't crash, `_flush_fts5` runs on `after_commit` - but only for tasks created *after* the hooks register
- No initial population of FTS5 from existing tasks

## Fix

1. Register FTS5 hooks independently of embedding hooks (move before or separate from embedding)
2. Add an `init_fts5_index()` function that backfills existing tasks into the FTS5 virtual table
3. Call `init_fts5_index()` in `init_extensions` after creating the FTS5 table

## Relevant Files

- `app/extensions.py` - `init_extensions` creates FTS5 table but doesn't populate it
- `app/services/embedding.py` - `register_fts5_hooks` and `_flush_fts5`
- `app/__init__.py` - `create_app()` calls hooks in sequence
""",
    },
    {
        "title": "bug: No 'Related Captures' anywhere - semantic search broken, no FTS5 fallback",
        "labels": ["bug", "backend"],
        "milestone": "phase1",
        "body": """## Problem

The SPEC calls for "Related Captures" on project pages, task detail pages, and the dashboard. None exist because:

1. The embedding model crashes Python (see #1)
2. `related_captures = []` is hardcoded in both detail views
3. No FTS5 fallback even if we wanted one

The UI templates have `{% if related_captures %}` blocks that will never render.

## Fix

1. Add a FTS5-based "Related Captures" function that searches inbox items (project_id IS NULL) against the current project/task keywords
2. Wire it into project detail and task detail views
3. Add the section to the dashboard template

This gives useful suggestions even without semantic search.

## Relevant Files

- `app/views/projects/__init__.py` - `related_captures = []` hardcoded
- `app/views/tasks/__init__.py` - `related_captures = []` hardcoded
- `app/templates/projects/detail.html` - `{% if related_captures %}` block
- `app/templates/tasks/detail.html` - `{% if related_captures %}` block
- `app/templates/index.html` - no related suggestions section at all
""",
    },
    {
        "title": "bug: Inbox summary bar link points to nonexistent filter /tasks?status=inbox",
        "labels": ["bug", "frontend"],
        "milestone": "phase1",
        "body": """## Problem

The dashboard summary bar has a link to `/tasks?status=inbox`, but there is no status called "inbox". The inbox is defined as tasks with `project_id IS NULL`. Clicking the Inbox count in the summary bar goes to an empty task list.

## Fix

Either:
A) Add a special case in the task list view for `status=inbox` that filters on `project_id IS NULL`, or
B) Change the link to `/tasks?project_id=` (empty = inbox)

Option A is cleaner since it keeps the summary bar consistent with the other status links.

## Relevant Files

- `app/templates/index.html` - summary bar link
- `app/views/tasks/__init__.py` - `list_tasks` filter logic
""",
    },
    {
        "title": "bug: Gantt bars are single-day pins when start_date is null",
        "labels": ["bug", "frontend"],
        "milestone": "phase2",
        "body": """## Problem

The Gantt view uses `start_date` for the bar start, but `start_date` is nullable. When it's null, the fallback in the view is `due_date`, making every task without a start_date render as a single-day pin instead of a bar.

The board serializes tasks without `start_date` either, so the Gantt can't distinguish between "no start date" and "same start and end date."

## Fix

1. In the Gantt view, if `start_date` is null, default to `due_date - 7 days` (or some reasonable span)
2. Serialize `start_date` in the board view's task_data so it's available everywhere
3. Consider showing a visual indicator when start_date is estimated vs actual

## Relevant Files

- `app/views/main.py` - `gantt()` serializes tasks, board serializes without start_date
- `app/templates/gantt.html` - Gantt rendering logic
""",
    },
    {
        "title": "bug: Project edit JS breaks if project name contains a single quote",
        "labels": ["bug", "frontend"],
        "milestone": "phase1",
        "body": """## Problem

The project detail page uses template string interpolation for Alpine.js data:

```javascript
name: '{{ project.name | e }}',
description: `{{ project.description or '' | e }}`,
```

If the project name contains a single quote (e.g., "Chris's Project"), the JavaScript breaks with a SyntaxError. The task detail page does it correctly using `<script type="application/json">` + `tojson`.

## Fix

Use the same pattern as task detail: serialize to JSON in a script tag, then parse in Alpine.

```html
<script type="application/json" id="project-data">{{ { 'name': project.name, ... } | tojson }}</script>
```

## Relevant Files

- `app/templates/projects/detail.html` - `projectForm()` Alpine component
""",
    },
    {
        "title": "tech-debt: Dates stored as strings instead of Date type",
        "labels": ["tech-debt", "backend"],
        "milestone": "phase1",
        "body": """## Problem

Every date field (`start_date`, `due_date`, `recurrence_end`) is `String(10)` instead of `Date`. This means:

- Date comparisons in filters are string comparisons (happens to work for YYYY-MM-DD, but is fragile)
- No timezone awareness
- The `_generate_recurring_events` function has to `strptime`/`strftime` manually
- SQLite can't use date functions natively

## Fix

1. Change model columns from `String(10)` to `Date`
2. Run an Alembic migration (or manual migration script)
3. Update all views that do string comparisons on dates
4. Update templates that format dates

This is a moderate-risk refactor since it touches many files, but the risk is low because YYYY-MM-DD string comparison is equivalent to date comparison in most cases.

## Relevant Files

- `app/models.py` - Task and Project date fields
- `app/views/main.py` - `_generate_recurring_events` uses strptime
- All templates that reference date fields
""",
    },
    {
        "title": "tech-debt: No CSRF protection on any POST/PATCH/DELETE route",
        "labels": ["tech-debt"],
        "milestone": "phase1",
        "body": """## Problem

Every POST/PATCH/DELETE route accepts requests without CSRF tokens. For a "solo user, zero auth" app this is lower risk, but if you ever run this on a shared network or behind a reverse proxy accessible from the internet, XSS could let anyone manipulate your data.

## Fix

1. Add Flask-WTF or a simple custom CSRF token
2. Include CSRF token in all forms and AJAX requests
3. Validate on all mutation endpoints

## Relevant Files

- All view files with POST/PATCH/DELETE routes
""",
    },
    {
        "title": "tech-debt: get_descendant_ids() is N+1 - use recursive CTE instead",
        "labels": ["tech-debt", "backend"],
        "milestone": "phase1",
        "body": """## Problem

`Project.get_descendant_ids()` loads all children eagerly in a loop, then recurses. With deep nesting this becomes O(n^2) queries. A single CTE query would be O(n):

```sql
WITH RECURSIVE descendants(id) AS (
    VALUES (?) UNION ALL
    SELECT p.id FROM projects p JOIN descendants d ON p.parent_id = d.id
) SELECT id FROM descendants;
```

## Fix

Replace the Python recursion with a raw SQL CTE or SQLAlchemy expression.

## Relevant Files

- `app/models.py` - `Project.get_descendant_ids()` and `is_ancestor_of()`
""",
    },
    {
        "title": "tech-debt: warmup_model() blocks create_app() - first request hangs 5-10s",
        "labels": ["tech-debt", "backend"],
        "milestone": "phase1",
        "body": """## Problem

The embedding model loads synchronously during app startup via `warmup_model()` in `register_embedding_hooks`. This means every request (including `flask run --reload`) triggers a ~300MB model download/load on first boot. The first request hangs for 5-10 seconds while the model downloads from HuggingFace.

## Fix

1. Move model loading to a lazy singleton (already partially done via `get_model()`)
2. Remove `warmup_model()` from `register_embedding_hooks`
3. Optionally add a background thread that warms up the model after startup
4. Add a UI indicator when semantic search is "warming up"

## Relevant Files

- `app/services/embedding.py` - `warmup_model()` and `register_embedding_hooks`
- `app/__init__.py` - `create_app()` calls hooks
""",
    },
    {
        "title": "refactor: export_csv duplicates ~60 lines of filter/sort logic from list_tasks",
        "labels": ["refactor", "backend"],
        "milestone": "phase3",
        "body": """## Problem

The CSV export rebuilds the exact same query from scratch as `list_tasks`. Any filter added to `list_tasks` must be manually added to `export_csv`. This is a maintenance hazard.

## Fix

Extract the shared query-building logic into `_build_task_query(app, **kwargs)` and use it in both `list_tasks` and `export_csv`.

## Relevant Files

- `app/views/tasks/__init__.py` - `list_tasks()` and `export_csv()`
""",
    },
    {
        "title": "refactor: Dashboard runs 5 separate queries instead of one",
        "labels": ["refactor", "backend"],
        "milestone": "phase1",
        "body": """## Problem

The dashboard issues 5 independent SELECTs (on_fire, delegated, active, backlog, inbox). With a large task table this is wasteful - one query with a CASE expression could do it all and let Python sort into the lists.

## Fix

Replace the 5 queries with a single `Task.query.all()` (or filtered query) and partition in Python. The overhead of loading all tasks once is less than 5 separate scans.

## Relevant Files

- `app/views/main.py` - `index()` view function
""",
    },
    {
        "title": "refactor: list_projects computes task counts in Python instead of SQL",
        "labels": ["refactor", "backend"],
        "milestone": "phase1",
        "body": """## Problem

```python
for p in projects:
    p.task_count = len(p.tasks)
    done = sum(1 for t in p.tasks if t.status == "done")
```

This loads all tasks for all projects into memory. A `func.count()` with `group_by` would be much faster with many projects.

## Fix

Use a correlated subquery or GROUP BY to compute task_count and completion_pct in SQL.

## Relevant Files

- `app/views/projects/__init__.py` - `list_projects()`
""",
    },
    {
        "title": "tech-debt: No pagination anywhere in the app",
        "labels": ["tech-debt"],
        "milestone": "phase3",
        "body": """## Problem

The task list, project list, search results - none are paginated. With 1000+ tasks the list view will render thousands of table rows in one response. The search view has `limit(50)` but the task list doesn't.

## Fix

1. Add pagination to the task list view (most impactful)
2. Add pagination to project list
3. Consider virtual scrolling for the board view instead

## Relevant Files

- `app/views/tasks/__init__.py` - `list_tasks()`
- `app/views/projects/__init__.py` - `list_projects()`
- `app/views/main.py` - `board()`
""",
    },
    {
        "title": "frontend: No feedback when inline saves fail silently",
        "labels": ["frontend"],
        "milestone": "phase3",
        "body": """## Problem

The task detail `save()` function does `location.reload()` on success but only shows an `alert()` on error. If the network is flaky, you might lose edits without noticing. The board's drag-and-drop and status change have the same issue.

## Fix

1. Add a toast/notification system (simple Alpine component)
2. Show success toasts briefly, error toasts persist until dismissed
3. Replace `alert()` calls with toast errors
4. Consider optimistic updates instead of reload on save

## Relevant Files

- `app/templates/tasks/detail.html` - `taskForm().save()`
- `app/templates/board.html` - `board().changeStatus()` and `onDrop()`
""",
    },
    {
        "title": "frontend: Board drag-and-drop has no undo",
        "labels": ["frontend"],
        "milestone": "phase2",
        "body": """## Problem

Drop a card in the wrong column - status changes instantly via PATCH. No way to reverse it except manually editing the task again.

## Fix

1. Store previous status before the PATCH
2. Add an "Undo" toast that appears briefly after a drag-drop
3. If clicked, revert to previous status

## Relevant Files

- `app/templates/board.html` - `board().onDrop()`
""",
    },
    {
        "title": "frontend: Overdue indicator is client-side only (board), missing from list and project views",
        "labels": ["frontend"],
        "milestone": "phase2",
        "body": """## Problem

The `isOverdue()` function in the board runs in Alpine.js, but the list view and project detail have no overdue highlighting at all. A task due yesterday looks identical to one due tomorrow in those views.

## Fix

1. Add overdue highlighting to the task list view (red text or icon on due_date column)
2. Add overdue highlighting to the project detail task list
3. Consider adding a filter for "overdue" tasks

## Relevant Files

- `app/templates/tasks/list.html` - task table rendering
- `app/templates/projects/detail.html` - task list rendering
""",
    },
    {
        "title": "quick-win: Add keyboard shortcut (Ctrl+K or /) to open capture modal",
        "labels": ["quick-win", "frontend"],
        "milestone": "phase3",
        "body": """## Problem

The SPEC says "capture in under 5 seconds." But you still need to: 1) click "+ New", 2) type title, 3) click Save. A global keyboard shortcut would actually hit that 5-second goal.

## Fix

Add a keydown listener on the document that opens the capture modal when the user presses `Ctrl+K` or `/`. Close with `Escape` (already works for modals).

## Relevant Files

- `app/templates/base.html` - add global keydown handler
""",
    },
    {
        "title": "tech-debt: Log FTS5 inserts use wrong schema (rowid, content) vs task schema (task_id, title, description, tags_text)",
        "labels": ["tech-debt", "backend"],
        "milestone": "phase1",
        "body": """## Problem

The log creation views insert into FTS5 using:

```python
conn.execute("INSERT INTO search_index(rowid, content) VALUES (?, ?)", ...)
```

But the FTS5 table was created with columns `task_id UNINDEXED, title, description, tags_text`. The log inserts are using a completely different schema and will fail silently (wrapped in try/except).

This means log keyword search via FTS5 never works - it falls back to ilike on Log.title and Log.notes.

## Fix

1. Either create a separate FTS5 table for logs, or
2. Add logs to the existing search_index using the correct column names (use title/description columns)
3. Remove the try/except swallowing so these errors are visible

## Relevant Files

- `app/views/logs/__init__.py` - `create_project_log()` and `create_task_log()` FTS5 inserts
- `app/extensions.py` - FTS5 table creation
""",
    },
]


def create_issue(title, body, labels, milestone):
    payload = {
        "title": title,
        "body": body,
        "labels": [LABELS[l] for l in labels],
        "milestone": MILESTONES[milestone],
    }

    req = __import__("urllib.request").request.Request(
        BASE,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"token {FORGEJO_TOKEN}",
        },
        method="POST",
    )
    resp = __import__("urllib.request").request.urlopen(req)
    result = json.loads(resp.read())
    print(f"Created #{result['number']}: {title}")
    return result


if __name__ == "__main__":
    for issue in ISSUES:
        create_issue(
            issue["title"],
            issue["body"],
            issue["labels"],
            issue["milestone"],
        )
