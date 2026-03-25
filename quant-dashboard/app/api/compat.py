"""Catch-all handler for unimplemented API endpoints.

CRITICAL: Any unmatched /api/v1/* path must return 404 JSON, NEVER 500.
FreqUI treats HTTP 500 as "bot offline" and breaks the entire UI.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["compat"])


@router.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    include_in_schema=False,
)
async def catch_all(_request: Request, path: str) -> JSONResponse:
    """Return 404 JSON for any unimplemented /api/v1/* endpoint."""
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found"},
    )
