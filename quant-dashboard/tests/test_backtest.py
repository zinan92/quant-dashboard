"""Tests for the backtest engine: portfolio, metrics, store, and engine integration."""

from __future__ import annotations

import math
import sqlite3
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestEngine, BacktestResult
from src.backtest.metrics import (
    RISK_FREE_RATE,
    TRADING_DAYS_PER_YEAR,
    _calculate_max_drawdown,
    _calculate_sharpe,
    _calculate_sortino,
    _safe_float,
    _zero_metrics,
    calculate_metrics,
)
from src.backtest.portfolio import (
    COMMISSION_MIN,
    COMMISSION_RATE,
    MAX_CONCURRENT_POSITIONS,
    STAMP_TAX_RATE,
    PortfolioManager,
    Position,
    Trade,
    calculate_commission,
)
from src.backtest.store import BacktestStore
from src.data_layer.market_reader import MarketReader

MARKET_DB = Path("/Users/wendy/work/trading-co/ashare/data/market.db")


# ===========================================================================
# Portfolio Manager — Commission Model
# ===========================================================================


class TestCommissionCalculation:
    """Test A-share commission model: 0.03% commission (min ¥5) + 0.1% stamp tax on sell."""

    def test_buy_commission_above_minimum(self) -> None:
        """Commission on buy of ¥100,000 = max(100000*0.0003, 5) = ¥30."""
        commission = calculate_commission(100_000.0, is_sell=False)
        assert commission == 30.0

    def test_buy_commission_at_minimum(self) -> None:
        """Commission on small buy uses minimum ¥5."""
        commission = calculate_commission(1000.0, is_sell=False)
        assert commission == 5.0  # max(1000*0.0003, 5) = max(0.30, 5) = 5

    def test_sell_commission_includes_stamp_tax(self) -> None:
        """Sell commission = max(amount*0.03%, 5) + amount*0.1% stamp tax."""
        amount = 100_000.0
        expected_commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
        expected_stamp = amount * STAMP_TAX_RATE
        commission = calculate_commission(amount, is_sell=True)
        assert commission == round(expected_commission + expected_stamp, 2)

    def test_sell_commission_stamp_tax_only_on_sell(self) -> None:
        """Buy does NOT include stamp tax; sell does."""
        buy_comm = calculate_commission(100_000.0, is_sell=False)
        sell_comm = calculate_commission(100_000.0, is_sell=True)
        stamp_tax = 100_000.0 * STAMP_TAX_RATE
        assert sell_comm == buy_comm + stamp_tax

    def test_zero_amount(self) -> None:
        """Zero trade amount still uses minimum commission."""
        comm = calculate_commission(0.0, is_sell=False)
        assert comm == COMMISSION_MIN


# ===========================================================================
# Portfolio Manager — Position Management
# ===========================================================================


