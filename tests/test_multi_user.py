"""Multi-user feature tests: auth, user management, scoped queries, project sharing."""
import pytest
from app.models import User, Project, Task, Log, db


def _add_user(app, username, password, is_admin=False):
    """Create a user and return its id."""
    with app.app_context():
        user = User(username=username, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def _add_project(app, name, user_id, color="#ff0000"):
    """Create a project and return its id."""
    with app.app_context():
        proj = Project(name=name, color=color, user_id=user_id)
        db.session.add(proj)
        db.session.commit()
        return proj.id


def _add_task(app, title, user_id, project_id=None):
    """Create a task and return its id."""
    with app.app_context():
        task = Task(title=title, status="backlog", user_id=user_id, project_id=project_id)
        db.session.add(task)
        db.session.commit()
        return task.id


# --- Auth Tests ---

class TestLogin:
    def test_login_page_loads(self, raw_client):
        r = raw_client.get("/login")
        assert r.status_code == 200
        assert b"Sign in" in r.data

    def test_login_success(self, app, raw_client):
        _add_user(app, "testuser", "secret")
        r = raw_client.post("/login", data={"username": "testuser", "password": "secret"}, follow_redirects=True)
        assert r.status_code == 200
        assert b"Sign in" not in r.data

    def test_login_bad_username(self, raw_client):
        r = raw_client.post("/login", data={"username": "nonexistent", "password": "secret"}, follow_redirects=True)
        assert b"not found" in r.data.lower()

    def test_login_bad_password(self, app, raw_client):
        _add_user(app, "testuser2", "correct")
        r = raw_client.post("/login", data={"username": "testuser2", "password": "wrong"}, follow_redirects=True)
        assert b"Incorrect password" in r.data

    def test_logout(self, raw_client):
        # Log in first, then log out
        raw_client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        r = raw_client.get("/logout", follow_redirects=True)
        assert r.status_code == 200
        assert b"Sign in" in r.data

    def test_unauthenticated_redirects_to_login(self, raw_client):
        r = raw_client.get("/")
        assert r.status_code in (302, 200)
        if r.status_code == 200:
            assert b"Sign in" in r.data


# --- User Management Tests (admin actions via mocked client) ---

class TestUserManagement:
    def test_create_user(self, client):
        r = client.post("/settings/users", data={
            "action": "create",
            "username": "newuser",
            "password": "pass123",
        }, follow_redirects=True)
        assert r.status_code == 200
        assert b"created" in r.data.lower()

    def test_create_user_duplicate(self, client):
        r = client.post("/settings/users", data={
            "action": "create",
            "username": "admin",
            "password": "pass123",
        }, follow_redirects=True)
        assert b"already exists" in r.data.lower()

    def test_create_user_missing_username(self, client):
        r = client.post("/settings/users", data={
            "action": "create",
            "username": "",
            "password": "pass123",
        }, follow_redirects=True)
        assert b"required" in r.data.lower()

    def test_create_user_missing_password(self, client):
        r = client.post("/settings/users", data={
            "action": "create",
            "username": "newuser",
            "password": "",
        }, follow_redirects=True)
        assert b"required" in r.data.lower()

    def test_create_user_as_admin(self, client):
        r = client.post("/settings/users", data={
            "action": "create",
            "username": "superuser",
            "password": "pass123",
            "is_admin": "on",
        }, follow_redirects=True)
        with client.application.app_context():
            user = User.query.filter_by(username="superuser").first()
            assert user is not None
            assert user.is_admin is True

    def test_reset_password(self, app, client):
        uid = _add_user(app, "resetme", "oldpass")
        r = client.post("/settings/users", data={
            "action": "reset_password",
            "user_id": uid,
            "new_password": "newpass",
        }, follow_redirects=True)
        assert b"Password reset" in r.data
        with client.application.app_context():
            user = User.query.get(uid)
            assert user.check_password("newpass")

    def test_toggle_admin(self, app, client):
        uid = _add_user(app, "togglable", "pass")
        r = client.post("/settings/users", data={
            "action": "toggle_admin",
            "user_id": uid,
        }, follow_redirects=True)
        assert b"admin" in r.data.lower()
        with client.application.app_context():
            user = User.query.get(uid)
            assert user.is_admin is True

    def test_cannot_toggle_own_admin(self, client):
        with client.application.app_context():
            admin_id = User.query.filter_by(username="admin").first().id
        r = client.post("/settings/users", data={
            "action": "toggle_admin",
            "user_id": admin_id,
        }, follow_redirects=True)
        assert b"cannot change your own" in r.data.lower()

    def test_delete_user_reassigns_items(self, app, client):
        uid = _add_user(app, "deleteme", "pass")
        with app.app_context():
            admin_id = User.query.filter_by(username="admin").first().id
        pid = _add_project(app, "DeleteMe Project", uid)
        tid = _add_task(app, "DeleteMe Task", uid, pid)

        r = client.post("/settings/users", data={
            "action": "delete",
            "user_id": uid,
        }, follow_redirects=True)
        assert b"deleted" in r.data.lower()

        with app.app_context():
            assert User.query.get(uid) is None
            proj = Project.query.get(pid)
            assert proj.user_id == admin_id
            task = Task.query.get(tid)
            assert task.user_id == admin_id

    def test_cannot_delete_own_account(self, client):
        with client.application.app_context():
            admin_id = User.query.filter_by(username="admin").first().id
        r = client.post("/settings/users", data={
            "action": "delete",
            "user_id": admin_id,
        }, follow_redirects=True)
        assert b"cannot delete your own" in r.data.lower()

    def test_change_own_password(self, client):
        r = client.post("/settings/users", data={
            "action": "change_own_password",
            "new_password": "newadminpass",
        }, follow_redirects=True)
        assert b"changed" in r.data.lower()
        with client.application.app_context():
            admin = User.query.filter_by(username="admin").first()
            assert admin.check_password("newadminpass")


# --- Non-admin user can access settings/users and change own password ---

class TestNonAdminPasswordChange:
    def test_non_admin_can_access_settings_users(self, app, raw_client):
        uid = _add_user(app, "regular_user", "pass123")
        raw_client.post("/login", data={"username": "regular_user", "password": "pass123"}, follow_redirects=True)
        r = raw_client.get("/settings/users")
        assert r.status_code == 200
        assert b"Change Your Password" in r.data
        # Admin-only sections should not be visible
        assert b"Create User" not in r.data

    def test_non_admin_can_change_own_password(self, app, raw_client):
        uid = _add_user(app, "regular_user2", "oldpass")
        raw_client.post("/login", data={"username": "regular_user2", "password": "oldpass"}, follow_redirects=True)
        r = raw_client.post("/settings/users", data={
            "action": "change_own_password",
            "new_password": "newpass",
        }, follow_redirects=True)
        assert b"changed" in r.data.lower()
        with app.app_context():
            user = User.query.filter_by(username="regular_user2").first()
            assert user.check_password("newpass")

    def test_non_admin_cannot_create_user(self, app, raw_client):
        uid = _add_user(app, "regular_user3", "pass123")
        raw_client.post("/login", data={"username": "regular_user3", "password": "pass123"}, follow_redirects=True)
        r = raw_client.post("/settings/users", data={
            "action": "create",
            "username": "hacker",
            "password": "hack",
        }, follow_redirects=True)
        assert b"only administrators" in r.data.lower()

# --- Scoped Query Tests (real login via raw_client) ---

class TestScopedQuery:
    def test_admin_sees_all_tasks(self, app, raw_client):
        # Reset admin password in case a prior test changed it
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            admin.set_password("admin")
            db.session.commit()

        uid = _add_user(app, "scoped_user", "pass")
        _add_task(app, "Scoped Task", uid)

        raw_client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)
        r = raw_client.get("/tasks")
        assert b"Scoped Task" in r.data

    def test_regular_user_sees_only_own_tasks(self, app, raw_client):
        with app.app_context():
            admin_id = User.query.filter_by(username="admin").first().id
        _add_task(app, "Admin Only Task", admin_id)
        uid = _add_user(app, "scoped_user2", "pass")
        _add_task(app, "My Task", uid)

        raw_client.post("/login", data={"username": "scoped_user2", "password": "pass"}, follow_redirects=True)
        r = raw_client.get("/tasks")
        assert b"My Task" in r.data
        assert b"Admin Only Task" not in r.data

    def test_shared_project_visible_to_other_user(self, app, raw_client):
        with app.app_context():
            admin_id = User.query.filter_by(username="admin").first().id
        pid = _add_project(app, "Shared Project", admin_id)
        uid = _add_user(app, "shared_user", "pass")
        with app.app_context():
            proj = Project.query.get(pid)
            proj.set_shared_with([uid])
            db.session.commit()

        raw_client.post("/login", data={"username": "shared_user", "password": "pass"}, follow_redirects=True)
        r = raw_client.get("/projects")
        assert b"Shared Project" in r.data

    def test_unshared_project_not_visible_to_other_user(self, app, raw_client):
        with app.app_context():
            admin_id = User.query.filter_by(username="admin").first().id
        _add_project(app, "Private Project", admin_id)
        _add_user(app, "private_user", "pass")

        raw_client.post("/login", data={"username": "private_user", "password": "pass"}, follow_redirects=True)
        r = raw_client.get("/projects")
        assert b"Private Project" not in r.data

    def test_assigned_task_visible_to_assignee(self, app, raw_client):
        """A task assigned to a user should be visible even if they don't own the project."""
        with app.app_context():
            admin_id = User.query.filter_by(username="admin").first().id
        pid = _add_project(app, "Admin Project", admin_id)
        tid = _add_task(app, "Assigned Task", admin_id, project_id=pid)
        uid = _add_user(app, "sarah", "pass")
        with app.app_context():
            task = Task.query.get(tid)
            task.assignee = "sarah"
            task.status = "delegated"
            db.session.commit()

        raw_client.post("/login", data={"username": "sarah", "password": "pass"}, follow_redirects=True)
        r = raw_client.get("/tasks")
        assert b"Assigned Task" in r.data
        # But the project itself should not be visible (only the assigned task)
        r2 = raw_client.get("/projects")
        assert b"Admin Project" not in r2.data


# --- Dashboard Tests ---

class TestMultiUserDashboard:
    def test_dashboard_loads_for_admin(self, client):
        r = client.get("/")
        assert r.status_code == 200
