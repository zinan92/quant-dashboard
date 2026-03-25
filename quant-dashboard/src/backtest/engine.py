"""Core backtest engine.

Takes a strategy, stock universe, date range, and initial capital.
Iterates daily: generates signals across all stocks, executes simulated trades,
updates portfolio, and records results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.backtest.metrics import calculate_metrics
from src.backtest.portfolio import PortfolioManager, Trade
from src.backtest.store import BacktestStore
from src.data_layer.market_reader import MarketReader
from src.strategy.base import Signal, SignalType, Strategy, get_strategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Container for backtest results.

    Attributes
    ----------
    run_id : int or None
        Database run ID (set after persistence).
    strategy_name : str
        Name of the strategy used.
    start_date : str
        Backtest start date.
    end_date : str
        Backtest end date.
    initial_capital : float
        Starting capital.
    final_nav : float
        Final portfolio NAV.
    metrics : dict[str, Any]
        Performance metrics dictionary.
    trades : list[Trade]
        Completed trades.
    nav_history : list[dict[str, Any]]
        Daily NAV records.
    """

    run_id: int | None = None
    strategy_name: str = ""
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 0.0
    final_nav: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    nav_history: list[dict[str, Any]] = field(default_factory=list)


# Buy signal types
_BUY_SIGNALS = {SignalType.BUY_1, SignalType.BUY_2, SignalType.BUY_3}
# Sell signal types
_SELL_SIGNALS = {SignalType.SELL_1, SignalType.SELL_2, SignalType.SELL_3}


