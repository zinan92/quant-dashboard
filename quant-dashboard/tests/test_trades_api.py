"""Tests for trades API endpoints: /trades, /status, /performance."""

from __future__ import annotations

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


class TestTradesEmptyState:
    """Test /trades endpoint with no backtest data (empty state)."""

    def test_trades_returns_200(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Trades endpoint returns 200 even with no backtest data."""
        # Mock with empty store
        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/trades",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert response.status_code == 200
        finally:
            app.api.trades._store = original_store

    def test_trades_empty_returns_empty_array(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Empty state returns empty trades array."""
        # Mock with empty store
        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/trades",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            assert "trades" in data
            assert isinstance(data["trades"], list)
            assert len(data["trades"]) == 0
            assert data["trades_count"] == 0
            assert data["total_trades"] == 0
        finally:
            app.api.trades._store = original_store

    def test_trades_empty_has_pagination_fields(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Empty state includes pagination fields."""
        # Mock with empty store
        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/trades?offset=10",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            assert "offset" in data
            assert data["offset"] == 10
        finally:
            app.api.trades._store = original_store

    def test_trades_requires_auth(self, client: TestClient) -> None:
        """Trades endpoint requires authentication."""
        response = client.get("/api/v1/trades")
        assert response.status_code == 401


class TestStatusEmptyState:
    """Test /status endpoint (always returns empty array)."""

    def test_status_returns_200(self, client: TestClient, auth_token: str) -> None:
        """Status endpoint returns 200."""
        response = client.get(
            "/api/v1/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    def test_status_returns_empty_array(self, client: TestClient, auth_token: str) -> None:
        """Status always returns empty array (no live trades in webserver mode)."""
        response = client.get(
            "/api/v1/status",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 0

    def test_status_requires_auth(self, client: TestClient) -> None:
        """Status endpoint requires authentication."""
        response = client.get("/api/v1/status")
        assert response.status_code == 401


class TestPerformanceEmptyState:
    """Test /performance endpoint with no backtest data."""

    def test_performance_returns_200(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Performance endpoint returns 200 even with no backtest data."""
        # Mock with empty store
        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/performance",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert response.status_code == 200
        finally:
            app.api.trades._store = original_store

    def test_performance_empty_returns_empty_array(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Empty state returns empty performance array."""
        # Mock with empty store
        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/performance",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            assert isinstance(data, list)
            assert len(data) == 0
        finally:
            app.api.trades._store = original_store

    def test_performance_requires_auth(self, client: TestClient) -> None:
        """Performance endpoint requires authentication."""
        response = client.get("/api/v1/performance")
        assert response.status_code == 401


class TestTradesWithBacktestData:
    """Test /trades endpoint with actual backtest data."""

    def test_trades_returns_trade_list(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Trades returns list of trades with correct schema."""
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

        temp_store.save_run(
            strategy="chan_theory",
            start_date="2025-11-03",
            end_date="2025-11-12",
            initial_capital=100000.0,
            metrics={},
            trades=trades,
            nav_history=[],
        )

        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/trades",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert response.status_code == 200
            data = response.json()

            assert data["total_trades"] == 2
            assert data["trades_count"] == 2
            assert len(data["trades"]) == 2

            # Check first trade has required fields
            trade = data["trades"][0]
            assert trade["trade_id"] == 1
            assert trade["pair"] == "000001"
            assert trade["open_date"] == "2025-11-03"
            assert trade["close_date"] == "2025-11-10"
            assert trade["open_rate"] == 10.0
            assert trade["close_rate"] == 11.0
            assert trade["profit_abs"] == 1000.0
            assert trade["profit_ratio"] == 0.10
            assert trade["profit_pct"] == 10.0
            assert trade["is_open"] is False
            assert trade["exchange"] == "ashare"
            assert trade["strategy"] == "chan_theory"
            assert "fee_open" in trade
            assert "fee_close" in trade
            assert trade["amount"] == 1000.0

        finally:
            app.api.trades._store = original_store

    def test_trades_pagination_limit(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Trades respects limit parameter."""
        trades = [
            Trade(
                trade_id=i,
                symbol=f"00000{i % 3 + 1}",
                entry_date="2025-11-03",
                exit_date="2025-11-10",
                entry_price=10.0,
                exit_price=11.0,
                shares=1000,
                pnl=1000.0,
                pnl_pct=0.10,
                commission_total=10.0,
            )
            for i in range(1, 11)
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

        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/trades?limit=5",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            assert data["total_trades"] == 10
            assert data["trades_count"] == 5
            assert len(data["trades"]) == 5

        finally:
            app.api.trades._store = original_store

    def test_trades_pagination_offset(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Trades respects offset parameter."""
        trades = [
            Trade(
                trade_id=i,
                symbol=f"00000{i % 3 + 1}",
                entry_date="2025-11-03",
                exit_date="2025-11-10",
                entry_price=10.0,
                exit_price=11.0,
                shares=1000,
                pnl=1000.0,
                pnl_pct=0.10,
                commission_total=10.0,
            )
            for i in range(1, 11)
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

        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/trades?offset=5&limit=3",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            assert data["offset"] == 5
            assert data["total_trades"] == 10
            assert data["trades_count"] == 3
            assert data["trades"][0]["trade_id"] == 6  # First trade after offset

        finally:
            app.api.trades._store = original_store

    def test_trades_timestamps_are_milliseconds(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Trade timestamps are in millisecond epoch format."""
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

        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/trades",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            trade = data["trades"][0]
            # Millisecond timestamps should be > 1 billion (year 2001+)
            assert trade["open_timestamp"] > 1_000_000_000_000
            assert trade["close_timestamp"] > 1_000_000_000_000

        finally:
            app.api.trades._store = original_store


class TestPerformanceWithBacktestData:
    """Test /performance endpoint with actual backtest data."""

    def test_performance_returns_per_pair_summary(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Performance returns per-pair profit summary."""
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
                symbol="000001",
                entry_date="2025-11-15",
                exit_date="2025-11-20",
                entry_price=12.0,
                exit_price=13.0,
                shares=1000,
                pnl=1000.0,
                pnl_pct=0.0833,
                commission_total=10.0,
            ),
            Trade(
                trade_id=3,
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

        temp_store.save_run(
            strategy="chan_theory",
            start_date="2025-11-03",
            end_date="2025-11-20",
            initial_capital=100000.0,
            metrics={},
            trades=trades,
            nav_history=[],
        )

        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/performance",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            assert response.status_code == 200
            data = response.json()

            assert len(data) == 2  # Two distinct pairs

            # Performance should be sorted by profit (descending)
            assert data[0]["pair"] == "000001"
            assert data[0]["count"] == 2
            assert data[0]["profit_abs"] == 3000.0

            assert data[1]["pair"] == "000002"
            assert data[1]["count"] == 1
            assert data[1]["profit_abs"] == -500.0

        finally:
            app.api.trades._store = original_store

    def test_performance_includes_required_fields(self, client: TestClient, auth_token: str, temp_store: BacktestStore) -> None:
        """Each performance entry has required fields."""
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
        ]

        temp_store.save_run(
            strategy="chan_theory",
            start_date="2025-11-03",
            end_date="2025-11-10",
            initial_capital=100000.0,
            metrics={},
            trades=trades,
            nav_history=[],
        )

        import app.api.trades
        original_store = app.api.trades._store
        app.api.trades._store = temp_store

        try:
            response = client.get(
                "/api/v1/performance",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            data = response.json()

            entry = data[0]
            assert "pair" in entry
            assert "profit" in entry
            assert "profit_pct" in entry
            assert "profit_abs" in entry
            assert "count" in entry

        finally:
            app.api.trades._store = original_store
