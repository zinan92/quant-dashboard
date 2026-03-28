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


def generate_portfolio_tearsheet(
    backtest_result: BacktestResult, reader: MarketReader | None = None
) -> str:
    """Generate a QuantStats HTML tearsheet for the portfolio.

    Parameters
    ----------
    backtest_result : BacktestResult
        The backtest result containing nav_history.
    reader : MarketReader, optional
        MarketReader instance for fetching benchmark data.

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
            title="Portfolio Tearsheet",
        )

        # Read the HTML file
        html_content = Path(tmp_path).read_text(encoding="utf-8")

        return html_content
    finally:
        # Clean up temporary file
        Path(tmp_path).unlink(missing_ok=True)