class BacktestEngine:
    """Backtest engine that iterates daily over a stock universe.

    Parameters
    ----------
    strategy : Strategy or str
        The trading strategy (instance or name to look up).
    symbols : list[str]
        Stock symbol codes to backtest across.
    start_date : str
        Start date in YYYY-MM-DD format.
    end_date : str
        End date in YYYY-MM-DD format.
    initial_capital : float
        Starting capital in CNY (default 1,000,000).
    market_reader : MarketReader or None
        Data reader for K-line data. Uses default if None.
    store : BacktestStore or None
        Result store. Uses default if None.
    """

    def __init__(
        self,
        strategy: Strategy | str,
        symbols: list[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 1_000_000.0,
        market_reader: MarketReader | None = None,
        store: BacktestStore | None = None,
    ) -> None:
        if isinstance(strategy, str):
            self._strategy = get_strategy(strategy)
        else:
            self._strategy = strategy

        self._symbols = symbols
        self._start_date = start_date
        self._end_date = end_date
        self._initial_capital = initial_capital
        self._reader = market_reader or MarketReader()
        self._store = store or BacktestStore()

        # Progress tracking (0.0 to 1.0)
        self.progress: float = 0.0
        self._running: bool = False

    @property
    def running(self) -> bool:
        """Whether the backtest is currently running."""
        return self._running

    def run(self, persist: bool = True) -> BacktestResult:
        """Execute the backtest.

        Parameters
        ----------
        persist : bool
            Whether to save results to the database (default True).

        Returns
        -------
        BacktestResult
            Complete backtest results including metrics and trades.
        """
        self._running = True
        self.progress = 0.0

        try:
            result = self._execute_backtest()

            if persist:
                run_id = self._store.save_run(
                    strategy=result.strategy_name,
                    start_date=result.start_date,
                    end_date=result.end_date,
                    initial_capital=result.initial_capital,
                    metrics=result.metrics,
                    trades=result.trades,
                    nav_history=result.nav_history,
                )
                result.run_id = run_id

            return result
        finally:
            self._running = False
            self.progress = 1.0

    def _execute_backtest(self) -> BacktestResult:
        """Internal backtest execution logic."""
        portfolio = PortfolioManager(self._initial_capital)

        # ---------------------------------------------------------------
        # 1. Pre-load all K-line data and generate signals per symbol
        # ---------------------------------------------------------------
        symbol_data: dict[str, pd.DataFrame] = {}
        symbol_signals: dict[str, list[Signal]] = {}

        total_symbols = len(self._symbols)
        for idx, symbol in enumerate(self._symbols):
            df = self._reader.get_stock_klines(
                symbol, "DAY", start_date=self._start_date, end_date=self._end_date
            )
            if df.empty or len(df) < 10:
                continue

            symbol_data[symbol] = df.reset_index(drop=True)

            # Generate signals
            try:
                signals = self._strategy.generate_signals(df)
                if signals:
                    symbol_signals[symbol] = signals
            except Exception:
                logger.warning("Signal generation failed for %s", symbol, exc_info=True)

            # Update progress (signal generation is ~50% of work)
            self.progress = 0.5 * (idx + 1) / total_symbols

        # ---------------------------------------------------------------
        # 2. Build a global trade calendar from available data
        # ---------------------------------------------------------------
        all_dates: set[str] = set()
        for df in symbol_data.values():
            all_dates.update(df["date"].tolist())
        trade_dates = sorted(all_dates)

        if not trade_dates:
            return BacktestResult(
                strategy_name=self._strategy.name,
                start_date=self._start_date,
                end_date=self._end_date,
                initial_capital=self._initial_capital,
                final_nav=self._initial_capital,
                metrics=calculate_metrics([], [], self._initial_capital),
            )

        # Build per-symbol date-to-signal lookup
        signal_lookup: dict[str, dict[str, Signal]] = {}
        for symbol, signals in symbol_signals.items():
            signal_lookup[symbol] = {s.date: s for s in signals}

        # Build per-symbol date-to-price lookup (close price)
        price_lookup: dict[str, dict[str, float]] = {}
        for symbol, df in symbol_data.items():
            price_lookup[symbol] = dict(zip(df["date"].tolist(), df["close"].astype(float).tolist()))

        # ---------------------------------------------------------------
        # 3. Iterate daily
        # ---------------------------------------------------------------
        total_dates = len(trade_dates)

        for day_idx, date in enumerate(trade_dates):
            # Current prices for all held symbols
            current_prices: dict[str, float] = {}
            for symbol in list(portfolio.positions.keys()):
                if symbol in price_lookup and date in price_lookup[symbol]:
                    current_prices[symbol] = price_lookup[symbol][date]
                else:
                    # Use last known price if no data for today
                    current_prices[symbol] = portfolio.positions[symbol].cost_price

            # Also gather prices for all symbols that have data today
            for symbol in symbol_data:
                if symbol in price_lookup and date in price_lookup[symbol]:
                    current_prices[symbol] = price_lookup[symbol][date]

            nav = portfolio.get_nav(current_prices)

            # --- Check sell signals first (free up capital) ---
            for symbol in list(portfolio.positions.keys()):
                if symbol in signal_lookup and date in signal_lookup[symbol]:
                    signal = signal_lookup[symbol][date]
                    if signal.signal_type in _SELL_SIGNALS:
                        price = current_prices.get(symbol)
                        if price is not None:
                            portfolio.sell(symbol, price, date)

            # --- Check buy signals ---
            for symbol in symbol_data:
                if symbol in signal_lookup and date in signal_lookup[symbol]:
                    signal = signal_lookup[symbol][date]
                    if signal.signal_type in _BUY_SIGNALS:
                        price = current_prices.get(symbol)
                        if price is not None and portfolio.can_buy(symbol):
                            portfolio.buy(symbol, price, date, nav=nav)

            # --- Record daily NAV ---
            portfolio.record_daily_nav(date, current_prices)

            # Update progress (daily iteration is the other ~50%)
            self.progress = 0.5 + 0.5 * (day_idx + 1) / total_dates

        # ---------------------------------------------------------------
        # 4. Force-close remaining positions at the end
        # ---------------------------------------------------------------
        last_date = trade_dates[-1]
        for symbol in list(portfolio.positions.keys()):
            price = None
            if symbol in price_lookup and last_date in price_lookup[symbol]:
                price = price_lookup[symbol][last_date]
            if price is None:
                price = portfolio.positions[symbol].cost_price
            portfolio.sell(symbol, price, last_date)

        # ---------------------------------------------------------------
        # 5. Calculate metrics
        # ---------------------------------------------------------------
        metrics = calculate_metrics(
            nav_history=portfolio.nav_history,
            closed_trades=portfolio.closed_trades,
            initial_capital=self._initial_capital,
        )

        final_nav = portfolio.nav_history[-1]["nav"] if portfolio.nav_history else self._initial_capital

        return BacktestResult(
            strategy_name=self._strategy.name,
            start_date=self._start_date,
            end_date=self._end_date,
            initial_capital=self._initial_capital,
            final_nav=final_nav,
            metrics=metrics,
            trades=portfolio.closed_trades,
            nav_history=portfolio.nav_history,
        )
