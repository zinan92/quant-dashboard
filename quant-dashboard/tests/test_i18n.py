"""Tests for the i18n module."""

from __future__ import annotations

import pytest

from src.i18n import TRANSLATIONS, t


class TestTranslationFunction:
    """Test the t() translation function."""

    def test_english_returns_key(self) -> None:
        """When lang='en', t() should return the English text (key itself)."""
        assert t("Total Return", "en") == "Total Return"
        assert t("📈 A-Share Quant Dashboard", "en") == "📈 A-Share Quant Dashboard"
        assert t("🚀 Run Backtest", "en") == "🚀 Run Backtest"

    def test_chinese_returns_translation(self) -> None:
        """When lang='zh', t() should return the Chinese translation."""
        assert t("Total Return", "zh") == "总收益率"
        assert t("📈 A-Share Quant Dashboard", "zh") == "📈 A股量化交易仪表盘"
        assert t("🚀 Run Backtest", "zh") == "🚀 运行回测"

    def test_unknown_key_returns_key(self) -> None:
        """When a key is not in TRANSLATIONS, return the key itself."""
        assert t("Unknown Key", "zh") == "Unknown Key"
        assert t("Another Unknown", "zh") == "Another Unknown"

    def test_default_language_is_english(self) -> None:
        """When lang is not specified, default to English (return key)."""
        assert t("Total Return") == "Total Return"

    def test_all_expected_keys_present(self) -> None:
        """Verify that all expected translation keys (English text) are present in TRANSLATIONS."""
        expected_keys = [
            # Page title and headers
            "A-Share Quant Dashboard — Chan Theory",
            "📈 A-Share Quant Dashboard",
            "**Strategy:** Chan Theory — Mechanical fractal detection based on MACD divergence",
            # Sidebar
            "⚙️ Backtest Configuration",
            "📊 A-Share Quant Dashboard — Chan Theory Showcase",
            "Language",
            # Controls
            "Strategy",
            "Select the trading strategy to backtest",
            "Date Range",
            "Start Date",
            "End Date",
            "Initial Capital (¥)",
            "Initial capital in RMB",
            "🚀 Run Backtest",
            # Tab names
            "📊 Portfolio Overview",
            "📈 Stock Analysis",
            # Performance metrics
            "📊 Performance Summary",
            "Total Return",
            "CAGR",
            "Sharpe Ratio",
            "Sortino Ratio",
            "Max Drawdown",
            "Win Rate",
            # Portfolio Overview
            "📈 Portfolio Tearsheet (QuantStats)",
            "📋 Trade History",
            # Trade table columns
            "Stock",
            "Entry Date",
            "Exit Date",
            "Entry Price",
            "Exit Price",
            "P&L",
            "P&L %",
            "Hold Days",
            # Stock Analysis
            "Select a stock to analyze:",
            "Select a stock that was traded during the backtest",
            "**Analyzing:** ",
            "#### Interactive Backtest Chart",
            "#### Performance Metrics",
            "Return",
            "# Trades",
            "#### Trade History for This Stock",
            # Messages
            "Loading stock list...",
            "Loaded {count} stocks from market.db",
            "Initializing backtest engine...",
            "Running backtest... {percent}%",
            "Backtest complete!",
            "✅ Backtest complete! Executed {count} trades.",
            "No trades executed during backtest period.",
            "No trades executed. Please run backtest first.",
            "Generating QuantStats tearsheet...",
            "Running single-stock backtest for {stock}...",
            "Error running backtest for {stock}: {error}",
            "No trades found for {stock}",
            # Welcome
            "👈 Configure backtest parameters in the sidebar, then click **Run Backtest** to begin.",
            "## Welcome to A-Share Quant Dashboard!",
        ]

        for key in expected_keys:
            assert key in TRANSLATIONS, f"Missing translation key: {key}"

    def test_translation_values_are_strings(self) -> None:
        """All translation values should be strings."""
        for key, value in TRANSLATIONS.items():
            assert isinstance(value, str), f"Translation for {key} is not a string"

    def test_translation_values_are_nonempty(self) -> None:
        """All translation values should be non-empty."""
        for key, value in TRANSLATIONS.items():
            assert len(value) > 0, f"Translation for {key} is empty"

    def test_format_placeholders_preserved(self) -> None:
        """Translations with format placeholders should work correctly."""
        # Test that format placeholders are preserved
        assert "{count}" in t("Loaded {count} stocks from market.db", "zh")
        assert "{percent}" in t("Running backtest... {percent}%", "zh")
        assert "{stock}" in t("Running single-stock backtest for {stock}...", "zh")
        
        # Test that we can actually format them
        result = t("Loaded {count} stocks from market.db", "zh").format(count=100)
        assert "100" in result
        
        result = t("Running backtest... {percent}%", "zh").format(percent=50)
        assert "50" in result

    def test_metric_labels_translation(self) -> None:
        """Key metric labels should have correct Chinese translations."""
        assert t("Total Return", "zh") == "总收益率"
        assert t("CAGR", "zh") == "年化收益率"
        assert t("Sharpe Ratio", "zh") == "夏普比率"
        assert t("Sortino Ratio", "zh") == "索提诺比率"
        assert t("Max Drawdown", "zh") == "最大回撤"
        assert t("Win Rate", "zh") == "胜率"

    def test_sidebar_labels_translation(self) -> None:
        """Sidebar control labels should have correct Chinese translations."""
        assert t("Strategy", "zh") == "策略"
        assert t("Start Date", "zh") == "开始日期"
        assert t("End Date", "zh") == "结束日期"
        assert t("Initial Capital (¥)", "zh") == "初始资金 (¥)"
        assert t("🚀 Run Backtest", "zh") == "🚀 运行回测"

    def test_tab_names_translation(self) -> None:
        """Tab names should have correct Chinese translations."""
        assert t("📊 Portfolio Overview", "zh") == "📊 投资组合概览"
        assert t("📈 Stock Analysis", "zh") == "📈 个股分析"

    def test_trade_table_columns_translation(self) -> None:
        """Trade table columns should have correct Chinese translations."""
        assert t("Stock", "zh") == "股票"
        assert t("Entry Date", "zh") == "买入日期"
        assert t("Exit Date", "zh") == "卖出日期"
        assert t("Entry Price", "zh") == "买入价"
        assert t("Exit Price", "zh") == "卖出价"
        assert t("P&L", "zh") == "盈亏"
        assert t("P&L %", "zh") == "收益率%"
        assert t("Hold Days", "zh") == "持有天数"
