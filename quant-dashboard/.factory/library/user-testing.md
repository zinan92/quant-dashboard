# User Testing Guide — A-Share Quant Dashboard

## Environment Setup

- **Server**: FastAPI on port 8020
- **Start command**: `cd /Users/wendy/work/trading-co/quant-dashboard && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8020`
- **Healthcheck**: `curl -sf http://localhost:8020/api/v1/ping` → `{"status":"pong"}`
- **Credentials**: admin/admin (HTTP Basic Auth for login, Bearer JWT for subsequent requests)

## API Testing

- **Login**: `curl -X POST http://localhost:8020/api/v1/token/login -u admin:admin`
- **Authenticated requests**: Use `Authorization: Bearer <access_token>` header

## CSI 300 Data

- CSI 300 data is fetched via AkShare on server startup (seed_csi300.py / startup event)
- Stored in `data/index_cache.db`
- Available via pair_candles endpoint with symbol `000300.SH`

## Validation Concurrency

### Surface: API (curl)
- Max concurrent validators: 3
- Each validator can safely test different endpoints concurrently
- No shared mutable state between API read endpoints

## Flow Validator Guidance: API

### Isolation rules
- All validators can share the same server instance on port 8020
- Each validator should use its own JWT token (login separately)
- Read-only endpoints don't interfere with each other
- Backtest endpoints may conflict if multiple validators start backtests simultaneously — serialize backtest tests

### Testing approach
- Use `curl` for all API assertions
- Always check HTTP status code AND response body
- For CSI 300 data: check pair_candles endpoint with pair=000300.SH&timeframe=1d

## Validation Concurrency: Browser
- Max concurrent validators: 1
- Browser tests share a single FreqUI instance and backend
- Running multiple browser validators simultaneously could cause race conditions with backtest state

## Flow Validator Guidance: Browser (FreqUI)

### Isolation rules
- Only one browser validator at a time (FreqUI is a single-page app with global state)
- The backend has a singleton backtest engine — only one backtest runs at a time
- Validators must wait for any running backtest to complete before starting a new one

### Testing approach
- Use `agent-browser` skill for all browser-based assertions
- **URL**: http://localhost:8020
- **Login flow**: Enter server URL as http://localhost:8020, username: admin, password: admin
- **Backtest flow**: After login, navigate to Backtest view, select chan_theory strategy, run backtest, wait for completion
- **Performance metrics (VAL-UI-007)**: After backtest completes, look for summary metrics table showing win rate, profit factor, Sharpe, max drawdown. These should be visible in the backtest results panel.
- **Benchmark comparison (VAL-BENCH-002)**: After backtest, FreqUI may show market_change data if the endpoint responds correctly. The market change endpoint is at `/api/v1/backtest/history/{filename}/market_change`.
- **Console errors (VAL-CROSS-003)**: After navigating through the UI, check browser console for JavaScript TypeErrors and other errors. Some warnings are acceptable; focus on errors that break functionality.

### Known issues from previous rounds
- Round 1: Timestamp RangeError and .split errors — these were fixed by changing timestamp format
- Round 2: Missing strategy_comparison, exit_reason_summary fields, trade missing stake_amount/leverage — these have been fixed in the backend
- Current state: Backend returns all required fields. Need to verify FreqUI now renders them correctly.

### FreqUI login specifics
- FreqUI login page has:
  - Server URL field (may be prefilled or need http://localhost:8020)
  - Username field
  - Password field
  - Login button
- After successful login, FreqUI connects and shows the dashboard
- Navigate to "Backtest" tab/panel to run backtests
