"""Tests for strategy API endpoints: GET /strategies and GET /strategy/{name}."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _get_access_token() -> str:
    """Helper to get a valid access token."""
    resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
    return resp.json()["access_token"]


def _auth_headers() -> dict[str, str]:
    """Return Authorization header dict with a valid token."""
    return {"Authorization": f"Bearer {_get_access_token()}"}


# ===========================================================================
# GET /api/v1/strategies
# ===========================================================================


class TestListStrategies:
    """GET /api/v1/strategies — returns list of available strategies."""

    def test_returns_200(self) -> None:
        resp = client.get("/api/v1/strategies", headers=_auth_headers())
        assert resp.status_code == 200

    def test_returns_strategies_key(self) -> None:
        resp = client.get("/api/v1/strategies", headers=_auth_headers())
        data = resp.json()
        assert "strategies" in data
        assert isinstance(data["strategies"], list)

    def test_includes_chan_theory(self) -> None:
        """The strategies list must include 'chan_theory'."""
        resp = client.get("/api/v1/strategies", headers=_auth_headers())
        data = resp.json()
        assert "chan_theory" in data["strategies"]

    def test_requires_auth(self) -> None:
        """Endpoint requires authentication."""
        resp = client.get("/api/v1/strategies")
        assert resp.status_code in (401, 403)

    def test_strategies_is_nonempty(self) -> None:
        resp = client.get("/api/v1/strategies", headers=_auth_headers())
        data = resp.json()
        assert len(data["strategies"]) > 0


# ===========================================================================
# GET /api/v1/strategy/{name}
# ===========================================================================


class TestGetStrategyDetail:
    """GET /api/v1/strategy/{name} — returns strategy details."""

    def test_returns_200_for_chan_theory(self) -> None:
        resp = client.get("/api/v1/strategy/chan_theory", headers=_auth_headers())
        assert resp.status_code == 200

    def test_returns_strategy_name(self) -> None:
        resp = client.get("/api/v1/strategy/chan_theory", headers=_auth_headers())
        data = resp.json()
        assert data["strategy"] == "chan_theory"

    def test_returns_timeframe(self) -> None:
        resp = client.get("/api/v1/strategy/chan_theory", headers=_auth_headers())
        data = resp.json()
        assert data["timeframe"] == "1d"

    def test_returns_code_as_string(self) -> None:
        """Code field contains the YAML strategy definition as a string."""
        resp = client.get("/api/v1/strategy/chan_theory", headers=_auth_headers())
        data = resp.json()
        assert "code" in data
        assert isinstance(data["code"], str)

    def test_code_contains_yaml_content(self) -> None:
        """The code field should contain recognizable YAML content."""
        resp = client.get("/api/v1/strategy/chan_theory", headers=_auth_headers())
        data = resp.json()
        # The YAML file has the strategy name in it
        assert "chan_theory" in data["code"] or "缠论" in data["code"]

    def test_returns_params_as_list(self) -> None:
        resp = client.get("/api/v1/strategy/chan_theory", headers=_auth_headers())
        data = resp.json()
        assert "params" in data
        assert isinstance(data["params"], list)

    def test_params_have_name_field(self) -> None:
        """Each parameter dict should have at least a 'name' field."""
        resp = client.get("/api/v1/strategy/chan_theory", headers=_auth_headers())
        data = resp.json()
        for param in data["params"]:
            assert "name" in param

    def test_all_required_fields_present(self) -> None:
        """Verify all required fields: strategy, timeframe, code, params."""
        resp = client.get("/api/v1/strategy/chan_theory", headers=_auth_headers())
        data = resp.json()
        required = ["strategy", "timeframe", "code", "params"]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_nonexistent_strategy_returns_404(self) -> None:
        resp = client.get("/api/v1/strategy/nonexistent", headers=_auth_headers())
        assert resp.status_code == 404

    def test_requires_auth(self) -> None:
        resp = client.get("/api/v1/strategy/chan_theory")
        assert resp.status_code in (401, 403)