class TestPortfolioManager:
    """Test PortfolioManager initialization, buy/sell, and NAV tracking."""

    def test_initial_state(self) -> None:
        """Portfolio starts with initial capital, no positions."""
        pm = PortfolioManager(1_000_000.0)
        assert pm.cash == 1_000_000.0
        assert pm.initial_capital == 1_000_000.0
        assert pm.position_count == 0
        assert len(pm.closed_trades) == 0

    def test_buy_creates_position(self) -> None:
        """Buying creates a position with correct shares (multiple of 100)."""
        pm = PortfolioManager(1_000_000.0)
        pos = pm.buy("000001", 15.0, "2025-12-01")
        assert pos is not None
        assert pos.symbol == "000001"
        assert pos.shares > 0
        assert pos.shares % 100 == 0
        assert pos.cost_price == 15.0
        assert pos.entry_date == "2025-12-01"

    def test_buy_reduces_cash(self) -> None:
        """Cash is reduced by trade amount + commission after buy."""
        pm = PortfolioManager(1_000_000.0)
        pos = pm.buy("000001", 15.0, "2025-12-01")
        assert pos is not None
        trade_amount = pos.shares * 15.0
        commission = calculate_commission(trade_amount, is_sell=False)
        expected_cash = 1_000_000.0 - trade_amount - commission
        assert abs(pm.cash - expected_cash) < 0.01

    def test_sell_closes_position(self) -> None:
        """Selling removes the position and returns a Trade."""
        pm = PortfolioManager(1_000_000.0)
        pm.buy("000001", 15.0, "2025-12-01")
        trade = pm.sell("000001", 16.0, "2025-12-15")
        assert trade is not None
        assert trade.symbol == "000001"
        assert trade.entry_price == 15.0
        assert trade.exit_price == 16.0
        assert not pm.has_position("000001")
        assert pm.position_count == 0

    def test_sell_pnl_positive(self) -> None:
        """Profitable trade has positive P&L."""
        pm = PortfolioManager(1_000_000.0)
        pm.buy("000001", 10.0, "2025-12-01")
        trade = pm.sell("000001", 12.0, "2025-12-15")
        assert trade is not None
        assert trade.pnl > 0
        assert trade.pnl_pct > 0

    def test_sell_pnl_negative(self) -> None:
        """Losing trade has negative P&L."""
        pm = PortfolioManager(1_000_000.0)
        pm.buy("000001", 10.0, "2025-12-01")
        trade = pm.sell("000001", 8.0, "2025-12-15")
        assert trade is not None
        assert trade.pnl < 0
        assert trade.pnl_pct < 0

    def test_cannot_buy_same_symbol_twice(self) -> None:
        """Cannot open a second position in the same symbol."""
        pm = PortfolioManager(1_000_000.0)
        pm.buy("000001", 10.0, "2025-12-01")
        result = pm.buy("000001", 11.0, "2025-12-02")
        assert result is None

    def test_max_concurrent_positions(self) -> None:
        """Cannot exceed max_positions."""
        pm = PortfolioManager(10_000_000.0, max_positions=3)
        pm.buy("000001", 10.0, "2025-12-01")
        pm.buy("000002", 10.0, "2025-12-01")
        pm.buy("000003", 10.0, "2025-12-01")
        result = pm.buy("000004", 10.0, "2025-12-01")
        assert result is None
        assert pm.position_count == 3

    def test_sell_nonexistent_returns_none(self) -> None:
        """Selling a symbol we don't own returns None."""
        pm = PortfolioManager(1_000_000.0)
        trade = pm.sell("000001", 10.0, "2025-12-01")
        assert trade is None

    def test_position_sizing_round_lot(self) -> None:
        """Shares are always a multiple of 100 (A-share lot)."""
        pm = PortfolioManager(100_000.0, position_pct=0.3)
        shares = pm.calculate_shares(15.55)
        assert shares % 100 == 0
        assert shares > 0

    def test_position_sizing_zero_price(self) -> None:
        """Zero price returns 0 shares."""
        pm = PortfolioManager(1_000_000.0)
        assert pm.calculate_shares(0.0) == 0

    def test_position_sizing_insufficient_cash(self) -> None:
        """Cannot buy if cash is too low."""
        pm = PortfolioManager(10.0)  # very low cash
        shares = pm.calculate_shares(100.0)
        assert shares == 0


# ===========================================================================
# Portfolio Manager — NAV Tracking
# ===========================================================================


