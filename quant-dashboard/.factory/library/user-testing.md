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
