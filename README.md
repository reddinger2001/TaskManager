# TaskManager

A local-first, solo-use task management app with semantic search. Think: lightweight Things/GTD that lives on your machine.

## Features

- **Inbox → Backlog → Active → Done** workflow with quick-capture (Ctrl+K / /)
- **Pulse-check dashboard** — see project health, fires, and overdue tasks in 5 seconds
- **Task dependencies** — block tasks on each other with cycle detection
- **Semantic search** — AI-powered full-text search via ONNX (works offline, ~65MB vs. 500MB+ for PyTorch)
- **Kanban board** and **Gantt view** for visual planning
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

# First run seeds tutorial data automatically
flask run --host 0.0.0.0 --port 5001
```

Open http://localhost:5001 — you'll see 3 sample projects with 12 tutorial tasks.

### From Package

```bash
unzip taskmanager-*.zip -d TaskManager/
cd TaskManager/
./setup.sh                     # or setup.bat on Windows
./run.sh                       # or run.bat on Windows
```

That's it. The app starts at http://localhost:5001.

### Building a Package

```bash
python3 package.py              # creates taskmanager-0.1.0.zip
python3 package.py --wheel      # also pre-downloads ONNX model for offline use
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Flask 3.x + SQLAlchemy |
| Database | SQLite + FTS5 (keyword search) + sqlite-vec (semantic search) |
| AI/Embeddings | all-MiniLM-L6-v2 via ONNX Runtime (~65MB total) |
| Frontend | Tailwind CSS (CDN) + Alpine.js |
| Testing | pytest (165 tests, 100% passing) |

## Security

- **CycloneDX SBOM** — `snyk-report.json` and `snyk-venv-report.json` in the repo
- **Last scanned**: 2026-07-16 — 0 known vulnerabilities (pip-audit)
- No authentication required (solo-use design)

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///instance/taskmanager.db` | Database location |
| `EMBEDDING_ENABLED` | `false` | Enable semantic search (adds ~65MB) |
| `SECRET_KEY` | auto-generated | Flask session secret |

## License

MIT
