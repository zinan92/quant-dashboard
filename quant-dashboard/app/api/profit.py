"""Profit and daily P&L endpoints.

GET /api/v1/profit returns profit summary from the latest backtest.
GET /api/v1/daily returns daily P&L data for equity curve visualization.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from src.backtest.store import BacktestStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["profit"])

_store = BacktestStore()


def _date_to_ms_epoch(date_str: str) -> int:
    """Convert YYYY-MM-DD to millisecond epoch timestamp."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return 0


def _build_zeroed_profit() -> dict[str, Any]:
    """Build a zeroed profit response for when no backtest exists."""
    return {
        "profit_closed_coin": 0.0,
        "profit_closed_percent": 0.0,
        "profit_closed_ratio": 0.0,
        "profit_closed_percent_mean": 0.0,
        "profit_closed_fiat": 0.0,
        "profit_all_coin": 0.0,
        "profit_all_percent": 0.0,
        "profit_all_ratio": 0.0,
        "profit_all_percent_mean": 0.0,
        "profit_all_fiat": 0.0,
        "trade_count": 0,
        "closed_trade_count": 0,
        "first_trade_date": "",
        "first_trade_timestamp": 0,
        "latest_trade_date": "",
        "latest_trade_timestamp": 0,
        "avg_duration": "0:00:00",
        "best_pair": "",
        "best_rate": 0.0,
        "winning_trades": 0,
        "losing_trades": 0,
        "profit_factor": 0.0,
        "winrate": 0.0,
        "expectancy": 0.0,
        "expectancy_ratio": 0.0,
        # Performance metrics
        "sharpe": 0.0,
        "sortino": 0.0,
        "calmar": 0.0,
        "max_drawdown": 0.0,
        "max_drawdown_abs": 0.0,
        "max_drawdown_start": "",
        "max_drawdown_start_timestamp": 0,
        "max_drawdown_end": "",
        "max_drawdown_end_timestamp": 0,
        "trading_volume": 0.0,
        "bot_start_timestamp": 0,
        "bot_start_date": "",
    }


