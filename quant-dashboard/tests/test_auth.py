"""Tests for JWT authentication endpoints."""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.auth import JWT_ALGORITHM, JWT_SECRET
from app.main import app

client = TestClient(app)


class TestLoginSuccess:
    """POST /api/v1/token/login with valid credentials."""

    def test_login_returns_200(self) -> None:
        resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
        assert resp.status_code == 200

    def test_login_returns_access_token(self) -> None:
        resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
        data = resp.json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    def test_login_returns_refresh_token(self) -> None:
        resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
        data = resp.json()
        assert "refresh_token" in data
        assert isinstance(data["refresh_token"], str)
        assert len(data["refresh_token"]) > 0

    def test_access_token_is_valid_jwt(self) -> None:
        resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
        token = resp.json()["access_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == "admin"
        assert payload["type"] == "access"

    def test_refresh_token_is_valid_jwt(self) -> None:
        resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
        token = resp.json()["refresh_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert payload["sub"] == "admin"
        assert payload["type"] == "refresh"

    def test_access_token_expires_in_15_minutes(self) -> None:
        resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
        token = resp.json()["access_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        exp = payload["exp"]
        iat = payload["iat"]
        # Allow 2 seconds of clock drift
        assert abs((exp - iat) - 15 * 60) <= 2

    def test_refresh_token_expires_in_30_days(self) -> None:
        resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
        token = resp.json()["refresh_token"]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        exp = payload["exp"]
        iat = payload["iat"]
        # Allow 2 seconds of clock drift
        assert abs((exp - iat) - 30 * 24 * 60 * 60) <= 2


class TestLoginFailure:
    """POST /api/v1/token/login with invalid credentials."""

    def test_wrong_password_returns_401(self) -> None:
        resp = client.post("/api/v1/token/login", auth=("admin", "wrong"))
        assert resp.status_code == 401

    def test_wrong_username_returns_401(self) -> None:
        resp = client.post("/api/v1/token/login", auth=("wronguser", "admin"))
        assert resp.status_code == 401

    def test_no_credentials_returns_401(self) -> None:
        resp = client.post("/api/v1/token/login")
        assert resp.status_code == 401

    def test_wrong_creds_returns_json_detail(self) -> None:
        resp = client.post("/api/v1/token/login", auth=("admin", "wrong"))
        data = resp.json()
        assert "detail" in data


class TestTokenRefresh:
    """POST /api/v1/token/refresh with a valid refresh token."""

    def _get_tokens(self) -> dict:
        resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
        return resp.json()

    def test_refresh_returns_200(self) -> None:
        tokens = self._get_tokens()
        resp = client.post(
            "/api/v1/token/refresh",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        )
        assert resp.status_code == 200

    def test_refresh_returns_new_access_token(self) -> None:
        tokens = self._get_tokens()
        resp = client.post(
            "/api/v1/token/refresh",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        )
        data = resp.json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0

    def test_refresh_with_access_token_fails(self) -> None:
        """Using an access token for refresh should fail."""
        tokens = self._get_tokens()
        resp = client.post(
            "/api/v1/token/refresh",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 401

    def test_refresh_with_invalid_token_fails(self) -> None:
        resp = client.post(
            "/api/v1/token/refresh",
            headers={"Authorization": "Bearer invalid-token-string"},
        )
        assert resp.status_code == 401

    def test_refresh_without_bearer_fails(self) -> None:
        resp = client.post("/api/v1/token/refresh")
        # FastAPI's HTTPBearer returns 403 when no credentials are provided
        assert resp.status_code in (401, 403)

    def test_refreshed_access_token_works(self) -> None:
        """New access token from refresh should work on protected endpoints."""
        tokens = self._get_tokens()
        resp = client.post(
            "/api/v1/token/refresh",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        )
        new_access = resp.json()["access_token"]
        # Use new token on a protected endpoint
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {new_access}"},
        )
        assert resp.status_code == 200

    def test_expired_refresh_token_fails(self) -> None:
        """Expired refresh token should be rejected."""
        # Create an expired token manually
        payload = {
            "sub": "admin",
            "type": "refresh",
            "iat": time.time() - 7200,
            "exp": time.time() - 3600,  # expired 1 hour ago
        }
        expired_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        resp = client.post(
            "/api/v1/token/refresh",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401


class TestUnauthorizedAccess:
    """Protected endpoints should return 401 without auth."""

    def test_show_config_without_auth_returns_401_or_403(self) -> None:
        resp = client.get("/api/v1/show_config")
        assert resp.status_code in (401, 403)

    def test_show_config_with_invalid_token_returns_401(self) -> None:
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401

    def test_show_config_with_valid_token_returns_200(self) -> None:
        login_resp = client.post("/api/v1/token/login", auth=("admin", "admin"))
        token = login_resp.json()["access_token"]
        resp = client.get(
            "/api/v1/show_config",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
