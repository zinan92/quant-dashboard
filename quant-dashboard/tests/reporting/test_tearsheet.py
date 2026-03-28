"""Tests for tearsheet reporting module."""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.engine import BacktestResult
from src.data_layer.market_reader import MarketReader
from src.reporting.tearsheet import (
    extract_daily_returns,
    generate_portfolio_tearsheet,
    get_benchmark_returns,
)


class TestExtractDailyReturns:
    """Test extract_daily_returns function."""

    def test_extract_returns_from_nav_history(self):
        """Test extracting returns from a valid nav_history."""
        # Create mock BacktestResult with nav_history
        nav_history = [
            {"date": "2024-01-02", "nav": 1000000.0, "daily_return": 0.0},
            {"date": "2024-01-03", "nav": 1010000.0, "daily_return": 0.01},
            {"date": "2024-01-04", "nav": 1005000.0, "daily_return": -0.00495},
        ]
        result = BacktestResult(nav_history=nav_history)

        # Extract returns
        returns = extract_daily_returns(result)

        # Verify it's a Series with DatetimeIndex
        assert isinstance(returns, pd.Series)
        assert isinstance(returns.index, pd.DatetimeIndex)
        assert returns.dtype == "float64"
        assert returns.index.name == "date"
        assert returns.name == "returns"

        # Verify length
        assert len(returns) == 3

        # Verify values
        assert returns.iloc[0] == 0.0
        assert returns.iloc[1] == 0.01
        assert abs(returns.iloc[2] - (-0.00495)) < 1e-6

        # Verify dates
        assert str(returns.index[0].date()) == "2024-01-02"
        assert str(returns.index[1].date()) == "2024-01-03"
        assert str(returns.index[2].date()) == "2024-01-04"

    def test_extract_returns_empty_nav_history(self):
        """Test extracting returns from empty nav_history."""
        result = BacktestResult(nav_history=[])

        returns = extract_daily_returns(result)

        # Should return empty Series with correct schema
        assert isinstance(returns, pd.Series)
        assert isinstance(returns.index, pd.DatetimeIndex)
        assert returns.dtype == "float64"
        assert len(returns) == 0
        assert returns.index.name == "date"
        assert returns.name == "returns"

    def test_returns_correctness(self):
        """Test that returns are arithmetically correct within tolerance."""
        # Create nav_history where we calculate expected daily returns
        nav_history = [
            {"date": "2024-01-02", "nav": 100000.0, "daily_return": 0.0},
            {"date": "2024-01-03", "nav": 105000.0, "daily_return": 0.05},  # (105000-100000)/100000
            {"date": "2024-01-04", "nav": 102900.0, "daily_return": -0.02},  # (102900-105000)/105000
        ]

        # Verify the daily_return values are correct
        expected_return_1 = (105000.0 - 100000.0) / 100000.0
        expected_return_2 = (102900.0 - 105000.0) / 105000.0

        assert abs(nav_history[1]["daily_return"] - expected_return_1) < 1e-6
        assert abs(nav_history[2]["daily_return"] - expected_return_2) < 1e-6

        result = BacktestResult(nav_history=nav_history)
        returns = extract_daily_returns(result)

        # Verify extracted values match
        assert abs(returns.iloc[0] - 0.0) < 1e-6
        assert abs(returns.iloc[1] - expected_return_1) < 1e-6
        assert abs(returns.iloc[2] - expected_return_2) < 1e-6


