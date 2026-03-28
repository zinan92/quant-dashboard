# Architecture

## System Overview

Hybrid backtest dashboard: existing custom BacktestEngine for portfolio-level results, backtesting.py for per-stock interactive visualization, QuantStats for portfolio tearsheets, Streamlit as the host.

## Components

### Data Layer (existing, frozen)
- `src/data_layer/market_reader.py` — SQLite reader for ashare market.db
- Returns DataFrames with lowercase columns: date, open, high, low, close, volume, amount, dif, dea, macd
- Date is string YYYY-MM-DD format

### Strategy Layer (existing, frozen)
- `src/strategy/chan_theory.py` — Chan Theory engine (fractal→pen→hub→divergence→signals)
- `generate_signals(df) → list[Signal]` where Signal has date, signal_type, signal_strength
- SignalType: BUY_1/2/3, SELL_1/2/3, HUB_OSCILLATION

### Backtest Engine (existing, frozen)
- `src/backtest/engine.py` — Portfolio-level backtester
- Iterates all stocks day-by-day with shared PortfolioManager
- Max 5 concurrent positions, 30% sizing, 100-share lots
- Returns BacktestResult with nav_history, trades, metrics

### Adapter Layer (NEW)
- `src/adapters/backtesting_adapter.py` — Data format conversion (lowercase→title-case, string→DatetimeIndex) + A-share commission callable
- `src/adapters/chan_theory_bt.py` — Wraps Chan Theory signals into backtesting.py Strategy class

### Reporting Layer (NEW)
- `src/reporting/tearsheet.py` — QuantStats HTML tearsheet generation from BacktestEngine results with CSI 300 benchmark

### Dashboard (REWRITE)
- `streamlit_app.py` — Two-tab layout embedding backtesting.py Bokeh charts and QuantStats tearsheets

## Data Flow

```
market.db → MarketReader → BacktestEngine → BacktestResult
                                              ├→ nav_history → QuantStats tearsheet (Tab 1)
                                              └→ traded stock list → per-stock selector
                                                                       ↓
market.db → MarketReader → backtesting_adapter → backtesting.py → Bokeh chart (Tab 2)
```
