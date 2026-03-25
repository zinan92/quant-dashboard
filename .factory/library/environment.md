# Environment

**What belongs here:** Required env vars, external dependencies, data paths, setup notes.
**What does NOT belong here:** Service ports/commands (use `.factory/services.yaml`).

---

## Data Sources

- **ashare market.db**: `/Users/wendy/work/trading-co/ashare/data/market.db` (READ ONLY)
  - 422 A-share stocks with daily K-lines (symbol_type=STOCK, timeframe=DAY)
  - 421 stocks with 30-min K-lines (symbol_type=STOCK, timeframe=MINS_30)
  - 5 indices: 上证指数(000001.SH), 深证成指(399001.SZ), 创业板指(399006.SZ), 科创50(000688.SH), 北证50(899050.BJ)
  - Data range: ~2025-11-03 to 2026-03-24
  - MACD indicators (dif, dea, macd) already in klines table columns
  - `trade_calendar` table with `is_trading_day` flags for 2026
  - `stock_basic` table with 5,478 A-share stocks listing info
  - **CSI 300 (沪深300) is NOT in market.db** — must be supplemented via AkShare

- **AkShare**: Used to fetch CSI 300 index data. Free, no API key needed.
  - `pip install akshare`
  - Function: `ak.index_zh_a_hist(symbol="000300", period="daily")`

## Python Environment

- Python 3.13.7 available at `/opt/homebrew/bin/python3`
- No virtualenv — install globally or create one in project
- Key packages needed: fastapi, uvicorn, pyjwt, akshare, pandas, numpy, ruff, pytest, mypy

## Node.js Environment

- Node.js 25.8.1
- pnpm 10.30.3
- Used for building FreqUI frontend

## Chan Theory Strategy YAML

Source URL: https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/strategies/chan_theory.yaml

Key mechanical rules to implement:
- Fractal (分型): Top fractal = bar where high > both neighbors' highs. Bottom fractal = bar where low < both neighbors' lows.
- Pen (笔): Alternating top-bottom fractals with at least 4 bars between them.
- Hub (中枢): Overlapping price range of at least 3 consecutive strokes.
- MACD divergence: Price new high + MACD histogram area shrinking = top divergence (sell). Price new low + MACD histogram area shrinking = bottom divergence (buy).
- Buy points: 一买 = bottom divergence at last hub in downtrend. 二买 = first pullback after leaving down-hub doesn't break hub high. 三买 = breakout above hub that holds.