class TestGetBenchmarkReturns:
    """Test get_benchmark_returns function."""

    def test_benchmark_returns_from_real_data(self):
        """Test fetching CSI 300 benchmark returns from real market.db."""
        reader = MarketReader()

        # Fetch a short period
        returns = get_benchmark_returns("2024-01-02", "2024-01-10", reader)

        # Verify it's a Series with DatetimeIndex
        assert isinstance(returns, pd.Series)
        assert isinstance(returns.index, pd.DatetimeIndex)
        assert returns.dtype == "float64"
        assert returns.index.name == "date"
        assert returns.name == "benchmark"

        # Should have some data (CSI 300 should exist)
        assert len(returns) > 0

        # All values should be numeric (no NaN after dropna)
        assert not returns.isna().any()

    def test_benchmark_returns_alignment(self):
        """Test that benchmark returns can be aligned with portfolio dates."""
        reader = MarketReader()

        # Get benchmark returns for a range
        benchmark = get_benchmark_returns("2024-01-01", "2024-01-31", reader)

        # Create a portfolio returns series with fewer dates
        portfolio_dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
        portfolio_returns = pd.Series([0.01, -0.005, 0.02], index=portfolio_dates)

        # Align benchmark to portfolio dates
        aligned_benchmark = benchmark.reindex(portfolio_returns.index)

        # Verify alignment
        assert len(aligned_benchmark) == len(portfolio_returns)
        assert aligned_benchmark.index.equals(portfolio_returns.index)

        # Fill NaN with 0 (as done in generate_portfolio_tearsheet)
        aligned_benchmark = aligned_benchmark.fillna(0.0)

        # No NaN after alignment
        assert not aligned_benchmark.isna().any()

    def test_benchmark_returns_empty_date_range(self):
        """Test benchmark returns with a date range that has no data."""
        reader = MarketReader()

        # Use a future date range that shouldn't have data
        returns = get_benchmark_returns("2030-01-01", "2030-01-10", reader)

        # Should return empty series with correct schema
        assert isinstance(returns, pd.Series)
        assert isinstance(returns.index, pd.DatetimeIndex)
        assert returns.dtype == "float64"
        assert len(returns) == 0

    def test_benchmark_returns_default_reader(self):
        """Test that get_benchmark_returns works with default reader."""
        # Call without reader parameter
        returns = get_benchmark_returns("2024-01-02", "2024-01-10")

        # Should still work
        assert isinstance(returns, pd.Series)
        assert isinstance(returns.index, pd.DatetimeIndex)


class TestGeneratePortfolioTearsheet:
    """Test generate_portfolio_tearsheet function."""

    def test_tearsheet_generation_with_real_backtest(self):
        """Test generating tearsheet with a real backtest result."""
        # Create a realistic BacktestResult with nav_history
        nav_history = []
        base_nav = 1000000.0
        dates = pd.date_range("2024-01-02", "2024-01-31", freq="B")  # Business days

        for i, date in enumerate(dates):
            if i == 0:
                daily_return = 0.0
                nav = base_nav
            else:
                # Simulate some returns
                daily_return = 0.002 * ((-1) ** i)  # Alternating +0.2% / -0.2%
                nav = nav_history[i - 1]["nav"] * (1 + daily_return)

            nav_history.append(
                {"date": date.strftime("%Y-%m-%d"), "nav": nav, "daily_return": daily_return}
            )

        result = BacktestResult(
            strategy_name="ChanTheory",
            start_date="2024-01-02",
            end_date="2024-01-31",
            initial_capital=1000000.0,
            final_nav=nav_history[-1]["nav"],
            nav_history=nav_history,
        )

        # Generate tearsheet
        html = generate_portfolio_tearsheet(result)

        # Verify HTML output
        assert isinstance(html, str)
        assert len(html) > 5000  # Should be substantial HTML content
        assert "<html" in html.lower()
        assert "</html>" in html.lower()

    def test_tearsheet_contains_key_sections(self):
        """Test that tearsheet contains expected sections."""
        # Create backtest result
        nav_history = []
        dates = pd.date_range("2024-01-02", "2024-02-29", freq="B")

        for i, date in enumerate(dates):
            if i == 0:
                daily_return = 0.0
                nav = 1000000.0
            else:
                daily_return = 0.001 * ((-1) ** i)
                nav = nav_history[i - 1]["nav"] * (1 + daily_return)

            nav_history.append(
                {"date": date.strftime("%Y-%m-%d"), "nav": nav, "daily_return": daily_return}
            )

        result = BacktestResult(
            start_date="2024-01-02",
            end_date="2024-02-29",
            nav_history=nav_history,
        )

        html = generate_portfolio_tearsheet(result)

        # Check for key sections that QuantStats includes
        # Note: actual content depends on QuantStats version, but these are common
        html_lower = html.lower()

        # Should contain some metrics/analysis
        assert "return" in html_lower or "performance" in html_lower
        # Should have some visual elements
        assert "chart" in html_lower or "plot" in html_lower or "graph" in html_lower or "svg" in html_lower

    def test_tearsheet_empty_nav_history(self):
        """Test tearsheet generation with empty nav_history."""
        result = BacktestResult(
            start_date="2024-01-02",
            end_date="2024-01-31",
            nav_history=[],
        )

        html = generate_portfolio_tearsheet(result)

        # Should return minimal HTML
        assert isinstance(html, str)
        assert len(html) > 0
        assert "<html" in html.lower()

    def test_tearsheet_with_custom_reader(self):
        """Test tearsheet generation with custom MarketReader."""
        reader = MarketReader()

        nav_history = [
            {"date": "2024-01-02", "nav": 1000000.0, "daily_return": 0.0},
            {"date": "2024-01-03", "nav": 1010000.0, "daily_return": 0.01},
            {"date": "2024-01-04", "nav": 1015000.0, "daily_return": 0.00495},
        ]

        result = BacktestResult(
            start_date="2024-01-02",
            end_date="2024-01-04",
            nav_history=nav_history,
        )

        # Generate with explicit reader
        html = generate_portfolio_tearsheet(result, reader=reader)

        # Should work
        assert isinstance(html, str)
        assert len(html) > 1000

    def test_tearsheet_benchmark_alignment_no_nan(self):
        """Test that benchmark is properly aligned and has no NaN values."""
        # Create backtest result with specific dates
        nav_history = [
            {"date": "2024-01-02", "nav": 1000000.0, "daily_return": 0.0},
            {"date": "2024-01-03", "nav": 1005000.0, "daily_return": 0.005},
            {"date": "2024-01-04", "nav": 1010000.0, "daily_return": 0.00498},
        ]

        result = BacktestResult(
            start_date="2024-01-02",
            end_date="2024-01-04",
            nav_history=nav_history,
        )

        # Extract returns and benchmark manually to verify alignment
        portfolio_returns = extract_daily_returns(result)
        benchmark_returns = get_benchmark_returns(result.start_date, result.end_date)

        # Align benchmark
        aligned_benchmark = benchmark_returns.reindex(portfolio_returns.index).fillna(0.0)

        # Verify no NaN after alignment
        assert not aligned_benchmark.isna().any()
        assert len(aligned_benchmark) == len(portfolio_returns)

        # Now generate tearsheet (should not raise errors)
        html = generate_portfolio_tearsheet(result)
        assert isinstance(html, str)
        assert len(html) > 1000


