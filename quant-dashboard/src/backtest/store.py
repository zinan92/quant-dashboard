"""Persistence layer for backtest results.

Stores backtest runs, trades, and daily NAV in ``data/backtest.db``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.backtest.portfolio import Trade

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "backtest.db"


class BacktestStore:
    """SQLite-backed storage for backtest results.

    Tables:
        - ``backtest_runs``: run metadata and aggregate metrics
        - ``backtest_trades``: individual trades for each run
        - ``daily_nav``: daily NAV snapshots for each run
    """

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        conn = self._get_connection()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS backtest_runs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy        TEXT    NOT NULL,
                    start_date      TEXT    NOT NULL,
                    end_date        TEXT    NOT NULL,
                    initial_capital REAL    NOT NULL,
                    metrics_json    TEXT    NOT NULL DEFAULT '{}',
                    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS backtest_trades (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id    INTEGER NOT NULL,
                    run_id      INTEGER NOT NULL,
                    symbol      TEXT    NOT NULL,
                    entry_date  TEXT    NOT NULL,
                    exit_date   TEXT    NOT NULL,
                    entry_price REAL    NOT NULL,
                    exit_price  REAL    NOT NULL,
                    shares      INTEGER NOT NULL,
                    pnl         REAL    NOT NULL,
                    pnl_pct     REAL    NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES backtest_runs(id)
                );

                CREATE TABLE IF NOT EXISTS daily_nav (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id      INTEGER NOT NULL,
                    date        TEXT    NOT NULL,
                    nav         REAL    NOT NULL,
                    daily_return REAL   NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES backtest_runs(id),
                    UNIQUE(run_id, date)
                );

                CREATE INDEX IF NOT EXISTS ix_backtest_trades_run_id
                    ON backtest_trades(run_id);
                CREATE INDEX IF NOT EXISTS ix_daily_nav_run_id
                    ON daily_nav(run_id);
                """
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save_run(
        self,
        strategy: str,
        start_date: str,
        end_date: str,
        initial_capital: float,
        metrics: dict[str, Any],
        trades: list[Trade],
        nav_history: list[dict[str, Any]],
    ) -> int:
        """Save a complete backtest run to the database.

        Parameters
        ----------
        strategy : str
            Strategy name.
        start_date, end_date : str
            Date range (YYYY-MM-DD).
        initial_capital : float
            Starting capital.
        metrics : dict
            Performance metrics (serialized as JSON).
        trades : list[Trade]
            Completed trades.
        nav_history : list[dict]
            Daily NAV records.

        Returns
        -------
        int
            The newly created run ID.
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO backtest_runs (strategy, start_date, end_date, initial_capital, metrics_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (strategy, start_date, end_date, initial_capital, json.dumps(metrics)),
            )
            run_id = cursor.lastrowid
            assert run_id is not None

            # Insert trades
            for trade in trades:
                conn.execute(
                    """
                    INSERT INTO backtest_trades
                        (trade_id, run_id, symbol, entry_date, exit_date,
                         entry_price, exit_price, shares, pnl, pnl_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trade.trade_id,
                        run_id,
                        trade.symbol,
                        trade.entry_date,
                        trade.exit_date,
                        trade.entry_price,
                        trade.exit_price,
                        trade.shares,
                        trade.pnl,
                        trade.pnl_pct,
                    ),
                )

            # Insert daily NAV
            for entry in nav_history:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_nav (run_id, date, nav, daily_return)
                    VALUES (?, ?, ?, ?)
                    """,
                    (run_id, entry["date"], entry["nav"], entry["daily_return"]),
                )

            conn.commit()
        finally:
            conn.close()

        return run_id

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        """Retrieve a single backtest run by ID."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM backtest_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()

    def get_latest_run(self) -> dict[str, Any] | None:
        """Retrieve the most recent backtest run."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM backtest_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()

    def get_all_runs(self) -> list[dict[str, Any]]:
        """Retrieve all backtest runs."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM backtest_runs ORDER BY id DESC"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_trades(self, run_id: int) -> list[dict[str, Any]]:
        """Retrieve all trades for a backtest run."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM backtest_trades WHERE run_id = ? ORDER BY entry_date ASC",
                (run_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_daily_nav(self, run_id: int) -> list[dict[str, Any]]:
        """Retrieve daily NAV for a backtest run."""
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM daily_nav WHERE run_id = ? ORDER BY date ASC",
                (run_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
