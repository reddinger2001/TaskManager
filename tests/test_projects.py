"""Tests for project CRUD operations, nesting, and detail views."""

import pytest


class TestProjectCreate:
    """Test project creation."""

    def test_create_project_minimum(self, client):
        """Only name is required."""
        resp = client.post("/projects/new", data={
            "name": "New Project",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"New Project" in resp.data

    def test_create_project_with_description(self, client):
        resp = client.post("/projects/new", data={
            "name": "Project with description",
            "description": "A meaningful project description",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"A meaningful project description" in resp.data

    def test_create_project_requires_name(self, client):
        """Empty name is rejected."""
        resp = client.post("/projects/new", data={
            "name": "",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"name is required" in resp.data.lower()

    def test_create_project_auto_assigns_color(self, client):
        """A color is auto-assigned from the palette."""
        resp = client.post("/projects/new", data={
            "name": "Auto color project",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Should have a hex color in the response
        assert b"#" in resp.data

    def test_create_project_redirects_to_detail(self, client):
        """After creation, redirect to project detail page."""
        resp = client.post("/projects/new", data={
            "name": "Redirect test project",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "/projects/" in resp.location

    def test_create_project_with_dates(self, client):
        resp = client.post("/projects/new", data={
            "name": "Timed project",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        }, follow_redirects=True)
        assert resp.status_code == 200


class TestProjectList:
    """Test the project list view."""

    def test_list_loads(self, client):
        resp = client.get("/projects")
        assert resp.status_code == 200

    def test_list_shows_projects(self, client, populated_db):
        resp = client.get("/projects")
        assert b"SOC Modernization" in resp.data
        assert b"VendorSync" in resp.data

    def test_list_shows_task_counts(self, client, populated_db):
        """Project cards show task counts."""
        resp = client.get("/projects")
        # SOC Modernization has tasks assigned to it
        data = resp.data.decode()
        assert "task" in data.lower()

    def test_list_shows_completion_percentage(self, client, populated_db):
        """Completion percentage is shown on project cards."""
        resp = client.get("/projects")
        # VendorSync has 1 done out of several tasks
        assert b"%" in resp.data or b"completion" in resp.data.lower()

    def test_list_shows_project_colors(self, client, populated_db):
        """Project color indicators are rendered."""
        resp = client.get("/projects")
        assert b"#00e5ff" in resp.data or b"#7c4dff" in resp.data


class TestProjectDetail:
    """Test the project detail view."""

    def test_detail_loads(self, client, populated_db):
        resp = client.get("/projects/1")
        assert resp.status_code == 200
        assert b"SOC Modernization" in resp.data

    def test_detail_404(self, client):
        resp = client.get("/projects/99999")
        assert resp.status_code == 404

    def test_detail_shows_description(self, client, populated_db):
        resp = client.get("/projects/1")
        assert b"Modernize SOC operations" in resp.data

    def test_detail_shows_tasks(self, client, populated_db):
        """Project detail shows all tasks including from child projects."""
        resp = client.get("/projects/1")
        # SOC Modernization (proj 1) has tasks directly + from Phase 2 (proj 3)
        assert b"Resolve P0 outage" in resp.data  # Direct task
        assert b"Follow up on compliance audit" in resp.data  # From child project

    def test_detail_shows_child_projects(self, client, populated_db):
        """Child projects are displayed under the parent."""
        resp = client.get("/projects/1")
        assert "SOC Modernization — Phase 2".encode() in resp.data
        assert b"Sub-projects" in resp.data or "↳".encode() in resp.data

    def test_detail_shows_logs(self, client, populated_db):
        """Project logs are displayed."""
        resp = client.get("/projects/1")
        assert b"Sprint planning notes" in resp.data

    def test_detail_shows_edit_button(self, client, populated_db):
        resp = client.get("/projects/1")
        assert b"Edit" in resp.data

    def test_detail_shows_delete_button(self, client, populated_db):
        resp = client.get("/projects/1")
        assert b"Delete" in resp.data

    def test_child_project_shows_parent_link(self, client, populated_db):
        """Child project shows a link back to parent."""
        resp = client.get("/projects/3")  # Phase 2 is child of proj 1
        assert b"Parent" in resp.data or b"/projects/1" in resp.data

    def test_detail_shows_project_color(self, client, populated_db):
        """Project color is displayed on detail page."""
        resp = client.get("/projects/1")
        assert b"#00e5ff" in resp.data

    def test_detail_shows_created_date(self, client, populated_db):
        resp = client.get("/projects/1")
        assert b"Created" in resp.data

    def test_detail_has_add_log_button(self, client, populated_db):
        """+ Log button is present on project detail."""
        resp = client.get("/projects/1")
        assert b"+ Log" in resp.data or b"+log" in resp.data.lower()


class TestProjectUpdate:
    """Test project updates via PATCH."""

    def test_update_name(self, client, populated_db):
        resp = client.patch("/projects/1", json={"name": "Renamed Project"})
        assert resp.status_code == 200
        assert resp.json["ok"] is True

    def test_update_description(self, client, populated_db):
        resp = client.patch("/projects/1", json={"description": "New description"})
        assert resp.status_code == 200

    def test_update_color(self, client, populated_db):
        resp = client.patch("/projects/1", json={"color": "#ff0000"})
        assert resp.status_code == 200

    def test_update_dates(self, client, populated_db):
        resp = client.patch("/projects/1", json={
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        })
        assert resp.status_code == 200

    def test_update_parent_id(self, client, populated_db):
        """Set a parent project."""
        # Move VendorSync (proj 2) under SOC Modernization (proj 1)
        resp = client.patch("/projects/2", json={"parent_id": 1})
        assert resp.status_code == 200
        assert resp.json["ok"] is True

    def test_update_parent_clears_to_none(self, client, populated_db):
        """Clear the parent project."""
        # Phase 2 (proj 3) has parent_id=1
        resp = client.patch("/projects/3", json={"parent_id": None})
        assert resp.status_code == 200

    def test_update_circular_reference_rejected(self, client, populated_db):
        """Cannot set parent to self or a descendant (circular ref)."""
        # SOC Modernization (proj 1) is ancestor of Phase 2 (proj 3)
        # Trying to make Phase 2 the parent of SOC Modernization would create a cycle
        resp = client.patch("/projects/1", json={"parent_id": 3})
        assert resp.status_code == 400
        assert b"circular" in resp.data.lower()

    def test_update_404(self, client):
        resp = client.patch("/projects/99999", json={"name": "Nope"})
        assert resp.status_code == 404

    def test_update_clears_description(self, client, populated_db):
        """Setting description to empty string clears it."""
        resp = client.patch("/projects/1", json={"description": ""})
        assert resp.status_code == 200


class TestProjectDelete:
    """Test project deletion."""

    def test_delete_project(self, client, populated_db):
        resp = client.delete("/projects/1")
        assert resp.status_code == 302  # Redirect to project list

    def test_delete_project_post_method(self, client, populated_db):
        """Delete via POST with _method=DELETE (browser form)."""
        resp = client.post("/projects/1", data={"_method": "DELETE"}, follow_redirects=True)
        assert resp.status_code == 200

    def test_delete_project_404(self, client):
        resp = client.delete("/projects/99999")
        assert resp.status_code == 404

    def test_delete_removes_from_list(self, client, populated_db):
        """After deletion, project no longer appears in the list."""
        client.delete("/projects/1", follow_redirects=True)
        resp = client.get("/projects")
        # The child project (Phase 2) also contains "SOC Modernization" in its name,
        # so check that the specific project card is gone by looking for the link
        assert b'href="/projects/1"' not in resp.data

    def test_delete_cascades_to_tasks(self, client, populated_db):
        """Deleting a project also removes its tasks (or at least they're orphaned)."""
        # Delete VendorSync (proj 2) — it has tasks
        client.delete("/projects/2", follow_redirects=True)
        # The task should no longer be accessible under that project
        resp = client.get("/tasks?project_id=2")
        # Tasks that were under proj 2 should not appear anymore
        assert b"Review vendor contracts" not in resp.data
