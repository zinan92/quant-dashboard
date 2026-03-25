"""Tests for pairs API endpoints: whitelist, blacklist, available_pairs, pair_candles, plot_config."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from src.data_layer.index_fetcher import IndexFetcher


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def seed_csi300_data() -> None:
    """Seed CSI 300 data once at the start of the test session.

    This fixture runs before any tests and ensures the index_cache.db
    has CSI 300 data available for testing.
    """
    fetcher = IndexFetcher()
    df = fetcher.get_csi300()
    if df.empty:
        try:
            # Fetch real data from AkShare (this will be cached for all tests)
            fetcher.fetch_and_store(
                symbol="000300",
                period="daily",
                start_date="20251101",
                end_date="20260325",
            )
        except Exception as e:
            # If AkShare fails (network issues, rate limiting), skip seeding
            # The CSI 300 test will be handled separately
            pytest.skip(f"Failed to seed CSI 300 data from AkShare: {e}")


@pytest.fixture
def auth_token(client: TestClient) -> str:
    """Login and return an access token for authenticated requests."""
    response = client.post(
        "/api/v1/token/login",
        auth=("admin", "admin"),
    )
    assert response.status_code == 200
    return response.json()["access_token"]


class TestWhitelist:
    """Test /whitelist endpoint."""

    def test_whitelist_returns_200(self, client: TestClient, auth_token: str) -> None:
        """Whitelist endpoint returns 200."""
        response = client.get(
            "/api/v1/whitelist",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    def test_whitelist_has_required_fields(self, client: TestClient, auth_token: str) -> None:
        """Whitelist response has required fields."""
        response = client.get(
            "/api/v1/whitelist",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert "whitelist" in data
        assert "length" in data
        assert "method" in data

    def test_whitelist_is_list_of_strings(self, client: TestClient, auth_token: str) -> None:
        """Whitelist is a list of stock symbols."""
        response = client.get(
            "/api/v1/whitelist",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert isinstance(data["whitelist"], list)
        assert len(data["whitelist"]) > 0
        # Check all entries are strings
        for pair in data["whitelist"]:
            assert isinstance(pair, str)

    def test_whitelist_length_matches_array_length(self, client: TestClient, auth_token: str) -> None:
        """Length field matches actual array length."""
        response = client.get(
            "/api/v1/whitelist",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert data["length"] == len(data["whitelist"])

    def test_whitelist_method_is_static_pairlist(self, client: TestClient, auth_token: str) -> None:
        """Method is StaticPairList."""
        response = client.get(
            "/api/v1/whitelist",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert data["method"] == ["StaticPairList"]

    def test_whitelist_includes_known_stock(self, client: TestClient, auth_token: str) -> None:
        """Whitelist includes known stock 000001."""
        response = client.get(
            "/api/v1/whitelist",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert "000001" in data["whitelist"]

    def test_whitelist_requires_auth(self, client: TestClient) -> None:
        """Whitelist endpoint requires authentication."""
        response = client.get("/api/v1/whitelist")
        assert response.status_code == 401


class TestBlacklist:
    """Test /blacklist endpoint."""

    def test_blacklist_returns_200(self, client: TestClient, auth_token: str) -> None:
        """Blacklist endpoint returns 200."""
        response = client.get(
            "/api/v1/blacklist",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    def test_blacklist_is_empty(self, client: TestClient, auth_token: str) -> None:
        """Blacklist is empty (no stocks are blacklisted)."""
        response = client.get(
            "/api/v1/blacklist",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert data["blacklist"] == []
        assert data["length"] == 0

    def test_blacklist_has_method_field(self, client: TestClient, auth_token: str) -> None:
        """Blacklist has method field."""
        response = client.get(
            "/api/v1/blacklist",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert "method" in data

    def test_blacklist_requires_auth(self, client: TestClient) -> None:
        """Blacklist endpoint requires authentication."""
        response = client.get("/api/v1/blacklist")
        assert response.status_code == 401


class TestAvailablePairs:
    """Test /available_pairs endpoint."""

    def test_available_pairs_returns_200(self, client: TestClient, auth_token: str) -> None:
        """Available pairs endpoint returns 200."""
        response = client.get(
            "/api/v1/available_pairs",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    def test_available_pairs_has_required_fields(self, client: TestClient, auth_token: str) -> None:
        """Available pairs response has required fields."""
        response = client.get(
            "/api/v1/available_pairs",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert "length" in data
        assert "pairs" in data
        assert "pair_interval" in data

    def test_available_pairs_pair_interval_format(self, client: TestClient, auth_token: str) -> None:
        """Pair interval is a list of {pair, timeframe} objects."""
        response = client.get(
            "/api/v1/available_pairs",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert isinstance(data["pair_interval"], list)
        assert len(data["pair_interval"]) > 0

        # Check first entry has correct format
        entry = data["pair_interval"][0]
        assert "pair" in entry
        assert "timeframe" in entry
        assert entry["timeframe"] == "1d"

    def test_available_pairs_length_matches(self, client: TestClient, auth_token: str) -> None:
        """Length field matches array lengths."""
        response = client.get(
            "/api/v1/available_pairs",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert data["length"] == len(data["pairs"])
        assert data["length"] == len(data["pair_interval"])

    def test_available_pairs_requires_auth(self, client: TestClient) -> None:
        """Available pairs endpoint requires authentication."""
        response = client.get("/api/v1/available_pairs")
        assert response.status_code == 401


class TestPairCandles:
    """Test /pair_candles endpoint."""

    def test_pair_candles_returns_200(self, client: TestClient, auth_token: str) -> None:
        """Pair candles endpoint returns 200 for valid pair."""
        response = client.get(
            "/api/v1/pair_candles?pair=000001&timeframe=1d",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    def test_pair_candles_has_required_fields(self, client: TestClient, auth_token: str) -> None:
        """Pair candles response has required fields."""
        response = client.get(
            "/api/v1/pair_candles?pair=000001&timeframe=1d",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert "pair" in data
        assert "timeframe" in data
        assert "columns" in data
        assert "data" in data

    def test_pair_candles_columns_format(self, client: TestClient, auth_token: str) -> None:
        """Columns is an array of OHLCV field names."""
        response = client.get(
            "/api/v1/pair_candles?pair=000001&timeframe=1d",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert data["columns"] == ["date", "open", "high", "low", "close", "volume"]

    def test_pair_candles_data_is_2d_array(self, client: TestClient, auth_token: str) -> None:
        """Data is a 2D array of OHLCV values."""
        response = client.get(
            "/api/v1/pair_candles?pair=000001&timeframe=1d",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0

        # Check first candle has correct format
        candle = data["data"][0]
        assert isinstance(candle, list)
        assert len(candle) == 6  # [timestamp, o, h, l, c, v]
        # Timestamp should be millisecond epoch
        assert candle[0] > 1_000_000_000_000

    def test_pair_candles_respects_limit(self, client: TestClient, auth_token: str) -> None:
        """Limit parameter restricts number of candles returned."""
        response = client.get(
            "/api/v1/pair_candles?pair=000001&timeframe=1d&limit=10",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert len(data["data"]) <= 10

    def test_pair_candles_nonexistent_pair_returns_404(self, client: TestClient, auth_token: str) -> None:
        """Nonexistent pair returns 404."""
        response = client.get(
            "/api/v1/pair_candles?pair=999999&timeframe=1d",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 404

    def test_pair_candles_requires_auth(self, client: TestClient) -> None:
        """Pair candles endpoint requires authentication."""
        response = client.get("/api/v1/pair_candles?pair=000001")
        assert response.status_code == 401


class TestPlotConfig:
    """Test /plot_config endpoint."""

    def test_plot_config_returns_200(self, client: TestClient, auth_token: str) -> None:
        """Plot config endpoint returns 200."""
        response = client.get(
            "/api/v1/plot_config",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    def test_plot_config_is_dict(self, client: TestClient, auth_token: str) -> None:
        """Plot config is a dictionary."""
        response = client.get(
            "/api/v1/plot_config",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert isinstance(data, dict)

    def test_plot_config_has_chan_theory_config(self, client: TestClient, auth_token: str) -> None:
        """Plot config includes chan_theory strategy configuration."""
        response = client.get(
            "/api/v1/plot_config?strategy=chan_theory",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert "chan_theory" in data

    def test_plot_config_has_macd_subplot(self, client: TestClient, auth_token: str) -> None:
        """Plot config includes MACD subplot for chan_theory."""
        response = client.get(
            "/api/v1/plot_config?strategy=chan_theory",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        assert "chan_theory" in data
        assert "subplots" in data["chan_theory"]
        assert "MACD" in data["chan_theory"]["subplots"]

    def test_plot_config_requires_auth(self, client: TestClient) -> None:
        """Plot config endpoint requires authentication."""
        response = client.get("/api/v1/plot_config")
        assert response.status_code == 401


class TestIndexDataAccess:
    """Test that pair_candles endpoint serves INDEX data."""

    def test_pair_candles_serves_chinext_index(self, client: TestClient, auth_token: str) -> None:
        """Pair candles returns ChiNext (399006.SZ) index data from market.db."""
        response = client.get(
            "/api/v1/pair_candles?pair=399006.SZ&timeframe=1d",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["pair"] == "399006.SZ"
        assert len(data["data"]) > 0

    def test_pair_candles_serves_csi300_index(self, client: TestClient, auth_token: str) -> None:
        """Pair candles returns CSI 300 (000300.SH) index data from index_cache.db.

        This test verifies that:
        1. The IndexFetcher seeding on startup works
        2. pair_candles correctly queries index_cache.db for CSI 300
        3. At least 60 data points are available (VAL-DATA-002 requirement)
        """
        response = client.get(
            "/api/v1/pair_candles?pair=000300.SH&timeframe=1d",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["pair"] == "000300.SH"
        assert len(data["data"]) >= 60, "CSI 300 data should have at least 60 data points"

    def test_pair_candles_index_data_format(self, client: TestClient, auth_token: str) -> None:
        """INDEX data follows the same format as STOCK data."""
        response = client.get(
            "/api/v1/pair_candles?pair=399006.SZ&timeframe=1d",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        data = response.json()

        # Same columns as STOCK data
        assert data["columns"] == ["date", "open", "high", "low", "close", "volume"]

        # Data is 2D array with 6 elements per candle
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0
        candle = data["data"][0]
        assert len(candle) == 6
