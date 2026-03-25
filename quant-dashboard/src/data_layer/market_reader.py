"""Read-only access to ashare's market.db for stock and index K-line data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DEFAULT_DB_PATH = Path("/Users/wendy/work/trading-co/ashare/data/market.db")


class MarketReader:
    """Provides read-only access to the ashare market.db SQLite database.

    Supports querying stock K-lines, index K-lines, available stock symbols,
    and the trade calendar. All connections are opened in read-only mode
    (using the ``file:`` URI with ``?mode=ro``).
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)
        if not self._db_path.exists():
            raise FileNotFoundError(f"market.db not found at {self._db_path}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        """Open a read-only connection using the ``file:`` URI scheme."""
        uri = f"file:{self._db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Stock K-lines
    # ------------------------------------------------------------------

    def get_stock_klines(
        self,
        symbol_code: str,
        timeframe: str = "DAY",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return OHLCV data for a single stock.

        Parameters
        ----------
        symbol_code : str
            The stock code, e.g. ``"000001"``.
        timeframe : str
            One of ``"DAY"``, ``"MINS_30"``, ``"MINS_5"``.
        start_date, end_date : str, optional
            Date strings in ``YYYY-MM-DD`` format for filtering.

        Returns
        -------
        pd.DataFrame
            Columns: ``date, open, high, low, close, volume, amount,
            dif, dea, macd``.
        """
        query = (
            "SELECT trade_time AS date, open, high, low, close, volume, amount, "
            "dif, dea, macd "
            "FROM klines "
            "WHERE symbol_type = 'STOCK' AND symbol_code = ? AND timeframe = ?"
        )
        params: list[str] = [symbol_code, timeframe]

        if start_date is not None:
            query += " AND trade_time >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND trade_time <= ?"
            params.append(end_date)

        query += " ORDER BY trade_time ASC"

        conn = self._get_connection()
        try:
            df = pd.read_sql_query(query, conn, params=params)
        finally:
            conn.close()

        return df

    # ------------------------------------------------------------------
    # Index K-lines
    # ------------------------------------------------------------------

    def get_index_klines(
        self,
        symbol_code: str,
        timeframe: str = "DAY",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """Return OHLCV data for a market index.

        Parameters
        ----------
        symbol_code : str
            The index code, e.g. ``"399006.SZ"`` (创业板指).
        timeframe : str
            Typically ``"DAY"``.
        start_date, end_date : str, optional
            Date strings in ``YYYY-MM-DD`` format for filtering.

        Returns
        -------
        pd.DataFrame
            Columns: ``date, open, high, low, close, volume, amount,
            dif, dea, macd``.
        """
        query = (
            "SELECT trade_time AS date, open, high, low, close, volume, amount, "
            "dif, dea, macd "
            "FROM klines "
            "WHERE symbol_type = 'INDEX' AND symbol_code = ? AND timeframe = ?"
        )
        params: list[str] = [symbol_code, timeframe]

        if start_date is not None:
            query += " AND trade_time >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND trade_time <= ?"
            params.append(end_date)

        query += " ORDER BY trade_time ASC"

        conn = self._get_connection()
        try:
            df = pd.read_sql_query(query, conn, params=params)
        finally:
            conn.close()

        return df

    # ------------------------------------------------------------------
    # Stock list / available pairs
    # ------------------------------------------------------------------

    def get_available_pairs(self) -> list[str]:
        """Return a sorted list of distinct stock symbol codes in the database.

        Only includes symbols with daily K-line data (``timeframe='DAY'``).
        """
        query = (
            "SELECT DISTINCT symbol_code FROM klines "
            "WHERE symbol_type = 'STOCK' AND timeframe = 'DAY' "
            "ORDER BY symbol_code ASC"
        )
        conn = self._get_connection()
        try:
            cursor = conn.execute(query)
            pairs = [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

        return pairs

    # ------------------------------------------------------------------
    # Index list
    # ------------------------------------------------------------------

    def get_available_indices(self) -> list[dict[str, str]]:
        """Return a list of available indices with code and name."""
        query = (
            "SELECT DISTINCT symbol_code, symbol_name FROM klines "
            "WHERE symbol_type = 'INDEX' "
            "ORDER BY symbol_code ASC"
        )
        conn = self._get_connection()
        try:
            cursor = conn.execute(query)
            indices = [{"code": row[0], "name": row[1]} for row in cursor.fetchall()]
        finally:
            conn.close()

        return indices

    # ------------------------------------------------------------------
    # Trade calendar
    # ------------------------------------------------------------------

    def get_trade_calendar(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        trading_only: bool = True,
    ) -> list[str]:
        """Return a list of trade dates.

        Parameters
        ----------
        start_date, end_date : str, optional
            Date strings in ``YYYY-MM-DD`` format.
        trading_only : bool
            If ``True``, only return trading days.

        Returns
        -------
        list[str]
            Sorted list of date strings.
        """
        query = "SELECT date FROM trade_calendar WHERE 1=1"
        params: list[str | int] = []

        if trading_only:
            query += " AND is_trading_day = ?"
            params.append(1)
        if start_date is not None:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date ASC"

        conn = self._get_connection()
        try:
            cursor = conn.execute(query, params)
            dates = [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

        return dates

    # ------------------------------------------------------------------
    # Stock basic info
    # ------------------------------------------------------------------

    def get_stock_basic(self, symbol: str | None = None) -> pd.DataFrame:
        """Return basic stock information from the ``stock_basic`` table.

        Parameters
        ----------
        symbol : str, optional
            If provided, filter for this single stock symbol.

        Returns
        -------
        pd.DataFrame
            Columns from the ``stock_basic`` table.
        """
        query = "SELECT * FROM stock_basic"
        params: list[str] = []

        if symbol is not None:
            query += " WHERE symbol = ?"
            params.append(symbol)

        query += " ORDER BY symbol ASC"

        conn = self._get_connection()
        try:
            df = pd.read_sql_query(query, conn, params=params)
        finally:
            conn.close()

        return df
