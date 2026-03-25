"""Tests for the data layer: MarketReader and IndexFetcher."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data_layer.index_fetcher import IndexFetcher
from src.data_layer.market_reader import MarketReader

# ---------------------------------------------------------------------------
# MarketReader — reads from real ashare market.db (read-only)
# ---------------------------------------------------------------------------

MARKET_DB = Path("/Users/wendy/work/trading-co/ashare/data/market.db")


@pytest.fixture()
def reader() -> MarketReader:
    """Create a MarketReader pointing at the real market.db."""
    return MarketReader(db_path=MARKET_DB)


class TestMarketReaderStockKlines:
    """Test stock K-line queries."""

    def test_get_stock_klines_000001_returns_dataframe(self, reader: MarketReader) -> None:
        """Query stock 000001 daily klines returns a non-empty DataFrame with OHLCV columns."""
        df = reader.get_stock_klines("000001", "DAY")
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0, "Expected non-empty DataFrame for stock 000001"
        for col in ("date", "open", "high", "low", "close", "volume"):
            assert col in df.columns, f"Missing column: {col}"

    def test_get_stock_klines_000001_ohlcv_values(self, reader: MarketReader) -> None:
        """OHLCV values are numeric and sensible for stock 000001."""
        df = reader.get_stock_klines("000001", "DAY")
        assert df["open"].dtype in ("float64", "int64")
        assert df["close"].dtype in ("float64", "int64")
        assert (df["high"] >= df["low"]).all(), "high must be >= low"
        assert (df["volume"] >= 0).all(), "volume must be non-negative"

    def test_get_stock_klines_date_filtering(self, reader: MarketReader) -> None:
        """Date range filtering narrows results."""
        df_all = reader.get_stock_klines("000001", "DAY")
        df_filtered = reader.get_stock_klines(
            "000001", "DAY", start_date="2025-12-01", end_date="2025-12-31"
        )
        assert len(df_filtered) <= len(df_all)
        if not df_filtered.empty:
            assert df_filtered["date"].min() >= "2025-12-01"
            assert df_filtered["date"].max() <= "2025-12-31"

    def test_get_stock_klines_nonexistent_returns_empty(self, reader: MarketReader) -> None:
        """Querying a non-existent stock code returns an empty DataFrame."""
        df = reader.get_stock_klines("XXXXXX", "DAY")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0


class TestMarketReaderIndexKlines:
    """Test index K-line queries."""

    def test_get_index_klines_chinext(self, reader: MarketReader) -> None:
        """Query ChiNext (创业板指 399006.SZ) returns non-empty data with OHLCV."""
        df = reader.get_index_klines("399006.SZ", "DAY")
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0, "Expected non-empty DataFrame for ChiNext index"
        for col in ("date", "open", "high", "low", "close", "volume"):
            assert col in df.columns, f"Missing column: {col}"

    def test_get_index_klines_shanghai_composite(self, reader: MarketReader) -> None:
        """Query Shanghai Composite (上证指数 000001.SH) returns data."""
        df = reader.get_index_klines("000001.SH", "DAY")
        assert len(df) > 0

    def test_get_index_klines_nonexistent_returns_empty(self, reader: MarketReader) -> None:
        """Non-existent index returns empty DataFrame."""
        df = reader.get_index_klines("999999.XX", "DAY")
        assert len(df) == 0


class TestMarketReaderAvailablePairs:
    """Test available pairs listing."""

    def test_get_available_pairs_returns_list(self, reader: MarketReader) -> None:
        """get_available_pairs returns a list of strings."""
        pairs = reader.get_available_pairs()
        assert isinstance(pairs, list)
        assert all(isinstance(p, str) for p in pairs)

    def test_get_available_pairs_count(self, reader: MarketReader) -> None:
        """There should be 400+ stock symbols available."""
        pairs = reader.get_available_pairs()
        assert len(pairs) >= 400, f"Expected 400+ pairs, got {len(pairs)}"

    def test_get_available_pairs_includes_000001(self, reader: MarketReader) -> None:
        """Stock 000001 (平安银行) should be in the list."""
        pairs = reader.get_available_pairs()
        assert "000001" in pairs

    def test_get_available_pairs_sorted(self, reader: MarketReader) -> None:
        """Pairs should be returned in sorted order."""
        pairs = reader.get_available_pairs()
        assert pairs == sorted(pairs)


class TestMarketReaderTradeCalendar:
    """Test trade calendar queries."""

    def test_get_trade_calendar_returns_dates(self, reader: MarketReader) -> None:
        """get_trade_calendar returns a list of date strings."""
        dates = reader.get_trade_calendar()
        assert isinstance(dates, list)
        assert len(dates) > 0

    def test_get_trade_calendar_filtering(self, reader: MarketReader) -> None:
        """Date filtering works."""
        dates = reader.get_trade_calendar(
            start_date="2026-01-01", end_date="2026-01-31"
        )
        for d in dates:
            assert d >= "2026-01-01"
            assert d <= "2026-01-31"


class TestMarketReaderAvailableIndices:
    """Test index listing."""

    def test_get_available_indices(self, reader: MarketReader) -> None:
        """Should return at least 5 indices."""
        indices = reader.get_available_indices()
        assert len(indices) >= 5
        codes = [idx["code"] for idx in indices]
        assert "399006.SZ" in codes, "ChiNext should be available"


class TestMarketReaderErrors:
    """Test error handling."""

    def test_missing_db_raises_error(self) -> None:
        """Opening a non-existent DB path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            MarketReader(db_path="/nonexistent/path/market.db")


