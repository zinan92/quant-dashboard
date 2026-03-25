# FreqUI Compatibility Notes

**What belongs here:** Discovered compatibility requirements between our FastAPI backend and FreqUI.

---

## Polling Endpoints

FreqUI periodically polls these endpoints on every refresh cycle. ALL must return valid JSON (200), never 500:
- `/api/v1/whitelist`
- `/api/v1/blacklist`
- `/api/v1/status`
- `/api/v1/profit`
- `/api/v1/sysinfo` — returns `{cpu_pct: [...], ram_pct: float}`

## show_config Required Fields

FreqUI expects these fields in `/api/v1/show_config` response:
- `runmode`: Must be `"webserver"` for backtest features
- `api_version`: `2.34` or higher for strategy parameter features
- `timerange`: String like `"20251103-20260324"` — FreqUI's `TimeRangeSelect.vue` calls `.split("-")` on this; missing field causes TypeError
- `stake_currency`, `strategy`, `exchange`, `bot_name`, `timeframe`, `state`, `dry_run`, `trading_mode`

## Known Display Quirks

- Some backtest result fields show "Tot Profit undefined" and "N/A (undefinedx)" in FreqUI. Likely related to missing fields in the backtest result schema or CNY currency handling. Non-blocking but could be improved.

## CSI 300 Data Seeding

CSI 300 (沪深300) index data is NOT in ashare's `market.db`. It must be fetched via AkShare and stored in `data/index_cache.db`. The `seed_csi300.py` script handles this. Without seeding, the `/api/v1/backtest/history/{filename}/market_change` endpoint returns empty data.

## Build Requirement

`frontend/dist/` is excluded by `.gitignore`. After fresh clone, run `pnpm install && pnpm run build` in `frontend/` before starting the server.
