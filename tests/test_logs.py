"""Tests for log CRUD operations on projects and tasks."""

import pytest


class TestLogCreateOnProject:
    """Test creating logs attached to projects."""

    def test_create_log_on_project(self, client, populated_db):
        resp = client.post("/projects/1/logs", data={
            "title": "New meeting notes",
            "notes": "Discussed timeline and blockers",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # After creating a log, redirect to referrer (dashboard /).
        # Verify the log was created by checking project detail.
        resp = client.get("/projects/1")
        assert b"New meeting notes" in resp.data

    def test_create_log_on_project_no_notes(self, client, populated_db):
        """Notes are optional."""
        client.post("/projects/1/logs", data={
            "title": "Quick note",
        }, follow_redirects=True)
        resp = client.get("/projects/1")
        assert b"Quick note" in resp.data

    def test_create_log_requires_title(self, client, populated_db):
        """Empty title is rejected — redirects back."""
        resp = client.post("/projects/1/logs", data={
            "title": "",
            "notes": "No title allowed",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Should NOT contain the log since it was rejected
        assert b"No title allowed" not in resp.data

    def test_create_log_on_project_404(self, client):
        resp = client.post("/projects/99999/logs", data={
            "title": "Nope",
        })
        assert resp.status_code == 404


class TestLogCreateOnTask:
    """Test creating logs attached to tasks."""

    def test_create_log_on_task(self, client, populated_db):
        client.post("/tasks/1/logs", data={
            "title": "Status update",
            "notes": "Still waiting on firewall team",
        }, follow_redirects=True)
        resp = client.get("/tasks/1")
        assert b"Status update" in resp.data

    def test_create_log_on_task_404(self, client):
        resp = client.post("/tasks/99999/logs", data={
            "title": "Nope",
        })
        assert resp.status_code == 404


class TestLogDelete:
    """Test log deletion."""

    def test_delete_log(self, client, populated_db):
        """Delete a log via DELETE method."""
        resp = client.delete("/logs/1")
        assert resp.status_code == 302  # Redirect back

    def test_delete_log_post_method(self, client, populated_db):
        """Delete via POST with _method=DELETE (browser form)."""
        resp = client.post("/logs/1", data={"_method": "DELETE"}, follow_redirects=True)
        assert resp.status_code == 200

    def test_delete_log_404(self, client):
        resp = client.delete("/logs/99999")
        assert resp.status_code == 404

    def test_delete_removes_from_project_detail(self, client, populated_db):
        """After deletion, log no longer appears on project detail."""
        # Delete the sprint planning notes (log 1) from project 1
        client.delete("/logs/1", follow_redirects=True)
        resp = client.get("/projects/1")
        assert b"Sprint planning notes" not in resp.data

    def test_delete_removes_from_task_detail(self, client, populated_db):
        """After deletion, log no longer appears on task detail."""
        # Delete the blocker update (log 3) from task 1
        client.delete("/logs/3", follow_redirects=True)
        resp = client.get("/tasks/1")
        assert b"Blocker update" not in resp.data