class TestMarketReaderReadOnly:
    """Verify market.db access is truly read-only."""

    def test_connection_is_readonly(self, reader: MarketReader) -> None:
        """Attempting to write via the connection should fail."""
        conn = reader._get_connection()
        try:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("CREATE TABLE test_write (id INTEGER)")
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# IndexFetcher — fetch CSI 300 via AkShare and cache locally
# ---------------------------------------------------------------------------


@pytest.fixture()
def fetcher(tmp_path: Path) -> IndexFetcher:
    """Create an IndexFetcher with a temp cache DB."""
    cache_db = tmp_path / "index_cache.db"
    return IndexFetcher(cache_db_path=cache_db)


def _make_mock_csi300_df() -> pd.DataFrame:
    """Create a mock AkShare response for CSI 300."""
    dates = pd.date_range("2025-11-03", periods=90, freq="B")
    return pd.DataFrame(
        {
            "日期": dates,
            "开盘": [3800.0 + i * 2 for i in range(90)],
            "收盘": [3810.0 + i * 2 for i in range(90)],
            "最高": [3820.0 + i * 2 for i in range(90)],
            "最低": [3790.0 + i * 2 for i in range(90)],
            "成交量": [1000000 + i * 1000 for i in range(90)],
            "成交额": [50000000.0 + i * 10000 for i in range(90)],
        }
    )


class TestIndexFetcher:
    """Test IndexFetcher with mocked AkShare calls."""

    def test_fetch_and_store_csi300_mock(self, fetcher: IndexFetcher) -> None:
        """fetch_and_store inserts mocked CSI 300 data into the cache."""
        mock_df = _make_mock_csi300_df()

        with patch("akshare.index_zh_a_hist", return_value=mock_df) as mock_ak:
            count = fetcher.fetch_and_store(symbol="000300", period="daily")
            mock_ak.assert_called_once()
            assert count == 90

    def test_get_csi300_after_fetch(self, fetcher: IndexFetcher) -> None:
        """get_csi300 returns stored data after a fetch."""
        mock_df = _make_mock_csi300_df()

        with patch("akshare.index_zh_a_hist", return_value=mock_df):
            fetcher.fetch_and_store(symbol="000300", period="daily")

        df = fetcher.get_csi300()
        assert isinstance(df, pd.DataFrame)
        assert len(df) >= 60, f"Expected at least 60 rows, got {len(df)}"
        for col in ("date", "open", "high", "low", "close", "volume"):
            assert col in df.columns

    def test_get_csi300_date_filtering(self, fetcher: IndexFetcher) -> None:
        """Date filtering works on cached CSI 300 data."""
        mock_df = _make_mock_csi300_df()

        with patch("akshare.index_zh_a_hist", return_value=mock_df):
            fetcher.fetch_and_store(symbol="000300", period="daily")

        df = fetcher.get_csi300(start_date="2025-12-01", end_date="2025-12-31")
        if not df.empty:
            assert df["date"].min() >= "2025-12-01"
            assert df["date"].max() <= "2025-12-31"

    def test_get_csi300_empty_before_fetch(self, fetcher: IndexFetcher) -> None:
        """get_csi300 returns empty DataFrame before any fetch."""
        df = fetcher.get_csi300()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_fetch_empty_response(self, fetcher: IndexFetcher) -> None:
        """fetch_and_store handles empty AkShare response gracefully."""
        with patch("akshare.index_zh_a_hist", return_value=pd.DataFrame()):
            count = fetcher.fetch_and_store(symbol="000300", period="daily")
            assert count == 0

    def test_upsert_does_not_duplicate(self, fetcher: IndexFetcher) -> None:
        """Fetching twice should upsert, not duplicate rows."""
        mock_df = _make_mock_csi300_df()

        with patch("akshare.index_zh_a_hist", return_value=mock_df):
            fetcher.fetch_and_store(symbol="000300", period="daily")
            fetcher.fetch_and_store(symbol="000300", period="daily")

        df = fetcher.get_csi300()
        assert len(df) == 90, "Upsert should not create duplicate rows"

    def test_schema_created_on_init(self, tmp_path: Path) -> None:
        """IndexFetcher creates the schema on initialization."""
        cache_db = tmp_path / "new_cache.db"
        fetcher = IndexFetcher(cache_db_path=cache_db)
        assert cache_db.exists()

        conn = sqlite3.connect(str(cache_db))
        try:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            assert "index_klines" in table_names
        finally:
            conn.close()
