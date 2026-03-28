"""QuantStats-based portfolio tearsheet generation.

This module provides functions to:
1. Extract daily returns from BacktestResult
2. Fetch benchmark returns (CSI 300)
3. Generate HTML tearsheets with QuantStats
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import quantstats as qs

if TYPE_CHECKING:
    from src.backtest.engine import BacktestResult
    from src.data_layer.market_reader import MarketReader


def extract_daily_returns(backtest_result: BacktestResult) -> pd.Series:
    """Extract daily returns from BacktestResult as a pandas Series.

    Parameters
    ----------
    backtest_result : BacktestResult
        The backtest result containing nav_history.

    Returns
    -------
    pd.Series
        Daily returns series with DatetimeIndex, dtype float64.
        Index name is 'date', series name is 'returns'.

    Notes
    -----
    The nav_history is a list of dicts with keys: date (str), nav (float),
    daily_return (float). This function extracts the daily_return field
    and converts the date to a DatetimeIndex.
    """
    if not backtest_result.nav_history:
        # Return empty series with correct schema
        empty_series = pd.Series([], dtype="float64", name="returns")
        empty_series.index = pd.DatetimeIndex([], name="date")
        return empty_series

    # Extract dates and daily_return values
    dates = [record["date"] for record in backtest_result.nav_history]
    returns = [record["daily_return"] for record in backtest_result.nav_history]

    # Create series with DatetimeIndex
    series = pd.Series(returns, index=pd.to_datetime(dates), dtype="float64", name="returns")
    series.index.name = "date"

    return series


def get_benchmark_returns(
    start_date: str, end_date: str, reader: MarketReader | None = None
) -> pd.Series:
    """Get CSI 300 index daily returns for the specified date range.

    Parameters
    ----------
    start_date : str
        Start date in YYYY-MM-DD format.
    end_date : str
        End date in YYYY-MM-DD format.
    reader : MarketReader, optional
        MarketReader instance. If None, creates a default instance.

    Returns
    -------
    pd.Series
        Daily returns series with DatetimeIndex, dtype float64.
        Index name is 'date', series name is 'benchmark'.

    Notes
    -----
    Uses MarketReader.get_index_klines() to fetch CSI 300 data (symbol '000300').
    Calculates returns as: (close[i] - close[i-1]) / close[i-1]
    """
    if reader is None:
        from src.data_layer.market_reader import MarketReader

        reader = MarketReader()

    # Fetch CSI 300 index data (000300.SH is the full symbol code in market.db)
    df = reader.get_index_klines(
        symbol_code="000300.SH", timeframe="DAY", start_date=start_date, end_date=end_date
    )

    if df.empty:
        # Return empty series with correct schema
        empty_series = pd.Series([], dtype="float64", name="benchmark")
        empty_series.index = pd.DatetimeIndex([], name="date")
        return empty_series

    # Convert date column to datetime
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df = df.sort_index()

    # Calculate daily returns from close prices
    returns = df["close"].pct_change()

    # First value will be NaN, drop it
    returns = returns.dropna()

    # Convert to float64 and set name
    returns = returns.astype("float64")
    returns.name = "benchmark"

    return returns


def _translate_metrics_to_chinese(html: str) -> str:
    """Translate English metric labels to Chinese in the HTML tearsheet.

    Parameters
    ----------
    html : str
        HTML content with English labels.

    Returns
    -------
    str
        HTML content with Chinese labels.

    Notes
    -----
    This function performs string replacement to translate common QuantStats
    metric labels, chart titles, and table headers from English to Chinese.
    """
    # Define translation mappings
    translations = {
        # Metric labels (right side panel)
        "Start Period": "开始日期",
        "End Period": "结束日期",
        "Risk-Free Rate": "无风险利率",
        "Time in Market": "持仓时间",
        "Cumulative Return": "累计收益率",
        "Total Return": "总收益率",
        "CAGR﹪": "年化收益率",
        "Sharpe": "夏普比率",
        "Prob. Sharpe Ratio": "概率夏普比率",
        "Smart Sharpe": "智能夏普比率",
        "Sortino": "索提诺比率",
        "Smart Sortino": "智能索提诺比率",
        "Sortino/√2": "调整索提诺比率",
        "Smart Sortino/√2": "智能调整索提诺比率",
        "Omega": "欧米伽比率",
        "Max Drawdown": "最大回撤",
        "Max DD Date": "最大回撤日期",
        "Max DD Period Start": "回撤期开始",
        "Max DD Period End": "回撤期结束",
        "Longest DD Days": "最长回撤天数",
        "Volatility (ann.)": "波动率 (年化)",
        "Calmar": "卡玛比率",
        "Skew": "偏度",
        "Kurtosis": "峰度",
        "Expected Daily": "日均收益",
        "Expected Monthly": "月均收益",
        "Expected Yearly": "年均收益",
        "Kelly Criterion": "凯利准则",
        "Risk of Ruin": "破产风险",
        "Daily Value-at-Risk": "日均风险价值",
        "Expected Shortfall (cVaR)": "预期损失",
        "Max Consecutive Wins": "最大连续盈利",
        "Max Consecutive Losses": "最大连续亏损",
        "Gain/Pain Ratio": "收益痛苦比",
        "Gain/Pain": "收益痛苦比",
        "Payoff Ratio": "盈亏比",
        "Profit Factor": "利润因子",
        "Common Sense Ratio": "常识比率",
        "CPC Index": "CPC指数",
        "Tail Ratio": "尾部比率",
        "Outlier Win Ratio": "异常盈利比率",
        "Outlier Loss Ratio": "异常亏损比率",
        "MTD": "月初至今",
        "3M": "近3个月",
        "6M": "近6个月",
        "YTD": "年初至今",
        "1Y": "近1年",
        "3Y (ann.)": "近3年(年化)",
        "5Y (ann.)": "近5年(年化)",
        "10Y (ann.)": "近10年(年化)",
        "All-time (ann.)": "全部(年化)",
        # Chart and section titles
        "Cumulative Returns": "累计收益",
        "Returns": "收益率",
        "Log Returns": "对数收益",
        "Daily Returns": "日收益率",
        "Monthly Returns": "月度收益",
        "Distribution of Returns": "收益分布",
        "Monthly Distribution": "月度分布",
        "Rolling Volatility": "滚动波动率",
        "Rolling Sharpe": "滚动夏普比率",
        "Rolling Sortino": "滚动索提诺比率",
        "Rolling Beta": "滚动贝塔系数",
        "Underwater Plot": "水下图",
        "Drawdown Periods": "回撤周期",
        "Worst Drawdowns": "最大回撤",
        "Worst 10 Drawdowns": "最大回撤 Top 10",
        "Drawdown": "回撤",
        "EOY Returns vs Benchmark": "年度收益 vs 基准",
        "EOY Returns": "年度收益",
        # Table column headers
        "Strategy": "策略",
        "Benchmark": "基准",
        "Started": "开始",
        "Recovered": "恢复",
        "Days": "天数",
        "Multiplier": "倍数",
        "Won": "胜出",
        # Months (for monthly returns heatmap)
        "Jan": "1月",
        "Feb": "2月",
        "Mar": "3月",
        "Apr": "4月",
        "May": "5月",
        "Jun": "6月",
        "Jul": "7月",
        "Aug": "8月",
        "Sep": "9月",
        "Oct": "10月",
        "Nov": "11月",
        "Dec": "12月",
    }

    # Apply translations
    for english, chinese in translations.items():
        # Replace in HTML, being careful to match whole words where possible
        # Use word boundaries for metric names in tables
        html = html.replace(f">{english}<", f">{chinese}<")
        html = html.replace(f">{english}%<", f">{chinese}%<")
        html = html.replace(f" {english} ", f" {chinese} ")
        # Also replace in title attributes and labels
        html = html.replace(f'"{english}"', f'"{chinese}"')
        html = html.replace(f"'{english}'", f"'{chinese}'")

    return html


def generate_portfolio_tearsheet(
    backtest_result: BacktestResult, reader: MarketReader | None = None, lang: str = "en"
) -> str:
    """Generate a QuantStats HTML tearsheet for the portfolio.

    Parameters
    ----------
    backtest_result : BacktestResult
        The backtest result containing nav_history.
    reader : MarketReader, optional
        MarketReader instance for fetching benchmark data.
    lang : str, optional
        Language for the tearsheet. 'en' for English (default), 'zh' for Chinese.

    Returns
    -------
    str
        Complete HTML tearsheet as a string.

    Notes
    -----
    This function:
    1. Extracts portfolio daily returns
    2. Fetches CSI 300 benchmark returns aligned to portfolio dates
    3. Generates QuantStats HTML report
    4. Returns the HTML as a string

    The generated tearsheet includes:
    - Monthly returns table
    - Drawdown analysis
    - Benchmark comparison
    - Risk metrics (Sharpe, Sortino, Calmar, etc.)

    When lang='zh', uses a custom Chinese template and translates metric labels.
    """
    # Extract portfolio returns
    portfolio_returns = extract_daily_returns(backtest_result)

    if portfolio_returns.empty:
        # Return minimal HTML if no data
        return "<html><body><h1>No data available</h1></body></html>"

    # Get benchmark returns aligned to portfolio dates
    start_date = backtest_result.start_date
    end_date = backtest_result.end_date
    benchmark_returns = get_benchmark_returns(start_date, end_date, reader)

    # Align benchmark to portfolio dates (in case of missing data)
    # We need to reindex benchmark to match portfolio dates
    if not benchmark_returns.empty:
        benchmark_returns = benchmark_returns.reindex(portfolio_returns.index)
        # Fill any NaN values with 0 (no return on days where benchmark data is missing)
        benchmark_returns = benchmark_returns.fillna(0.0)
    else:
        # If no benchmark data, create a zero series
        benchmark_returns = pd.Series(0.0, index=portfolio_returns.index, name="benchmark")

    # Determine template path based on language
    template_path = None
    if lang == "zh":
        # Use custom Chinese template
        template_path = Path(__file__).parent / "templates" / "tearsheet_zh.html"
        if not template_path.exists():
            # Fall back to default if Chinese template doesn't exist
            template_path = None

    # Generate HTML tearsheet using QuantStats
    # We'll write to a temporary file and read it back
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as tmp_file:
        tmp_path = tmp_file.name

    try:
        # Generate the report
        qs.reports.html(
            portfolio_returns,
            benchmark=benchmark_returns,
            output=tmp_path,
            title="投资组合报告" if lang == "zh" else "Portfolio Tearsheet",
            template_path=str(template_path) if template_path else None,
        )

        # Read the HTML file
        html_content = Path(tmp_path).read_text(encoding="utf-8")

        # Post-process HTML to translate metric labels if Chinese
        if lang == "zh":
            html_content = _translate_metrics_to_chinese(html_content)

        return html_content
    finally:
        # Clean up temporary file
        Path(tmp_path).unlink(missing_ok=True)
