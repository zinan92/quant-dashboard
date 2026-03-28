# A-Share Quant Dashboard — Chan Theory (缠论)

A quantitative trading dashboard for China A-share market, featuring Chan Theory (缠论) strategy backtesting with interactive charts and professional portfolio analytics.

## Features

- **Two-tab Streamlit dashboard**
  - **Portfolio Overview** — QuantStats tearsheet with performance metrics, drawdown analysis, and trade history (benchmarked against CSI 300)
  - **Stock Analysis** — Per-stock interactive Bokeh charts powered by backtesting.py
- **Chan Theory strategy engine** — Fractal → Pen → Hub → Divergence → Signal pipeline with BUY/SELL signal generation
- **Portfolio backtesting** — Multi-stock backtest with max 5 concurrent positions, 30% sizing, and 100-share lot constraints
- **A-share market data** — SQLite database with ~1,940 stocks and 5 years of daily K-line data

## Tech Stack

| Layer | Technology |
|-------|------------|
| UI | Streamlit |
| Charting | backtesting.py (Bokeh), QuantStats, Plotly |
| Strategy | Chan Theory (custom engine) |
| Data | pandas, SQLite (market.db), AKShare |
| Quality | pytest, mypy, Ruff |

## Quick Start

```bash
# Install dependencies (Python ≥ 3.13)
pip install -r requirements.txt

# Launch the dashboard
streamlit run streamlit_app.py
```

## Project Structure

```
quant-dashboard/
├── streamlit_app.py          # Main dashboard (two-tab layout)
├── src/
│   ├── data_layer/           # SQLite market data reader
│   ├── strategy/             # Chan Theory signal engine
│   ├── backtest/             # Portfolio-level backtest engine
│   ├── adapters/             # backtesting.py data/strategy adapters
│   └── reporting/            # QuantStats tearsheet generation
├── tests/                    # Test suite (177 tests)
├── data/                     # Market database (market.db)
├── requirements.txt
└── pyproject.toml
```

## Testing

```bash
pytest
```

## License

Private — internal use only.
