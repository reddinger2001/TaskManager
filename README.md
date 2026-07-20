# TaskManager

A local-first task management app with multi-user support and FTS5 keyword search. Think: lightweight Things/GTD that lives on your machine — works solo or with a small team.

## Features

- **Inbox → Backlog → Active → Done** workflow with quick-capture (Ctrl+K / /)
- **Pulse-check dashboard** — see project health, fires, and overdue tasks in 5 seconds
- **Multi-user support** — admin + regular users, project sharing, row-level isolation
- **Task dependencies** — block tasks on each other with cycle detection
- **FTS5 keyword search** — fast full-text search across tasks, logs, and projects
- **Kanban board** and **Gantt view** for visual planning
- **Calendar view** — month/week/day with color-coded statuses
- **Backup/restore** — single SQLite file, export/import from Settings
- **Three themes** — Dark, Medium, Light (toggle in Settings)
- **Built-in help system** — no external docs needed

## Quick Start

### From Source

```bash
# Requires Python 3.10+
git clone https://github.com/ChrisReddinger/TaskManager.git
cd TaskManager
python3 -m venv .venv
source .venv/bin/activate      # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# First run: setup wizard creates admin account, then seeds tutorial data
flask run --host 0.0.0.0 --port 5001
```

Open http://localhost:5001 — you'll be prompted to create an admin account, then see 3 sample projects with 12 tutorial tasks.

### From Package

```bash
unzip taskmanager-*.zip -d TaskManager/
cd TaskManager/
./setup.sh                     # or setup.bat on Windows
./run.sh                       # or run.bat on Windows
```

That's it. The app starts at http://localhost:5001. First launch shows the setup wizard.

### Upgrading from Solo Mode (0.1.x → 0.2.x)

If you have an existing TaskManager database without users, the migration runs automatically on startup. After upgrading:
1. Login with username `admin`, password `admin`
2. Change your password immediately in Settings → Users
3. All existing tasks/projects are assigned to the admin user

### Building a Package

```bash
python3 package.py              # creates taskmanager-0.2.0.zip
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Flask 3.x + SQLAlchemy |
| Database | SQLite + FTS5 (keyword search) |
| Auth | Flask-Login + Werkzeug password hashing |
| Frontend | Tailwind CSS (CDN) + Alpine.js |
| Testing | pytest (192 tests, 100% passing) |

## Security

- **CycloneDX SBOM** — `snyk-report.json` and `snyk-venv-report.json` in the repo
- **Last scanned**: 2026-07-16 — 0 known vulnerabilities (pip-audit)
- **CSRF protection** on all POST/DELETE routes via Flask-WTF
- **Password hashing** via Werkzeug (PBKDF2)

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///instance/taskmanager.db` | Database location |
| `SECRET_KEY` | auto-generated | Flask session secret |

## License

MIT
