"""Portfolio management for backtest simulation.

Tracks positions, cash balance, daily NAV, and simulated trade execution
with the A-share commission model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Commission model constants (A-share)
# ---------------------------------------------------------------------------

COMMISSION_RATE = 0.0003   # 0.03% per trade
COMMISSION_MIN = 5.0       # Minimum ¥5 per trade
STAMP_TAX_RATE = 0.001     # 0.1% stamp tax on sell only

# Position sizing per Chan Theory rules (日线级别)
MAX_POSITION_PCT_LOW = 0.30   # 30% of portfolio per position (minimum)
MAX_POSITION_PCT_HIGH = 0.50  # 50% of portfolio per position (maximum)
MAX_CONCURRENT_POSITIONS = 5


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Position:
    """An open position in the portfolio.

    Attributes
    ----------
    symbol : str
        Stock symbol code.
    shares : int
        Number of shares held (always a multiple of 100 for A-shares).
    cost_price : float
        Average cost price per share.
    entry_date : str
        Date the position was entered (YYYY-MM-DD).
    """

    symbol: str
    shares: int
    cost_price: float
    entry_date: str


@dataclass
class Trade:
    """A completed (closed) trade.

    Attributes
    ----------
    trade_id : int
        Unique trade identifier.
    symbol : str
        Stock symbol code.
    entry_date : str
        Date the position was opened.
    exit_date : str
        Date the position was closed.
    entry_price : float
        Entry price per share.
    exit_price : float
        Exit price per share.
    shares : int
        Number of shares traded.
    pnl : float
        Profit/loss in absolute CNY.
    pnl_pct : float
        Profit/loss as a decimal ratio (0.05 = 5%).
    commission_total : float
        Total commission paid (entry + exit).
    """

    trade_id: int
    symbol: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    commission_total: float


# ---------------------------------------------------------------------------
# Commission calculation
# ---------------------------------------------------------------------------


def calculate_commission(amount: float, is_sell: bool) -> float:
    """Calculate A-share trading commission.

    Parameters
    ----------
    amount : float
        Total trade amount (price × shares) in CNY.
    is_sell : bool
        Whether this is a sell order (stamp tax applies on sell only).

    Returns
    -------
    float
        Total commission in CNY.
    """
    commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
    if is_sell:
        stamp_tax = amount * STAMP_TAX_RATE
        commission += stamp_tax
    return round(commission, 2)


# ---------------------------------------------------------------------------
# Portfolio manager
# ---------------------------------------------------------------------------


class PortfolioManager:
    """Manages portfolio positions, cash, NAV tracking, and trade execution.

    Parameters
    ----------
    initial_capital : float
        Starting cash balance in CNY.
    max_positions : int
        Maximum number of concurrent positions (default 5).
    position_pct : float
        Target position size as a fraction of total portfolio value (default 0.30).
    """

    def __init__(
        self,
        initial_capital: float,
        max_positions: int = MAX_CONCURRENT_POSITIONS,
        position_pct: float = MAX_POSITION_PCT_LOW,
    ) -> None:
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.max_positions = max_positions
        self.position_pct = position_pct

        self.positions: dict[str, Position] = {}  # symbol -> Position
        self.closed_trades: list[Trade] = []
        self._trade_counter: int = 0

        # Daily NAV tracking: list of (date, nav, daily_return)
        self.nav_history: list[dict[str, Any]] = []
        self._prev_nav: float = initial_capital

    # ------------------------------------------------------------------
    # Portfolio value
    # ------------------------------------------------------------------

    def get_nav(self, prices: dict[str, float]) -> float:
        """Calculate current Net Asset Value.

        Parameters
        ----------
        prices : dict[str, float]
            Current prices for held symbols: ``{symbol: close_price}``.

        Returns
        -------
        float
            Total portfolio value (cash + positions at market value).
        """
        portfolio_value = self.cash
        for symbol, pos in self.positions.items():
            price = prices.get(symbol, pos.cost_price)
            portfolio_value += pos.shares * price
        return round(portfolio_value, 2)

    def record_daily_nav(self, date: str, prices: dict[str, float]) -> float:
        """Record NAV snapshot for the given date.

        Parameters
        ----------
        date : str
            Date in YYYY-MM-DD format.
        prices : dict[str, float]
            Current prices for held symbols.

        Returns
        -------
        float
            The recorded NAV value.
        """
        nav = self.get_nav(prices)
        daily_return = (nav - self._prev_nav) / self._prev_nav if self._prev_nav > 0 else 0.0
        self.nav_history.append({
            "date": date,
            "nav": round(nav, 2),
            "daily_return": round(daily_return, 6),
        })
        self._prev_nav = nav
        return nav

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def calculate_shares(self, price: float, nav: float | None = None) -> int:
        """Calculate the number of shares to buy based on position sizing rules.

        Buys ``position_pct`` of portfolio value, rounded down to nearest 100 shares
        (A-share lot size). Also ensures we don't spend more cash than available.

        Parameters
        ----------
        price : float
            Current stock price.
        nav : float or None
            Current NAV. If None, uses cash as the reference.

        Returns
        -------
        int
            Number of shares to buy (multiple of 100). Returns 0 if no valid size.
        """
        if price <= 0:
            return 0

        reference = nav if nav is not None else self.cash
        target_amount = reference * self.position_pct

        # Don't exceed available cash (minus estimated commission)
        max_amount = self.cash - COMMISSION_MIN  # reserve for commission
        if max_amount <= 0:
            return 0

        target_amount = min(target_amount, max_amount)
        shares = int(target_amount / price)

        # Round down to nearest 100 (A-share lot size)
        shares = (shares // 100) * 100
        return max(shares, 0)

    # ------------------------------------------------------------------
    # Trade execution
    # ------------------------------------------------------------------

    def can_buy(self, symbol: str) -> bool:
        """Check if we can open a new position for the given symbol.

        Returns
        -------
        bool
            True if under max positions and symbol not already held.
        """
        if symbol in self.positions:
            return False
        if len(self.positions) >= self.max_positions:
            return False
        if self.cash <= COMMISSION_MIN:
            return False
        return True

    def buy(self, symbol: str, price: float, date: str, nav: float | None = None) -> Position | None:
        """Execute a buy order.

        Parameters
        ----------
        symbol : str
            Stock symbol to buy.
        price : float
            Buy price per share.
        date : str
            Trade date (YYYY-MM-DD).
        nav : float or None
            Current NAV for position sizing.

        Returns
        -------
        Position or None
            The opened position, or None if the buy could not be executed.
        """
        if not self.can_buy(symbol):
            return None

        shares = self.calculate_shares(price, nav)
        if shares <= 0:
            return None

        trade_amount = shares * price
        commission = calculate_commission(trade_amount, is_sell=False)
        total_cost = trade_amount + commission

        if total_cost > self.cash:
            # Reduce shares to fit
            shares = (int((self.cash - COMMISSION_MIN) / price) // 100) * 100
            if shares <= 0:
                return None
            trade_amount = shares * price
            commission = calculate_commission(trade_amount, is_sell=False)
            total_cost = trade_amount + commission

        self.cash -= total_cost
        position = Position(
            symbol=symbol,
            shares=shares,
            cost_price=price,
            entry_date=date,
        )
        self.positions[symbol] = position
        return position

    def sell(self, symbol: str, price: float, date: str) -> Trade | None:
        """Execute a sell order — close the entire position.

        Parameters
        ----------
        symbol : str
            Stock symbol to sell.
        price : float
            Sell price per share.
        date : str
            Trade date (YYYY-MM-DD).

        Returns
        -------
        Trade or None
            The completed trade, or None if no position to sell.
        """
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]
        trade_amount = position.shares * price
        sell_commission = calculate_commission(trade_amount, is_sell=True)
        buy_commission = calculate_commission(position.shares * position.cost_price, is_sell=False)

        net_proceeds = trade_amount - sell_commission
        self.cash += net_proceeds

        # Calculate P&L: gross P&L minus total commissions
        gross_pnl = (price - position.cost_price) * position.shares
        total_commission = buy_commission + sell_commission
        pnl = gross_pnl - total_commission
        pnl_pct = pnl / (position.shares * position.cost_price) if position.cost_price > 0 else 0.0

        self._trade_counter += 1
        trade = Trade(
            trade_id=self._trade_counter,
            symbol=symbol,
            entry_date=position.entry_date,
            exit_date=date,
            entry_price=position.cost_price,
            exit_price=price,
            shares=position.shares,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 6),
            commission_total=round(total_commission, 2),
        )
        self.closed_trades.append(trade)
        del self.positions[symbol]
        return trade

    def has_position(self, symbol: str) -> bool:
        """Check if we currently hold a position in the given symbol."""
        return symbol in self.positions

    @property
    def position_count(self) -> int:
        """Return the number of currently open positions."""
        return len(self.positions)
