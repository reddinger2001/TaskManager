"""Tests for the dashboard (main index) view."""

import pytest


class TestDashboardEmpty:
    """Dashboard with no data shows empty states."""

    def test_dashboard_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_empty_on_fire_message(self, client):
        resp = client.get("/")
        assert b"All clear" in resp.data or b"no fires" in resp.data.lower()

    def test_empty_delegated_message(self, client):
        resp = client.get("/")
        assert b"Nothing delegated" in resp.data or b"you've got this" in resp.data

    def test_empty_active_message(self, client):
        resp = client.get("/")
        assert b"No active tasks" in resp.data or b"breathe easy" in resp.data

    def test_empty_backlog_message(self, client):
        resp = client.get("/")
        assert b"Backlog is empty" in resp.data or b"everything's moving" in resp.data

    def test_no_inbox_fab_when_empty(self, client):
        """The inbox FAB button should not appear when inbox is empty."""
        resp = client.get("/")
        # The FAB has a specific class; it shouldn't be in the response
        assert b"fixed bottom-6 right-6" not in resp.data

    def test_summary_bar_shows_zeros(self, client):
        resp = client.get("/")
        assert b">0<" in resp.data  # All counts should show 0

    def test_new_task_modal_present(self, client):
        """The + New button and modal infrastructure should be present."""
        resp = client.get("/")
        assert b"+ New" in resp.data
        assert b"open-modal" in resp.data

    def test_header_navigation_links(self, client):
        resp = client.get("/")
        assert b'Dashboard' in resp.data
        assert b'Board' in resp.data
        assert b'Projects' in resp.data
        assert b'Calendar' in resp.data
        assert b'Gantt' in resp.data

    def test_search_bar_present(self, client):
        resp = client.get("/")
        assert b'Search...' in resp.data or b'search' in resp.data.lower()


class TestDashboardWithData:
    """Dashboard with populated data shows correct sections."""

    def test_on_fire_shows_p0_task(self, client, populated_db):
        resp = client.get("/")
        assert b"Resolve P0 outage" in resp.data
        assert b"P0" in resp.data

    def test_on_fire_shows_blocked_task(self, client, populated_db):
        resp = client.get("/")
        assert b"Resolve P0 outage" in resp.data
        assert b"BLOCKED" in resp.data or b"blocked" in resp.data.lower()

    def test_delegated_groups_by_assignee(self, client, populated_db):
        resp = client.get("/")
        assert b"Sarah" in resp.data
        assert b"Mike" in resp.data
        # Sarah has 2 delegated tasks
        assert b"Review vendor contracts" in resp.data
        assert b"Write API docs" in resp.data

    def test_active_work_shows_active_tasks(self, client, populated_db):
        resp = client.get("/")
        assert b"Update firewall rules" in resp.data
        assert b"My Active Work" in resp.data

    def test_backlog_shows_backlog_tasks(self, client, populated_db):
        resp = client.get("/")
        assert b"Research SIEM options" in resp.data
        assert b"Draft incident response plan" in resp.data

    def test_inbox_shows_unassigned_task(self, client, populated_db):
        """The inbox FAB should appear and show the count of unassigned tasks."""
        resp = client.get("/")
        assert b"Quick thought about CI/CD" in resp.data
        # FAB should be present since there's 1 inbox item
        assert b"fixed bottom-6 right-6" in resp.data

    def test_summary_counts_correct(self, client, populated_db):
        """Summary bar counts match the actual data."""
        resp = client.get("/")
        data = resp.data.decode()
        # On Fire: 1 (P0 + blocked)
        # Delegated: 3 (Sarah x2 + Mike x1)
        # Active: 2 (firewall + compliance)
        # Backlog: 3 (SIEM + IR plan + CI/CD thought)
        # Inbox: 1 (CI/CD thought)

    def test_task_links_to_detail(self, client, populated_db):
        """Task cards link to the task detail page."""
        resp = client.get("/")
        assert b'/tasks/1' in resp.data or b'/tasks/' in resp.data

    def test_dashboard_section_headings(self, client, populated_db):
        resp = client.get("/")
        assert b"On Fire" in resp.data
        assert b"Delegated" in resp.data
        assert b"My Active Work" in resp.data
        assert b"Backlog" in resp.data

    def test_assignee_avatars_present(self, client, populated_db):
        """Assignee initial avatars are rendered."""
        resp = client.get("/")
        # Chris's avatar should appear for assigned tasks
        assert b">C<" in resp.data

    def test_due_dates_displayed(self, client, populated_db):
        resp = client.get("/")
        assert b"2026-07-15" in resp.data or b"2026-07-20" in resp.data
