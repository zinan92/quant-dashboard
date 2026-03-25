"""Performance metrics calculation for backtest results.

Calculates: total return, annualized return (CAGR), max drawdown, Sharpe ratio,
Sortino ratio, Calmar ratio, win rate, profit factor, trade count, avg trade duration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np

from src.backtest.portfolio import Trade

# Risk-free rate for Sharpe ratio calculation
RISK_FREE_RATE = 0.025  # 2.5% annual
TRADING_DAYS_PER_YEAR = 244  # A-share trading days per year


def calculate_metrics(
    nav_history: list[dict[str, Any]],
    closed_trades: list[Trade],
    initial_capital: float,
) -> dict[str, Any]:
    """Calculate comprehensive performance metrics from backtest results.

    Parameters
    ----------
    nav_history : list[dict]
        Daily NAV records, each with keys: ``date``, ``nav``, ``daily_return``.
    closed_trades : list[Trade]
        List of completed trades.
    initial_capital : float
        Starting capital in CNY.

    Returns
    -------
    dict[str, Any]
        Dictionary containing all performance metrics. All values are numeric
        (never NaN — NaN is replaced with 0.0).
    """
    metrics: dict[str, Any] = {}

    # -------------------------------------------------------------------
    # NAV-based metrics
    # -------------------------------------------------------------------
    if not nav_history:
        # Return zeroed metrics if no data
        return _zero_metrics()

    navs = np.array([entry["nav"] for entry in nav_history], dtype=np.float64)
    daily_returns = np.array([entry["daily_return"] for entry in nav_history], dtype=np.float64)

    final_nav = float(navs[-1])
    total_days = len(nav_history)

    # Total return (decimal ratio)
    total_return = (final_nav - initial_capital) / initial_capital
    metrics["profit_total"] = _safe_float(total_return)

    # Total return (absolute CNY)
    metrics["profit_total_abs"] = _safe_float(final_nav - initial_capital)

    # Annualized return (CAGR)
    years = total_days / TRADING_DAYS_PER_YEAR
    if years > 0 and final_nav > 0 and initial_capital > 0:
        cagr = (final_nav / initial_capital) ** (1.0 / years) - 1.0
    else:
        cagr = 0.0
    metrics["cagr"] = _safe_float(cagr)

    # Max drawdown
    max_dd, max_dd_abs = _calculate_max_drawdown(navs)
    metrics["max_drawdown"] = _safe_float(max_dd)
    metrics["max_drawdown_abs"] = _safe_float(max_dd_abs)

    # Sharpe ratio (annualized)
    metrics["sharpe"] = _safe_float(_calculate_sharpe(daily_returns))

    # Sortino ratio (annualized)
    metrics["sortino"] = _safe_float(_calculate_sortino(daily_returns))

    # Calmar ratio
    if max_dd != 0:
        calmar = cagr / abs(max_dd)
    else:
        calmar = 0.0
    metrics["calmar"] = _safe_float(calmar)

    # -------------------------------------------------------------------
    # Trade-based metrics
    # -------------------------------------------------------------------
    trade_count = len(closed_trades)
    metrics["trade_count"] = trade_count

    if trade_count > 0:
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]

        # Win rate (decimal ratio)
        win_rate = len(wins) / trade_count
        metrics["winrate"] = _safe_float(win_rate)

        # Profit factor
        total_profit = sum(t.pnl for t in wins) if wins else 0.0
        total_loss = abs(sum(t.pnl for t in losses)) if losses else 0.0
        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0
        metrics["profit_factor"] = _safe_float(profit_factor)

        # Average trade P&L
        avg_pnl = sum(t.pnl for t in closed_trades) / trade_count
        metrics["avg_trade_pnl"] = _safe_float(avg_pnl)

        # Average trade duration (in days)
        durations = []
        for t in closed_trades:
            try:
                entry_dt = datetime.strptime(t.entry_date, "%Y-%m-%d")
                exit_dt = datetime.strptime(t.exit_date, "%Y-%m-%d")
                durations.append((exit_dt - entry_dt).days)
            except (ValueError, TypeError):
                pass
        avg_duration = sum(durations) / len(durations) if durations else 0.0
        metrics["avg_trade_duration"] = _safe_float(avg_duration)
    else:
        metrics["winrate"] = 0.0
        metrics["profit_factor"] = 0.0
        metrics["avg_trade_pnl"] = 0.0
        metrics["avg_trade_duration"] = 0.0

    # Backtest duration
    if nav_history:
        metrics["backtest_start"] = nav_history[0]["date"]
        metrics["backtest_end"] = nav_history[-1]["date"]
        metrics["total_days"] = total_days

    return metrics


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _calculate_max_drawdown(navs: np.ndarray) -> tuple[float, float]:
    """Calculate maximum drawdown from a NAV series.

    Returns
    -------
    tuple[float, float]
        (max_drawdown_ratio, max_drawdown_abs)
        Drawdown ratio is negative (e.g. -0.10 = 10% drawdown).
    """
    if len(navs) < 2:
        return 0.0, 0.0

    peak = navs[0]
    max_dd_ratio = 0.0
    max_dd_abs = 0.0

    for nav in navs:
        if nav > peak:
            peak = nav
        dd_abs = nav - peak
        dd_ratio = dd_abs / peak if peak > 0 else 0.0
        if dd_ratio < max_dd_ratio:
            max_dd_ratio = dd_ratio
            max_dd_abs = dd_abs

    return max_dd_ratio, max_dd_abs


def _calculate_sharpe(daily_returns: np.ndarray) -> float:
    """Calculate annualized Sharpe ratio.

    Sharpe = (mean_daily_return - daily_risk_free) / std_daily_return * sqrt(N)
    """
    if len(daily_returns) < 2:
        return 0.0

    daily_rf = RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
    excess_returns = daily_returns - daily_rf
    std = float(np.std(excess_returns, ddof=1))

    if std == 0:
        return 0.0

    sharpe = float(np.mean(excess_returns)) / std * float(np.sqrt(TRADING_DAYS_PER_YEAR))
    return float(sharpe)


def _calculate_sortino(daily_returns: np.ndarray) -> float:
    """Calculate annualized Sortino ratio.

    Sortino = (mean_daily_return - daily_risk_free) / downside_std * sqrt(N)
    Only considers negative returns for the denominator.
    """
    if len(daily_returns) < 2:
        return 0.0

    daily_rf = RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
    excess_returns = daily_returns - daily_rf

    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) < 1:
        return 0.0

    downside_std = float(np.std(downside_returns, ddof=1))
    if downside_std == 0:
        return 0.0

    sortino = float(np.mean(excess_returns)) / downside_std * float(np.sqrt(TRADING_DAYS_PER_YEAR))
    return float(sortino)


def _safe_float(value: float) -> float:
    """Return 0.0 if value is NaN or Inf, otherwise round to 6 decimal places."""
    if np.isnan(value) or np.isinf(value):
        return 0.0
    return round(float(value), 6)


def _zero_metrics() -> dict[str, Any]:
    """Return a dict with all metrics set to zero/empty defaults."""
    return {
        "profit_total": 0.0,
        "profit_total_abs": 0.0,
        "cagr": 0.0,
        "max_drawdown": 0.0,
        "max_drawdown_abs": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "calmar": 0.0,
        "trade_count": 0,
        "winrate": 0.0,
        "profit_factor": 0.0,
        "avg_trade_pnl": 0.0,
        "avg_trade_duration": 0.0,
    }
