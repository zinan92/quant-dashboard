"""Backtest endpoints: start, poll, abort, reset, history.

Runs backtests in a background thread and exposes progress/results via API.
Results match FreqTrade's backtest schema so FreqUI can display them.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth import get_current_user
from src.backtest.engine import BacktestEngine, BacktestResult
from src.backtest.store import BacktestStore
from src.data_layer.market_reader import MarketReader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["backtest"])

# ---------------------------------------------------------------------------
# Global state for the current backtest (single-user model like FreqTrade)
# ---------------------------------------------------------------------------

_backtest_lock = threading.Lock()
_current_engine: BacktestEngine | None = None
_current_result: BacktestResult | None = None
_current_status: str = "not_started"  # "not_started" | "running" | "completed" | "error"
_current_error: str = ""
_current_filename: str = ""
_current_run_id: str = ""

# Shared instances
_store = BacktestStore()
_reader = MarketReader()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class BacktestRequest(BaseModel):
    """Request body for starting a backtest."""

    strategy: str = "chan_theory"
    timerange: str = ""
    dry_run_wallet: float = Field(default=1_000_000.0, alias="dry_run_wallet")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_timerange(timerange: str) -> tuple[str, str]:
    """Parse FreqTrade-style timerange string into (start_date, end_date).

    Supports formats:
    - ``"20251103-20260324"`` → ``("2025-11-03", "2026-03-24")``
    - ``""`` → defaults to recent 3 months
    """
    if not timerange or "-" not in timerange:
        # Default: recent data window
        return "2025-11-01", "2026-03-24"

    parts = timerange.split("-", 1)
    if len(parts) != 2 or len(parts[0]) != 8 or len(parts[1]) != 8:
        return "2025-11-01", "2026-03-24"

    start_raw, end_raw = parts
    start_date = f"{start_raw[:4]}-{start_raw[4:6]}-{start_raw[6:8]}"
    end_date = f"{end_raw[:4]}-{end_raw[4:6]}-{end_raw[6:8]}"
    return start_date, end_date


def _date_to_ms_epoch(date_str: str) -> int:
    """Convert ``YYYY-MM-DD`` to millisecond epoch timestamp."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return 0


