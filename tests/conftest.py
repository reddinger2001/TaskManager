"""Pytest configuration and shared fixtures for TaskManager tests."""

import os
import tempfile

import pytest

from app.models import db


@pytest.fixture(scope="session")
def test_db_path():
    """Create a temporary database file for the test suite."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture(scope="session")
def app(test_db_path):
    """Create the Flask app with a test database and NO embedding hooks.

    Embedding hooks are skipped because sentence-transformers crashes
    in the test environment. FTS5 is still available for keyword search.
    """
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key"

    from flask import Flask
    import os as _os

    def create_test_app():
        base_dir = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), ".."))
        app = Flask(__name__, template_folder=_os.path.join(base_dir, "app", "templates"))
        app.config.from_object("app.config.Config")

        from app.extensions import init_extensions
        init_extensions(app)

        from app.views.main import main_bp
        app.register_blueprint(main_bp)

        from app.views.projects import projects_bp
        app.register_blueprint(projects_bp)

        from app.views.logs import logs_bp
        app.register_blueprint(logs_bp)

        from app.views.tasks import tasks_bp
        app.register_blueprint(tasks_bp)

        return app

    test_app = create_test_app()

    with test_app.app_context():
        db.create_all()

    yield test_app


@pytest.fixture
def client(app):
    """Create a test client for the Flask app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a CLI runner for the Flask app."""
    return app.test_cli_runner()


@pytest.fixture
def populated_db(app):
    """Populate the database with a rich set of test data for comprehensive testing.

    Drops and recreates all tables first to ensure a clean state, then
    recreates FTS5/vec0 virtual tables.
    """
    from app.models import Project, Task, Log

    with app.app_context():
        # Drop and recreate all tables for a clean slate
        db.drop_all()
        db.create_all()

        # Recreate FTS5 and vec0 virtual tables (lost on drop_all)
        raw_conn = db.engine.raw_connection()
        try:
            raw_conn.enable_load_extension(True)
            import sqlite_vec
            sqlite_vec.load(raw_conn)
            raw_conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS task_embeddings USING vec0("
                "task_id INTEGER PRIMARY KEY, embedding float[384]"
                ")"
            )
            raw_conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5("
                "task_id UNINDEXED, title, description, tags_text"
                ")"
            )
            raw_conn.commit()
        except Exception:
            pass
        finally:
            raw_conn.close()

        # Projects — flush first so IDs are assigned before we reference them
        proj1 = Project(name="SOC Modernization", description="Modernize SOC operations", color="#00e5ff")
        proj2 = Project(name="VendorSync", description="Vendor synchronization tool", color="#7c4dff")

        db.session.add_all([proj1, proj2])
        db.session.flush()

        # Now proj1.id is available for the child project
        proj3 = Project(
            name="SOC Modernization — Phase 2",
            description="Follow-on work",
            color="#69f0ae",
            parent_id=proj1.id,
        )
        db.session.add(proj3)
        db.session.flush()

        # Tasks across statuses and priorities
        tasks = [
            Task(title="Resolve P0 outage", description="Critical production incident", status="blocked", priority="P0", assignee="Chris", due_date="2026-07-15", project_id=proj1.id),
            Task(title="Update firewall rules", status="active", priority="P1", assignee="Chris", due_date="2026-07-20", project_id=proj1.id),
            Task(title="Review vendor contracts", status="delegated", assignee="Sarah", project_id=proj2.id),
            Task(title="Write API docs", status="delegated", assignee="Sarah", project_id=proj2.id),
            Task(title="Deploy monitoring agent", status="delegated", assignee="Mike", project_id=proj1.id),
            Task(title="Research SIEM options", status="backlog", priority="P2", project_id=proj1.id),
            Task(title="Draft incident response plan", status="backlog", project_id=proj1.id),
            Task(title="Quick thought about CI/CD", status="backlog"),  # Inbox capture — no project
            Task(title="Follow up on compliance audit", status="active", assignee="Chris", project_id=proj3.id),
            Task(title="Completed task example", status="done", assignee="Chris", project_id=proj2.id),
        ]

        db.session.add_all(tasks)
        db.session.flush()

        # Logs
        logs = [
            Log(title="Sprint planning notes", notes="Discussed priorities for next sprint", project_id=proj1.id),
            Log(title="Vendor meeting summary", notes="Met with Acme Corp, they agreed to timeline", task_id=tasks[2].id),
            Log(title="Blocker update", notes="Waiting on firewall team to respond", task_id=tasks[0].id),
        ]

        db.session.add_all(logs)
        db.session.commit()

        yield {
            "projects": [proj1, proj2, proj3],
            "tasks": tasks,
            "logs": logs,
        }
