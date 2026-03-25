"""Tests for FastAPI endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from football_scout.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestMetaEndpoints:
    def test_get_leagues(self, client):
        resp = client.get("/api/meta/leagues")
        assert resp.status_code == 200
        data = resp.json()
        assert "leagues" in data
        assert isinstance(data["leagues"], list)

    def test_get_seasons(self, client):
        resp = client.get("/api/meta/seasons")
        assert resp.status_code == 200
        assert "seasons" in resp.json()

    def test_get_positions(self, client):
        resp = client.get("/api/meta/positions")
        assert resp.status_code == 200
        assert "positions" in resp.json()

    def test_get_sources(self, client):
        resp = client.get("/api/meta/sources")
        assert resp.status_code == 200
        sources = resp.json()["sources"]
        assert "statsbomb" in sources
        assert "understat" in sources


class TestPlayerEndpoints:
    def test_list_players_empty(self, client):
        resp = client.get("/api/players")
        assert resp.status_code == 200
        data = resp.json()
        assert "players" in data
        assert "total" in data

    def test_get_player_not_found(self, client):
        resp = client.get("/api/players/nonexistent_123")
        assert resp.status_code == 404


class TestShortlistEndpoint:
    def test_shortlist_empty_data(self, client):
        resp = client.post("/api/shortlist", json={
            "position_group": "CM",
            "max_age": 26,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "players" in data
        assert "total_matches" in data


class TestClusterEndpoint:
    def test_clusters_no_data(self, client):
        resp = client.get("/api/clusters/CM")
        # Will return 404 (no data) or 200 with empty results
        assert resp.status_code in (200, 404)


class TestReportEndpoint:
    def test_report_not_found(self, client):
        resp = client.get("/api/reports/nonexistent_123")
        assert resp.status_code == 404
