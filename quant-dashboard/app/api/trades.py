"""Trades endpoints: trade history, status, performance.

GET /api/v1/trades returns paginated trade history from the latest backtest.
GET /api/v1/status returns empty array (no live trades in webserver mode).
GET /api/v1/performance returns per-pair profit summary.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from src.backtest.store import BacktestStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["trades"])

_store = BacktestStore()


def _date_to_ms_epoch(date_str: str) -> int:
    """Convert YYYY-MM-DD to millisecond epoch timestamp."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return 0


@router.get("/trades")
def get_trades(
    limit: Annotated[int, Query()] = 500,
    offset: Annotated[int, Query()] = 0,
    _user: Annotated[str, Depends(get_current_user)] = "",
) -> dict[str, Any]:
    """Get trade history from the latest backtest.

    Query parameters:
        limit: Maximum number of trades to return (default 500)
        offset: Number of trades to skip (default 0)

    Returns:
        {
            "trades": [
                {
                    "trade_id": int,
                    "pair": str,  # stock symbol
                    "open_date": str,
                    "open_timestamp": int,  # millisecond epoch
                    "close_date": str,
                    "close_timestamp": int,
                    "open_rate": float,
                    "close_rate": float,
                    "profit_abs": float,
                    "profit_ratio": float,
                    "profit_pct": float,
                    "is_open": bool,  # always false in webserver mode
                    "exchange": str,
                    "strategy": str,
                    "fee_open": float,
                    "fee_close": float,
                    "amount": float,  # shares
                    "stake_amount": float,
                    "close_profit_abs": float
                },
                ...
            ],
            "trades_count": int,  # number of trades in this response
            "offset": int,
            "total_trades": int  # total trades across all pages
        }

    Returns empty trades array if no backtest has been run.
    """
    latest_run = _store.get_latest_run()
    if latest_run is None:
        logger.info("No backtest run found, returning empty trades")
        return {
            "trades": [],
            "trades_count": 0,
            "offset": offset,
            "total_trades": 0,
        }

    run_id = latest_run["id"]
    strategy = latest_run["strategy"]
    all_trades = _store.get_trades(run_id)
    total_trades = len(all_trades)

    # Apply pagination
    paginated_trades = all_trades[offset : offset + limit]

    # Convert to FreqTrade trade format
    trades_output = []
    for t in paginated_trades:
        # Calculate fees (0.03% commission on each side)
        stake_amount = t["entry_price"] * t["shares"]
        fee_rate = 0.0003
        fee_open = stake_amount * fee_rate
        fee_close = t["exit_price"] * t["shares"] * fee_rate

        trades_output.append({
            "trade_id": t["trade_id"],
            "pair": t["symbol"],
            "open_date": t["entry_date"],
            "open_timestamp": _date_to_ms_epoch(t["entry_date"]),
            "close_date": t["exit_date"],
            "close_timestamp": _date_to_ms_epoch(t["exit_date"]),
            "open_rate": t["entry_price"],
            "close_rate": t["exit_price"],
            "profit_abs": t["pnl"],
            "profit_ratio": t["pnl_pct"],
            "profit_pct": t["pnl_pct"] * 100.0,  # as percentage
            "is_open": False,  # all trades are closed in backtest
            "exchange": "ashare",
            "strategy": strategy,
            "fee_open": fee_rate,
            "fee_close": fee_rate + 0.001,  # includes stamp tax on sell
            "amount": float(t["shares"]),
            "stake_amount": stake_amount,
            "close_profit_abs": t["pnl"],
        })

    return {
        "trades": trades_output,
        "trades_count": len(trades_output),
        "offset": offset,
        "total_trades": total_trades,
    }


@router.get("/status")
def get_status(
    _user: Annotated[str, Depends(get_current_user)] = "",
) -> list[Any]:
    """Get currently open trades.

    In webserver mode (backtest only), there are never any open trades.
    Always returns an empty array.

    FreqUI calls this endpoint on every refresh cycle.
    """
    return []


@router.get("/performance")
def get_performance(
    _user: Annotated[str, Depends(get_current_user)] = "",
) -> list[dict[str, Any]]:
    """Get per-pair performance summary from the latest backtest.

    Returns:
        [
            {
                "pair": str,
                "profit": float,  # total profit ratio
                "profit_pct": float,  # profit as percentage
                "profit_abs": float,  # absolute profit in CNY
                "count": int  # number of trades
            },
            ...
        ]

    Returns empty array if no backtest has been run.
    """
    latest_run = _store.get_latest_run()
    if latest_run is None:
        logger.info("No backtest run found, returning empty performance")
        return []

    run_id = latest_run["id"]
    trades = _store.get_trades(run_id)

    # Aggregate by pair
    pair_stats: dict[str, dict[str, Any]] = {}
    for t in trades:
        pair = t["symbol"]
        if pair not in pair_stats:
            pair_stats[pair] = {
                "pair": pair,
                "profit_ratio": 0.0,
                "profit_abs": 0.0,
                "count": 0,
            }

        pair_stats[pair]["profit_ratio"] += t["pnl_pct"]
        pair_stats[pair]["profit_abs"] += t["pnl"]
        pair_stats[pair]["count"] += 1

    # Convert to list and add profit_pct
    performance = []
    for stats in pair_stats.values():
        performance.append({
            "pair": stats["pair"],
            "profit": stats["profit_ratio"],
            "profit_pct": stats["profit_ratio"] * 100.0,
            "profit_abs": stats["profit_abs"],
            "count": stats["count"],
        })

    # Sort by profit descending
    performance.sort(key=lambda x: x["profit"], reverse=True)

    return performance
