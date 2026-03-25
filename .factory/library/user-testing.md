# User Testing

**What belongs here:** Testing surface, required testing skills/tools, resource cost classification per surface.

---

## Validation Surface

**Primary surface:** Web browser at http://localhost:8020 (FreqUI SPA)
**Tool:** `agent-browser` for browser-based validation
**Secondary surface:** REST API endpoints via curl

### What to test via browser:
- FreqUI login page loads
- Login with credentials succeeds
- Dashboard connects (no error banners)
- Strategy dropdown shows chan_theory
- Backtest can be started and completes
- Equity curve chart renders
- Trade list table displays
- Performance metrics visible
- Deep link navigation works (/backtest, /trade)
- Fresh start with no data doesn't show errors

### What to test via curl:
- All 14+ MVP API endpoints return correct schemas
- Auth flow (login → token → authenticated request)
- Unimplemented endpoints return 404 JSON (not 500)
- API routes take precedence over SPA fallback

## Validation Concurrency

**Machine specs:** 16 GB RAM, 10 CPU cores
**Baseline usage:** ~6 GB used

### agent-browser surface:
- Dev server (FastAPI + static files): ~200 MB
- Each agent-browser instance: ~300 MB
- Headroom: 10 GB * 0.7 = 7 GB usable
- 5 instances = 1.5 GB + 200 MB server = 1.7 GB — well within budget
- **Max concurrent: 5**

### curl surface:
- Negligible resource usage
- **Max concurrent: 5**

---

## Flow Validator Guidance: curl

**API Base URL:** http://localhost:8020
**Auth credentials:** username=`freqtrader`, password=`freqtrader` (HTTP Basic Auth for login, JWT Bearer for subsequent requests)
**Default credentials may also be:** username=`admin`, password=`admin` — try both if one fails.

### Authentication flow:
1. POST /api/v1/token/login with HTTP Basic Auth header → get `access_token` and `refresh_token`
2. Use `Authorization: Bearer <access_token>` for all authenticated endpoints
3. POST /api/v1/token/refresh with `Authorization: Bearer <refresh_token>` → get new `access_token`

### Isolation rules:
- Each curl subagent operates on stateless GET endpoints or idempotent POST requests
- **Backtest assertions must be serialized** within the subagent that handles them — only one backtest can run at a time (global state)
- No write conflicts between subagents since only one group triggers backtest execution

### Response validation:
- Check HTTP status codes precisely (200, 401, 404)
- Parse JSON responses and verify field presence and types
- Empty arrays `[]` and objects `{}` are valid responses for "no data" scenarios
- All timestamps should be millisecond epoch integers
- Profit ratios are decimals (0.05 = 5%)

### Evidence format:
Write a JSON report to `.factory/validation/backend/user-testing/flows/<group-id>.json` with:
```json
{
  "groupId": "<group-id>",
  "assertions": [
    {
      "id": "VAL-XXX-NNN",
      "status": "pass" | "fail" | "blocked",
      "reason": "description of what was observed",
      "evidence": "curl command and response summary"
    }
  ],
  "frictions": [],
  "blockers": [],
  "toolsUsed": ["curl"]
}
```

## Discovered Testing Knowledge (Backend Milestone)

### Pair format
- The `pair_candles` endpoint uses **plain stock codes** (e.g., `000001`) NOT exchange-suffixed format (`000001.SZ`). The `available_pairs` and `whitelist` endpoints confirm this format.

### Index data limitation
- The `pair_candles` endpoint only queries `symbol_type='STOCK'` from market.db. Index data (ChiNext, CSI 300) is accessible via `MarketReader.get_index_klines()` in the data layer but is NOT exposed through any REST API endpoint.
- CSI 300 data is NOT in market.db and requires AkShare fetching via `IndexFetcher.fetch_and_store()`.

### Backtest speed
- Backtests for the full 422-stock universe over ~5 months complete near-instantly. The `running=true` intermediate polling state is only observable in the POST response, not during GET polling.

### Backtest history accumulation
- Each backtest run adds to the history without cleanup. History can grow large across test runs.

### Auth credentials
- Default: username=`admin`, password=`admin` (configurable via env vars `API_USERNAME`, `API_PASSWORD`)