def _build_freqtrade_result(result: BacktestResult, filename: str) -> dict[str, Any]:
    """Build the FreqTrade-compatible backtest_result object.

    Schema:
    ```json
    {
        "strategy": {
            "<strategy_name>": {
                "trades": [...],
                "profit_total": ...,
                "profit_total_abs": ...,
                "max_drawdown": ...,
                "sharpe": ...,
                "sortino": ...,
                "winrate": ...,
                "trade_count": ...,
                ...
            }
        },
        "metadata": {
            "<strategy_name>": {
                "run_id": ...,
                "filename": ...,
                "strategy": ...,
                "backtest_start_ts": ...,
                "backtest_end_ts": ...,
                "timeframe": "1d"
            }
        }
    }
    ```
    """
    strategy_name = result.strategy_name

    # Build trades array in FreqTrade format
    trades: list[dict[str, Any]] = []
    for t in result.trades:
        stake_amount = round(t.shares * t.entry_price, 2)
        trades.append({
            "trade_id": t.trade_id,
            "pair": t.symbol,
            "open_date": t.entry_date,
            "close_date": t.exit_date,
            "open_rate": t.entry_price,
            "close_rate": t.exit_price,
            "profit_abs": t.pnl,
            "profit_ratio": t.pnl_pct,
            "profit_pct": round(t.pnl_pct * 100, 4),
            "stake_amount": stake_amount,
            "amount": t.shares,
            "is_open": False,
            "exchange": "ashare",
            "strategy": strategy_name,
            "fee_open": 0.0003,
            "fee_close": 0.0013,  # commission + stamp tax
            "open_timestamp": _date_to_ms_epoch(t.entry_date),
            "close_timestamp": _date_to_ms_epoch(t.exit_date),
            "exit_reason": t.exit_reason,  # Required by FreqUI
            "sell_reason": t.exit_reason,  # Deprecated field, but some FreqUI versions may check it
            # Additional required fields for FreqUI TradeList.vue
            "leverage": 1.0,
            "is_short": False,
            "trading_mode": "spot",
            "orders": [],
            "max_stake_amount": None,
            "open_order_id": None,
            "has_open_orders": False,
            "enter_tag": None,
            "quote_currency": "CNY",
        })

    # Build exit_reason_summary (aggregate profit/loss by exit reason)
    exit_reason_stats: dict[str, dict[str, Any]] = {}
    for t in result.trades:
        reason = t.exit_reason
        if reason not in exit_reason_stats:
            exit_reason_stats[reason] = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "profit_mean": 0.0,
                "profit_mean_pct": 0.0,
                "profit_total_abs": 0.0,
                "profit_total": 0.0,
                "profit_total_pct": 0.0,
            }
        stats = exit_reason_stats[reason]
        stats["trades"] += 1
        stats["profit_total_abs"] += t.pnl
        stats["profit_total"] += t.pnl_pct
        if t.pnl > 0:
            stats["wins"] += 1
        elif t.pnl < 0:
            stats["losses"] += 1
        else:
            stats["draws"] += 1
    
    # Calculate means
    exit_reason_summary = []
    for reason, stats in exit_reason_stats.items():
        if stats["trades"] > 0:
            stats["profit_mean"] = stats["profit_total"] / stats["trades"]
            stats["profit_mean_pct"] = stats["profit_mean"] * 100
            stats["profit_total_pct"] = stats["profit_total"] * 100
            stats["winrate"] = stats["wins"] / stats["trades"] if stats["trades"] > 0 else 0.0
        exit_reason_summary.append(stats)

    # Build results_per_pair (aggregate statistics by symbol) - MUST be array, FreqUI calls .length on it
    pair_stats: dict[str, dict[str, Any]] = {}
    for t in result.trades:
        pair = t.symbol
        if pair not in pair_stats:
            pair_stats[pair] = {
                "key": pair,
                "trades": 0,
                "profit_mean": 0.0,
                "profit_total": 0.0,
                "profit_total_abs": 0.0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
            }
        stats = pair_stats[pair]
        stats["trades"] += 1
        stats["profit_total"] += t.pnl_pct
        stats["profit_total_abs"] += t.pnl
        if t.pnl > 0:
            stats["wins"] += 1
        elif t.pnl < 0:
            stats["losses"] += 1
        else:
            stats["draws"] += 1

    # Calculate means for each pair
    results_per_pair = []
    for pair, stats in pair_stats.items():
        if stats["trades"] > 0:
            stats["profit_mean"] = stats["profit_total"] / stats["trades"]
        results_per_pair.append(stats)

    # Sort by profit descending
    results_per_pair.sort(key=lambda x: x["profit_total_abs"], reverse=True)

    # Build pairlist - MUST be array, used by BacktestResultChart
    pairlist = list(pair_stats.keys())

    # Get metrics early so we can use it in all calculations
    metrics = result.metrics.copy()

    # Best and worst pairs
    if results_per_pair:
        best_pair = {"key": results_per_pair[0]["key"], "profit_total": results_per_pair[0]["profit_total"]}
        worst_pair = {"key": results_per_pair[-1]["key"], "profit_total": results_per_pair[-1]["profit_total"]}
    else:
        best_pair = {"key": "", "profit_total": 0.0}
        worst_pair = {"key": "", "profit_total": 0.0}

    # Strategy comparison - array with one entry (our strategy)
    total_wins = sum(1 for t in result.trades if t.pnl > 0)
    total_losses = sum(1 for t in result.trades if t.pnl < 0)
    total_draws = len(result.trades) - total_wins - total_losses
    total_profit = sum(t.pnl_pct for t in result.trades)
    total_profit_abs = sum(t.pnl for t in result.trades)
    avg_duration = sum((datetime.strptime(t.exit_date, "%Y-%m-%d") - datetime.strptime(t.entry_date, "%Y-%m-%d")).days 
                      for t in result.trades) / len(result.trades) if result.trades else 0.0

    strategy_comparison = [{
        "key": strategy_name,
        "trades": len(result.trades),
        "profit_mean": total_profit / len(result.trades) if result.trades else 0.0,
        "profit_total_abs": total_profit_abs,
        "profit_total_pct": total_profit * 100,
        "duration_avg": avg_duration,
        "wins": total_wins,
        "draws": total_draws,
        "losses": total_losses,
        "max_drawdown_account": metrics.get("max_drawdown", 0.0),
    }]

    # Calculate daily statistics
    # Group trades by date to calculate winning/losing days
    daily_pnl: dict[str, float] = {}
    for t in result.trades:
        exit_date = t.exit_date
        if exit_date not in daily_pnl:
            daily_pnl[exit_date] = 0.0
        daily_pnl[exit_date] += t.pnl

    winning_days = sum(1 for pnl in daily_pnl.values() if pnl > 0)
    losing_days = sum(1 for pnl in daily_pnl.values() if pnl < 0)
    draw_days = sum(1 for pnl in daily_pnl.values() if pnl == 0)

    # Best and worst days
    if daily_pnl:
        best_day_pnl = max(daily_pnl.values())
        worst_day_pnl = min(daily_pnl.values())
    else:
        best_day_pnl = 0.0
        worst_day_pnl = 0.0

    # Total days and trades per day
    total_days = metrics.get("total_days", 1)
    trades_per_day = len(result.trades) / total_days if total_days > 0 else 0.0

    # Build timerange in YYYYMMDD-YYYYMMDD format (required by FreqUI TimeRangeSelect.vue)
    timerange_start = result.start_date.replace("-", "")[:8]  # "2025-11-01" -> "20251101"
    timerange_end = result.end_date.replace("-", "")[:8]      # "2026-03-24" -> "20260324"
    timerange = f"{timerange_start}-{timerange_end}"

    # Build strategy metrics dict (metrics already defined earlier)
    
    # Calculate cumulative sum min/max from daily NAV data if available
    # For now, use approximations based on max drawdown
    final_balance = result.final_nav
    starting_balance = result.initial_capital
    max_dd = metrics.get("max_drawdown", 0.0)
    
    csum_max = final_balance - starting_balance
    csum_min = -(max_dd * starting_balance) if max_dd > 0 else 0.0
    
    # Drawdown timestamps - approximate using backtest period
    drawdown_start_ts = _date_to_ms_epoch(result.start_date)
    drawdown_end_ts = _date_to_ms_epoch(result.end_date)
    
    # Calculate average stake and total volume
    avg_stake_amount = sum(t.shares * t.entry_price for t in result.trades) / len(result.trades) if result.trades else 0.0
    total_volume = sum(t.shares * t.entry_price for t in result.trades)

    strategy_data: dict[str, Any] = {
        "trades": trades,
        "profit_total": metrics.get("profit_total", 0.0),
        "profit_total_abs": metrics.get("profit_total_abs", 0.0),
        "max_drawdown": metrics.get("max_drawdown", 0.0),
        "max_drawdown_abs": metrics.get("max_drawdown_abs", 0.0),
        "sharpe": metrics.get("sharpe", 0.0) or 0.0,  # Ensure not NaN/null
        "sortino": metrics.get("sortino", 0.0) or 0.0,
        "calmar": metrics.get("calmar", 0.0) or 0.0,
        "winrate": metrics.get("winrate", 0.0) or 0.0,
        "trade_count": metrics.get("trade_count", 0),
        "total_trades": metrics.get("trade_count", 0),  # Alias for trade_count
        "profit_factor": metrics.get("profit_factor", 0.0) or 0.0,
        "cagr": metrics.get("cagr", 0.0) or 0.0,
        "avg_trade_pnl": metrics.get("avg_trade_pnl", 0.0) or 0.0,
        "avg_trade_duration": metrics.get("avg_trade_duration", 0.0) or 0.0,
        "total_days": metrics.get("total_days", 0),
        "backtest_days": metrics.get("total_days", 0),  # Alias for total_days
        "backtest_start": result.start_date,
        "backtest_end": result.end_date,
        "backtest_start_ts": _date_to_ms_epoch(result.start_date),  # Required by FreqUI - must be integer
        "backtest_end_ts": _date_to_ms_epoch(result.end_date),      # Required by FreqUI - must be integer
        "timerange": timerange,  # Required by FreqUI TimeRangeSelect.vue (format: "20251101-20260324")
        "timeframe": "1d",  # Required by FreqUI
        "strategy_name": strategy_name,  # Required by FreqUI
        "stake_currency": "CNY",  # Required by FreqUI
        "stake_amount": 100000.0,  # Approximate position size
        "starting_balance": result.initial_capital,
        "final_balance": result.final_nav,
        "max_open_trades": 5,  # From Chan Theory rules
        "initial_capital": result.initial_capital,
        "final_nav": result.final_nav,
        "exit_reason_summary": exit_reason_summary,  # FreqUI needs this for performance metrics
        # New required fields for FreqUI BacktestResultAnalysis.vue
        "strategy_comparison": strategy_comparison,
        "results_per_pair": results_per_pair,  # MUST be array
        "results_per_enter_tag": [],  # Empty array, MUST exist
        "pairlist": pairlist,  # MUST be array
        "best_pair": best_pair,
        "worst_pair": worst_pair,
        "market_change": metrics.get("market_change", 0.0),
        "rejected_signals": 0,
        "timedout_entry_orders": 0,
        "timedout_exit_orders": 0,
        "canceled_trade_entries": 0,
        "backtest_best_day": best_day_pnl / starting_balance if starting_balance > 0 else 0.0,
        "backtest_worst_day": worst_day_pnl / starting_balance if starting_balance > 0 else 0.0,
        "backtest_best_day_abs": best_day_pnl,
        "backtest_worst_day_abs": worst_day_pnl,
        "winning_days": winning_days,
        "draw_days": draw_days,
        "losing_days": losing_days,
        "trades_per_day": trades_per_day,
        "csum_min": csum_min,
        "csum_max": csum_max,
        "drawdown_start_ts": drawdown_start_ts,
        "drawdown_end_ts": drawdown_end_ts,
        "max_drawdown_high": starting_balance,
        "max_drawdown_low": starting_balance * (1 - max_dd) if max_dd > 0 else starting_balance,
        "stoploss": -0.1,
        "trailing_stop": False,
        "minimal_roi": {"0": 0.1},
        "use_exit_signal": True,
        "enable_protections": False,
        "avg_stake_amount": avg_stake_amount,
        "total_volume": total_volume,
    }

    # Build metadata dict
    metadata: dict[str, Any] = {
        "run_id": str(result.run_id) if result.run_id else _current_run_id,
        "filename": filename,
        "strategy": strategy_name,
        "backtest_start_ts": _date_to_ms_epoch(result.start_date),
        "backtest_end_ts": _date_to_ms_epoch(result.end_date),
        "timeframe": "1d",
    }

    return {
        "strategy": {strategy_name: strategy_data},
        "metadata": {strategy_name: metadata},
    }


