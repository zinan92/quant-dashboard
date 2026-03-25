"""Strategy endpoints: list and detail for registered strategies."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_user
from src.strategy.base import get_strategy, list_strategies

router = APIRouter(prefix="/api/v1", tags=["strategy"])


@router.get("/strategies")
def get_strategies(
    _user: Annotated[str, Depends(get_current_user)],
) -> dict:
    """Return a list of all available strategy names.

    Response matches FreqTrade schema: ``{"strategies": ["chan_theory", ...]}``
    """
    return {"strategies": list_strategies()}


@router.get("/strategy/{name}")
def get_strategy_detail(
    name: str,
    _user: Annotated[str, Depends(get_current_user)],
) -> dict:
    """Return detailed information about a specific strategy.

    Response matches FreqTrade schema:
    ``{"strategy": name, "timeframe": "1d", "code": "<yaml>", "params": [...]}``
    """
    try:
        strategy = get_strategy(name)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy '{name}' not found",
        )

    # Get YAML code if available (Chan Theory has a YAML file)
    code = ""
    if hasattr(strategy, "get_yaml_content"):
        code = strategy.get_yaml_content()

    return {
        "strategy": strategy.name,
        "timeframe": strategy.timeframe,
        "code": code,
        "params": strategy.get_params(),
    }
