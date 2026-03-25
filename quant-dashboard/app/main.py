"""FastAPI application entry point.

Creates the FastAPI app, adds CORS middleware, and registers all API routers.
API routes are registered BEFORE the catch-all so specific endpoints take priority.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.backtest import router as backtest_router
from app.api.compat import router as compat_router
from app.api.pairs import router as pairs_router
from app.api.profit import router as profit_router
from app.api.strategy import router as strategy_router
from app.api.system import router as system_router
from app.api.trades import router as trades_router
from app.auth import router as auth_router
from src.data_layer.index_fetcher import IndexFetcher

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup: seed CSI 300 index data if cache is empty or stale
    logger.info("Starting application, seeding index data if needed...")
    try:
        fetcher = IndexFetcher()
        # Check if CSI 300 data exists
        df = fetcher.get_csi300()
        if df.empty:
            logger.info("CSI 300 cache is empty, fetching from AkShare...")
            count = fetcher.fetch_and_store(
                symbol="000300",
                period="daily",
                start_date="20251101",
                end_date="20260325",
            )
            logger.info(f"Seeded {count} CSI 300 data points")
        else:
            logger.info(f"CSI 300 cache already populated with {len(df)} rows")
    except Exception as e:
        logger.error(f"Failed to seed index data: {e}")
        # Don't fail startup if seeding fails - the app can still serve stock data

    yield

    # Shutdown: cleanup if needed
    logger.info("Shutting down application")


app = FastAPI(
    title="A-Share Quant Dashboard",
    description="FreqTrade-compatible API for Chan Theory backtesting on A-shares",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware — allow all origins for public access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers — ORDER MATTERS: specific routes before catch-all
app.include_router(auth_router)
app.include_router(system_router)
app.include_router(strategy_router)
app.include_router(backtest_router)
app.include_router(profit_router)
app.include_router(trades_router)
app.include_router(pairs_router)

# Catch-all MUST be last so it only matches truly unimplemented endpoints
app.include_router(compat_router)
