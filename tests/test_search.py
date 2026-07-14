"""Tests for the search functionality."""

import pytest


class TestSearchEmpty:
    """Search with no query."""

    def test_empty_search_loads(self, client):
        resp = client.get("/search")
        assert resp.status_code == 200

    def test_empty_search_shows_placeholder(self, client):
        resp = client.get("/search?q=")
        assert resp.status_code == 200
        assert b"Type something" in resp.data or b"type something" in resp.data.lower()


class TestKeywordSearch:
    """Test keyword search (ilike fallback for projects and logs)."""

    def test_search_finds_project(self, client, populated_db):
        """Search finds projects by name (ilike)."""
        resp = client.get("/search?q=SOC")
        assert resp.status_code == 200
        # The highlight function wraps matches in <mark> tags, so search for parts
        data = resp.data.decode()
        assert "SOC" in data and "Modernization" in data

    def test_search_finds_log_by_title(self, client, populated_db):
        """Search finds logs by title (ilike)."""
        resp = client.get("/search?q=sprint")
        assert resp.status_code == 200
        # "Sprint" will be highlighted, search for the rest
        data = resp.data.decode()
        assert "planning notes" in data

    def test_search_finds_log_by_notes(self, client, populated_db):
        """Search finds logs by notes content (ilike)."""
        resp = client.get("/search?q=Acme")
        assert resp.status_code == 200
        assert b"Vendor meeting summary" in resp.data

    def test_search_case_insensitive(self, client, populated_db):
        """Search is case-insensitive."""
        resp = client.get("/search?q=soc")
        assert resp.status_code == 200
        data = resp.data.decode()
        assert "Modernization" in data

    def test_search_partial_match(self, client, populated_db):
        """Partial word matches work."""
        resp = client.get("/search?q=Vend")
        assert resp.status_code == 200
        data = resp.data.decode()
        assert "Sync" in data or "Vendor" in data

    def test_search_no_results(self, client, populated_db):
        """Search with no matches returns empty results."""
        resp = client.get("/search?q=xyznonexistent123")
        assert resp.status_code == 200
        assert b"No results" in resp.data or b"no result" in resp.data.lower()

    def test_search_highlighting(self, client, populated_db):
        """Search results have highlighting markup."""
        resp = client.get("/search?q=SOC")
        assert resp.status_code == 200
        assert b"<mark" in resp.data or b"</mark>" in resp.data

    def test_search_semantic_disabled_gracefully(self, client, populated_db):
        """Semantic search being disabled doesn't crash the page."""
        resp = client.get("/search?q=firewall&semantic=true")
        assert resp.status_code == 200

    def test_search_shows_result_count(self, client, populated_db):
        """Search results show the total count."""
        resp = client.get("/search?q=SOC")
        assert resp.status_code == 200
        assert b"Found" in resp.data and b"results" in resp.data

    def test_search_has_semantic_toggle(self, client, populated_db):
        """Search page has a semantic search toggle checkbox."""
        resp = client.get("/search?q=SOC")
        assert resp.status_code == 200
        assert b"Semantic" in resp.data

    def test_search_shows_section_headers(self, client, populated_db):
        """Search results are grouped by type (Tasks, Projects, Logs)."""
        resp = client.get("/search?q=SOC")
        data = resp.data.decode()
        assert "Projects" in data or "Logs" in data


class TestSearchNavigation:
    """Test search-related navigation from other pages."""

    def test_search_bar_on_dashboard(self, client):
        """Search bar is accessible from the dashboard header."""
        resp = client.get("/")
        assert b'action="/search"' in resp.data or b'search' in resp.data.lower()
