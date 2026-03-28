# Architecture

**What belongs here:** Architectural decisions, patterns, and design rationale.

---

## System Architecture (Post-Dashboard-Rewrite)

```
┌────────────────────────────────────────────────┐
│  Streamlit App (streamlit_app.py)              │  ← Single-file dashboard on :8020
│  ├── Sidebar: Strategy selector,               │
│  │   date range, capital, Run button           │
│  ├── Tab 1: Portfolio Overview                 │
│  │   ├── 6 metric cards (st.metric)            │
│  │   ├── QuantStats tearsheet (html embed)     │
│  │   └── Trade history table (expandable)      │
│  └── Tab 2: Stock Analysis                     │
│      ├── Stock dropdown (traded stocks)        │
│      ├── backtesting.py Bokeh chart (html)     │
│      └── Per-stock metrics & trade table       │
└──────────┬─────────────────────────────────────┘
           │ Direct Python imports (no REST API)
┌──────────▼───────────────────────────────┐
│  Backend Modules                          │
│  ├── Strategy Engine (src/strategy/)     │  ← Chan Theory implementation
│  ├── Backtest Engine (src/backtest/)     │  ← Signal → Trade → NAV
│  ├── Data Layer (src/data_layer/)        │  ← Reads market.db + index_cache.db
│  ├── Adapters (src/adapters/)            │  ← backtesting.py integration
│  │   ├── backtesting_adapter.py          │  ← Data format + commission model
│  │   └── chan_theory_bt.py               │  ← Strategy wrapper + per-stock backtest
│  └── Reporting (src/reporting/)          │
│      └── tearsheet.py                    │  ← QuantStats tearsheet generation
└──────────┬───────────────────────────────┘
           │ SQLite (read-only)        │ SQLite (read-write)
┌──────────▼────────┐    ┌────────────▼────────┐
│  ashare market.db  │    │  data/backtest.db    │
│  (422 stocks +     │    │  data/index_cache.db │
│   5 indices)       │    │  (CSI 300 cache,     │
└───────────────────┘    │   backtest results)  │
                          └─────────────────────┘
```

## Project Structure

```
quant-dashboard/
├── streamlit_app.py         # Streamlit dashboard (main entry point)
├── src/
│   ├── data_layer/
│   │   ├── market_reader.py # Read-only access to ashare market.db
│   │   └── index_fetcher.py # AkShare CSI 300 supplementation → index_cache.db
│   ├── strategy/
│   │   ├── chan_theory.py    # Mechanical Chan Theory implementation
│   │   └── base.py          # Strategy base class
│   ├── backtest/
│   │   ├── engine.py        # Core backtest engine
│   │   ├── portfolio.py     # Position management, NAV calculation
│   │   └── metrics.py       # Performance metrics (Sharpe, Sortino, etc.)
│   ├── adapters/
│   │   ├── backtesting_adapter.py  # Data format conversion + A-share commission
│   │   └── chan_theory_bt.py       # backtesting.py Strategy wrapper + per-stock backtest
│   └── reporting/
│       └── tearsheet.py     # QuantStats HTML tearsheet generation
├── strategies/
│   └── chan_theory.yaml      # Copy of strategy definition
├── data/
│   ├── backtest.db           # Backtest results storage
│   └── index_cache.db        # Cached CSI 300 index data
├── tests/
│   ├── test_data_layer.py
│   ├── test_chan_theory.py
│   ├── test_backtest.py
│   ├── adapters/
│   │   ├── test_backtesting_adapter.py  # Data adapter + commission tests
│   │   └── test_chan_theory_bt.py       # Strategy wrapper + backtest tests
│   └── reporting/
│       └── test_tearsheet.py            # QuantStats tearsheet tests
├── requirements.txt
└── pyproject.toml
```

## Key Design Decisions

1. **Streamlit direct imports**: The Streamlit app imports Python modules directly — no REST API layer. This simplifies the architecture and eliminates serialization overhead.
2. **Read-only market.db**: We never write to ashare's database. Our own data goes in `data/backtest.db` and `data/index_cache.db`.
3. **No custom Plotly charts**: All visualization uses backtesting.py (Bokeh) for per-stock interactive charts and QuantStats for portfolio tearsheets. Charts are embedded via `st.components.v1.html()`.
4. **Hybrid backtest architecture**: BacktestEngine runs the portfolio backtest (all stocks, shared capital, max 5 positions) for NAV/returns. backtesting.py runs per individual stock for interactive Bokeh visualization only.
5. **Threading for backtest**: Backtest runs in a background thread so Streamlit can show progress indicators during execution.
6. **QuantStats tearsheet**: Portfolio-level HTML tearsheet generated from BacktestResult.nav_history with CSI 300 benchmark comparison.