class TestCrossValidation:
    """Cross-validation tests combining multiple components."""

    def test_import_from_module(self):
        """Test that functions can be imported from src.reporting."""
        from src.reporting import (
            extract_daily_returns,
            generate_portfolio_tearsheet,
            get_benchmark_returns,
        )

        # Verify they are callable
        assert callable(extract_daily_returns)
        assert callable(get_benchmark_returns)
        assert callable(generate_portfolio_tearsheet)

    def test_end_to_end_workflow(self):
        """Test the complete workflow from BacktestResult to tearsheet."""
        # 1. Create a BacktestResult (simulating what BacktestEngine would produce)
        nav_history = []
        dates = pd.date_range("2024-01-02", "2024-01-15", freq="B")

        for i, date in enumerate(dates):
            if i == 0:
                daily_return = 0.0
                nav = 1000000.0
            else:
                daily_return = 0.0015 * (1 if i % 2 == 0 else -1)
                nav = nav_history[i - 1]["nav"] * (1 + daily_return)

            nav_history.append(
                {"date": date.strftime("%Y-%m-%d"), "nav": nav, "daily_return": daily_return}
            )

        result = BacktestResult(
            strategy_name="ChanTheory",
            start_date=dates[0].strftime("%Y-%m-%d"),
            end_date=dates[-1].strftime("%Y-%m-%d"),
            initial_capital=1000000.0,
            final_nav=nav_history[-1]["nav"],
            nav_history=nav_history,
        )

        # 2. Extract portfolio returns
        portfolio_returns = extract_daily_returns(result)
        assert len(portfolio_returns) == len(dates)
        assert not portfolio_returns.isna().any()

        # 3. Get benchmark returns
        benchmark_returns = get_benchmark_returns(result.start_date, result.end_date)
        assert isinstance(benchmark_returns, pd.Series)

        # 4. Generate tearsheet
        html = generate_portfolio_tearsheet(result)
        assert len(html) > 5000
        assert "<html" in html.lower()

        # All steps completed successfully