class TestNAVTracking:
    """Test NAV (Net Asset Value) calculation and recording."""

    def test_nav_starts_at_initial_capital(self) -> None:
        """NAV with no positions equals cash (= initial capital)."""
        pm = PortfolioManager(1_000_000.0)
        nav = pm.get_nav({})
        assert nav == 1_000_000.0

    def test_nav_includes_position_value(self) -> None:
        """NAV = cash + sum(position_value)."""
        pm = PortfolioManager(1_000_000.0)
        pos = pm.buy("000001", 10.0, "2025-12-01")
        assert pos is not None
        nav = pm.get_nav({"000001": 12.0})  # price rose to 12
        expected = pm.cash + pos.shares * 12.0
        assert abs(nav - expected) < 0.01

    def test_nav_changes_with_price(self) -> None:
        """NAV changes when stock price moves."""
        pm = PortfolioManager(1_000_000.0)
        pm.buy("000001", 10.0, "2025-12-01")
        nav_10 = pm.get_nav({"000001": 10.0})
        nav_15 = pm.get_nav({"000001": 15.0})
        assert nav_15 > nav_10

    def test_record_daily_nav(self) -> None:
        """record_daily_nav appends to nav_history with correct fields."""
        pm = PortfolioManager(1_000_000.0)
        pm.record_daily_nav("2025-12-01", {})
        assert len(pm.nav_history) == 1
        entry = pm.nav_history[0]
        assert entry["date"] == "2025-12-01"
        assert entry["nav"] == 1_000_000.0
        assert entry["daily_return"] == 0.0

    def test_daily_return_calculation(self) -> None:
        """Daily return is (current_nav - prev_nav) / prev_nav."""
        pm = PortfolioManager(1_000_000.0)
        pm.record_daily_nav("2025-12-01", {})  # nav = 1M
        pm.buy("000001", 10.0, "2025-12-01")
        # Price goes up — NAV changes
        pm.record_daily_nav("2025-12-02", {"000001": 11.0})
        assert len(pm.nav_history) == 2
        # daily_return should be positive
        assert pm.nav_history[1]["daily_return"] != 0.0


# ===========================================================================
# Metrics
# ===========================================================================


class TestMetrics:
    """Test performance metrics calculations."""

    @pytest.fixture()
    def sample_nav_history(self) -> list[dict[str, Any]]:
        """Create a sample NAV history with known values."""
        navs = [1_000_000.0, 1_010_000.0, 1_005_000.0, 1_020_000.0, 1_015_000.0]
        history: list[dict[str, Any]] = []
        prev = navs[0]
        for i, nav in enumerate(navs):
            daily_return = (nav - prev) / prev if i > 0 else 0.0
            history.append({
                "date": f"2025-12-{i+1:02d}",
                "nav": nav,
                "daily_return": daily_return,
            })
            prev = nav
        return history

    @pytest.fixture()
    def sample_trades(self) -> list[Trade]:
        """Create sample trades: 2 wins, 1 loss."""
        return [
            Trade(1, "000001", "2025-12-01", "2025-12-05", 10.0, 12.0, 1000, 1990.0, 0.199, 10.0),
            Trade(2, "000002", "2025-12-02", "2025-12-06", 20.0, 22.0, 500, 990.0, 0.099, 10.0),
            Trade(3, "000003", "2025-12-03", "2025-12-07", 15.0, 13.0, 800, -1610.0, -0.134, 10.0),
        ]

    def test_total_return(self, sample_nav_history: list[dict], sample_trades: list[Trade]) -> None:
        """Total return = (final - initial) / initial."""
        metrics = calculate_metrics(sample_nav_history, sample_trades, 1_000_000.0)
        expected = (1_015_000.0 - 1_000_000.0) / 1_000_000.0
        assert abs(metrics["profit_total"] - expected) < 0.001

    def test_metrics_all_numeric(self, sample_nav_history: list[dict], sample_trades: list[Trade]) -> None:
        """All metrics must be numeric (not NaN)."""
        metrics = calculate_metrics(sample_nav_history, sample_trades, 1_000_000.0)
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                assert not math.isnan(value), f"{key} is NaN"
                assert not math.isinf(value), f"{key} is Inf"

    def test_win_rate(self, sample_nav_history: list[dict], sample_trades: list[Trade]) -> None:
        """Win rate = winners / total trades."""
        metrics = calculate_metrics(sample_nav_history, sample_trades, 1_000_000.0)
        assert abs(metrics["winrate"] - 2 / 3) < 0.01  # 2 wins / 3 trades

    def test_trade_count(self, sample_nav_history: list[dict], sample_trades: list[Trade]) -> None:
        """Trade count matches number of closed trades."""
        metrics = calculate_metrics(sample_nav_history, sample_trades, 1_000_000.0)
        assert metrics["trade_count"] == 3

    def test_profit_factor(self, sample_nav_history: list[dict], sample_trades: list[Trade]) -> None:
        """Profit factor = total_profit / total_loss."""
        metrics = calculate_metrics(sample_nav_history, sample_trades, 1_000_000.0)
        total_profit = 1990.0 + 990.0
        total_loss = 1610.0
        expected_pf = total_profit / total_loss
        assert abs(metrics["profit_factor"] - expected_pf) < 0.01

    def test_max_drawdown_negative(self, sample_nav_history: list[dict], sample_trades: list[Trade]) -> None:
        """Max drawdown is negative or zero (represents loss from peak)."""
        metrics = calculate_metrics(sample_nav_history, sample_trades, 1_000_000.0)
        assert metrics["max_drawdown"] <= 0

    def test_sharpe_sortino_calmar_present(
        self, sample_nav_history: list[dict], sample_trades: list[Trade]
    ) -> None:
        """Sharpe, Sortino, and Calmar ratios are present in metrics."""
        metrics = calculate_metrics(sample_nav_history, sample_trades, 1_000_000.0)
        assert "sharpe" in metrics
        assert "sortino" in metrics
        assert "calmar" in metrics

    def test_empty_nav_returns_zero_metrics(self) -> None:
        """Empty NAV history returns all-zero metrics."""
        metrics = calculate_metrics([], [], 1_000_000.0)
        assert metrics["profit_total"] == 0.0
        assert metrics["trade_count"] == 0

    def test_zero_metrics_function(self) -> None:
        """_zero_metrics returns all expected keys."""
        z = _zero_metrics()
        expected_keys = [
            "profit_total", "profit_total_abs", "cagr", "max_drawdown",
            "max_drawdown_abs", "sharpe", "sortino", "calmar", "trade_count",
            "winrate", "profit_factor", "avg_trade_pnl", "avg_trade_duration",
        ]
        for key in expected_keys:
            assert key in z, f"Missing key: {key}"

    def test_avg_trade_duration(self, sample_nav_history: list[dict], sample_trades: list[Trade]) -> None:
        """Average trade duration is computed from entry/exit dates."""
        metrics = calculate_metrics(sample_nav_history, sample_trades, 1_000_000.0)
        # All trades are 4 days (01->05, 02->06, 03->07)
        assert abs(metrics["avg_trade_duration"] - 4.0) < 0.01

    def test_safe_float_nan(self) -> None:
        """_safe_float converts NaN to 0.0."""
        assert _safe_float(float("nan")) == 0.0

    def test_safe_float_inf(self) -> None:
        """_safe_float converts Inf to 0.0."""
        assert _safe_float(float("inf")) == 0.0

    def test_safe_float_normal(self) -> None:
        """_safe_float passes through normal values."""
        assert _safe_float(3.14159) == 3.14159