def _run_backtest_thread(
    strategy: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    filename: str,
) -> None:
    """Run a backtest in a background thread."""
    global _current_engine, _current_result, _current_status, _current_error

    try:
        symbols = _reader.get_available_pairs()

        engine = BacktestEngine(
            strategy=strategy,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            market_reader=_reader,
            store=_store,
        )

        with _backtest_lock:
            _current_engine = engine

        result = engine.run(persist=True)

        with _backtest_lock:
            _current_result = result
            _current_status = "completed"

    except Exception as exc:
        logger.exception("Backtest failed")
        with _backtest_lock:
            _current_status = "error"
            _current_error = str(exc)
    finally:
        with _backtest_lock:
            _current_engine = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/backtest")
def start_backtest(
    request: BacktestRequest,
    _user: Annotated[str, Depends(get_current_user)],
) -> dict:
    """Start a new backtest in a background thread.

    Returns ``{running: true, progress: 0, status: "running"}`` immediately.
    """
    global _current_status, _current_result, _current_error, _current_filename, _current_run_id

    with _backtest_lock:
        if _current_status == "running":
            return {
                "running": True,
                "progress": _current_engine.progress if _current_engine else 0.0,
                "status": "running",
                "status_msg": "Backtest already in progress",
            }

    start_date, end_date = _parse_timerange(request.timerange)

    # Generate a unique filename for this run
    run_id = uuid.uuid4().hex[:8]
    filename = f"backtest-result-{request.strategy}-{start_date}-{end_date}-{run_id}.json"

    with _backtest_lock:
        _current_status = "running"
        _current_result = None
        _current_error = ""
        _current_filename = filename
        _current_run_id = run_id

    thread = threading.Thread(
        target=_run_backtest_thread,
        args=(request.strategy, start_date, end_date, request.dry_run_wallet, filename),
        daemon=True,
    )
    thread.start()

    return {
        "running": True,
        "progress": 0.0,
        "status": "running",
        "status_msg": f"Backtest started: {request.strategy} ({start_date} to {end_date})",
    }


