# Architecture

**What belongs here:** Architectural decisions, patterns, and design rationale.

---

## System Architecture (Post-Streamlit Pivot)

```
┌────────────────────────────────────────┐
│  Streamlit App (streamlit_app.py)      │  ← Single-file dashboard on :8020
│  ├── Sidebar: Strategy selector,       │
│  │   date range, capital, Run button   │
│  ├── Performance cards (6 metrics)     │
│  ├── NAV chart + benchmark overlays    │
│  ├── Drawdown chart                    │
│  ├── Trade list table                  │
│  ├── Monthly returns heatmap           │
│  └── Per-stock performance bar chart   │
└──────────┬─────────────────────────────┘
           │ Direct Python imports (no REST API)
┌──────────▼───────────────┐
│  Backend Modules          │
│  ├── Strategy Engine     │  ← Chan Theory quantitative implementation
│  ├── Backtest Engine     │  ← Signal → Trade → NAV calculation
│  └── Data Layer          │  ← Reads ashare market.db + local index_cache.db
└──────────┬───────────────┘
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
│   └── backtest/
│       ├── engine.py        # Core backtest engine
│       ├── portfolio.py     # Position management, NAV calculation
│       └── metrics.py       # Performance metrics (Sharpe, Sortino, etc.)
├── strategies/
│   └── chan_theory.yaml      # Copy of strategy definition
├── data/
│   ├── backtest.db           # Backtest results storage
│   └── index_cache.db        # Cached CSI 300 index data
├── tests/
│   ├── test_data_layer.py
│   ├── test_chan_theory.py
│   └── test_backtest.py
├── requirements.txt
└── pyproject.toml
```

## Key Design Decisions

1. **Streamlit direct imports**: The Streamlit app imports Python modules directly — no REST API layer. This simplifies the architecture and eliminates serialization overhead.
2. **Read-only market.db**: We never write to ashare's database. Our own data goes in `data/backtest.db` and `data/index_cache.db`.
3. **Plotly for charts**: All interactive charts (NAV, drawdown, heatmap, bar) use `plotly.graph_objects` via `st.plotly_chart()`.
4. **Benchmark overlays**: CSI 300 from `index_cache.db` (fetched via AkShare) and ChiNext from `market.db`, both normalized to the same starting point on the NAV chart.
5. **Threading for backtest**: Backtest runs in a background thread so Streamlit can show progress indicators during execution.