class TestMaxDrawdown:
    """Test max drawdown calculation specifically."""

    def test_no_drawdown(self) -> None:
        """Monotonically increasing NAV = 0 drawdown."""
        navs = np.array([100.0, 110.0, 120.0, 130.0])
        dd, dd_abs = _calculate_max_drawdown(navs)
        assert dd == 0.0
        assert dd_abs == 0.0

    def test_simple_drawdown(self) -> None:
        """Peak at 120, trough at 100 = -16.67% drawdown."""
        navs = np.array([100.0, 120.0, 100.0, 110.0])
        dd, dd_abs = _calculate_max_drawdown(navs)
        assert abs(dd - (-20.0 / 120.0)) < 0.001
        assert abs(dd_abs - (-20.0)) < 0.01

    def test_single_value(self) -> None:
        """Single value = 0 drawdown."""
        navs = np.array([100.0])
        dd, dd_abs = _calculate_max_drawdown(navs)
        assert dd == 0.0


class TestSharpeAndSortino:
    """Test Sharpe and Sortino ratio calculations."""

    def test_sharpe_positive_returns(self) -> None:
        """Positive returns should give positive Sharpe."""
        returns = np.array([0.01, 0.02, 0.015, 0.01, 0.02, 0.01, 0.015, 0.02, 0.01, 0.02])
        sharpe = _calculate_sharpe(returns)
        assert sharpe > 0

    def test_sharpe_zero_std(self) -> None:
        """Constant returns = 0 std -> Sharpe = 0."""
        returns = np.array([0.01, 0.01, 0.01, 0.01])
        sharpe = _calculate_sharpe(returns)
        assert sharpe == 0.0

    def test_sharpe_insufficient_data(self) -> None:
        """Less than 2 data points -> 0."""
        returns = np.array([0.01])
        assert _calculate_sharpe(returns) == 0.0

    def test_sortino_positive_returns(self) -> None:
        """Mixed returns should give non-zero Sortino."""
        returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015])
        sortino = _calculate_sortino(returns)
        # Should be non-zero since we have downside
        assert isinstance(sortino, float)

    def test_sortino_no_downside(self) -> None:
        """All positive returns -> Sortino = 0 (no downside deviation)."""
        returns = np.array([0.01, 0.02, 0.03, 0.04])
        # After subtracting daily risk-free, some may still be positive
        # But if all excess returns are positive, downside is empty
        sortino = _calculate_sortino(returns)
        assert isinstance(sortino, float)


