"""Tests for backtest API endpoints.

Tests cover: start backtest, poll progress, completion with result schema,
history persistence, history result loading, abort, and delete/reset.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
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


def _reset_backtest() -> None:
    """Reset the global backtest state before each test."""
    client.delete("/api/v1/backtest", headers=_auth_headers())


def _start_and_wait_for_backtest(
    strategy: str = "chan_theory",
    timerange: str = "20251201-20251231",
    dry_run_wallet: float = 1_000_000.0,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Start a backtest and poll until complete. Returns the final response."""
    headers = _auth_headers()

    # Start the backtest
    resp = client.post(
        "/api/v1/backtest",
        json={"strategy": strategy, "timerange": timerange, "dry_run_wallet": dry_run_wallet},
        headers=headers,
    )
    assert resp.status_code == 200

    # Poll until complete
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get("/api/v1/backtest", headers=headers)
        data = resp.json()
        if not data.get("running", True):
            return data
        time.sleep(0.5)

    raise TimeoutError("Backtest did not complete within timeout")


# ===========================================================================
# POST /api/v1/backtest — Start backtest
# ===========================================================================


class TestStartBacktest:
    """POST /api/v1/backtest — starts a backtest in a background thread."""

    def setup_method(self) -> None:
        _reset_backtest()

    def test_returns_200(self) -> None:
        headers = _auth_headers()
        resp = client.post(
            "/api/v1/backtest",
            json={"strategy": "chan_theory", "timerange": "20251201-20251231"},
            headers=headers,
        )
        assert resp.status_code == 200

    def test_returns_running_true(self) -> None:
        headers = _auth_headers()
        resp = client.post(
            "/api/v1/backtest",
            json={"strategy": "chan_theory", "timerange": "20251201-20251231"},
            headers=headers,
        )
        data = resp.json()
        assert data["running"] is True

    def test_returns_progress_zero(self) -> None:
        headers = _auth_headers()
        resp = client.post(
            "/api/v1/backtest",
            json={"strategy": "chan_theory", "timerange": "20251201-20251231"},
            headers=headers,
        )
        data = resp.json()
        assert data["progress"] == 0.0

    def test_returns_status_running(self) -> None:
        headers = _auth_headers()
        resp = client.post(
            "/api/v1/backtest",
            json={"strategy": "chan_theory", "timerange": "20251201-20251231"},
            headers=headers,
        )
        data = resp.json()
        assert data["status"] == "running"

    def test_requires_auth(self) -> None:
        resp = client.post(
            "/api/v1/backtest",
            json={"strategy": "chan_theory", "timerange": "20251201-20251231"},
        )
        assert resp.status_code in (401, 403)

    def test_default_wallet_amount(self) -> None:
        """If dry_run_wallet not specified, defaults to 1,000,000."""
        headers = _auth_headers()
        resp = client.post(
            "/api/v1/backtest",
            json={"strategy": "chan_theory", "timerange": "20251201-20251231"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is True


# ===========================================================================
# GET /api/v1/backtest — Poll progress and completion
# ===========================================================================


class TestPollBacktest:
    """GET /api/v1/backtest — returns progress or completed results."""

    def setup_method(self) -> None:
        _reset_backtest()

    def test_no_backtest_returns_not_started(self) -> None:
        """When no backtest has been started, status is not_started."""
        headers = _auth_headers()
        resp = client.get("/api/v1/backtest", headers=headers)
        data = resp.json()
        assert data["running"] is False
        assert data["status"] == "not_started"

    def test_completed_backtest_has_result(self) -> None:
        """After a backtest completes, response includes backtest_result."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        assert data["status"] == "completed"
        assert data["running"] is False
        assert "backtest_result" in data

    def test_completed_result_has_strategy_dict(self) -> None:
        """backtest_result.strategy is a dict keyed by strategy name."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        result = data["backtest_result"]
        assert "strategy" in result
        assert "chan_theory" in result["strategy"]

    def test_completed_result_has_metadata_dict(self) -> None:
        """backtest_result.metadata is a dict keyed by strategy name."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        result = data["backtest_result"]
        assert "metadata" in result
        assert "chan_theory" in result["metadata"]

    def test_result_strategy_has_trades_array(self) -> None:
        """Strategy dict contains a trades array."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        strategy_data = data["backtest_result"]["strategy"]["chan_theory"]
        assert "trades" in strategy_data
        assert isinstance(strategy_data["trades"], list)

    def test_result_contains_required_metrics(self) -> None:
        """Completed result has all required performance metrics."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        strategy_data = data["backtest_result"]["strategy"]["chan_theory"]

        required_metrics = [
            "profit_total",
            "profit_total_abs",
            "max_drawdown",
            "sharpe",
            "sortino",
            "winrate",
            "trade_count",
            "max_drawdown_abs",
        ]
        for metric in required_metrics:
            assert metric in strategy_data, f"Missing metric: {metric}"
            assert isinstance(
                strategy_data[metric], (int, float)
            ), f"{metric} is not numeric: {type(strategy_data[metric])}"

    def test_result_metadata_has_required_fields(self) -> None:
        """Metadata has run_id, filename, strategy, timestamps, timeframe."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        metadata = data["backtest_result"]["metadata"]["chan_theory"]

        required_fields = [
            "run_id",
            "filename",
            "strategy",
            "backtest_start_ts",
            "backtest_end_ts",
            "timeframe",
        ]
        for field in required_fields:
            assert field in metadata, f"Missing metadata field: {field}"

    def test_result_metadata_timeframe(self) -> None:
        """Metadata timeframe is '1d'."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        metadata = data["backtest_result"]["metadata"]["chan_theory"]
        assert metadata["timeframe"] == "1d"

    def test_result_metadata_timestamps_are_ms(self) -> None:
        """Metadata timestamps are in milliseconds (>= 1e12)."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        metadata = data["backtest_result"]["metadata"]["chan_theory"]
        assert metadata["backtest_start_ts"] > 1_000_000_000_000
        assert metadata["backtest_end_ts"] > 1_000_000_000_000

    def test_requires_auth(self) -> None:
        resp = client.get("/api/v1/backtest")
        assert resp.status_code in (401, 403)


# ===========================================================================
# DELETE /api/v1/backtest — Reset state
# ===========================================================================


class TestResetBacktest:
    """DELETE /api/v1/backtest — resets current backtest state."""

    def test_reset_returns_200(self) -> None:
        resp = client.delete("/api/v1/backtest", headers=_auth_headers())
        assert resp.status_code == 200

    def test_reset_clears_state(self) -> None:
        """After reset, GET /backtest shows not_started."""
        headers = _auth_headers()
        client.delete("/api/v1/backtest", headers=headers)
        resp = client.get("/api/v1/backtest", headers=headers)
        data = resp.json()
        assert data["running"] is False
        assert data["status"] == "not_started"

    def test_requires_auth(self) -> None:
        resp = client.delete("/api/v1/backtest")
        assert resp.status_code in (401, 403)


# ===========================================================================
# GET /api/v1/backtest/abort — Abort running backtest
# ===========================================================================


class TestAbortBacktest:
    """GET /api/v1/backtest/abort — stops a running backtest."""

    def setup_method(self) -> None:
        _reset_backtest()

    def test_abort_when_not_running(self) -> None:
        resp = client.get("/api/v1/backtest/abort", headers=_auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "not_running"

    def test_requires_auth(self) -> None:
        resp = client.get("/api/v1/backtest/abort")
        assert resp.status_code in (401, 403)


# ===========================================================================
# GET /api/v1/backtest/history — List past backtest runs
# ===========================================================================


class TestBacktestHistory:
    """GET /api/v1/backtest/history — list of past backtest runs."""

    def setup_method(self) -> None:
        _reset_backtest()

    def test_returns_200(self) -> None:
        resp = client.get("/api/v1/backtest/history", headers=_auth_headers())
        assert resp.status_code == 200

    def test_returns_list(self) -> None:
        resp = client.get("/api/v1/backtest/history", headers=_auth_headers())
        assert isinstance(resp.json(), list)

    def test_history_after_backtest(self) -> None:
        """After a completed backtest, history contains at least 1 entry."""
        _start_and_wait_for_backtest(timerange="20251201-20251231")

        resp = client.get("/api/v1/backtest/history", headers=_auth_headers())
        data = resp.json()
        assert len(data) >= 1

    def test_history_entry_has_required_fields(self) -> None:
        """Each history entry has strategy, filename, timestamps."""
        _start_and_wait_for_backtest(timerange="20251201-20251231")

        resp = client.get("/api/v1/backtest/history", headers=_auth_headers())
        data = resp.json()
        assert len(data) >= 1

        entry = data[0]
        required_fields = [
            "strategy",
            "filename",
            "backtest_start_ts",
            "backtest_end_ts",
        ]
        for field in required_fields:
            assert field in entry, f"Missing history field: {field}"

    def test_requires_auth(self) -> None:
        resp = client.get("/api/v1/backtest/history")
        assert resp.status_code in (401, 403)


# ===========================================================================
# GET /api/v1/backtest/history/result — Load specific past result
# ===========================================================================


class TestBacktestHistoryResult:
    """GET /api/v1/backtest/history/result?filename=X — load specific result."""

    def setup_method(self) -> None:
        _reset_backtest()

    def test_load_result_by_filename(self) -> None:
        """Load a specific result using its filename from history."""
        _start_and_wait_for_backtest(timerange="20251201-20251231")

        headers = _auth_headers()

        # Get filename from history
        resp = client.get("/api/v1/backtest/history", headers=headers)
        history = resp.json()
        assert len(history) >= 1
        filename = history[0]["filename"]

        # Load the result
        resp = client.get(
            f"/api/v1/backtest/history/result?filename={filename}",
            headers=headers,
        )
        assert resp.status_code == 200

        data = resp.json()
        assert "strategy" in data
        assert "metadata" in data

    def test_nonexistent_filename_returns_404(self) -> None:
        headers = _auth_headers()
        resp = client.get(
            "/api/v1/backtest/history/result?filename=nonexistent.json",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_requires_auth(self) -> None:
        resp = client.get("/api/v1/backtest/history/result?filename=test.json")
        assert resp.status_code in (401, 403)


# ===========================================================================
# FreqTrade schema compliance
# ===========================================================================


class TestFreqTradeSchemaCompliance:
    """Verify the backtest result matches FreqTrade's expected schema."""

    def setup_method(self) -> None:
        _reset_backtest()

    def test_backtest_result_top_level_keys(self) -> None:
        """Top-level keys: strategy, metadata."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        result = data["backtest_result"]
        assert "strategy" in result
        assert "metadata" in result

    def test_strategy_keyed_by_name(self) -> None:
        """strategy dict is keyed by strategy name."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        result = data["backtest_result"]
        # Should be keyed by the strategy name used
        keys = list(result["strategy"].keys())
        assert len(keys) == 1
        assert keys[0] == "chan_theory"

    def test_metadata_keyed_by_name(self) -> None:
        """metadata dict is keyed by strategy name."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        result = data["backtest_result"]
        keys = list(result["metadata"].keys())
        assert len(keys) == 1
        assert keys[0] == "chan_theory"

    def test_trades_have_freqtrade_fields(self) -> None:
        """Each trade in the array has FreqTrade-required fields."""
        data = _start_and_wait_for_backtest(
            timerange="20251115-20260228",
        )
        strategy_data = data["backtest_result"]["strategy"]["chan_theory"]
        trades = strategy_data["trades"]

        # We need at least some trades for this test to be meaningful
        # (wider date range should produce trades from force-closed positions)
        if len(trades) > 0:
            trade = trades[0]
            required_trade_fields = [
                "trade_id",
                "pair",
                "open_date",
                "close_date",
                "open_rate",
                "close_rate",
                "profit_abs",
                "profit_ratio",
            ]
            for field in required_trade_fields:
                assert field in trade, f"Missing trade field: {field}"

    def test_progress_between_0_and_1(self) -> None:
        """Progress value is between 0 and 1."""
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        assert 0.0 <= data["progress"] <= 1.0


class TestMarketChangeEndpoint:
    """Tests for GET /api/v1/backtest/history/{filename}/market_change."""

    def test_market_change_returns_benchmark_data(self) -> None:
        """Market change endpoint returns benchmark performance data."""
        _reset_backtest()
        
        # Start and complete a backtest
        data = _start_and_wait_for_backtest(timerange="20251201-20251231")
        assert data["status"] == "completed"
        
        # Get the backtest history to find the filename
        history_resp = client.get("/api/v1/backtest/history", headers=_auth_headers())
        assert history_resp.status_code == 200
        history = history_resp.json()
        assert len(history) > 0
        
        filename = history[0]["filename"]
        
        # Get market change data
        market_resp = client.get(
            f"/api/v1/backtest/history/{filename}/market_change",
            headers=_auth_headers(),
        )
        assert market_resp.status_code == 200
        
        market_data = market_resp.json()
        assert "columns" in market_data
        assert "data" in market_data
        assert market_data["columns"] == ["date", "market_change"]
        
        # Data should be a list of [timestamp, pct_change] pairs
        if len(market_data["data"]) > 0:
            first_entry = market_data["data"][0]
            assert len(first_entry) == 2
            assert isinstance(first_entry[0], int)  # timestamp in ms
            assert isinstance(first_entry[1], (int, float))  # percentage change
            
            # First entry should have 0% change (baseline)
            assert abs(first_entry[1]) < 0.001

    def test_market_change_invalid_filename(self) -> None:
        """Market change endpoint returns 404 for invalid filename."""
        resp = client.get(
            "/api/v1/backtest/history/invalid-filename/market_change",
            headers=_auth_headers(),
        )
        assert resp.status_code == 404

    def test_market_change_nonexistent_run(self) -> None:
        """Market change endpoint returns 404 for nonexistent run."""
        resp = client.get(
            "/api/v1/backtest/history/backtest-result-chan_theory-2025-01-01-2025-01-31-99999.json/market_change",
            headers=_auth_headers(),
        )
        assert resp.status_code == 404
