"""Fetch supplementary index data (e.g. CSI 300) via AkShare and cache locally."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DEFAULT_CACHE_DB = Path(__file__).resolve().parent.parent.parent / "data" / "index_cache.db"


class IndexFetcher:
    """Fetches index data from AkShare and stores it in a local SQLite cache.

    The primary use case is supplementing ashare's ``market.db`` with indices
    not present there (e.g. CSI 300 / 沪深300).
    """

    def __init__(self, cache_db_path: Path | str = DEFAULT_CACHE_DB) -> None:
        self._cache_db = Path(cache_db_path)
        self._cache_db.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._cache_db))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._get_connection()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS index_klines (
                    symbol      TEXT    NOT NULL,
                    date        TEXT    NOT NULL,
                    open        REAL    NOT NULL,
                    high        REAL    NOT NULL,
                    low         REAL    NOT NULL,
                    close       REAL    NOT NULL,
                    volume      REAL    NOT NULL,
                    amount      REAL,
                    UNIQUE(symbol, date)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_index_klines_symbol ON index_klines (symbol)"
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Fetch from AkShare
    # ------------------------------------------------------------------

    def fetch_and_store(
        self,
        symbol: str = "000300",
        period: str = "daily",
        start_date: str = "20251101",
        end_date: str = "20260325",
    ) -> int:
        """Fetch index data from AkShare and upsert into the local cache.

        Parameters
        ----------
        symbol : str
            AkShare index symbol, e.g. ``"000300"`` for CSI 300.
        period : str
            Data period, typically ``"daily"``.
        start_date, end_date : str
            Date range in ``YYYYMMDD`` format.

        Returns
        -------
        int
            Number of rows inserted/updated.
        """
        import akshare as ak  # noqa: PLC0415 — lazy import for test mocking

        df = ak.index_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        if df is None or df.empty:
            return 0

        # AkShare returns columns in Chinese; map to English
        column_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }
        df = df.rename(columns=column_map)

        # Keep only the columns we need
        keep_cols = ["date", "open", "high", "low", "close", "volume", "amount"]
        available = [c for c in keep_cols if c in df.columns]
        df = df[available].copy()

        # Ensure date is a string in YYYY-MM-DD format
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df["symbol"] = symbol

        # Fill missing amount with 0
        if "amount" not in df.columns:
            df["amount"] = 0.0

        conn = self._get_connection()
        try:
            for _, row in df.iterrows():
                conn.execute(
                    """
                    INSERT INTO index_klines (symbol, date, open, high, low, close, volume, amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, date) DO UPDATE SET
                        open=excluded.open, high=excluded.high, low=excluded.low,
                        close=excluded.close, volume=excluded.volume, amount=excluded.amount
                    """,
                    (
                        row["symbol"],
                        row["date"],
                        float(row["open"]),
                        float(row["high"]),
                        float(row["low"]),
                        float(row["close"]),
                        float(row["volume"]),
                        float(row.get("amount", 0)),
                    ),
                )
            conn.commit()
            count = len(df)
        finally:
            conn.close()

        return count

    # ------------------------------------------------------------------
    # Read from local cache
    # ------------------------------------------------------------------

    def get_csi300(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return cached CSI 300 daily data.

        Parameters
        ----------
        start_date, end_date : str, optional
            Date strings in ``YYYY-MM-DD`` format.

        Returns
        -------
        pd.DataFrame
            Columns: ``date, open, high, low, close, volume, amount``.
        """
        return self.get_index_data("000300", start_date=start_date, end_date=end_date)

    def get_index_data(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return cached index data for the given symbol.

        Parameters
        ----------
        symbol : str
            The index symbol as stored in cache (e.g. ``"000300"``).
        start_date, end_date : str, optional
            Date strings in ``YYYY-MM-DD`` format.

        Returns
        -------
        pd.DataFrame
            Columns: ``date, open, high, low, close, volume, amount``.
        """
        query = (
            "SELECT date, open, high, low, close, volume, amount "
            "FROM index_klines WHERE symbol = ?"
        )
        params: list[str] = [symbol]

        if start_date is not None:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date ASC"

        conn = self._get_connection()
        try:
            df = pd.read_sql_query(query, conn, params=params)
        finally:
            conn.close()

        return df
