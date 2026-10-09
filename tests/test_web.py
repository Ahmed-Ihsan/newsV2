"""Tests for the web dashboard module."""

import pytest


def test_web_import():
    """Test that the web module can be imported."""
    from trend_radar.web import create_app, HAS_FASTAPI
    assert isinstance(HAS_FASTAPI, bool)


def test_web_create_app():
    """Test that create_app returns a FastAPI instance."""
    from trend_radar.web import create_app, HAS_FASTAPI
    if not HAS_FASTAPI:
        pytest.skip("fastapi not installed")
    app = create_app()
    assert app is not None
    assert app.title == "Trend Radar"


def test_web_dashboard_html():
    """Test that the dashboard HTML is generated."""
    from trend_radar.web import _dashboard_html
    html = _dashboard_html()
    assert "Trend Radar" in html
    assert "<!DOCTYPE html>" in html
    assert "fetch" in html.lower()


def test_web_api_routes():
    """Test that all expected API routes are registered."""
    from trend_radar.web import create_app, HAS_FASTAPI
    if not HAS_FASTAPI:
        pytest.skip("fastapi not installed")
    app = create_app()
    routes = [r.path for r in app.routes]
    assert "/" in routes
    assert "/api/fetch" in routes
    assert "/api/ai" in routes
    assert "/api/search" in routes
    assert "/api/keywords" in routes
    assert "/api/stats" in routes
    assert "/api/sources" in routes
