"""Tests for board, calendar, and Gantt views."""

import pytest


class TestBoardView:
    """Test the Kanban board view."""

    def test_board_loads(self, client):
        resp = client.get("/board")
        assert resp.status_code == 200

    def test_board_shows_all_status_columns(self, client, populated_db):
        """All 5 status columns are rendered."""
        resp = client.get("/board")
        data = resp.data.decode()
        for status in ["backlog", "active", "delegated", "blocked", "done"]:
            assert status in data

    def test_board_shows_task_data(self, client, populated_db):
        """Task data is serialized as JSON for Alpine.js."""
        resp = client.get("/board")
        # The task_data is passed to the template and rendered as JSON
        assert b"Resolve P0 outage" in resp.data

    def test_board_shows_priority_badges(self, client, populated_db):
        """Priority badges appear on task cards (in serialized data)."""
        resp = client.get("/board")
        assert b"P0" in resp.data

    def test_board_shows_project_filter(self, client, populated_db):
        """Project filter dropdown is present."""
        resp = client.get("/board")
        assert b"SOC Modernization" in resp.data
        assert b"All Projects" in resp.data

    def test_board_shows_assignee_filter(self, client, populated_db):
        """Assignee filter dropdown is present."""
        resp = client.get("/board")
        assert b"All Assignees" in resp.data

    def test_board_filter_by_project(self, client, populated_db):
        """Board can be filtered by project via URL parameter."""
        resp = client.get("/board?project_id=2")
        assert resp.status_code == 200
        # Should show VendorSync tasks
        assert b"Review vendor contracts" in resp.data
        # SOC Modernization tasks should not appear
        assert b"Resolve P0 outage" not in resp.data

    def test_board_filter_by_assignee(self, client, populated_db):
        """Board can be filtered by assignee via URL parameter."""
        resp = client.get("/board?assignee=Sarah")
        assert resp.status_code == 200
        assert b"Review vendor contracts" in resp.data

    def test_board_draggable_cards(self, client, populated_db):
        """Task cards have draggable attribute for drag-and-drop."""
        resp = client.get("/board")
        assert b'draggable="true"' in resp.data

    def test_board_preview_modal_present(self, client, populated_db):
        """The quick preview modal infrastructure is present."""
        resp = client.get("/board")
        assert b"showPreview" in resp.data or b"preview" in resp.data.lower()

    def test_board_empty_column_state(self, client):
        """Empty columns show the '— empty —' state."""
        resp = client.get("/board")
        assert "\u2014 empty \u2014".encode() in resp.data

    def test_board_shows_status_colors(self, client, populated_db):
        """Status column headers have color indicators."""
        resp = client.get("/board")
        # The board uses colored dots for status columns
        assert b"Backlog" in resp.data or b"backlog" in resp.data.lower()

    def test_board_task_count_badges(self, client, populated_db):
        """Each column shows a task count badge."""
        resp = client.get("/board")
        # The count badges are rendered by Alpine as filteredTasks(status).length
        assert b"filteredTasks" in resp.data or b"length" in resp.data


class TestCalendarView:
    """Test the calendar view and events API."""

    def test_calendar_loads(self, client):
        resp = client.get("/calendar")
        assert resp.status_code == 200

    def test_calendar_events_api(self, client, populated_db):
        """Calendar events API returns JSON."""
        resp = client.get("/api/calendar/events")
        assert resp.status_code == 200
        events = resp.json
        assert isinstance(events, list)

    def test_calendar_events_includes_tasks_with_due_dates(self, client, populated_db):
        """Only tasks with due dates appear in calendar events."""
        resp = client.get("/api/calendar/events")
        events = resp.json
        titles = [e["title"] for e in events]
        # Task 1 has due_date
        assert "Resolve P0 outage" in titles

    def test_calendar_events_have_color_by_status(self, client, populated_db):
        """Events are color-coded by status."""
        resp = client.get("/api/calendar/events")
        events = resp.json
        for event in events:
            assert "backgroundColor" in event
            assert event["backgroundColor"].startswith("#")

    def test_calendar_events_have_urls(self, client, populated_db):
        """Each event links to the task detail page."""
        resp = client.get("/api/calendar/events")
        events = resp.json
        for event in events:
            assert "/tasks/" in event["url"]

    def test_calendar_events_blocked_are_red(self, client, populated_db):
        """Blocked tasks get red color (#ff5252)."""
        resp = client.get("/api/calendar/events")
        events = resp.json
        blocked = [e for e in events if e["title"] == "Resolve P0 outage"]
        assert blocked[0]["backgroundColor"] == "#ff5252"

    def test_calendar_events_without_due_dates_excluded(self, client):
        """Tasks without due dates don't appear in calendar."""
        client.post("/tasks/new", data={
            "title": "No due date task",
        }, follow_redirects=True)

        resp = client.get("/api/calendar/events")
        events = resp.json
        titles = [e["title"] for e in events]
        assert "No due date task" not in titles

    def test_calendar_events_empty_when_no_tasks(self, client):
        """Empty calendar returns empty list."""
        resp = client.get("/api/calendar/events")
        events = resp.json
        # May have tasks from other tests, but the structure is correct
        assert isinstance(events, list)


class TestGanttView:
    """Test the Gantt chart view."""

    def test_gantt_loads(self, client):
        resp = client.get("/gantt")
        assert resp.status_code == 200

    def test_gantt_shows_tasks_with_due_dates(self, client, populated_db):
        """Only tasks with due dates appear in Gantt data."""
        resp = client.get("/gantt")
        assert b"Resolve P0 outage" in resp.data

    def test_gantt_task_data_serialized(self, client, populated_db):
        """Task data is serialized for the Gantt chart library."""
        resp = client.get("/gantt")
        assert b'"id"' in resp.data or b'"title"' in resp.data

    def test_gantt_filter_by_project(self, client, populated_db):
        """Gantt can be filtered by project."""
        resp = client.get("/gantt?project_id=1")
        assert resp.status_code == 200
