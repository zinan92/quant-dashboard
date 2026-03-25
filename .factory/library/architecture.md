# Architecture

**What belongs here:** Architectural decisions, patterns, and design rationale.

---

## System Architecture

```
┌──────────────────────────┐
│  FreqUI (Vue.js SPA)     │  ← Open source, unmodified, served as static files
│  Static build in         │
│  frontend/dist/          │
└──────────┬───────────────┘
           │ REST API /api/v1/*
┌──────────▼───────────────┐
│  FastAPI Backend (:8020)  │  ← Our code
│  ├── Auth (JWT)          │
│  ├── FreqTrade API shim  │  ← Translates our data to FreqTrade response format
│  ├── Strategy Engine     │  ← Chan Theory quantitative implementation
│  ├── Backtest Engine     │  ← Signal → Trade → NAV calculation
│  └── Data Layer          │  ← Reads ashare market.db + local backtest.db
└──────────┬───────────────┘
           │ SQLite (read-only)        │ SQLite (read-write)
┌──────────▼────────┐    ┌────────────▼────────┐
│  ashare market.db  │    │  data/backtest.db    │
│  (422 stocks +     │    │  (backtest results,  │
│   5 indices)       │    │   trades, NAV)       │
└───────────────────┘    └─────────────────────┘
```

## Project Structure

```
quant-dashboard/
├── app/
│   ├── main.py              # FastAPI app, SPA fallback, CORS
│   ├── auth.py              # JWT auth (login, refresh, dependency)
│   ├── api/                 # FreqTrade-compatible API endpoints
│   │   ├── system.py        # ping, version, show_config, sysinfo
│   │   ├── profit.py        # profit, daily, weekly, monthly
│   │   ├── trades.py        # trades, status, performance
│   │   ├── strategy.py      # strategies, strategy/{name}
│   │   ├── backtest.py      # backtest start/poll/history
│   │   ├── pairs.py         # whitelist, blacklist, available_pairs, pair_candles
│   │   └── compat.py        # catch-all for unimplemented endpoints (return 404 JSON)
│   └── schemas.py           # Pydantic models matching FreqTrade schemas
├── src/
│   ├── data_layer/
│   │   ├── market_reader.py # Read-only access to ashare market.db
│   │   └── index_fetcher.py # AkShare CSI 300 supplementation
│   ├── strategy/
│   │   ├── chan_theory.py    # Mechanical Chan Theory implementation
│   │   └── base.py          # Strategy base class
│   └── backtest/
│       ├── engine.py        # Core backtest engine
│       ├── portfolio.py     # Position management, NAV calculation
│       └── metrics.py       # Performance metrics (Sharpe, Sortino, etc.)
├── strategies/
│   └── chan_theory.yaml      # Copy of strategy definition
├── frontend/                 # FreqUI source (cloned)
│   └── dist/                 # Built static files
├── data/
│   └── backtest.db           # Backtest results storage
├── tests/
├── requirements.txt
└── pyproject.toml
```

## Key Design Decisions

1. **FreqTrade API compatibility**: We implement the exact same REST API schema that FreqUI expects, so we can use FreqUI without modification.
2. **Read-only market.db**: We never write to ashare's database. Our own data goes in `data/backtest.db`.
3. **SPA fallback**: FastAPI serves API routes first, then falls back to `frontend/dist/index.html` for all other routes (SPA deep linking).
4. **404 not 500 for unimplemented endpoints**: Critical — FreqUI interprets HTTP 500 as "bot offline".
5. **Webserver mode**: `show_config` returns `runmode: "webserver"` which tells FreqUI to enable backtest features and disable live trading features.
