"""FastAPI application entry point.

Creates the FastAPI app, adds CORS middleware, and registers all API routers.
API routes are registered BEFORE the catch-all so specific endpoints take priority.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

# Static files and SPA routing
# CRITICAL: Mount static files AFTER API routes so /api/v1/* takes precedence
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    # Serve benchmark comparison page BEFORE static mounts
    # Use /benchmark-comparison to avoid conflict with FreqUI's client-side /benchmark route
    # Serve from committed source (frontend/benchmark.html) not gitignored build artifact
    benchmark_html_path = Path(__file__).parent.parent / "frontend" / "benchmark.html"
    
    @app.get("/benchmark-comparison")
    async def benchmark_comparison():
        """Serve benchmark comparison page."""
        return FileResponse(benchmark_html_path)

    # Mount static assets (JS, CSS, images, etc.)
    app.mount(
        "/assets",
        StaticFiles(directory=str(frontend_dist / "assets")),
        name="static-assets",
    )

    # Serve favicon and other root-level static files
    @app.get("/favicon.ico")
    async def favicon():
        """Serve favicon from frontend dist."""
        return FileResponse(frontend_dist / "favicon.ico")

    # SPA fallback: serve index.html for all non-API, non-static routes
    # This must be LAST so API routes take precedence
    @app.get("/{full_path:path}")
    async def spa_fallback(request: Request, full_path: str):
        """Serve index.html for SPA deep links.

        All routes NOT matching:
        - /api/v1/* (API routes)
        - /assets/* (static assets)
        - Static file extensions (.js, .css, .png, .ico, .svg, .woff, .woff2, .json)

        Return index.html to enable client-side routing.
        """
        # If path looks like a static file, try to serve it
        if "." in full_path.split("/")[-1]:
            file_path = frontend_dist / full_path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)

        # Otherwise, serve index.html for SPA routing
        return FileResponse(frontend_dist / "index.html")
else:
    logger.warning(f"Frontend dist directory not found at {frontend_dist}")
    logger.warning("Static file serving and SPA routing disabled")
