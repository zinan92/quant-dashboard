"""System endpoints: ping, version, show_config."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import get_current_user

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/ping")
def ping() -> dict:
    """Health check endpoint — no auth required."""
    return {"status": "pong"}


@router.get("/version")
def version() -> dict:
    """Return API version — no auth required (FreqUI needs this before login)."""
    return {"version": "1.0.0"}


@router.get("/show_config")
def show_config(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict:
    """Return bot configuration in FreqTrade-compatible format."""
    return {
        "runmode": "webserver",
        "stake_currency": "CNY",
        "api_version": 2.34,
        "exchange": "ashare",
        "bot_name": "A-Share Quant Dashboard",
        "timeframe": "1d",
        "strategy": "chan_theory",
        "state": "running",
        "dry_run": True,
        "trading_mode": "spot",
        "timerange": "20251103-20260324",  # Default timerange for backtests
    }


@router.get("/sysinfo")
def sysinfo(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict:
    """Return system information (CPU, RAM usage)."""
    import psutil

    return {
        "cpu_pct": psutil.cpu_percent(interval=1),
        "ram_pct": psutil.virtual_memory().percent,
    }