class TestChineseLanguageSupport:
    """Test Chinese language support for tearsheets."""

    def test_tearsheet_english_default(self):
        """Test that default language is English."""
        # Create minimal backtest result
        nav_history = [
            {"date": "2024-01-02", "nav": 1000000.0, "daily_return": 0.0},
            {"date": "2024-01-03", "nav": 1010000.0, "daily_return": 0.01},
            {"date": "2024-01-04", "nav": 1015000.0, "daily_return": 0.00495},
        ]

        result = BacktestResult(
            start_date="2024-01-02",
            end_date="2024-01-04",
            nav_history=nav_history,
        )

        # Generate with default language (English)
        html = generate_portfolio_tearsheet(result)

        # Should contain English labels
        assert "Key Performance Metrics" in html
        assert "Worst 10 Drawdowns" in html
        assert "Portfolio Tearsheet" in html

        # Should NOT contain Chinese labels
        assert "关键绩效指标" not in html
        assert "最大回撤 Top 10" not in html

    def test_tearsheet_chinese_language(self):
        """Test tearsheet generation with Chinese language."""
        nav_history = [
            {"date": "2024-01-02", "nav": 1000000.0, "daily_return": 0.0},
            {"date": "2024-01-03", "nav": 1010000.0, "daily_return": 0.01},
            {"date": "2024-01-04", "nav": 1015000.0, "daily_return": 0.00495},
        ]

        result = BacktestResult(
            start_date="2024-01-02",
            end_date="2024-01-04",
            nav_history=nav_history,
        )

        # Generate with Chinese language
        html = generate_portfolio_tearsheet(result, lang="zh")

        # Should contain Chinese labels
        assert "关键绩效指标" in html
        assert "最大回撤 Top 10" in html
        assert "投资组合报告" in html

        # Should NOT contain English labels (replaced by Chinese)
        assert "Key Performance Metrics" not in html
        assert "Worst 10 Drawdowns" not in html

    def test_tearsheet_chinese_metric_translations(self):
        """Test that specific metric labels are translated to Chinese."""
        nav_history = []
        dates = pd.date_range("2024-01-02", "2024-01-31", freq="B")

        for i, date in enumerate(dates):
            if i == 0:
                daily_return = 0.0
                nav = 1000000.0
            else:
                daily_return = 0.001 * ((-1) ** i)
                nav = nav_history[i - 1]["nav"] * (1 + daily_return)

            nav_history.append(
                {"date": date.strftime("%Y-%m-%d"), "nav": nav, "daily_return": daily_return}
            )

        result = BacktestResult(
            start_date="2024-01-02",
            end_date="2024-01-31",
            nav_history=nav_history,
        )

        html = generate_portfolio_tearsheet(result, lang="zh")

        # Check for specific Chinese metric labels
        # These are the most common metrics that should be translated
        chinese_metrics = [
            "夏普比率",  # Sharpe
            "索提诺比率",  # Sortino
            "最大回撤",  # Max Drawdown
            "年化收益率",  # CAGR
        ]

        for metric in chinese_metrics:
            assert metric in html, f"Chinese metric '{metric}' not found in HTML"

    def test_tearsheet_both_languages_produce_valid_html(self):
        """Test that both English and Chinese tearsheets produce valid HTML > 5000 chars."""
        nav_history = []
        dates = pd.date_range("2024-01-02", "2024-02-29", freq="B")

        for i, date in enumerate(dates):
            if i == 0:
                daily_return = 0.0
                nav = 1000000.0
            else:
                daily_return = 0.002 * ((-1) ** i)
                nav = nav_history[i - 1]["nav"] * (1 + daily_return)

            nav_history.append(
                {"date": date.strftime("%Y-%m-%d"), "nav": nav, "daily_return": daily_return}
            )

        result = BacktestResult(
            start_date="2024-01-02",
            end_date="2024-02-29",
            nav_history=nav_history,
        )

        # Generate both languages
        html_en = generate_portfolio_tearsheet(result, lang="en")
        html_zh = generate_portfolio_tearsheet(result, lang="zh")

        # Both should be valid HTML > 5000 chars
        assert len(html_en) > 5000
        assert len(html_zh) > 5000
        assert "<html" in html_en.lower()
        assert "<html" in html_zh.lower()
        assert "</html>" in html_en.lower()
        assert "</html>" in html_zh.lower()

    def test_chinese_template_file_exists(self):
        """Test that the Chinese template file exists."""
        from pathlib import Path

        template_path = Path(__file__).parent.parent.parent / "src" / "reporting" / "templates" / "tearsheet_zh.html"
        assert template_path.exists(), f"Chinese template not found at {template_path}"
        assert template_path.is_file()

        # Check that template has basic HTML structure
        content = template_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
        assert "</html>" in content
        assert "关键绩效指标" in content  # Key Performance Metrics in Chinese
