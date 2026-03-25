"""Pairs endpoints: whitelist, blacklist, available pairs, candles, plot config.

GET /api/v1/whitelist returns the list of tradeable stocks.
GET /api/v1/blacklist returns empty blacklist.
GET /api/v1/available_pairs returns all available pairs with timeframes.
GET /api/v1/pair_candles returns OHLCV data in FreqTrade format.
GET /api/v1/plot_config returns chart indicator configuration.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user
from src.data_layer.market_reader import MarketReader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["pairs"])

_reader = MarketReader()


def _date_to_ms_epoch(date_str: str) -> int:
    """Convert YYYY-MM-DD to millisecond epoch timestamp."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return 0


@router.get("/whitelist")
def get_whitelist(
    _user: Annotated[str, Depends(get_current_user)] = "",
) -> dict[str, Any]:
    """Get the whitelist of tradeable stock pairs.

    Returns:
        {
            "whitelist": [str, ...],
            "length": int,
            "method": ["StaticPairList"]
        }

    FreqUI calls this endpoint on every refresh cycle.
    """
    pairs = _reader.get_available_pairs()

    return {
        "whitelist": pairs,
        "length": len(pairs),
        "method": ["StaticPairList"],
    }


@router.get("/blacklist")
def get_blacklist(
    _user: Annotated[str, Depends(get_current_user)] = "",
) -> dict[str, Any]:
    """Get the blacklist of excluded pairs.

    In this system, there is no blacklist (all stocks are tradeable).
    Always returns an empty blacklist.

    FreqUI calls this endpoint on every refresh cycle.
    """
    return {
        "blacklist": [],
        "length": 0,
        "method": ["StaticPairList"],
    }


@router.get("/available_pairs")
def get_available_pairs(
    _user: Annotated[str, Depends(get_current_user)] = "",
) -> dict[str, Any]:
    """Get all available pairs with their timeframes and exchange info.

    Returns:
        {
            "length": int,
            "pairs": [str, ...],
            "pair_interval": [
                {
                    "pair": str,
                    "timeframe": str
                },
                ...
            ]
        }
    """
    pairs = _reader.get_available_pairs()

    # Build pair_interval list (all pairs have daily data)
    pair_interval = [{"pair": pair, "timeframe": "1d"} for pair in pairs]

    return {
        "length": len(pairs),
        "pairs": pairs,
        "pair_interval": pair_interval,
    }


@router.get("/pair_candles")
def get_pair_candles(
    pair: Annotated[str, Query()],
    timeframe: Annotated[str, Query()] = "1d",
    limit: Annotated[int, Query()] = 500,
    _user: Annotated[str, Depends(get_current_user)] = "",
) -> dict[str, Any]:
    """Get OHLCV candlestick data for a pair.

    Query parameters:
        pair: Stock symbol code (e.g., "000001")
        timeframe: Timeframe (default "1d")
        limit: Number of candles to return (default 500)

    Returns:
        {
            "pair": str,
            "timeframe": str,
            "columns": ["date", "open", "high", "low", "close", "volume"],
            "data": [
                [timestamp_ms, open, high, low, close, volume],
                ...
            ]
        }

    FreqTrade format uses a 2D array for OHLCV data with a separate columns header.
    """
    try:
        # Fetch K-line data from market.db
        df = _reader.get_stock_klines(pair, timeframe="DAY")

        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No data found for pair {pair}",
            )

        # Apply limit (take most recent N candles)
        if len(df) > limit:
            df = df.iloc[-limit:]

        # Convert to FreqTrade format: columns + 2D data array
        columns = ["date", "open", "high", "low", "close", "volume"]
        data = []

        for _, row in df.iterrows():
            timestamp_ms = _date_to_ms_epoch(row["date"])
            data.append([
                timestamp_ms,
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row["volume"]),
            ])

        return {
            "pair": pair,
            "timeframe": timeframe,
            "columns": columns,
            "data": data,
        }

    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market database not available",
        )
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except Exception as e:
        logger.error(f"Error fetching pair candles for {pair}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch candle data",
        )


@router.get("/plot_config")
def get_plot_config(
    strategy: Annotated[str, Query()] = "chan_theory",
    _user: Annotated[str, Depends(get_current_user)] = "",
) -> dict[str, Any]:
    """Get plot configuration for chart indicators.

    Query parameters:
        strategy: Strategy name (default "chan_theory")

    Returns chart configuration object that FreqUI uses to determine
    what indicators to overlay on candlestick charts.

    For Chan Theory, we display MACD indicator.
    """
    # Load strategy YAML for plot config
    strategy_file = Path(__file__).resolve().parent.parent.parent / "strategies" / "chan_theory.yaml"

    # Basic plot config for Chan Theory
    plot_config = {
        "chan_theory": {
            "main_plot": {},  # No main plot overlays (indicators go in subplots)
            "subplots": {
                "MACD": {
                    "dif": {"color": "blue", "type": "line"},
                    "dea": {"color": "orange", "type": "line"},
                    "macd": {"color": "red", "type": "bar"},
                }
            },
        }
    }

    return plot_config
