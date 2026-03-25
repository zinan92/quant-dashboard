"""JWT authentication for the FreqTrade-compatible API."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials, HTTPBearer

# Configuration from environment (defaults match FreqTrade convention)
API_USERNAME = os.environ.get("API_USERNAME", "admin")
API_PASSWORD = os.environ.get("API_PASSWORD", "admin")
JWT_SECRET = os.environ.get("JWT_SECRET", "quant-dashboard-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30

router = APIRouter(prefix="/api/v1", tags=["auth"])

basic_security = HTTPBasic()
bearer_security = HTTPBearer()


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    """Create a JWT token with the given subject and expiry."""
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_access_token(username: str) -> str:
    """Create an access token for the given username."""
    return _create_token(username, "access", timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(username: str) -> str:
    """Create a refresh token for the given username."""
    return _create_token(username, "refresh", timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


def verify_token(token: str, expected_type: str = "access") -> dict:
    """Verify and decode a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token type, expected {expected_type}",
        )

    return payload


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_security)],
) -> str:
    """FastAPI dependency: extract and validate the current user from Bearer token."""
    payload = verify_token(credentials.credentials, expected_type="access")
    username: str | None = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return username


@router.post("/token/login")
def login(
    credentials: Annotated[HTTPBasicCredentials, Depends(basic_security)],
) -> dict:
    """Authenticate with HTTP Basic Auth, returns JWT access and refresh tokens."""
    if credentials.username != API_USERNAME or credentials.password != API_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    access_token = create_access_token(credentials.username)
    refresh_token = create_refresh_token(credentials.username)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


@router.post("/token/refresh")
def refresh_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_security)],
) -> dict:
    """Refresh an access token using a valid refresh token."""
    payload = verify_token(credentials.credentials, expected_type="refresh")
    username: str | None = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    new_access_token = create_access_token(username)
    return {
        "access_token": new_access_token,
    }
