"""Pytest configuration and shared fixtures for TaskManager tests."""

from datetime import date

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
    """Create the Flask app with a test database."""
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
    os.environ["SECRET_KEY"] = "test-secret-key"

    from app import create_app

    test_app = create_app()
    # Disable CSRF in tests — test client doesn't carry tokens
    test_app.config["WTF_CSRF_ENABLED"] = False

    yield test_app


@pytest.fixture
def client(app):
    """Create a test client for the Flask app, automatically logged in as admin.

    Bypasses the require_login before_request hook so tests don't need to
    manage session cookies. scoped_query and g.current_user_id are set to admin.
    """
    from flask import g
    from app.models import User, scoped_query

    # Save original handlers so we can restore them
    original_handlers = list(app.before_request_funcs.get(None, []))

    # Remove the require_login before_request handler for tests
    handlers = [h for h in app.before_request_funcs.get(None, []) if h.__name__ != "require_login"]
    app.before_request_funcs[None] = handlers

    def setup_test_user():
        admin = User.query.filter_by(username="admin").first()
        g.scoped_query = lambda model: scoped_query(model, admin)
        g.current_user_id = admin.id
        g.current_user_is_admin = True
        g.current_username = "admin"

    handlers2 = [h for h in app.before_request_funcs.get(None, []) if h.__name__ != "set_scoped_query"]
    handlers2.append(setup_test_user)
    app.before_request_funcs[None] = handlers2

    with app.test_client() as c:
        try:
            yield c
        finally:
            # Restore original handlers so raw_client tests work correctly
            app.before_request_funcs[None] = original_handlers


@pytest.fixture
def raw_client(app):
    """Create a test client with NO mocking — real login required.

    Use this for tests that need to test auth, login/logout, and real
    scoped queries. You must log in before making requests.
    """
    with app.test_client() as c:
        yield c


@pytest.fixture
def runner(app):
    """Create a CLI runner for the Flask app."""
    return app.test_cli_runner()


@pytest.fixture
def populated_db(app):
    """Populate the database with a rich set of test data for comprehensive testing.

    Drops and recreates all tables first to ensure a clean state, then
    recreates FTS5 virtual tables and creates an admin user.
    """
    from app.models import Project, Task, Log, User

    with app.app_context():
        # Drop and recreate all tables for a clean slate
        db.drop_all()
        db.create_all()

        # Recreate FTS5 virtual table (lost on drop_all)
        raw_conn = db.engine.raw_connection()
        try:
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

        # Create admin user first
        admin = User(username="admin", is_admin=True)
        admin.set_password("admin")
        db.session.add(admin)
        db.session.flush()

        # Projects — flush first so IDs are assigned before we reference them
        proj1 = Project(name="SOC Modernization", description="Modernize SOC operations", color="#00e5ff", user_id=admin.id)
        proj2 = Project(name="VendorSync", description="Vendor synchronization tool", color="#7c4dff", user_id=admin.id)

        db.session.add_all([proj1, proj2])
        db.session.flush()

        # Now proj1.id is available for the child project
        proj3 = Project(
            name="SOC Modernization — Phase 2",
            description="Follow-on work",
            color="#69f0ae",
            parent_id=proj1.id,
            user_id=admin.id,
        )
        db.session.add(proj3)
        db.session.flush()

        # Tasks across statuses and priorities
        tasks = [
            Task(title="Resolve P0 outage", description="Critical production incident", status="blocked", priority="P0", assignee="Chris", due_date=date(2026, 7, 15), project_id=proj1.id, user_id=admin.id),
            Task(title="Update firewall rules", status="active", priority="P1", assignee="Chris", due_date=date(2026, 7, 20), project_id=proj1.id, user_id=admin.id),
            Task(title="Review vendor contracts", status="delegated", assignee="Sarah", project_id=proj2.id, user_id=admin.id),
            Task(title="Write API docs", status="delegated", assignee="Sarah", project_id=proj2.id, user_id=admin.id),
            Task(title="Deploy monitoring agent", status="delegated", assignee="Mike", project_id=proj1.id, user_id=admin.id),
            Task(title="Research SIEM options", status="backlog", priority="P2", project_id=proj1.id, user_id=admin.id),
            Task(title="Draft incident response plan", status="backlog", project_id=proj1.id, user_id=admin.id),
            Task(title="Quick thought about CI/CD", status="backlog"),  # Inbox capture — no project
            Task(title="Follow up on compliance audit", status="active", assignee="Chris", project_id=proj3.id, user_id=admin.id),
            Task(title="Completed task example", status="done", assignee="Chris", project_id=proj2.id, user_id=admin.id),
        ]

        # Fix inbox task — needs user_id
        tasks[7].user_id = admin.id

        db.session.add_all(tasks)
        db.session.flush()

        # Logs
        logs = [
            Log(title="Sprint planning notes", notes="Discussed priorities for next sprint", project_id=proj1.id, user_id=admin.id),
            Log(title="Vendor meeting summary", notes="Met with Acme Corp, they agreed to timeline", task_id=tasks[2].id, user_id=admin.id),
            Log(title="Blocker update", notes="Waiting on firewall team to respond", task_id=tasks[0].id, user_id=admin.id),
        ]

        db.session.add_all(logs)
        db.session.commit()

        yield {
            "projects": [proj1, proj2, proj3],
            "tasks": tasks,
            "logs": logs,
        }