@router.get("/backtest")
def get_backtest_status(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict:
    """Return current backtest progress or completed results.

    While running: ``{running: true, progress: 0.0-1.0, status: "running"}``
    When complete: ``{running: false, status: "completed", backtest_result: {...}}``
    """
    with _backtest_lock:
        current_status = _current_status
        current_engine = _current_engine
        current_result = _current_result
        current_error = _current_error
        current_filename = _current_filename

    if current_status == "running":
        progress = current_engine.progress if current_engine else 0.0
        return {
            "running": True,
            "progress": round(progress, 4),
            "status": "running",
            "status_msg": f"Backtest in progress ({round(progress * 100, 1)}%)",
        }

    if current_status == "completed" and current_result is not None:
        backtest_result = _build_freqtrade_result(current_result, current_filename)
        return {
            "running": False,
            "progress": 1.0,
            "status": "completed",
            "status_msg": "Backtest completed",
            "backtest_result": backtest_result,
        }

    if current_status == "error":
        return {
            "running": False,
            "progress": 0.0,
            "status": "error",
            "status_msg": f"Backtest failed: {current_error}",
        }

    # Not started
    return {
        "running": False,
        "progress": 0.0,
        "status": "not_started",
        "status_msg": "No backtest running",
    }


@router.delete("/backtest")
def reset_backtest(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict:
    """Reset current backtest state."""
    global _current_status, _current_result, _current_error, _current_engine, _current_filename

    with _backtest_lock:
        _current_status = "not_started"
        _current_result = None
        _current_error = ""
        _current_engine = None
        _current_filename = ""

    return {"status": "reset"}


@router.get("/backtest/abort")
def abort_backtest(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict:
    """Abort a running backtest.

    Note: The current engine doesn't support graceful cancellation,
    so we just mark the status as reset. The background thread will
    complete but its results will be discarded.
    """
    global _current_status, _current_result, _current_error

    with _backtest_lock:
        was_running = _current_status == "running"
        _current_status = "not_started"
        _current_result = None
        _current_error = ""

    return {
        "status": "aborted" if was_running else "not_running",
    }


@router.get("/backtest/history")
def get_backtest_history(
    _user: Annotated[str, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """Return list of past backtest runs from backtest.db.

    Each entry includes: strategy, filename, backtest_start_ts, backtest_end_ts.
    """
    runs = _store.get_all_runs()
    history: list[dict[str, Any]] = []

    for run in runs:
        metrics = json.loads(run.get("metrics_json", "{}")) if isinstance(run.get("metrics_json"), str) else {}
        filename = f"backtest-result-{run['strategy']}-{run['start_date']}-{run['end_date']}-{run['id']}.json"
        history.append({
            "strategy": run["strategy"],
            "filename": filename,
            "run_id": str(run["id"]),
            "backtest_start": run["start_date"],
            "backtest_end": run["end_date"],
            "backtest_start_ts": _date_to_ms_epoch(run["start_date"]),
            "backtest_end_ts": _date_to_ms_epoch(run["end_date"]),
            "timeframe": "1d",
            "profit_total": metrics.get("profit_total", 0.0),
            "trade_count": metrics.get("trade_count", 0),
        })

    return history


@router.get("/backtest/history/result")
def get_backtest_history_result(
    filename: Annotated[str, Query(description="Backtest result filename")],
    _user: Annotated[str, Depends(get_current_user)],
) -> dict:
    """Load a specific past backtest result by filename.

    The filename encodes the run ID; we extract it and load from backtest.db.
    """
    # Try to extract run_id from filename
    # Format: backtest-result-{strategy}-{start}-{end}-{run_id}.json
    run_id = _extract_run_id_from_filename(filename)
    if run_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot parse filename: {filename}",
        )

    run = _store.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run not found: {filename}",
        )

    # Reconstruct the result
    metrics = json.loads(run["metrics_json"]) if isinstance(run.get("metrics_json"), str) else {}
    trades_data = _store.get_trades(run_id)

    strategy_name = run["strategy"]

    # Build trades in FreqTrade format
    trades: list[dict[str, Any]] = []
    for t in trades_data:
        stake_amount = round(t["shares"] * t["entry_price"], 2)
        trades.append({
            "trade_id": t["trade_id"],
            "pair": t["symbol"],
            "open_date": t["entry_date"],
            "close_date": t["exit_date"],
            "open_rate": t["entry_price"],
            "close_rate": t["exit_price"],
            "profit_abs": t["pnl"],
            "profit_ratio": t["pnl_pct"],
            "profit_pct": round(t["pnl_pct"] * 100, 4),
            "stake_amount": stake_amount,
            "amount": t["shares"],
            "is_open": False,
            "exchange": "ashare",
            "strategy": strategy_name,
            "fee_open": 0.0003,
            "fee_close": 0.0013,
            "open_timestamp": _date_to_ms_epoch(t["entry_date"]),
            "close_timestamp": _date_to_ms_epoch(t["exit_date"]),
            # Additional required fields
            "leverage": 1.0,
            "is_short": False,
            "trading_mode": "spot",
            "orders": [],
            "max_stake_amount": None,
            "open_order_id": None,
            "has_open_orders": False,
            "enter_tag": None,
            "quote_currency": "CNY",
        })

    # Build results_per_pair
    pair_stats: dict[str, dict[str, Any]] = {}
    for t in trades_data:
        pair = t["symbol"]
        if pair not in pair_stats:
            pair_stats[pair] = {
                "key": pair,
                "trades": 0,
                "profit_mean": 0.0,
                "profit_total": 0.0,
                "profit_total_abs": 0.0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
            }
        stats = pair_stats[pair]
        stats["trades"] += 1
        stats["profit_total"] += t["pnl_pct"]
        stats["profit_total_abs"] += t["pnl"]
        if t["pnl"] > 0:
            stats["wins"] += 1
        elif t["pnl"] < 0:
            stats["losses"] += 1
        else:
            stats["draws"] += 1

    results_per_pair = []
    for pair, stats in pair_stats.items():
        if stats["trades"] > 0:
            stats["profit_mean"] = stats["profit_total"] / stats["trades"]
        results_per_pair.append(stats)
    results_per_pair.sort(key=lambda x: x["profit_total_abs"], reverse=True)

    pairlist = list(pair_stats.keys())

    if results_per_pair:
        best_pair = {"key": results_per_pair[0]["key"], "profit_total": results_per_pair[0]["profit_total"]}
        worst_pair = {"key": results_per_pair[-1]["key"], "profit_total": results_per_pair[-1]["profit_total"]}
    else:
        best_pair = {"key": "", "profit_total": 0.0}
        worst_pair = {"key": "", "profit_total": 0.0}

    # Strategy comparison
    total_wins = sum(1 for t in trades_data if t["pnl"] > 0)
    total_losses = sum(1 for t in trades_data if t["pnl"] < 0)
    total_draws = len(trades_data) - total_wins - total_losses
    total_profit = sum(t["pnl_pct"] for t in trades_data)
    total_profit_abs = sum(t["pnl"] for t in trades_data)
    
    strategy_comparison = [{
        "key": strategy_name,
        "trades": len(trades_data),
        "profit_mean": total_profit / len(trades_data) if trades_data else 0.0,
        "profit_total_abs": total_profit_abs,
        "profit_total_pct": total_profit * 100,
        "duration_avg": 0.0,  # Could calculate from trades if needed
        "wins": total_wins,
        "draws": total_draws,
        "losses": total_losses,
        "max_drawdown_account": metrics.get("max_drawdown", 0.0),
    }]

    # Timerange
    timerange_start = run["start_date"].replace("-", "")[:8]
    timerange_end = run["end_date"].replace("-", "")[:8]
    timerange = f"{timerange_start}-{timerange_end}"

    # Additional stats
    starting_balance = run["initial_capital"]
    max_dd = metrics.get("max_drawdown", 0.0)
    
    strategy_data: dict[str, Any] = {
        "trades": trades,
        "profit_total": metrics.get("profit_total", 0.0),
        "profit_total_abs": metrics.get("profit_total_abs", 0.0),
        "max_drawdown": max_dd,
        "max_drawdown_abs": metrics.get("max_drawdown_abs", 0.0),
        "sharpe": metrics.get("sharpe", 0.0) or 0.0,
        "sortino": metrics.get("sortino", 0.0) or 0.0,
        "calmar": metrics.get("calmar", 0.0) or 0.0,
        "winrate": metrics.get("winrate", 0.0) or 0.0,
        "trade_count": metrics.get("trade_count", 0),
        "total_trades": metrics.get("trade_count", 0),
        "profit_factor": metrics.get("profit_factor", 0.0) or 0.0,
        "cagr": metrics.get("cagr", 0.0) or 0.0,
        "backtest_start": run["start_date"],
        "backtest_end": run["end_date"],
        "backtest_start_ts": _date_to_ms_epoch(run["start_date"]),
        "backtest_end_ts": _date_to_ms_epoch(run["end_date"]),
        "initial_capital": run["initial_capital"],
        "timerange": timerange,
        "timeframe": "1d",
        "strategy_name": strategy_name,
        "stake_currency": "CNY",
        "starting_balance": starting_balance,
        "max_open_trades": 5,
        # New required fields
        "strategy_comparison": strategy_comparison,
        "results_per_pair": results_per_pair,
        "results_per_enter_tag": [],
        "pairlist": pairlist,
        "best_pair": best_pair,
        "worst_pair": worst_pair,
        "market_change": metrics.get("market_change", 0.0),
        "rejected_signals": 0,
        "timedout_entry_orders": 0,
        "timedout_exit_orders": 0,
        "canceled_trade_entries": 0,
        "backtest_best_day": 0.0,
        "backtest_worst_day": 0.0,
        "backtest_best_day_abs": 0.0,
        "backtest_worst_day_abs": 0.0,
        "winning_days": 0,
        "draw_days": 0,
        "losing_days": 0,
        "trades_per_day": 0.0,
        "csum_min": 0.0,
        "csum_max": 0.0,
        "drawdown_start_ts": _date_to_ms_epoch(run["start_date"]),
        "drawdown_end_ts": _date_to_ms_epoch(run["end_date"]),
        "max_drawdown_high": starting_balance,
        "max_drawdown_low": starting_balance * (1 - max_dd) if max_dd > 0 else starting_balance,
        "stoploss": -0.1,
        "trailing_stop": False,
        "minimal_roi": {"0": 0.1},
        "use_exit_signal": True,
        "enable_protections": False,
        "avg_stake_amount": sum(t["shares"] * t["entry_price"] for t in trades_data) / len(trades_data) if trades_data else 0.0,
        "total_volume": sum(t["shares"] * t["entry_price"] for t in trades_data),
    }

    metadata: dict[str, Any] = {
        "run_id": str(run["id"]),
        "filename": filename,
        "strategy": strategy_name,
        "backtest_start_ts": _date_to_ms_epoch(run["start_date"]),
        "backtest_end_ts": _date_to_ms_epoch(run["end_date"]),
        "timeframe": "1d",
    }

    return {
        "strategy": {strategy_name: strategy_data},
        "metadata": {strategy_name: metadata},
    }


def _extract_run_id_from_filename(filename: str) -> int | None:
    """Extract the database run ID from a backtest filename.

    Filename format: ``backtest-result-{strategy}-{start}-{end}-{id}.json``
    where ``{id}`` can be an integer (from DB) or a hex string (from UUID).
    """
    # Remove .json extension
    name = filename.removesuffix(".json")
    parts = name.split("-")

    if len(parts) < 2:
        return None

    # The last part is the run_id
    last = parts[-1]
    try:
        return int(last)
    except ValueError:
        pass

    # If it's a hex UUID, we can't map it to a DB ID directly
    # Try looking up by matching the filename pattern in history
    runs = _store.get_all_runs()
    for run in runs:
        run_filename = f"backtest-result-{run['strategy']}-{run['start_date']}-{run['end_date']}-{run['id']}.json"
        if run_filename == filename:
            return int(run["id"])

    return None


@router.get("/backtest/history/{filename}/market_change")
def get_market_change(
    filename: str,
    _user: Annotated[str, Depends(get_current_user)],
) -> dict[str, Any]:
    """Get benchmark market performance for the same period as a backtest.

    Given a backtest filename, returns the market performance data for the
    same date range. Uses CSI 300 (000300.SH) as the primary benchmark index.

    Returns:
        {
            "columns": ["date", "market_change"],
            "data": [[timestamp_ms, pct_change], ...]
        }

    The pct_change values show the cumulative percentage change from the
    backtest start date (normalized to 0 at start).
    """
    from src.data_layer.index_fetcher import IndexFetcher

    # Extract run_id from filename
    run_id = _extract_run_id_from_filename(filename)
    if run_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cannot parse filename: {filename}",
        )

    # Load the backtest run to get date range
    run = _store.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest run not found: {filename}",
        )

    start_date = run["start_date"]
    end_date = run["end_date"]

    # Fetch CSI 300 index data for the same period
    index_fetcher = IndexFetcher()
    df = index_fetcher.get_csi300(start_date=start_date, end_date=end_date)

    if df.empty:
        # Return empty data if no benchmark data available
        return {
            "columns": ["date", "market_change"],
            "data": [],
        }

    # Calculate cumulative percentage change from start
    # market_change = (current_close - start_close) / start_close
    start_close = df.iloc[0]["close"]

    data = []
    for _, row in df.iterrows():
        timestamp_ms = _date_to_ms_epoch(row["date"])
        pct_change = (row["close"] - start_close) / start_close
        data.append([timestamp_ms, round(pct_change, 6)])

    return {
        "columns": ["date", "market_change"],
        "data": data,
    }
