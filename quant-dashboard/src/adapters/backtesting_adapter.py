"""Data adapter and commission model for backtesting.py integration with A-share data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.data_layer.market_reader import MarketReader


def prepare_backtesting_data(
    symbol: str,
    start_date: str,
    end_date: str,
    reader: MarketReader,
) -> pd.DataFrame:
    """Prepare market data for backtesting.py format.

    Converts MarketReader output (lowercase columns, string date) to
    backtesting.py format (title-case OHLCV columns, DatetimeIndex).

    Parameters
    ----------
    symbol : str
        Stock symbol code (e.g., "000001").
    start_date : str
        Start date in YYYY-MM-DD format.
    end_date : str
        End date in YYYY-MM-DD format.
    reader : MarketReader
        MarketReader instance to fetch data from.

    Returns
    -------
    pd.DataFrame
        DataFrame with DatetimeIndex and title-case columns:
        Open, High, Low, Close, Volume, Dif, Dea, Macd.
        The 'amount' column is dropped.
    """
    # Fetch data from MarketReader
    df = reader.get_stock_klines(
        symbol_code=symbol,
        timeframe="DAY",
        start_date=start_date,
        end_date=end_date,
    )

    # Return empty DataFrame with correct schema if no data
    if df.empty:
        empty_df = pd.DataFrame(
            columns=["Open", "High", "Low", "Close", "Volume", "Dif", "Dea", "Macd"]
        )
        empty_df.index = pd.DatetimeIndex([], name="date")
        return empty_df

    # Rename columns to title-case
    df = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "dif": "Dif",
            "dea": "Dea",
            "macd": "Macd",
        }
    )

    # Drop the 'amount' column if it exists
    if "amount" in df.columns:
        df = df.drop(columns=["amount"])

    # Convert date column to DatetimeIndex
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    return df


def ashare_commission(size: float, price: float, is_buy: bool | None = None) -> float:
    """Calculate A-share commission for a trade.

    A-share commission model:
    - Buy: max(5.0, abs(size) * price * 0.0003)
    - Sell: max(5.0, abs(size) * price * 0.0003) + abs(size) * price * 0.001

    The sell includes 0.1% stamp tax on top of the base commission.

    Parameters
    ----------
    size : float
        Trade size in shares. When called by backtesting.py's 2-arg callback:
        positive for buy, negative for sell. The is_buy parameter will be inferred
        from the sign if not provided.
    price : float
        Trade price per share.
    is_buy : bool | None, optional
        True for buy trades, False for sell trades. If None, inferred from size:
        is_buy = (size > 0). Defaults to None.

    Returns
    -------
    float
        Total commission in currency units.
    """
    # Infer is_buy from sign of size if not provided
    if is_buy is None:
        is_buy = size > 0

    # Base commission: 0.03% with minimum 5 yuan
    base_commission = max(5.0, abs(size) * price * 0.0003)

    if is_buy:
        return base_commission
    else:
        # Sell includes stamp tax: 0.1%
        stamp_tax = abs(size) * price * 0.001
        return base_commission + stamp_tax
