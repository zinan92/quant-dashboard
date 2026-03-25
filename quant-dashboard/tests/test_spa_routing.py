"""Test SPA routing and static file serving."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestAPIRoutesPrecedence:
    """API routes should return JSON, not HTML."""

    def test_api_ping_returns_json(self):
        """GET /api/v1/ping returns JSON, not HTML."""
        resp = client.get("/api/v1/ping")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        assert "status" in resp.json()

    def test_api_version_returns_json(self):
        """GET /api/v1/version returns JSON, not HTML."""
        resp = client.get("/api/v1/version")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        assert "version" in resp.json()

    def test_api_strategies_returns_json(self):
        """GET /api/v1/strategies returns JSON, not HTML."""
        # Get token first
        auth = client.post("/api/v1/token/login", auth=("admin", "admin"))
        token = auth.json()["access_token"]

        resp = client.get(
            "/api/v1/strategies",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")

    def test_nonexistent_api_route_returns_json_404(self):
        """Non-existent API routes return JSON 404, not HTML."""
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404
        assert resp.headers["content-type"].startswith("application/json")
        # Should NOT be HTML
        assert not resp.text.startswith("<!DOCTYPE html>")


class TestSPAFallback:
    """Non-API routes should serve index.html for SPA routing."""

    def test_root_returns_html(self):
        """GET / returns HTML (index.html)."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        # Verify it's actually index.html from FreqUI
        assert "<!DOCTYPE html>" in resp.text
        assert "FreqUI" in resp.text

    def test_backtest_deep_link_returns_html(self):
        """GET /backtest returns HTML (SPA fallback)."""
        resp = client.get("/backtest")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "<!DOCTYPE html>" in resp.text
        assert "FreqUI" in resp.text

    def test_trade_deep_link_returns_html(self):
        """GET /trade returns HTML (SPA fallback)."""
        resp = client.get("/trade")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")
        assert "FreqUI" in resp.text

    def test_dashboard_deep_link_returns_html(self):
        """GET /dashboard returns HTML (SPA fallback)."""
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_nested_route_returns_html(self):
        """Nested routes like /backtest/results return HTML."""
        resp = client.get("/backtest/results/123")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")


class TestStaticAssets:
    """Static assets should be served with correct MIME types."""

    def test_favicon_accessible(self):
        """GET /favicon.ico returns an image."""
        resp = client.get("/favicon.ico")
        # May be 200 if exists, 404 if not — just verify it's not HTML
        if resp.status_code == 200:
            # Should be an image type
            assert "image" in resp.headers.get("content-type", "")

    def test_js_files_have_correct_mime_type(self):
        """JavaScript files under /assets/ have application/javascript MIME type."""
        # Find a JS file from the build output
        # From build output: index-BYHE955S.js
        resp = client.get("/assets/index-BYHE955S.js")
        if resp.status_code == 200:
            # Should be JavaScript MIME type
            content_type = resp.headers.get("content-type", "")
            assert (
                "javascript" in content_type or "text/javascript" in content_type
            ), f"Expected JavaScript MIME type, got {content_type}"

    def test_css_files_have_correct_mime_type(self):
        """CSS files under /assets/ have text/css MIME type."""
        # From build output: index-BMfDoxa3.css
        resp = client.get("/assets/index-BMfDoxa3.css")
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            assert "css" in content_type, f"Expected CSS MIME type, got {content_type}"


class TestRouteOrdering:
    """Verify that API routes take precedence over SPA fallback."""

    def test_api_route_not_caught_by_spa_fallback(self):
        """API routes are handled by API router, not SPA fallback."""
        resp = client.get("/api/v1/ping")
        # Should be JSON, not HTML
        assert resp.headers["content-type"].startswith("application/json")
        data = resp.json()
        assert data == {"status": "pong"}

    def test_spa_fallback_does_not_catch_static_assets(self):
        """Static assets are served by StaticFiles, not SPA fallback."""
        # Try to access a known asset
        # If build succeeded, this should serve the actual file
        resp = client.get("/assets/index-BYHE955S.js")
        # Should either be 200 (file served) or 404 (file not found)
        # Should NOT be HTML
        if resp.status_code == 200:
            assert not resp.text.startswith("<!DOCTYPE html>")
            assert resp.headers["content-type"] != "text/html"