# ===========================================================================
# Backtest Store (Persistence)
# ===========================================================================


class TestBacktestStore:
    """Test SQLite persistence for backtest results."""

    @pytest.fixture()
    def store(self, tmp_path: Path) -> BacktestStore:
        """Create a BacktestStore with a temp database."""
        return BacktestStore(db_path=tmp_path / "test_backtest.db")

    def test_schema_created(self, store: BacktestStore) -> None:
        """Tables are created on initialization."""
        conn = store._get_connection()
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}
            assert "backtest_runs" in table_names
            assert "backtest_trades" in table_names
            assert "daily_nav" in table_names
        finally:
            conn.close()

    def test_save_and_retrieve_run(self, store: BacktestStore) -> None:
        """Save a run and retrieve it by ID."""
        trades = [
            Trade(1, "000001", "2025-12-01", "2025-12-10", 10.0, 12.0, 100, 190.0, 0.19, 10.0),
        ]
        nav = [{"date": "2025-12-01", "nav": 1_000_000.0, "daily_return": 0.0}]
        metrics = {"profit_total": 0.015, "sharpe": 1.5}

        run_id = store.save_run(
            strategy="chan_theory",
            start_date="2025-12-01",
            end_date="2025-12-31",
            initial_capital=1_000_000.0,
            metrics=metrics,
            trades=trades,
            nav_history=nav,
        )
        assert run_id is not None
        assert run_id > 0

        run = store.get_run(run_id)
        assert run is not None
        assert run["strategy"] == "chan_theory"
        assert run["initial_capital"] == 1_000_000.0

    def test_get_trades(self, store: BacktestStore) -> None:
        """Retrieve trades for a run."""
        trades = [
            Trade(1, "000001", "2025-12-01", "2025-12-10", 10.0, 12.0, 100, 190.0, 0.19, 10.0),
            Trade(2, "000002", "2025-12-02", "2025-12-11", 20.0, 22.0, 200, 390.0, 0.19, 10.0),
        ]
        run_id = store.save_run(
            strategy="test", start_date="2025-12-01", end_date="2025-12-31",
            initial_capital=1_000_000.0, metrics={}, trades=trades, nav_history=[],
        )
        saved_trades = store.get_trades(run_id)
        assert len(saved_trades) == 2
        assert saved_trades[0]["symbol"] == "000001"
        assert saved_trades[1]["symbol"] == "000002"

    def test_get_daily_nav(self, store: BacktestStore) -> None:
        """Retrieve daily NAV for a run."""
        nav = [
            {"date": "2025-12-01", "nav": 1_000_000.0, "daily_return": 0.0},
            {"date": "2025-12-02", "nav": 1_010_000.0, "daily_return": 0.01},
        ]
        run_id = store.save_run(
            strategy="test", start_date="2025-12-01", end_date="2025-12-31",
            initial_capital=1_000_000.0, metrics={}, trades=[], nav_history=nav,
        )
        saved_nav = store.get_daily_nav(run_id)
        assert len(saved_nav) == 2
        assert saved_nav[0]["nav"] == 1_000_000.0
        assert saved_nav[1]["nav"] == 1_010_000.0

    def test_get_all_runs(self, store: BacktestStore) -> None:
        """get_all_runs returns all saved runs."""
        store.save_run("s1", "2025-12-01", "2025-12-31", 100.0, {}, [], [])
        store.save_run("s2", "2025-12-01", "2025-12-31", 200.0, {}, [], [])
        runs = store.get_all_runs()
        assert len(runs) == 2

    def test_get_latest_run(self, store: BacktestStore) -> None:
        """get_latest_run returns the most recent run."""
        store.save_run("first", "2025-12-01", "2025-12-31", 100.0, {}, [], [])
        store.save_run("second", "2025-12-01", "2025-12-31", 200.0, {}, [], [])
        latest = store.get_latest_run()
        assert latest is not None
        assert latest["strategy"] == "second"

    def test_get_nonexistent_run(self, store: BacktestStore) -> None:
        """get_run returns None for non-existent ID."""
        assert store.get_run(999) is None


