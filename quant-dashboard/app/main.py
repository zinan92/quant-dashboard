"""FastAPI application entry point.

Creates the FastAPI app, adds CORS middleware, and registers all API routers.
API routes are registered BEFORE the catch-all so specific endpoints take priority.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.backtest import router as backtest_router
from app.api.compat import router as compat_router
from app.api.strategy import router as strategy_router
from app.api.system import router as system_router
from app.auth import router as auth_router

app = FastAPI(
    title="A-Share Quant Dashboard",
    description="FreqTrade-compatible API for Chan Theory backtesting on A-shares",
    version="1.0.0",
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

# Catch-all MUST be last so it only matches truly unimplemented endpoints
app.include_router(compat_router)
