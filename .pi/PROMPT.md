# TaskManager — Agent Work Prompt

You are working on **TaskManager**, a solo PM's personal project management tool. Flask + SQLite + sqlite-vec + FTS5 + Tailwind CSS (CDN) + Alpine.js (CDN). Dark-mode sci-fi terminal aesthetic.

## Before You Start

1. **Read the spec:** `SPEC.md` — this is the source of truth for data models, views, and design decisions.
2. **Read the UI prototypes:** `ui-prototypes/dashboard.html`, `board.html`, `gantt.html` — these are the visual reference for every view.
3. **Check what's already done:** Look at the git log and existing code to understand current state.
4. **Pick the next issue** from Forgejo: `http://10.0.10.30:3000/Chris/TaskManager/issues?state=open` — go in order (lowest number first), unless an issue explicitly depends on another being done first.

## How to Work

### 1. Read the Issue

Open the issue and read its body carefully. It has a checklist of tasks, UI references, and verification criteria. **Do not skip the verification section.**

### 2. Implement

- Work in a feature branch: `feature/issue-{N}-{short-slug}`
- Write code that matches the existing style — don't introduce new patterns unless the issue requires them.
- Use the UI prototypes as your visual reference. If you're building a view, open the corresponding prototype and match it closely.
- For backend work: Flask blueprints, SQLAlchemy models, sqlite-vec for embeddings.
- For frontend: Jinja2 templates extending `base.html`, Alpine.js for interactivity, Tailwind via CDN.
- **No hand-written tests** — this is a small solo app. Verify manually by running the app and checking the behavior matches the issue's verification criteria.

### 3. Verify

Run the app (`flask run`) and test the feature yourself:
- Create/edit/delete the relevant objects
- Check the UI matches the prototype
- Confirm the verification criteria from the issue are met
- If something doesn't work, fix it — don't push broken code

### 4. Commit & Push

```bash
# Conventional commit format
git commit -m "feat: what you did (closes #N)"

# Push to forgejo ONLY — never push to origin/GitHub
git push forgejo feature/issue-{N}-{short-slug}
```

### 5. Create PR & Close Issue

- Create a pull request on Forgejo against `main`
- Once merged, close the issue with a brief comment summarizing what was done

## Key References

- **SPEC:** `/Volumes/DevEnvironment/projects/TaskManager/SPEC.md`
- **UI Prototypes:** `/Volumes/DevEnvironment/projects/TaskManager/ui-prototypes/`
- **Forgejo:** `http://10.0.10.30:3000/Chris/TaskManager`
- **Remote:** `forgejo` → `http://10.0.10.30:3000/Chris/TaskManager.git`
- **NEVER push to origin/GitHub**

## Tech Stack Reminders

- Flask + Flask-SQLAlchemy for backend
- SQLite with sqlite-vec (embeddings) and FTS5 (keyword search)
- `sentence-transformers` with `all-MiniLM-L6-v2` for embedding generation
- Tailwind CSS via CDN — no build step
- Alpine.js via CDN — no build step
- Jinja2 templates — server-rendered
- No auth, no RBAC, solo user only

## Design Principles (Non-Negotiable)

1. **One screen, one purpose** — don't make a page try to do everything
2. **No required fields except title** — if a field isn't filled, the system doesn't nag
3. **Status changes are one click** — whether via board drag, dropdown, or inline edit
4. **Logs stay attached** — a log always belongs to a project or task