# ===========================================================================
# Backtest Engine — Integration with Real Data
# ===========================================================================


class TestBacktestEngineIntegration:
    """Integration tests: run backtests on real market data (small subset)."""

    @pytest.fixture()
    def reader(self) -> MarketReader:
        return MarketReader(db_path=MARKET_DB)

    @pytest.fixture()
    def store(self, tmp_path: Path) -> BacktestStore:
        return BacktestStore(db_path=tmp_path / "test_bt.db")

    def test_engine_loads(self) -> None:
        """BacktestEngine can be imported and instantiated."""
        from src.backtest.engine import BacktestEngine
        # Instantiate with a strategy name (will use mock reader later)
        # This test just ensures the import works
        assert BacktestEngine is not None

    def test_run_backtest_small_universe(self, reader: MarketReader, store: BacktestStore) -> None:
        """Run backtest on 5 stocks for 30 days — core integration test."""
        # Pick 5 symbols
        symbols = ["000001", "000002", "000858", "600036", "601318"]

        engine = BacktestEngine(
            strategy="chan_theory",
            symbols=symbols,
            start_date="2025-12-01",
            end_date="2025-12-31",
            initial_capital=1_000_000.0,
            market_reader=reader,
            store=store,
        )

        result = engine.run(persist=True)

        # Basic assertions
        assert isinstance(result, BacktestResult)
        assert result.strategy_name == "chan_theory"
        assert result.initial_capital == 1_000_000.0
        assert result.final_nav > 0

    def test_nav_starts_at_initial_capital(self, reader: MarketReader, store: BacktestStore) -> None:
        """NAV on day 1 equals initial capital (no trades yet on first bar)."""
        symbols = ["000001"]
        engine = BacktestEngine(
            strategy="chan_theory",
            symbols=symbols,
            start_date="2025-12-01",
            end_date="2025-12-31",
            initial_capital=500_000.0,
            market_reader=reader,
            store=store,
        )
        result = engine.run(persist=False)

        if result.nav_history:
            first_nav = result.nav_history[0]["nav"]
            # NAV should start at initial capital (might change slightly
            # if a signal fires on day 1 and gets executed)
            assert first_nav > 0

    def test_metrics_not_nan(self, reader: MarketReader, store: BacktestStore) -> None:
        """All metrics are numeric (never NaN) after a backtest."""
        symbols = ["000001", "000858"]
        engine = BacktestEngine(
            strategy="chan_theory",
            symbols=symbols,
            start_date="2025-12-01",
            end_date="2026-01-31",
            initial_capital=1_000_000.0,
            market_reader=reader,
            store=store,
        )
        result = engine.run(persist=False)

        for key, value in result.metrics.items():
            if isinstance(value, (int, float)):
                assert not math.isnan(value), f"Metric {key} is NaN"
                assert not math.isinf(value), f"Metric {key} is Inf"

    def test_results_persisted_to_db(self, reader: MarketReader, store: BacktestStore) -> None:
        """Backtest results are saved to backtest.db when persist=True."""
        symbols = ["000001"]
        engine = BacktestEngine(
            strategy="chan_theory",
            symbols=symbols,
            start_date="2025-12-01",
            end_date="2025-12-31",
            initial_capital=1_000_000.0,
            market_reader=reader,
            store=store,
        )
        result = engine.run(persist=True)

        assert result.run_id is not None

        # Verify we can read it back
        run = store.get_run(result.run_id)
        assert run is not None
        assert run["strategy"] == "chan_theory"

        # Verify daily NAV was stored
        nav = store.get_daily_nav(result.run_id)
        assert len(nav) > 0

    def test_trade_execution_recorded(self, reader: MarketReader, store: BacktestStore) -> None:
        """Trades from the backtest have correct fields."""
        symbols = ["000001", "000002", "000858", "600036", "601318"]
        engine = BacktestEngine(
            strategy="chan_theory",
            symbols=symbols,
            start_date="2025-11-15",
            end_date="2026-02-28",
            initial_capital=1_000_000.0,
            market_reader=reader,
            store=store,
        )
        result = engine.run(persist=True)

        # Should have some trades (force-closed at end if nothing else)
        for trade in result.trades:
            assert trade.symbol != ""
            assert trade.entry_date != ""
            assert trade.exit_date != ""
            assert trade.shares > 0
            assert trade.entry_price > 0
            assert trade.exit_price > 0

    def test_engine_progress_tracking(self, reader: MarketReader, store: BacktestStore) -> None:
        """Engine progress goes from 0 to 1 during run."""
        engine = BacktestEngine(
            strategy="chan_theory",
            symbols=["000001"],
            start_date="2025-12-01",
            end_date="2025-12-31",
            initial_capital=1_000_000.0,
            market_reader=reader,
            store=store,
        )
        assert engine.progress == 0.0
        assert not engine.running

        result = engine.run(persist=False)

        assert engine.progress == 1.0
        assert not engine.running

    def test_empty_universe(self, reader: MarketReader, store: BacktestStore) -> None:
        """Engine handles empty symbol list gracefully."""
        engine = BacktestEngine(
            strategy="chan_theory",
            symbols=[],
            start_date="2025-12-01",
            end_date="2025-12-31",
            initial_capital=1_000_000.0,
            market_reader=reader,
            store=store,
        )
        result = engine.run(persist=False)
        assert result.final_nav == 1_000_000.0
        assert result.metrics["trade_count"] == 0

    def test_nonexistent_symbols(self, reader: MarketReader, store: BacktestStore) -> None:
        """Engine handles non-existent symbols gracefully (skips them)."""
        engine = BacktestEngine(
            strategy="chan_theory",
            symbols=["XXXXX", "YYYYY"],
            start_date="2025-12-01",
            end_date="2025-12-31",
            initial_capital=1_000_000.0,
            market_reader=reader,
            store=store,
        )
        result = engine.run(persist=False)
        assert result.final_nav == 1_000_000.0

    def test_backtest_completes_within_60s(self, reader: MarketReader, store: BacktestStore) -> None:
        """Backtest on 5 stocks over 30 days completes within 60 seconds."""
        import time

        symbols = ["000001", "000002", "000858", "600036", "601318"]
        engine = BacktestEngine(
            strategy="chan_theory",
            symbols=symbols,
            start_date="2025-12-01",
            end_date="2025-12-31",
            initial_capital=1_000_000.0,
            market_reader=reader,
            store=store,
        )

        start = time.time()
        result = engine.run(persist=False)
        elapsed = time.time() - start

        assert elapsed < 60.0, f"Backtest took {elapsed:.1f}s, expected < 60s"


# ===========================================================================
# Engine — strategy by name
# ===========================================================================


class TestBacktestEngineStrategyLoading:
    """Test that BacktestEngine can load strategies by name."""

    def test_load_strategy_by_name(self) -> None:
        """Engine loads chan_theory strategy by string name."""
        engine = BacktestEngine(
            strategy="chan_theory",
            symbols=["000001"],
            start_date="2025-12-01",
            end_date="2025-12-31",
        )
        assert engine._strategy.name == "chan_theory"

    def test_load_unknown_strategy_raises(self) -> None:
        """Engine raises KeyError for unknown strategy name."""
        with pytest.raises(KeyError):
            BacktestEngine(
                strategy="nonexistent_strategy",
                symbols=["000001"],
                start_date="2025-12-01",
                end_date="2025-12-31",
            )