@router.get("/profit")
def get_profit(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    """Get profit summary from the latest backtest.

    Returns zeroed values if no backtest has been run yet.
    All numeric fields are guaranteed to be numbers (not null/NaN).

    FreqUI calls this endpoint on every refresh cycle.
    """
    latest_run = _store.get_latest_run()
    if latest_run is None:
        logger.info("No backtest run found, returning zeroed profit")
        return _build_zeroed_profit()

    run_id = latest_run["id"]
    metrics_json = latest_run.get("metrics_json", "{}")
    try:
        metrics = json.loads(metrics_json)
    except (json.JSONDecodeError, TypeError):
        metrics = {}

    trades = _store.get_trades(run_id)
    start_date = latest_run["start_date"]
    end_date = latest_run["end_date"]

    # Calculate aggregate trade metrics
    trade_count = len(trades)
    if trade_count == 0:
        return _build_zeroed_profit()

    winning_trades = [t for t in trades if t["pnl"] > 0]
    losing_trades = [t for t in trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in trades)
    total_pnl_ratio = sum(t["pnl_pct"] for t in trades)

    # Best pair by profit
    pair_profits: dict[str, float] = {}
    for t in trades:
        pair = t["symbol"]
        pair_profits[pair] = pair_profits.get(pair, 0.0) + t["pnl"]
    best_pair = max(pair_profits, key=pair_profits.get) if pair_profits else ""
    best_rate = pair_profits.get(best_pair, 0.0) / latest_run["initial_capital"]

    # Win rate and profit factor
    winning_count = len(winning_trades)
    losing_count = len(losing_trades)
    winrate = winning_count / trade_count if trade_count > 0 else 0.0

    total_win = sum(t["pnl"] for t in winning_trades)
    total_loss = abs(sum(t["pnl"] for t in losing_trades))
    profit_factor = total_win / total_loss if total_loss > 0 else 0.0

    # Expectancy
    avg_win = total_win / winning_count if winning_count > 0 else 0.0
    avg_loss = total_loss / losing_count if losing_count > 0 else 0.0
    expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)
    expectancy_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

    # Average trade duration (days)
    durations = []
    for t in trades:
        try:
            entry_dt = datetime.strptime(t["entry_date"], "%Y-%m-%d")
            exit_dt = datetime.strptime(t["exit_date"], "%Y-%m-%d")
            durations.append((exit_dt - entry_dt).days)
        except (ValueError, TypeError):
            pass
    avg_duration_days = sum(durations) / len(durations) if durations else 0
    avg_duration_str = f"{int(avg_duration_days)} days 0:00:00"

    # Max drawdown from metrics
    max_drawdown = metrics.get("max_drawdown", 0.0)
    max_drawdown_abs = metrics.get("max_drawdown_abs", 0.0)

    # First and last trade dates
    first_trade = trades[0] if trades else None
    last_trade = trades[-1] if trades else None

    first_trade_date = first_trade["entry_date"] if first_trade else start_date
    first_trade_ts = _date_to_ms_epoch(first_trade_date)
    latest_trade_date = last_trade["exit_date"] if last_trade else end_date
    latest_trade_ts = _date_to_ms_epoch(latest_trade_date)

    # Bot start date (backtest start)
    bot_start_date = start_date
    bot_start_ts = _date_to_ms_epoch(bot_start_date)

    return {
        "profit_closed_coin": total_pnl,
        "profit_closed_percent": total_pnl_ratio * 100.0,  # as percentage
        "profit_closed_ratio": total_pnl_ratio,  # as decimal
        "profit_closed_percent_mean": (total_pnl_ratio / trade_count * 100.0) if trade_count > 0 else 0.0,
        "profit_closed_fiat": total_pnl,
        "profit_all_coin": total_pnl,
        "profit_all_percent": total_pnl_ratio * 100.0,
        "profit_all_ratio": total_pnl_ratio,
        "profit_all_percent_mean": (total_pnl_ratio / trade_count * 100.0) if trade_count > 0 else 0.0,
        "profit_all_fiat": total_pnl,
        "trade_count": trade_count,
        "closed_trade_count": trade_count,
        "first_trade_date": first_trade_date,
        "first_trade_timestamp": first_trade_ts,
        "latest_trade_date": latest_trade_date,
        "latest_trade_timestamp": latest_trade_ts,
        "avg_duration": avg_duration_str,
        "best_pair": best_pair,
        "best_rate": best_rate,
        "winning_trades": winning_count,
        "losing_trades": losing_count,
        "profit_factor": profit_factor,
        "winrate": winrate,
        "expectancy": expectancy,
        "expectancy_ratio": expectancy_ratio,
        # Performance metrics from backtest
        "sharpe": metrics.get("sharpe", 0.0),
        "sortino": metrics.get("sortino", 0.0),
        "calmar": metrics.get("calmar", 0.0),
        "max_drawdown": max_drawdown,
        "max_drawdown_abs": max_drawdown_abs,
        "max_drawdown_start": start_date,
        "max_drawdown_start_timestamp": _date_to_ms_epoch(start_date),
        "max_drawdown_end": end_date,
        "max_drawdown_end_timestamp": _date_to_ms_epoch(end_date),
        "trading_volume": sum(t["entry_price"] * t["shares"] for t in trades),
        "bot_start_timestamp": bot_start_ts,
        "bot_start_date": bot_start_date,
    }


@router.get("/daily")
def get_daily(
    timescale: Annotated[int, Query(alias="timescale")] = 30,
    _user: Annotated[str, Depends(get_current_user)] = "",
) -> dict[str, Any]:
    """Get daily P&L data from the latest backtest.

    Query parameters:
        timescale: Number of days to return (default 30, ignored for now)

    Returns:
        {
            "data": [
                {
                    "date": "YYYY-MM-DD",
                    "abs_profit": float,  # cumulative profit
                    "rel_profit": float,  # cumulative return ratio
                    "starting_balance": float,  # NAV at start of day
                    "trade_count": int
                },
                ...
            ],
            "stake_currency": "CNY",
            "fiat_display_currency": "CNY"
        }

    Returns empty data array if no backtest has been run.
    """
    latest_run = _store.get_latest_run()
    if latest_run is None:
        logger.info("No backtest run found, returning empty daily data")
        return {
            "data": [],
            "stake_currency": "CNY",
            "fiat_display_currency": "CNY",
        }

    run_id = latest_run["id"]
    initial_capital = latest_run["initial_capital"]
    nav_history = _store.get_daily_nav(run_id)

    # Convert to FreqTrade daily format
    data = []
    for entry in nav_history:
        nav = entry["nav"]
        abs_profit = nav - initial_capital
        rel_profit = (nav / initial_capital) - 1.0 if initial_capital > 0 else 0.0

        data.append({
            "date": entry["date"],
            "abs_profit": abs_profit,
            "rel_profit": rel_profit,
            "starting_balance": nav,
            "trade_count": 0,  # We don't track per-day trade count in daily_nav
        })

    return {
        "data": data,
        "stake_currency": "CNY",
        "fiat_display_currency": "CNY",
    }
