"""Tests for v0.5.0 web API endpoints: /api/diff, /api/health, /api/top."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from trend_radar.models import IntelItem, SourceType, TrendSnapshot


@pytest.fixture
def app_client():
    """Create a test client for the web app."""
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not installed")

    # Create a mock radar
    radar = MagicMock()
    radar.config = MagicMock()
    radar.config.cache_enabled = False
    radar.sources = {"github": MagicMock()}

    from trend_radar.web import create_app
    app = create_app(radar=radar)
    client = TestClient(app)
    return client, radar


class TestDiffEndpoint:
    """Test /api/diff endpoint."""

    def test_diff_endpoint(self, app_client):
        client, radar = app_client
        radar.diff_snapshots.return_value = {
            "rising": [], "falling": [], "new": [], "gone": [],
            "current_count": 0, "previous_count": 0,
            "current_ts": "", "previous_ts": "",
        }
        resp = client.get("/api/diff")
        assert resp.status_code == 200
        data = resp.json()
        assert "rising" in data

    def test_diff_with_data(self, app_client):
        client, radar = app_client
        radar.diff_snapshots.return_value = {
            "rising": [{"title": "repo1", "score_delta": 50, "score": 150, "source": "github"}],
            "falling": [],
            "new": [],
            "gone": [],
            "current_count": 5,
            "previous_count": 3,
            "current_ts": "2026-05-13T00:00:00",
            "previous_ts": "2026-05-12T00:00:00",
        }
        resp = client.get("/api/diff")
        assert resp.status_code == 200
        assert len(resp.json()["rising"]) == 1


class TestHealthEndpoint:
    """Test /api/health endpoint."""

    def test_health_endpoint(self, app_client):
        client, radar = app_client
        radar.check_health.return_value = {
            "github": {"status": "ok", "latency_ms": 150, "items_fetched": 3, "error": None},
        }
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["github"]["status"] == "ok"


class TestTopEndpoint:
    """Test /api/top endpoint."""

    def test_top_endpoint(self, app_client):
        client, radar = app_client
        radar.get_top_items.return_value = [
            IntelItem(title="repo1", source=SourceType.GITHUB, score=100),
        ]
        resp = client.get("/api/top")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1

    def test_top_with_params(self, app_client):
        client, radar = app_client
        radar.get_top_items.return_value = []
        resp = client.get("/api/top?limit=5&topic=ai&source=github")
        assert resp.status_code == 200


class TestDockerfile:
    """Test that Dockerfile exists and is valid."""

    def test_dockerfile_exists(self):
        dockerfile = Path("/tmp/dev/trend-radar/Dockerfile")
        assert dockerfile.exists()

    def test_dockerfile_has_entrypoint(self):
        content = Path("/tmp/dev/trend-radar/Dockerfile").read_text()
        assert "ENTRYPOINT" in content
        assert "trend-radar" in content

    def test_dockerfile_exposes_port(self):
        content = Path("/tmp/dev/trend-radar/Dockerfile").read_text()
        assert "EXPOSE 8765" in content

    def test_dockerignore_exists(self):
        dockerignore = Path("/tmp/dev/trend-radar/.dockerignore")
        assert dockerignore.exists()
