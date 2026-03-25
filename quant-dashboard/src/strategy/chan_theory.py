"""Chan Theory (缠论) mechanical quantitative strategy implementation.

Implements the full Chan Theory pipeline:
1. Fractal (分型) detection — top and bottom fractals from 3 consecutive K-bars.
2. Pen (笔) construction — alternating top/bottom fractals with ≥4 bars between.
3. Hub (中枢) identification — overlapping price range of 3+ consecutive strokes.
4. MACD divergence detection — compare price highs/lows with MACD histogram area.
5. Buy/sell point classification — 一买/二买/三买 and their sell-side mirrors.
6. Signal generation — returns (date, signal_type, signal_strength) tuples.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.strategy.base import (
    Signal,
    SignalStrength,
    SignalType,
    Strategy,
    register_strategy,
)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

STRATEGIES_DIR = Path(__file__).resolve().parent.parent.parent / "strategies"


@dataclass
class Fractal:
    """A top or bottom fractal identified from K-line data.

    Attributes
    ----------
    index : int
        Row index in the original DataFrame.
    date : str
        Date of the fractal bar.
    price : float
        The high for top fractals, the low for bottom fractals.
    is_top : bool
        ``True`` for top fractals, ``False`` for bottom fractals.
    """

    index: int
    date: str
    price: float
    is_top: bool


@dataclass
class Pen:
    """A pen (笔) connecting two alternating fractals.

    Attributes
    ----------
    start : Fractal
        The starting fractal.
    end : Fractal
        The ending fractal.
    direction : str
        ``'up'`` if start is bottom and end is top, ``'down'`` otherwise.
    """

    start: Fractal
    end: Fractal
    direction: str  # 'up' or 'down'

    @property
    def high(self) -> float:
        """Highest price in this pen."""
        return max(self.start.price, self.end.price)

    @property
    def low(self) -> float:
        """Lowest price in this pen."""
        return min(self.start.price, self.end.price)


@dataclass
class Hub:
    """A hub (中枢) — overlapping price range of 3+ consecutive pens/strokes.

    Attributes
    ----------
    pens : list[Pen]
        The pens forming this hub.
    high : float
        Upper bound of the overlapping region (ZG).
    low : float
        Lower bound of the overlapping region (ZD).
    direction : str
        Overall direction leading into the hub: ``'up'``, ``'down'``, or ``'flat'``.
    """

    pens: list[Pen]
    high: float  # ZG — upper bound of overlap
    low: float   # ZD — lower bound of overlap
    direction: str  # 'up', 'down', or 'flat'

    @property
    def start_date(self) -> str:
        return self.pens[0].start.date

    @property
    def end_date(self) -> str:
        return self.pens[-1].end.date

    @property
    def start_index(self) -> int:
        return self.pens[0].start.index

    @property
    def end_index(self) -> int:
        return self.pens[-1].end.index


# ---------------------------------------------------------------------------
# Core algorithms
# ---------------------------------------------------------------------------


def detect_fractals(df: pd.DataFrame) -> list[Fractal]:
    """Detect top and bottom fractals from OHLCV data.

    A **top fractal** occurs at bar *i* when:
        ``bar[i].high > bar[i-1].high AND bar[i].high > bar[i+1].high``

    A **bottom fractal** occurs at bar *i* when:
        ``bar[i].low < bar[i-1].low AND bar[i].low < bar[i+1].low``

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``date``, ``high``, ``low`` columns, sorted by date ascending.

    Returns
    -------
    list[Fractal]
        Detected fractals in chronological order.
    """
    if len(df) < 3:
        return []

    highs = df["high"].values
    lows = df["low"].values
    dates = df["date"].values

    fractals: list[Fractal] = []

    for i in range(1, len(df) - 1):
        # Top fractal: current high is strictly greater than both neighbors
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            fractals.append(
                Fractal(index=i, date=str(dates[i]), price=float(highs[i]), is_top=True)
            )
        # Bottom fractal: current low is strictly less than both neighbors
        if lows[i] < lows[i - 1] and lows[i] < lows[i + 1]:
            fractals.append(
                Fractal(index=i, date=str(dates[i]), price=float(lows[i]), is_top=False)
            )

    # Sort by index for chronological order (in case a bar has both top and bottom)
    fractals.sort(key=lambda f: (f.index, not f.is_top))
    return fractals


def construct_pens(fractals: list[Fractal], min_bars_between: int = 4) -> list[Pen]:
    """Construct pens (笔) from a sequence of fractals.

    A valid pen connects alternating top and bottom fractals with at least
    ``min_bars_between`` bars between them (default 4 per Chan Theory rules).

    Parameters
    ----------
    fractals : list[Fractal]
        Chronologically ordered fractals.
    min_bars_between : int
        Minimum number of bars between two fractals to form a valid pen.

    Returns
    -------
    list[Pen]
        Constructed pens in chronological order.
    """
    if len(fractals) < 2:
        return []

    pens: list[Pen] = []
    # Start from the first fractal, find the next alternating one
    current = fractals[0]

    for candidate in fractals[1:]:
        # Must be alternating type
        if candidate.is_top == current.is_top:
            # Same type — keep the more extreme one
            if current.is_top:
                # Keep the higher top
                if candidate.price > current.price:
                    current = candidate
            else:
                # Keep the lower bottom
                if candidate.price < current.price:
                    current = candidate
            continue

        # Must have enough bars between them
        if abs(candidate.index - current.index) < min_bars_between:
            continue

        # Valid pen
        if current.is_top:
            direction = "down"  # top → bottom
        else:
            direction = "up"    # bottom → top

        pens.append(Pen(start=current, end=candidate, direction=direction))
        current = candidate

    return pens


def identify_hubs(pens: list[Pen], min_pens: int = 3) -> list[Hub]:
    """Identify hubs (中枢) from a sequence of pens.

    A hub is the overlapping price range of ``min_pens`` or more consecutive pens.
    The overlap region is defined as:
        ZG = min of the highs of the overlapping pens
        ZD = max of the lows of the overlapping pens

    A valid hub requires ZG > ZD (i.e. there IS an overlapping range).

    Parameters
    ----------
    pens : list[Pen]
        Chronologically ordered pens.
    min_pens : int
        Minimum number of overlapping pens to form a hub (default 3).

    Returns
    -------
    list[Hub]
        Identified hubs in chronological order.
    """
    if len(pens) < min_pens:
        return []

    hubs: list[Hub] = []
    i = 0

    while i <= len(pens) - min_pens:
        # Try to start a hub at pen i
        # Initial overlap from first min_pens pens
        hub_pens = pens[i : i + min_pens]
        zg = min(p.high for p in hub_pens)  # upper bound of overlap
        zd = max(p.low for p in hub_pens)   # lower bound of overlap

        if zg <= zd:
            # No valid overlap — skip forward
            i += 1
            continue

        # Extend the hub as long as subsequent pens overlap with [ZD, ZG]
        j = i + min_pens
        while j < len(pens):
            pen = pens[j]
            new_zg = min(zg, pen.high)
            new_zd = max(zd, pen.low)
            if new_zg <= new_zd:
                break  # This pen doesn't overlap
            zg = new_zg
            zd = new_zd
            hub_pens = pens[i : j + 1]
            j += 1

        # Determine hub direction based on the pens leading into it
        if i > 0:
            leading_pen = pens[i - 1]
            hub_direction = leading_pen.direction
        else:
            # Use the first pen's direction to infer
            first_pen = hub_pens[0]
            hub_direction = "down" if first_pen.direction == "up" else "up"

        hubs.append(Hub(pens=hub_pens, high=zg, low=zd, direction=hub_direction))
        # Move past this hub
        i = j if j > i + min_pens else i + min_pens

    return hubs


def compute_macd_area(macd_values: np.ndarray, start_idx: int, end_idx: int) -> float:
    """Compute the cumulative MACD histogram area between two indices.

    Parameters
    ----------
    macd_values : np.ndarray
        The MACD histogram values (typically ``2 * (DIF - DEA)``).
    start_idx, end_idx : int
        Start and end indices (inclusive).

    Returns
    -------
    float
        Absolute cumulative area of the MACD histogram.
    """
    if start_idx >= end_idx or start_idx < 0 or end_idx >= len(macd_values):
        return 0.0
    segment = macd_values[start_idx : end_idx + 1]
    return float(np.sum(np.abs(segment)))


def detect_divergence(
    df: pd.DataFrame,
    fractals: list[Fractal],
    pens: list[Pen],
) -> list[dict]:
    """Detect MACD divergence between consecutive same-type fractals.

    **Top divergence**: price makes a new high but MACD histogram cumulative
    area between the two top fractals is *smaller* than the previous segment.

    **Bottom divergence**: price makes a new low but MACD histogram cumulative
    area between the two bottom fractals is *smaller* than the previous segment.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``high``, ``low``, ``macd`` columns.
    fractals : list[Fractal]
        Detected fractals.
    pens : list[Pen]
        Constructed pens (used for context).

    Returns
    -------
    list[dict]
        Each dict has keys: ``type`` (``'top'`` or ``'bottom'``),
        ``date``, ``index``, ``prev_fractal``, ``curr_fractal``.
    """
    if "macd" not in df.columns:
        return []

    macd_values = df["macd"].values.astype(float)

    divergences: list[dict] = []

    # Group fractals by type
    top_fractals = [f for f in fractals if f.is_top]
    bottom_fractals = [f for f in fractals if not f.is_top]

    # Check top divergence — consecutive top fractals
    for k in range(1, len(top_fractals)):
        prev_top = top_fractals[k - 1]
        curr_top = top_fractals[k]

        # Price makes new high
        if curr_top.price > prev_top.price:
            prev_area = compute_macd_area(macd_values, prev_top.index - 2, prev_top.index + 2)
            curr_area = compute_macd_area(macd_values, curr_top.index - 2, curr_top.index + 2)

            # Also check area between the two tops
            between_area_prev = compute_macd_area(
                macd_values,
                max(0, prev_top.index - 5),
                prev_top.index,
            )
            between_area_curr = compute_macd_area(
                macd_values,
                max(0, curr_top.index - 5),
                curr_top.index,
            )

            if curr_area < prev_area or between_area_curr < between_area_prev:
                divergences.append(
                    {
                        "type": "top",
                        "date": curr_top.date,
                        "index": curr_top.index,
                        "prev_fractal": prev_top,
                        "curr_fractal": curr_top,
                    }
                )

    # Check bottom divergence — consecutive bottom fractals
    for k in range(1, len(bottom_fractals)):
        prev_bot = bottom_fractals[k - 1]
        curr_bot = bottom_fractals[k]

        # Price makes new low
        if curr_bot.price < prev_bot.price:
            prev_area = compute_macd_area(macd_values, prev_bot.index - 2, prev_bot.index + 2)
            curr_area = compute_macd_area(macd_values, curr_bot.index - 2, curr_bot.index + 2)

            between_area_prev = compute_macd_area(
                macd_values,
                max(0, prev_bot.index - 5),
                prev_bot.index,
            )
            between_area_curr = compute_macd_area(
                macd_values,
                max(0, curr_bot.index - 5),
                curr_bot.index,
            )

            if curr_area < prev_area or between_area_curr < between_area_prev:
                divergences.append(
                    {
                        "type": "bottom",
                        "date": curr_bot.date,
                        "index": curr_bot.index,
                        "prev_fractal": prev_bot,
                        "curr_fractal": curr_bot,
                    }
                )

    return divergences


def classify_signals(
    df: pd.DataFrame,
    fractals: list[Fractal],
    pens: list[Pen],
    hubs: list[Hub],
    divergences: list[dict],
) -> list[Signal]:
    """Classify buy and sell points based on Chan Theory rules.

    Buy points:
        - 一买 (BUY_1): Bottom divergence at end of downtrend hub.
        - 二买 (BUY_2): First pullback after price leaves a downtrend hub upward.
        - 三买 (BUY_3): Breakout above hub that holds (price doesn't re-enter hub).

    Sell points:
        - 一卖 (SELL_1): Top divergence at end of uptrend hub.
        - 二卖 (SELL_2): First bounce after price leaves an uptrend hub downward.
        - 三卖 (SELL_3): Breakdown below hub that holds.

    Parameters
    ----------
    df : pd.DataFrame
        The OHLCV+MACD data.
    fractals : list[Fractal]
        Detected fractals.
    pens : list[Pen]
        Constructed pens.
    hubs : list[Hub]
        Identified hubs.
    divergences : list[dict]
        Detected divergences.

    Returns
    -------
    list[Signal]
        Classified signals in chronological order.
    """
    signals: list[Signal] = []
    used_dates: set[str] = set()  # Prevent duplicate signals on same date

    # --- 一买 / 一卖: divergence at hub ---
    for div in divergences:
        div_date = div["date"]
        div_index = div["index"]

        for hub in hubs:
            # Check if the divergence occurs near the end of a hub
            if div_index < hub.start_index or div_index > hub.end_index + 10:
                continue

            if div["type"] == "bottom" and hub.direction in ("down", "flat"):
                if div_date not in used_dates:
                    signals.append(
                        Signal(
                            date=div_date,
                            signal_type=SignalType.BUY_1,
                            signal_strength=SignalStrength.STRONG,
                        )
                    )
                    used_dates.add(div_date)

            elif div["type"] == "top" and hub.direction in ("up", "flat"):
                if div_date not in used_dates:
                    signals.append(
                        Signal(
                            date=div_date,
                            signal_type=SignalType.SELL_1,
                            signal_strength=SignalStrength.STRONG,
                        )
                    )
                    used_dates.add(div_date)

    # --- 二买 / 二卖: first pullback after leaving hub ---
    for hub in hubs:
        hub_end_idx = hub.end_index

        # Find pens after the hub
        post_hub_pens = [p for p in pens if p.start.index >= hub_end_idx]

        if len(post_hub_pens) < 2:
            continue

        first_pen = post_hub_pens[0]
        second_pen = post_hub_pens[1]

        # 二买: after downtrend hub, price goes up then pulls back but stays above hub.high
        if hub.direction in ("down", "flat"):
            if first_pen.direction == "up" and second_pen.direction == "down":
                pullback_low = second_pen.end.price
                if pullback_low > hub.low:  # Doesn't break back into hub
                    sig_date = second_pen.end.date
                    if sig_date not in used_dates:
                        signals.append(
                            Signal(
                                date=sig_date,
                                signal_type=SignalType.BUY_2,
                                signal_strength=SignalStrength.MODERATE,
                            )
                        )
                        used_dates.add(sig_date)

        # 二卖: after uptrend hub, price goes down then bounces but stays below hub.low
        if hub.direction in ("up", "flat"):
            if first_pen.direction == "down" and second_pen.direction == "up":
                bounce_high = second_pen.end.price
                if bounce_high < hub.high:  # Doesn't break back into hub
                    sig_date = second_pen.end.date
                    if sig_date not in used_dates:
                        signals.append(
                            Signal(
                                date=sig_date,
                                signal_type=SignalType.SELL_2,
                                signal_strength=SignalStrength.MODERATE,
                            )
                        )
                        used_dates.add(sig_date)

    # --- 三买 / 三卖: breakout/breakdown that holds ---
    for hub in hubs:
        hub_end_idx = hub.end_index

        # Find fractals after the hub
        post_hub_fractals = [f for f in fractals if f.index > hub_end_idx]

        if len(post_hub_fractals) < 2:
            continue

        # 三买: after hub, price breaks above hub.high and the next pullback stays above hub.high
        for k in range(1, len(post_hub_fractals)):
            f_prev = post_hub_fractals[k - 1]
            f_curr = post_hub_fractals[k]

            if f_prev.is_top and f_prev.price > hub.high:
                # Price broke above hub
                if not f_curr.is_top and f_curr.price > hub.high:
                    # Pullback bottom is above hub.high — 三买
                    sig_date = f_curr.date
                    if sig_date not in used_dates:
                        signals.append(
                            Signal(
                                date=sig_date,
                                signal_type=SignalType.BUY_3,
                                signal_strength=SignalStrength.MODERATE,
                            )
                        )
                        used_dates.add(sig_date)
                break  # Only check the first breakout attempt

            # 三卖: price breaks below hub.low and the next bounce stays below hub.low
            if not f_prev.is_top and f_prev.price < hub.low:
                if f_curr.is_top and f_curr.price < hub.low:
                    sig_date = f_curr.date
                    if sig_date not in used_dates:
                        signals.append(
                            Signal(
                                date=sig_date,
                                signal_type=SignalType.SELL_3,
                                signal_strength=SignalStrength.MODERATE,
                            )
                        )
                        used_dates.add(sig_date)
                break

    # --- Hub oscillation: if there are hubs but no divergence signals ---
    if hubs and not divergences:
        last_hub = hubs[-1]
        last_bar_idx = len(df) - 1
        # If the last bar is still within the hub's price range, emit oscillation
        if last_bar_idx >= last_hub.start_index:
            last_close = float(df.iloc[-1]["close"])
            if last_hub.low <= last_close <= last_hub.high:
                last_date = str(df.iloc[-1]["date"])
                if last_date not in used_dates:
                    signals.append(
                        Signal(
                            date=last_date,
                            signal_type=SignalType.HUB_OSCILLATION,
                            signal_strength=SignalStrength.WEAK,
                        )
                    )

    # Sort signals by date
    signals.sort(key=lambda s: s.date)
    return signals


# ---------------------------------------------------------------------------
# Strategy class
# ---------------------------------------------------------------------------


@register_strategy
class ChanTheoryStrategy(Strategy):
    """Chan Theory (缠论) mechanical quantitative strategy.

    Given a DataFrame with OHLCV+MACD data, this strategy runs the full
    Chan Theory pipeline and returns a list of classified signals.
    """

    @property
    def name(self) -> str:
        return "chan_theory"

    @property
    def display_name(self) -> str:
        return "缠论"

    @property
    def timeframe(self) -> str:
        return "1d"

    def get_params(self) -> list[dict]:
        return [
            {"name": "min_bars_between", "type": "int", "default": 4, "description": "Minimum bars between fractals"},
            {"name": "min_hub_pens", "type": "int", "default": 3, "description": "Minimum pens to form a hub"},
        ]

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """Run the full Chan Theory pipeline on OHLCV+MACD data.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain columns: ``date, open, high, low, close, volume``.
            Should also contain ``macd`` (and optionally ``dif, dea``).
            Rows must be sorted by date ascending.

        Returns
        -------
        list[Signal]
            Detected trading signals.
        """
        if df.empty or len(df) < 10:
            return []

        # Ensure required columns
        required = {"date", "high", "low", "close"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        # If MACD is missing, we can still detect fractals/pens/hubs but not divergence
        has_macd = "macd" in df.columns

        # Step 1: Fractal detection
        fractals = detect_fractals(df)
        if not fractals:
            return []

        # Step 2: Pen construction
        pens = construct_pens(fractals, min_bars_between=4)
        if not pens:
            return []

        # Step 3: Hub identification
        hubs = identify_hubs(pens, min_pens=3)

        # Step 4: MACD divergence detection
        divergences: list[dict] = []
        if has_macd:
            divergences = detect_divergence(df, fractals, pens)

        # Step 5: Signal classification
        signals = classify_signals(df, fractals, pens, hubs, divergences)

        return signals

    @staticmethod
    def get_yaml_path() -> Path:
        """Return the path to the strategy YAML file."""
        return STRATEGIES_DIR / "chan_theory.yaml"

    @staticmethod
    def get_yaml_content() -> str:
        """Return the content of the strategy YAML file."""
        yaml_path = STRATEGIES_DIR / "chan_theory.yaml"
        if yaml_path.exists():
            return yaml_path.read_text(encoding="utf-8")
        return ""
