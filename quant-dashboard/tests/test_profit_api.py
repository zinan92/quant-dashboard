"""Tests for profit API endpoints: /profit and /daily."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from src.backtest.portfolio import Trade
from src.backtest.store import BacktestStore


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def auth_token(client: TestClient) -> str:
    """Login and return an access token for authenticated requests."""
    response = client.post(
        "/api/v1/token/login",
        auth=("admin", "admin"),
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def temp_store() -> BacktestStore:
    """Create a temporary backtest store for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    store = BacktestStore(db_path)
    yield store
    # Cleanup
    db_path.unlink()


class TestProfitEmptyState:
    """Test /profit endpoint with no backtest data (empty state)."""

    def test_profit_returns_200(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Profit endpoint returns 200 even with no backtest data."""
        # Mock with empty store
        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/profit",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert response.status_code == 200
        finally:
            app.api.profit._store = original_store

    def test_profit_empty_returns_zeroed_values(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Empty state returns all fields as zeros (not null/NaN)."""
        # Mock with empty store
        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/profit",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            # Check all required fields are present and numeric
            assert data["profit_closed_coin"] == 0.0
            assert data["profit_all_coin"] == 0.0
            assert data["trade_count"] == 0
            assert data["winrate"] == 0.0
            assert data["sharpe"] == 0.0
            assert data["sortino"] == 0.0
            assert data["max_drawdown"] == 0.0
            assert data["max_drawdown_abs"] == 0.0
            assert data["profit_factor"] == 0.0
        finally:
            app.api.profit._store = original_store

    def test_profit_empty_no_null_fields(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """All numeric fields are numbers, not null."""
        # Mock with empty store
        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/profit",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            # Check that numeric fields are not None
            numeric_fields = [
                "profit_closed_coin", "profit_all_coin", "trade_count",
                "winrate", "sharpe", "sortino", "max_drawdown", "max_drawdown_abs",
                "profit_factor", "expectancy", "expectancy_ratio"
            ]
            for field in numeric_fields:
                assert field in data
                assert data[field] is not None
                assert isinstance(data[field], (int, float))
        finally:
            app.api.profit._store = original_store

    def test_profit_requires_auth(self, client: TestClient) -> None:
        """Profit endpoint requires authentication."""
        response = client.get("/api/v1/profit")
        assert response.status_code == 401


class TestDailyEmptyState:
    """Test /daily endpoint with no backtest data (empty state)."""

    def test_daily_returns_200(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Daily endpoint returns 200 even with no backtest data."""
        # Mock with empty store
        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/daily",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert response.status_code == 200
        finally:
            app.api.profit._store = original_store

    def test_daily_empty_returns_empty_array(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Empty state returns empty data array."""
        # Mock with empty store
        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/daily",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            assert "data" in data
            assert isinstance(data["data"], list)
            assert len(data["data"]) == 0
        finally:
            app.api.profit._store = original_store

    def test_daily_empty_has_currency_fields(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Empty state still includes currency fields."""
        # Mock with empty store
        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/daily",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            assert data["stake_currency"] == "CNY"
            assert data["fiat_display_currency"] == "CNY"
        finally:
            app.api.profit._store = original_store

    def test_daily_requires_auth(self, client: TestClient) -> None:
        """Daily endpoint requires authentication."""
        response = client.get("/api/v1/daily")
        assert response.status_code == 401


class TestProfitWithBacktestData:
    """Test /profit endpoint with actual backtest data."""

    def test_profit_with_trades_returns_metrics(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Profit returns calculated metrics from backtest trades."""
        # Create a mock backtest with trades
        trades = [
            Trade(
                trade_id=1,
                symbol="000001",
                entry_date="2025-11-03",
                exit_date="2025-11-10",
                entry_price=10.0,
                exit_price=11.0,
                shares=1000,
                pnl=1000.0,
                pnl_pct=0.10,
                commission_total=10.0,
            ),
            Trade(
                trade_id=2,
                symbol="000002",
                entry_date="2025-11-05",
                exit_date="2025-11-12",
                entry_price=20.0,
                exit_price=19.0,
                shares=500,
                pnl=-500.0,
                pnl_pct=-0.05,
                commission_total=10.0,
            ),
        ]

        metrics = {
            "total_return": 0.05,
            "annualized_return": 0.15,
            "sharpe": 1.2,
            "sortino": 1.5,
            "calmar": 0.8,
            "max_drawdown": 0.10,
            "max_drawdown_abs": 10000.0,
            "winrate": 0.5,
        }

        temp_store.save_run(
            strategy="chan_theory",
            start_date="2025-11-03",
            end_date="2025-11-12",
            initial_capital=100000.0,
            metrics=metrics,
            trades=trades,
            nav_history=[],
        )

        # Monkey patch the store in the profit module
        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/profit",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert response.status_code == 200
            data = response.json()

            # Check metrics are populated
            assert data["trade_count"] == 2
            assert data["winning_trades"] == 1
            assert data["losing_trades"] == 1
            assert data["winrate"] == 0.5
            assert data["sharpe"] == 1.2
            assert data["sortino"] == 1.5
            assert data["max_drawdown"] == 0.10

        finally:
            # Restore original store
            app.api.profit._store = original_store

    def test_profit_calculates_best_pair(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Profit calculates best performing pair."""
        trades = [
            Trade(
                trade_id=1,
                symbol="000001",
                entry_date="2025-11-03",
                exit_date="2025-11-10",
                entry_price=10.0,
                exit_price=12.0,
                shares=1000,
                pnl=2000.0,
                pnl_pct=0.20,
                commission_total=10.0,
            ),
            Trade(
                trade_id=2,
                symbol="000002",
                entry_date="2025-11-05",
                exit_date="2025-11-12",
                entry_price=20.0,
                exit_price=21.0,
                shares=500,
                pnl=500.0,
                pnl_pct=0.05,
                commission_total=10.0,
            ),
        ]

        temp_store.save_run(
            strategy="chan_theory",
            start_date="2025-11-03",
            end_date="2025-11-12",
            initial_capital=100000.0,
            metrics={},
            trades=trades,
            nav_history=[],
        )

        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/profit",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            assert data["best_pair"] == "000001"
            assert data["best_rate"] > 0

        finally:
            app.api.profit._store = original_store


class TestDailyWithBacktestData:
    """Test /daily endpoint with actual backtest data."""

    def test_daily_returns_nav_history(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Daily returns per-day NAV entries."""
        nav_history = [
            {"date": "2025-11-03", "nav": 100000.0, "daily_return": 0.0},
            {"date": "2025-11-04", "nav": 101000.0, "daily_return": 0.01},
            {"date": "2025-11-05", "nav": 102000.0, "daily_return": 0.0099},
        ]

        temp_store.save_run(
            strategy="chan_theory",
            start_date="2025-11-03",
            end_date="2025-11-05",
            initial_capital=100000.0,
            metrics={},
            trades=[],
            nav_history=nav_history,
        )

        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/daily",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            assert len(data["data"]) == 3
            assert data["data"][0]["date"] == "2025-11-03"
            assert data["data"][0]["abs_profit"] == 0.0
            assert data["data"][0]["rel_profit"] == 0.0
            assert data["data"][1]["abs_profit"] == 1000.0
            assert abs(data["data"][1]["rel_profit"] - 0.01) < 0.0001  # floating point tolerance

        finally:
            app.api.profit._store = original_store

    def test_daily_includes_required_fields(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Each daily entry has required fields."""
        nav_history = [
            {"date": "2025-11-03", "nav": 100000.0, "daily_return": 0.0},
        ]

        temp_store.save_run(
            strategy="chan_theory",
            start_date="2025-11-03",
            end_date="2025-11-03",
            initial_capital=100000.0,
            metrics={},
            trades=[],
            nav_history=nav_history,
        )

        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/daily",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            entry = data["data"][0]
            assert "date" in entry
            assert "abs_profit" in entry
            assert "rel_profit" in entry
            assert "starting_balance" in entry
            assert "trade_count" in entry

        finally:
            app.api.profit._store = original_store


class TestDailyTimescaleParameter:
    """Test /daily endpoint timescale parameter."""

    def test_daily_accepts_timescale_parameter(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Daily endpoint accepts timescale query parameter."""
        # Mock with empty store
        import app.api.profit
        original_store = app.api.profit._store
        app.api.profit._store = temp_store

        try:
            response = client.get(
                "/api/v1/daily?timescale=60",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert response.status_code == 200
        finally:
            app.api.profit._store = original_store
