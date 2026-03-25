"""Tests for benchmark comparison page endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestBenchmarkComparisonPage:
    """Tests for /benchmark-comparison endpoint."""

    def test_benchmark_comparison_returns_200(self) -> None:
        """Benchmark comparison page endpoint returns 200."""
        response = client.get("/benchmark-comparison")
        assert response.status_code == 200

    def test_benchmark_comparison_returns_html(self) -> None:
        """Benchmark comparison page returns HTML content."""
        response = client.get("/benchmark-comparison")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")

    def test_benchmark_comparison_html_contains_title(self) -> None:
        """Benchmark comparison HTML contains expected title."""
        response = client.get("/benchmark-comparison")
        assert response.status_code == 200
        content = response.text
        assert "Benchmark Comparison" in content
        assert "Chan Theory" in content or "CSI 300" in content

    def test_benchmark_comparison_html_contains_plotly(self) -> None:
        """Benchmark comparison HTML includes Plotly library."""
        response = client.get("/benchmark-comparison")
        assert response.status_code == 200
        content = response.text
        # Check for Plotly CDN script tag
        assert "plotly" in content.lower()
        assert "cdn" in content.lower() or "plot.ly" in content.lower()

    def test_benchmark_comparison_html_contains_chart_container(self) -> None:
        """Benchmark comparison HTML includes chart container element."""
        response = client.get("/benchmark-comparison")
        assert response.status_code == 200
        content = response.text
        # Check for chart div or similar container
        assert 'id="chart' in content

    def test_benchmark_comparison_no_auth_required(self) -> None:
        """Benchmark comparison page does not require authentication."""
        # This endpoint should be publicly accessible without auth token
        response = client.get("/benchmark-comparison")
        assert response.status_code == 200
        # If auth was required, we'd get 401 or redirect
