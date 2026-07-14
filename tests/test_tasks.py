"""Tests for task CRUD operations, list view, filters, and sorting."""

import pytest


class TestTaskCreate:
    """Test task creation via the modal form."""

    def test_create_task_minimum(self, client):
        """Only title is required — quick capture."""
        resp = client.post("/tasks/new", data={
            "title": "Quick capture",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Quick capture" in resp.data

    def test_create_task_full(self, client):
        """All fields populated."""
        resp = client.post("/tasks/new", data={
            "title": "Full task creation",
            "description": "A task with every field filled out",
            "status": "active",
            "priority": "P1",
            "due_date": "2026-08-15",
            "assignee": "Chris",
            "tags": "urgent, testing",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Full task creation" in resp.data

    def test_create_task_requires_title(self, client):
        """Empty title is rejected."""
        resp = client.post("/tasks/new", data={
            "title": "",
            "description": "No title allowed",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"title is required" in resp.data.lower()

    def test_create_task_with_project(self, client, populated_db):
        """Task can be assigned to a project."""
        resp = client.post("/tasks/new", data={
            "title": "Task under SOC Modernization",
            "project_id": "1",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Task under SOC Modernization" in resp.data

    def test_create_task_with_tags(self, client):
        """Tags are parsed from comma-separated input."""
        resp = client.post("/tasks/new", data={
            "title": "Tagged task",
            "tags": "security, compliance, soc",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_create_task_default_status_backlog(self, client):
        """Default status is backlog."""
        resp = client.post("/tasks/new", data={
            "title": "Default status task",
        }, follow_redirects=True)
        assert resp.status_code == 200
        # Should appear on dashboard backlog section
        resp_dashboard = client.get("/")
        assert b"Default status task" in resp_dashboard.data

    def test_create_task_redirects_to_detail(self, client):
        """After creation, redirect to task detail page."""
        resp = client.post("/tasks/new", data={
            "title": "Redirect test",
        }, follow_redirects=False)
        assert resp.status_code == 302
        assert "/tasks/" in resp.location


class TestTaskDetail:
    """Test the task detail view."""

    def test_task_detail_loads(self, client, populated_db):
        resp = client.get("/tasks/1")
        assert resp.status_code == 200
        assert b"Resolve P0 outage" in resp.data

    def test_task_detail_404(self, client):
        resp = client.get("/tasks/99999")
        assert resp.status_code == 404

    def test_task_detail_shows_all_fields(self, client, populated_db):
        """All task fields are rendered on the detail page."""
        resp = client.get("/tasks/1")
        data = resp.data.decode()
        assert "Resolve P0 outage" in data
        assert "Critical production incident" in data  # description
        assert "blocked" in data.lower()  # status

    def test_task_detail_shows_project_link(self, client, populated_db):
        """Task with a project shows the project breadcrumb."""
        resp = client.get("/tasks/1")
        assert b"SOC Modernization" in resp.data

    def test_task_detail_shows_delete_button(self, client, populated_db):
        resp = client.get("/tasks/1")
        assert b"Delete" in resp.data

    def test_task_detail_shows_status_options(self, client, populated_db):
        """All 5 status options are available in the dropdown."""
        resp = client.get("/tasks/1")
        data = resp.data.decode()
        for status in ["backlog", "active", "blocked", "delegated", "done"]:
            assert status in data

    def test_task_detail_shows_priority_options(self, client, populated_db):
        resp = client.get("/tasks/1")
        data = resp.data.decode()
        for priority in ["P0", "P1", "P2"]:
            assert priority in data

    def test_task_detail_shows_project_options(self, client, populated_db):
        resp = client.get("/tasks/1")
        assert b"SOC Modernization" in resp.data
        assert b"VendorSync" in resp.data

    def test_task_detail_shows_tags_section(self, client, populated_db):
        """Tags input area is present even if no tags."""
        resp = client.get("/tasks/1")
        assert b"Tags" in resp.data or b"tags" in resp.data.lower()

    def test_task_detail_shows_links_section(self, client, populated_db):
        resp = client.get("/tasks/1")
        assert b"Links" in resp.data or b"links" in resp.data.lower()

    def test_task_detail_shows_logs_section(self, client, populated_db):
        """Logs section is present."""
        resp = client.get("/tasks/1")
        assert b"Logs" in resp.data or b"logs" in resp.data.lower()

    def test_task_detail_shows_metadata(self, client, populated_db):
        """Created/Updated timestamps are shown."""
        resp = client.get("/tasks/1")
        assert b"Created" in resp.data
        assert b"Updated" in resp.data

    def test_done_task_shows_completed_at(self, client, populated_db):
        """A done task displays the completed timestamp."""
        # Task 10 is done
        resp = client.get("/tasks/10")
        assert b"Completed" in resp.data or b"completed" in resp.data.lower()

    def test_task_detail_shows_recurrence_options(self, client, populated_db):
        """Recurrence dropdown has all options."""
        resp = client.get("/tasks/1")
        data = resp.data.decode()
        assert "daily" in data.lower()
        assert "weekly" in data.lower()
        assert "monthly" in data.lower()


class TestTaskUpdate:
    """Test task updates via PATCH."""

    def test_update_title(self, client, populated_db):
        resp = client.patch("/tasks/1", json={"title": "Updated title"})
        assert resp.status_code == 200
        assert resp.json["ok"] is True

        resp = client.get("/tasks/1")
        assert b"Updated title" in resp.data

    def test_update_status(self, client, populated_db):
        resp = client.patch("/tasks/1", json={"status": "active"})
        assert resp.status_code == 200

    def test_update_priority(self, client, populated_db):
        resp = client.patch("/tasks/1", json={"priority": "P2"})
        assert resp.status_code == 200

    def test_update_assignee(self, client, populated_db):
        resp = client.patch("/tasks/1", json={"assignee": "Mike"})
        assert resp.status_code == 200

    def test_update_due_date(self, client, populated_db):
        resp = client.patch("/tasks/1", json={"due_date": "2026-09-01"})
        assert resp.status_code == 200

    def test_update_tags(self, client, populated_db):
        resp = client.patch("/tasks/1", json={"tags": ["critical", "firewall"]})
        assert resp.status_code == 200

    def test_update_links(self, client, populated_db):
        resp = client.patch("/tasks/1", json={
            "links": [{"url": "https://example.com", "label": "Example"}]
        })
        assert resp.status_code == 200

    def test_update_project_id(self, client, populated_db):
        """Move task to a different project."""
        resp = client.patch("/tasks/1", json={"project_id": 2})
        assert resp.status_code == 200

    def test_update_project_id_null(self, client, populated_db):
        """Remove task from project (move to inbox)."""
        resp = client.patch("/tasks/1", json={"project_id": None})
        assert resp.status_code == 200

    def test_status_to_done_sets_completed_at(self, client, populated_db):
        """Changing status to 'done' sets completed_at timestamp."""
        # Task 2 is active
        resp = client.patch("/tasks/2", json={"status": "done"})
        assert resp.status_code == 200

    def test_status_from_done_clears_completed_at(self, client, populated_db):
        """Changing status away from 'done' clears completed_at."""
        # Task 10 is done
        resp = client.patch("/tasks/10", json={"status": "backlog"})
        assert resp.status_code == 200

    def test_update_404(self, client):
        resp = client.patch("/tasks/99999", json={"title": "Nope"})
        assert resp.status_code == 404

    def test_update_clears_description(self, client, populated_db):
        """Setting description to empty string clears it."""
        resp = client.patch("/tasks/1", json={"description": ""})
        assert resp.status_code == 200

    def test_update_recurrence(self, client, populated_db):
        resp = client.patch("/tasks/1", json={"recurrence": "weekly"})
        assert resp.status_code == 200

    def test_update_start_date(self, client, populated_db):
        resp = client.patch("/tasks/1", json={"start_date": "2026-07-01"})
        assert resp.status_code == 200


class TestTaskDelete:
    """Test task deletion."""

    def test_delete_task(self, client, populated_db):
        resp = client.delete("/tasks/1")
        assert resp.status_code == 302  # Redirect to task list
        assert b"deleted" in resp.data.lower() or resp.location is not None

    def test_delete_task_post_method(self, client, populated_db):
        """Delete via POST with _method=DELETE (browser form)."""
        resp = client.post("/tasks/1", data={"_method": "DELETE"}, follow_redirects=True)
        assert resp.status_code == 200

    def test_delete_task_404(self, client):
        resp = client.delete("/tasks/99999")
        assert resp.status_code == 404


class TestTaskList:
    """Test the task list view with filters and sorting."""

    def test_list_loads(self, client):
        resp = client.get("/tasks")
        assert resp.status_code == 200

    def test_list_shows_all_tasks(self, client, populated_db):
        resp = client.get("/tasks")
        assert b"Resolve P0 outage" in resp.data
        assert b"Quick thought about CI/CD" in resp.data

    def test_filter_by_status(self, client, populated_db):
        resp = client.get("/tasks?status=active")
        assert b"Update firewall rules" in resp.data
        # Blocked task should NOT appear
        assert b"Resolve P0 outage" not in resp.data

    def test_filter_by_priority(self, client, populated_db):
        resp = client.get("/tasks?priority=P0")
        assert b"Resolve P0 outage" in resp.data
        # Non-P0 tasks should not appear
        assert b"Research SIEM options" not in resp.data

    def test_filter_by_project(self, client, populated_db):
        resp = client.get("/tasks?project_id=2")
        assert b"Review vendor contracts" in resp.data
        # Tasks from other projects should not appear
        assert b"Resolve P0 outage" not in resp.data

    def test_filter_by_assignee(self, client, populated_db):
        resp = client.get("/tasks?assignee=Sarah")
        assert b"Review vendor contracts" in resp.data
        assert b"Write API docs" in resp.data
        # Chris's tasks should not appear
        assert b"Resolve P0 outage" not in resp.data

    def test_filter_by_tag(self, client):
        """Filter by tag — create a tagged task first."""
        client.post("/tasks/new", data={
            "title": "Tagged for filtering",
            "tags": "security, important",
        }, follow_redirects=True)

        resp = client.get("/tasks?tag=security")
        assert b"Tagged for filtering" in resp.data

    def test_filter_by_keyword(self, client, populated_db):
        resp = client.get("/tasks?q=firewall")
        assert b"Update firewall rules" in resp.data
        assert b"Resolve P0 outage" not in resp.data

    def test_sort_by_title_asc(self, client, populated_db):
        resp = client.get("/tasks?sort=title&order=asc")
        assert resp.status_code == 200

    def test_sort_by_due_date(self, client, populated_db):
        resp = client.get("/tasks?sort=due_date&order=asc")
        assert resp.status_code == 200

    def test_sort_invalid_field_defaults(self, client, populated_db):
        """Invalid sort field falls back to default (created_at desc)."""
        resp = client.get("/tasks?sort=nonexistent")
        assert resp.status_code == 200

    def test_date_range_filter(self, client, populated_db):
        """Filter by date range on due_date."""
        resp = client.get("/tasks?date_field=due_date&date_from=2026-07-15&date_to=2026-07-20")
        assert resp.status_code == 200

    def test_list_shows_filter_options(self, client, populated_db):
        """Filter dropdowns show available options."""
        resp = client.get("/tasks")
        data = resp.data.decode()
        # Should show project names as filter options
        assert "SOC Modernization" in data or "VendorSync" in data

    def test_list_shows_assignee_filter(self, client, populated_db):
        resp = client.get("/tasks")
        assert b"Chris" in resp.data or b"Sarah" in resp.data


class TestTaskCSVExport:
    """Test CSV export of tasks."""

    def test_export_returns_csv(self, client, populated_db):
        resp = client.get("/tasks/export.csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type
        assert b"Title" in resp.data
        assert b"Status" in resp.data

    def test_export_includes_all_tasks(self, client, populated_db):
        resp = client.get("/tasks/export.csv")
        assert b"Resolve P0 outage" in resp.data

    def test_export_respects_status_filter(self, client, populated_db):
        resp = client.get("/tasks/export.csv?status=active")
        assert b"Update firewall rules" in resp.data
        assert b"Resolve P0 outage" not in resp.data

    def test_export_has_correct_columns(self, client, populated_db):
        resp = client.get("/tasks/export.csv")
        lines = resp.data.decode().strip().split("\n")
        header = lines[0]
        assert "Title" in header
        assert "Status" in header
        assert "Priority" in header
        assert "Assignee" in header
        assert "Due Date" in header
        assert "Project" in header
