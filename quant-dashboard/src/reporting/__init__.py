"""Portfolio reporting with QuantStats tearsheets."""

from src.reporting.tearsheet import (
    extract_daily_returns,
    generate_portfolio_tearsheet,
    get_benchmark_returns,
)

__all__ = [
    "extract_daily_returns",
    "generate_portfolio_tearsheet",
    "get_benchmark_returns",
]
