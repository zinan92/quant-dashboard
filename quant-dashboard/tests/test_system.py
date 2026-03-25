"""Tests for system endpoints: ping, version, show_config, and catch-all 404."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _get_access_token() -> str:
    """Helper to get a valid access token."""
    resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
    return resp.json()["access_token"]


class TestPing:
    """GET /api/v1/ping — no auth required."""

    def test_ping_returns_200(self) -> None:
        resp = client.get("/api/v1/ping")
        assert resp.status_code == 200

    def test_ping_returns_pong(self) -> None:
        resp = client.get("/api/v1/ping")
        assert resp.json() == {"status": "pong"}

    def test_ping_no_auth_needed(self) -> None:
        """Ping should work without any auth headers."""
        resp = client.get("/api/v1/ping")
        assert resp.status_code == 200


class TestVersion:
    """GET /api/v1/version — no auth required."""

    def test_version_returns_200(self) -> None:
        resp = client.get("/api/v1/version")
        assert resp.status_code == 200

    def test_version_returns_version_field(self) -> None:
        resp = client.get("/api/v1/version")
        data = resp.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_version_value(self) -> None:
        resp = client.get("/api/v1/version")
        assert resp.json()["version"] == "1.0.0"


class TestShowConfig:
    """GET /api/v1/show_config — requires auth."""

    def test_show_config_returns_200(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_show_config_runmode(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["runmode"] == "webserver"

    def test_show_config_stake_currency(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["stake_currency"] == "CNY"

    def test_show_config_api_version(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["api_version"] >= 2.34

    def test_show_config_exchange(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["exchange"] == "ashare"

    def test_show_config_bot_name(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["bot_name"] == "A-Share Quant Dashboard"

    def test_show_config_timeframe(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["timeframe"] == "1d"

    def test_show_config_strategy(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["strategy"] == "chan_theory"

    def test_show_config_state(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["state"] == "running"

    def test_show_config_dry_run(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["dry_run"] is True

    def test_show_config_trading_mode(self) -> None:
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.json()["trading_mode"] == "spot"

    def test_show_config_all_required_fields(self) -> None:
        """Verify all required fields are present in one assertion."""
        token = _get_access_token()
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        required_fields = [
            "runmode", "stake_currency", "api_version", "exchange",
            "bot_name", "timeframe", "strategy", "state", "dry_run",
            "trading_mode",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestCatchAll404:
    """Any unmatched /api/v1/* path returns 404 JSON, NEVER 500."""

    def test_nonexistent_endpoint_returns_404(self) -> None:
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404

    def test_nonexistent_returns_json(self) -> None:
        resp = client.get("/api/v1/nonexistent")
        data = resp.json()
        assert data == {"detail": "Not found"}

    def test_nonexistent_post_returns_404(self) -> None:
        resp = client.post("/api/v1/nonexistent")
        assert resp.status_code == 404

    def test_nonexistent_put_returns_404(self) -> None:
        resp = client.put("/api/v1/nonexistent")
        assert resp.status_code == 404

    def test_nonexistent_delete_returns_404(self) -> None:
        resp = client.delete("/api/v1/nonexistent")
        assert resp.status_code == 404

    def test_deeply_nested_nonexistent_returns_404(self) -> None:
        resp = client.get("/api/v1/some/deep/nested/path")
        assert resp.status_code == 404

    def test_nonexistent_never_returns_500(self) -> None:
        """Explicitly test that common unimplemented FreqUI endpoints don't 500."""
        paths = [
            "/api/v1/profit",
            "/api/v1/locks",
            "/api/v1/balance",
            "/api/v1/logs",
            "/api/v1/sysinfo",
        ]
        for path in paths:
            resp = client.get(path)
            assert resp.status_code != 500, f"{path} returned 500!"
            # Should be 404 (or 401/403 if auth is required before catch-all)
            assert resp.status_code in (404, 401, 403), f"{path} returned unexpected {resp.status_code}"
