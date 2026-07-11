# TaskManager — Specification

*A personal project management tool for a solo PM. Built for one brain, one workflow — and every decision reflects that.*

---

## The Problem It Solves

You're transitioning from "doer" to "orchestrator." You need visibility into what's on fire, what's blocked, what your team is working on, and what needs your attention — all in one screen. Previous attempts (TaskManagementPro, ForgeTrack, foax) each solved part of the problem but were built for the wrong role:

- **TaskManagementPro** — built for agent orchestration (you're not doing that anymore)
- **ForgeTrack** — built for enterprise multi-user (you're a solo user)
- **foax** — built as a Neovim plugin (you want web)

This is the tool you actually need right now: fast capture, automatic organization via semantic search, and a dashboard that tells you what matters.

---

## Core Philosophy

- **Capture in under 5 seconds.** If creating an item takes more than one field + one click, it won't happen.
- **The system organizes for you.** You don't triage later — you never triage. Semantic search surfaces connections automatically.
- **Status with teeth.** Five states, nothing ambiguous. A task is either backlog, being worked on, stuck, or done.
- **Solo user, zero auth.** No login, no RBAC, no audit trails. You're the only user. Everyone else is a name in an "assignee" field.
- **Local first, always.** SQLite database. No cloud, no subscriptions, no accounts. Portable Python deployment on corporate Windows machines.
- **Enter at any level.** A thought doesn't need a project. A task doesn't need a priority. Assign later or never.

---

## Terminology

| Term | Meaning |
|---|---|
| **Project** | A high-level container for related work. Nestable (parent/child). |
| **Task** | A unit of work. Can be a full task with status/priority or just a captured thought. |
| **Capture** | A raw thought saved to the inbox. Gets embedded for semantic search. Promoted to a task by filling in fields — same form, no separate flow. |
| **Log** | A structured note attached to a project or task. Meeting notes, decisions, blockers. Never standalone. |
| **Inbox** | The default home for all captures. The system surfaces related items via semantic search — you never manually organize. |

---

## Data Model

### Project

| Field | Type | Required | Notes |
|---|---|---|---|
| id | Integer (PK) | Yes | Auto-increment |
| name | String(200) | Yes | Display name |
| description | Text | No | Optional details |
| color | String(7) | No | Hex color for visual distinction, default auto-assigned |
| parent_id | Integer (FK → Project.id) | No | Self-referencing for nesting. NULL = top-level. |
| created_at | DateTime | Yes | Auto-set on creation |
| updated_at | DateTime | Yes | Auto-updated on changes |

### Task

| Field | Type | Required | Notes |
|---|---|---|---|
| id | Integer (PK) | Yes | Auto-increment |
| title | String(500) | Yes | The core content — always required |
| description | Text | No | Optional details |
| status | String(20) | Yes | Default: `backlog`. Values: `backlog`, `active`, `blocked`, `delegated`, `done` |
| priority | String(5) | No | Values: `P0`, `P1`, `P2`. NULL = no priority set. |
| due_date | Date | No | Optional deadline |
| assignee | String(100) | No | Name of person responsible (you or someone else). Free text. |
| project_id | Integer (FK → Project.id) | No | NULL = unassigned / inbox |
| tags | JSON | No | Array of strings. Stored as JSON in SQLite. |
| links | JSON | No | Array of objects: `{url, label}`. For attachments/external references. |
| created_at | DateTime | Yes | Auto-set on creation |
| updated_at | DateTime | Yes | Auto-updated on changes |
| completed_at | DateTime | No | Set when status changes to `done` |

### Log

| Field | Type | Required | Notes |
|---|---|---|---|
| id | Integer (PK) | Yes | Auto-increment |
| title | String(500) | Yes | Brief summary of the log entry |
| notes | Text | No | Full content — meeting notes, decisions, etc. |
| task_id | Integer (FK → Task.id) | Conditional | Set if attached to a task. NULL if attached to project. |
| project_id | Integer (FK → Project.id) | Conditional | Set if attached to a project. NULL if attached to task. One of task_id or project_id must be set. |
| created_at | DateTime | Yes | Auto-set on creation |
| updated_at | DateTime | Yes | Auto-updated on changes |

### Capture (semantic search index)

All tasks are indexed for semantic search. There is no separate "capture" table — a capture is simply a task with only the title filled in, and no project assigned. The inbox view shows all unassigned tasks.

The embedding vector is stored alongside the task:

| Field | Type | Notes |
|---|---|---|
| embedding | REAL[] (sqlite-vec) | 384-dim float array from all-MiniLM-L6-v2 |

FTS5 virtual table indexes: title, description, notes (from logs), tags — for keyword search.

---

## Status Model

Five states, nothing ambiguous:

| Status | Meaning | Dashboard Section |
|---|---|---|
| **backlog** | Captured, not yet committed to. Default state. | Backlog |
| **active** | Being worked on right now (by you). | My Active Work |
| **blocked** | Can't proceed — waiting on something external. | On Fire |
| **delegated** | Assigned to someone else, they're working on it. | Delegated |
| **done** | Finished. | (hidden from dashboard) |

---

## Views

### Dashboard (Home Screen)

Grouped by action needed, not by project. What you see in the first 5 seconds:

1. **🔴 On Fire** — P0 tasks + all blocked tasks
2. **👤 Delegated** — tasks delegated to others, grouped by assignee
3. **⚡ My Active Work** — tasks with status `active` and assignee = you (or unassigned)
4. **📋 Backlog** — remaining tasks, sorted by priority then due date
5. **📥 Inbox** — unassigned captures (no project), with count as a nudge
6. **🔗 Related Suggestions** — semantically related captures surfaced on the dashboard

Each section shows task cards with: title, status badge, priority badge, assignee, due date. Click to open detail.

### List View

Sortable, filterable table:

| Title | Status | Priority | Assignee | Due Date | Project |
|---|---|---|---|---|---|

Filters: status, priority, project, assignee, tags, date range. Sortable by any column.

### Board View

Kanban columns matching the 5 statuses: backlog / active / delegated / blocked / done. Cards show title, priority badge, assignee. Click card to open detail. Drag-and-drop between columns to change status.

### Gantt View

Timeline view showing tasks with due dates as bars on a calendar timeline. Grouped by project. Read-heavy — for stakeholder reporting, not daily editing. Exportable as PDF or clean HTML.

### Calendar View

Month/week/day calendar showing tasks by due date. Color-coded by status. Click a date to see what's due. Good for planning and spotting deadline clusters.

### Projects Page

Grid of project cards showing: name, color indicator, task count by status, completion percentage. Nesting shown via indentation or visual hierarchy. Click a project to drill into its tasks (list/board/Gantt views within the project context).

Each project page also shows:
- The project's logs (chronological)
- Related captures from the inbox (semantic suggestions)

### Task Detail

Full task view with all fields editable inline:
- Title, description, status, priority, due date, assignee, tags, links
- Associated logs (chronological list, add new log button)
- Related captures (semantic suggestions from inbox)

---

## Capture Flow

**One form. No modes. Fill what you need, save.**

Prominent "New" button in the header (always visible). Click → modal:

```
┌─────────────────────────────────────────────┐
│  ✕                                          │
│  New                                        │
│                                             │
│  Title *                                    │
│  ┌───────────────────────────────────────┐  │
│  │                                       │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Description                                │
│  ┌───────────────────────────────────────┐  │
│  │                                       │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Status: backlog ▼   Priority: — none — ▼  │
│  Due date: [date picker]                    │
│  Assignee: [text field]                     │
│  Project: — none — ▼                        │
│  Tags: [tag input]                          │
│  Links: [url + label input, repeatable]     │
│                                             │
│                    [Cancel]      [Save]     │
└─────────────────────────────────────────────┘
```

- **Quick capture:** Type title → Save. Done. Under 5 seconds.
- **Full task:** Fill whatever fields matter → Save. Done.
- No separate "promote" flow. It's always just "Save."

After saving, the embedding model processes the title + description in the background (~200ms). You don't notice it.

---

## Semantic Search & Suggestions

### How It Works

1. On save, the task's title + description are embedded using `all-MiniLM-L6-v2` (384-dim vector) via sqlite-vec
2. FTS5 indexes title, description, tags for keyword search
3. When viewing a project or task, related captures are surfaced by:
   - **Semantic similarity** — cosine distance against the project's task embeddings
   - **Keyword overlap** — FTS5 match against project name + task titles

### Where Suggestions Appear

- **Project page** — "Related captures" section showing inbox items semantically related to this project
- **Task detail** — same, scoped to the task's content
- **Dashboard** — a small "suggestions" section at the bottom
- **Global search** — hybrid keyword + semantic search with combined scoring

### Implementation Notes

Stolen from ProjectBrain:
- `sqlite-vec` for vector storage and ANN search
- `sentence-transformers` with `all-MiniLM-L6-v2` for embedding generation
- FTS5 virtual table for keyword search
- Hybrid scoring: combine semantic similarity (0-1) and keyword rank (normalized 0-1), weighted 60/40

---

## Global Search

Search bar in the header, always accessible. Searches across:
- Task titles, descriptions, tags
- Log titles and notes
- Project names and descriptions

Two modes:
- **Keyword** (default) — FTS5 full-text match
- **Semantic** — toggle for natural language search ("find things about SOC modernization")

Results show: type icon (task/log/project), title, snippet, relevance score.

---

## Export / Reporting

### Gantt Export

The Gantt view can be exported as a clean HTML page or PDF — suitable for sharing with stakeholders. No login required to view the exported file.

### Task List Export

List view can be exported as CSV — all visible columns, current filters applied.

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | Flask + Flask-SQLAlchemy | Known quantity, fast for solo apps |
| Database | SQLite + sqlite-vec + FTS5 | Zero infra, semantic search built in, portable |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Proven in ProjectBrain, 384-dim, fast |
| Frontend templating | Jinja2 | Server-rendered, no build step |
| CSS | Tailwind CSS (via CDN or local) | Utility-first, fast to build |
| JS interactivity | Alpine.js | 5KB, reactive modals/inline edits, no build step |
| Gantt chart | Mermaid.js | Server-rendered timeline diagrams |
| Calendar | FullCalendar | Proven, works with Flask |
| PDF export | WeasyPrint or wkhtmltopdf | Server-side PDF generation |

---

## Deployment

### Development (Mac)

```bash
cd TaskManager
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask run
```

Access at `http://localhost:5000`.

### Production (Corporate Windows 11)

Portable Python deployment — no installation, no admin rights:

1. Download Python embeddable zip from python.org (~10MB)
2. Extract to `%APPDATA%\Local\TaskManager\`
3. Copy app files into the same directory
4. Install dependencies: `python.exe -m pip install -r requirements.txt`
5. Run: `python.exe app.py`

Access at `http://localhost:5000`. Entire app lives in user profile — no system-level changes.

The total package (Python + app + dependencies) should be under 50MB, splittable into two email attachments if needed (25MB limit).

---

## What This Is Not

- Not a SaaS product
- Not for anyone else (multi-user is out of scope)
- Not an agent orchestration tool
- Not enterprise-grade (no auth, no RBAC, no audit trails)
- Not a replacement for Jira — it's a replacement for the pile of sticky notes and half-finished spreadsheets

---

## Out of Scope (For Now)

- Real-time collaboration / WebSockets
- Email notifications on task changes
- Status update forms sent to team members (Teams/Email integration)
- File attachments (links only — URLs with labels)
- Mobile app / PWA
- Multi-user / authentication

These can be added later. The core must work first.

---

## Build Phases

### Phase 1 — Foundation & Core (Week 1)

**Goal:** App runs, you can create projects and tasks, capture thoughts, see the dashboard.

- [ ] Project scaffolding (Flask app, SQLite schema, Tailwind + Alpine setup)
- [ ] Database models: Project, Task, Log
- [ ] sqlite-vec + FTS5 setup (embedding on save)
- [ ] CRUD: Projects (create, list, detail, update, delete)
- [ ] CRUD: Tasks (create, list, detail, update, delete)
- [ ] Capture modal (one form, all fields optional except title)
- [ ] Dashboard view (on fire, delegated, active, backlog, inbox sections)
- [ ] List view with filters and sorting
- [ ] Global search (keyword via FTS5)
- [ ] Semantic search + "related captures" suggestions on project pages

**Verification:** Can capture a thought in 5 seconds, see it on the dashboard, search for it, and see related suggestions on a project page.

### Phase 2 — Views & Organization (Week 2)

**Goal:** All views working, tasks feel organized without effort.

- [ ] Board view (Kanban columns, drag-and-drop status change)
- [ ] Calendar view (FullCalendar integration)
- [ ] Gantt view (Mermaid.js timeline)
- [ ] Tags on tasks (tag input, filter by tag)
- [ ] Links on tasks (add/remove URL + label pairs)
- [ ] Logs on projects and tasks (create, list, delete)
- [ ] Project nesting (parent/child, visual hierarchy)

**Verification:** Can view tasks in all three views (list/board/Gantt), filter by tag, see a calendar of due dates, and add logs to a project.

### Phase 3 — Polish & Export (Week 3)

**Goal:** Tool feels complete, ready for stakeholder use.

- [ ] Gantt export as PDF / clean HTML
- [ ] Task list export as CSV
- [ ] Dashboard refinements (visual polish, empty states)
- [ ] Search refinements (hybrid keyword + semantic scoring)
- [ ] Inline editing on task detail page
- [ ] Responsive design (works on laptop screens)
- [ ] Portable Python packaging (requirements.txt, run script)

**Verification:** Can export a Gantt chart for a stakeholder meeting, search naturally ("find things about SOC"), and package the app for portable deployment.

---

## Design Principles (Non-Negotiable)

1. **One screen, one purpose.** The dashboard tells you what needs attention. The list view lets you filter. The project page shows context. No page tries to do everything.

2. **No required fields except title.** If a field isn't filled, the system doesn't nag. It just works with what it has.

3. **The inbox is not a pile — it's a signal.** Semantic search turns the inbox from "things I'll organize later" into "here are things you might care about right now."

4. **Status changes are one click.** Whether via board drag, dropdown, or inline edit — changing a task's status takes one action, maximum.

5. **Logs stay attached.** A log entry always belongs to something (project or task). No orphan notes.

---

*Conceived July 2026. Built for one brain, one workflow.*
