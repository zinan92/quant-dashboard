"""Chan Theory strategy wrapper for backtesting.py framework.

Wraps the existing Chan Theory strategy (src.strategy.chan_theory) into
backtesting.py's Strategy class for interactive Bokeh visualization.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from backtesting import Backtest, Strategy

from src.adapters.backtesting_adapter import ashare_commission, prepare_backtesting_data
from src.strategy.base import SignalType
from src.strategy.chan_theory import ChanTheoryStrategy

if TYPE_CHECKING:
    from src.data_layer.market_reader import MarketReader


class ChanTheoryBTStrategy(Strategy):
    """Chan Theory strategy wrapper for backtesting.py.

    This strategy wraps the existing Chan Theory signal generator and translates
    signals into backtesting.py buy/sell actions with proper lot rounding.

    Class Variables
    ----------------
    original_df : pd.DataFrame
        The original lowercase DataFrame with MACD indicators, passed as a class
        variable before running the backtest.
    signal_lookup : dict[str, Signal]
        Lookup table mapping date strings to Signal objects for fast access.
    """

    # Class variables to be set before backtest run
    original_df: pd.DataFrame = pd.DataFrame()
    signal_lookup: dict = {}

    def init(self):
        """Initialize the strategy.

        Runs Chan Theory signal generation on the original lowercase DataFrame
        and builds a date → Signal lookup table for fast access in next().
        """
        # Generate signals using the original Chan Theory strategy
        chan_strategy = ChanTheoryStrategy()
        signals = chan_strategy.generate_signals(self.original_df)

        # Build lookup table: date_str → Signal
        self.signal_lookup = {signal.date: signal for signal in signals}

    def next(self):
        """Process the next bar.

        Checks if there's a signal for the current bar's date:
        - BUY_1/2/3: Execute buy with lot-rounded size
        - SELL_1/2/3: Close the position
        - Other signals: No action
        """
        # Get current bar's date as string (YYYY-MM-DD)
        current_date = str(self.data.index[-1].date())

        # Check if there's a signal for this date
        signal = self.signal_lookup.get(current_date)
        if signal is None:
            return

        # Handle buy signals
        if signal.signal_type in (SignalType.BUY_1, SignalType.BUY_2, SignalType.BUY_3):
            # Only buy if we don't have a position
            if not self.position:
                current_price = self.data.Close[-1]
                if current_price > 0:
                    # Calculate lot-rounded size: floor(equity * 0.95 / price / 100) * 100
                    equity = self.equity
                    raw_size = (equity * 0.95) / current_price
                    lot_rounded_size = int(raw_size / 100) * 100

                    if lot_rounded_size >= 100:
                        self.buy(size=lot_rounded_size)

        # Handle sell signals
        elif signal.signal_type in (SignalType.SELL_1, SignalType.SELL_2, SignalType.SELL_3):
            # Close position if we have one
            if self.position:
                self.position.close()


def run_single_stock_backtest(
    symbol: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    reader: MarketReader,
) -> tuple[dict, str]:
    """Run a single-stock backtest using backtesting.py with Chan Theory strategy.

    Parameters
    ----------
    symbol : str
        Stock symbol code (e.g., "000001").
    start_date : str
        Start date in YYYY-MM-DD format.
    end_date : str
        End date in YYYY-MM-DD format.
    initial_capital : float
        Initial capital in yuan.
    reader : MarketReader
        MarketReader instance to fetch data from.

    Returns
    -------
    tuple[dict, str]
        A tuple of (stats_dict, plot_html_string):
        - stats_dict: Dictionary containing backtest statistics like 'Return [%]',
          '# Trades', 'Sharpe Ratio', etc.
        - plot_html_string: HTML string containing the interactive Bokeh chart.

    Raises
    ------
    ValueError
        If the symbol has no data or the backtest fails.
    """
    # Fetch data in both formats
    # 1. Original lowercase format for Chan Theory signal generation
    original_df = reader.get_stock_klines(
        symbol_code=symbol,
        timeframe="DAY",
        start_date=start_date,
        end_date=end_date,
    )

    if original_df.empty:
        raise ValueError(f"No data available for symbol {symbol}")

    # 2. Title-case format with DatetimeIndex for backtesting.py
    bt_data = prepare_backtesting_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        reader=reader,
    )

    if bt_data.empty:
        raise ValueError(f"No data available for symbol {symbol}")

    # Set class variables for the strategy to access
    ChanTheoryBTStrategy.original_df = original_df
    ChanTheoryBTStrategy.signal_lookup = {}

    # Create and run backtest
    bt = Backtest(
        bt_data,
        ChanTheoryBTStrategy,
        cash=initial_capital,
        commission=ashare_commission,
        trade_on_close=True,
        exclusive_orders=True,
    )

    # Run the backtest
    stats = bt.run()

    # Convert stats to dictionary
    stats_dict = stats.to_dict() if hasattr(stats, "to_dict") else dict(stats)

    # Generate HTML plot
    # bt.plot() writes to a temporary file and returns a Bokeh figure
    # We need to capture the HTML output
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Generate the plot and save to temp file
        bt.plot(filename=str(tmp_path), open_browser=False)

        # Read the HTML content
        plot_html = tmp_path.read_text(encoding="utf-8")
    finally:
        # Clean up the temp file
        if tmp_path.exists():
            tmp_path.unlink()

    return stats_dict, plot_html
