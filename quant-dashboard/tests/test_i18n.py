"""Tests for the i18n module."""

from __future__ import annotations

import pytest

from src.i18n import TRANSLATIONS, t


class TestTranslationFunction:
    """Test the t() translation function."""

    def test_english_returns_key(self) -> None:
        """When lang='en', t() should return the key itself."""
        assert t("total_return", "en") == "total_return"
        assert t("dashboard_title", "en") == "dashboard_title"
        assert t("run_backtest", "en") == "run_backtest"

    def test_chinese_returns_translation(self) -> None:
        """When lang='zh', t() should return the Chinese translation."""
        assert t("total_return", "zh") == "总收益率"
        assert t("dashboard_title", "zh") == "📈 A股量化交易仪表盘"
        assert t("run_backtest", "zh") == "🚀 运行回测"

    def test_unknown_key_returns_key(self) -> None:
        """When a key is not in TRANSLATIONS, return the key itself."""
        assert t("unknown_key", "zh") == "unknown_key"
        assert t("another_unknown", "zh") == "another_unknown"

    def test_default_language_is_english(self) -> None:
        """When lang is not specified, default to English (return key)."""
        assert t("total_return") == "total_return"

    def test_all_expected_keys_present(self) -> None:
        """Verify that all expected translation keys are present in TRANSLATIONS."""
        expected_keys = [
            # Page title and headers
            "page_title",
            "dashboard_title",
            "strategy_subtitle",
            # Sidebar
            "sidebar_title",
            "sidebar_caption",
            "language",
            # Controls
            "strategy",
            "strategy_help",
            "date_range",
            "start_date",
            "end_date",
            "initial_capital",
            "initial_capital_help",
            "run_backtest",
            # Tab names
            "tab_portfolio_overview",
            "tab_stock_analysis",
            # Performance metrics
            "performance_summary",
            "total_return",
            "cagr",
            "sharpe_ratio",
            "sortino_ratio",
            "max_drawdown",
            "win_rate",
            # Portfolio Overview
            "portfolio_tearsheet",
            "trade_history",
            # Trade table columns
            "stock",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "pnl_pct",
            "hold_days",
            # Stock Analysis
            "stock_analysis_title",
            "select_stock",
            "select_stock_help",
            "analyzing",
            "interactive_chart",
            "performance_metrics",
            "return",
            "num_trades",
            "trade_history_stock",
            # Messages
            "loading_stocks",
            "stocks_loaded",
            "initializing_engine",
            "running_backtest_progress",
            "backtest_complete_progress",
            "backtest_complete_message",
            "no_trades",
            "no_trades_run_first",
            "generating_tearsheet",
            "running_single_backtest",
            "backtest_error",
            "no_trades_for_stock",
            # Welcome
            "welcome_configure",
            "welcome_title",
            "welcome_description",
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
        assert "{count}" in t("stocks_loaded", "zh")
        assert "{percent}" in t("running_backtest_progress", "zh")
        assert "{stock}" in t("running_single_backtest", "zh")
        
        # Test that we can actually format them
        result = t("stocks_loaded", "zh").format(count=100)
        assert "100" in result
        
        result = t("running_backtest_progress", "zh").format(percent=50)
        assert "50" in result

    def test_metric_labels_translation(self) -> None:
        """Key metric labels should have correct Chinese translations."""
        assert t("total_return", "zh") == "总收益率"
        assert t("cagr", "zh") == "年化收益率"
        assert t("sharpe_ratio", "zh") == "夏普比率"
        assert t("sortino_ratio", "zh") == "索提诺比率"
        assert t("max_drawdown", "zh") == "最大回撤"
        assert t("win_rate", "zh") == "胜率"

    def test_sidebar_labels_translation(self) -> None:
        """Sidebar control labels should have correct Chinese translations."""
        assert t("strategy", "zh") == "策略"
        assert t("start_date", "zh") == "开始日期"
        assert t("end_date", "zh") == "结束日期"
        assert t("initial_capital", "zh") == "初始资金 (¥)"
        assert t("run_backtest", "zh") == "🚀 运行回测"

    def test_tab_names_translation(self) -> None:
        """Tab names should have correct Chinese translations."""
        assert t("tab_portfolio_overview", "zh") == "📊 投资组合概览"
        assert t("tab_stock_analysis", "zh") == "📈 个股分析"

    def test_trade_table_columns_translation(self) -> None:
        """Trade table columns should have correct Chinese translations."""
        assert t("stock", "zh") == "股票"
        assert t("entry_date", "zh") == "买入日期"
        assert t("exit_date", "zh") == "卖出日期"
        assert t("entry_price", "zh") == "买入价"
        assert t("exit_price", "zh") == "卖出价"
        assert t("pnl", "zh") == "盈亏"
        assert t("pnl_pct", "zh") == "收益率%"
        assert t("hold_days", "zh") == "持有天数"
