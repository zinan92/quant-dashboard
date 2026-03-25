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

## Flow Validator Guidance: agent-browser

**App URL:** http://localhost:8020
**Auth credentials:** username=`admin`, password=`admin`
**Testing tool:** `agent-browser` skill (invoke via Skill tool at start of session)

### FreqUI Login Flow:
1. Navigate to http://localhost:8020 — FreqUI login page loads
2. The login page has fields for server URL, username, and password
3. Server URL should already be populated (or set to `http://localhost:8020`)
4. Enter username `admin` and password `admin`
5. Click the Login button
6. Dashboard should load — look for connected state (no red/orange error banners)

### FreqUI Navigation:
- **Dashboard/Home:** Shows bot status, open trades (empty in webserver mode)
- **Backtest page:** Access via sidebar or direct URL http://localhost:8020/backtest
  - Strategy dropdown to select `chan_theory`
  - Date range selector
  - "Start Backtest" button
  - After completion: equity curve chart, trade list table, performance metrics
- **Trade History:** Access via sidebar

### Backtest Flow in FreqUI:
1. Navigate to Backtest page
2. Select `chan_theory` from strategy dropdown
3. Optionally set timerange (default should work)
4. Click "Start" or equivalent button
5. Wait for completion (should be fast, <10 seconds)
6. Results appear: equity curve, trade table, metrics summary

### Known quirks:
- Some backtest metrics may show "undefined" or "N/A" for fields FreqUI expects but our backend doesn't populate exactly right. This is a known non-blocking issue.
- The backtest completes near-instantly so progress bar may not be visible.
- After login, FreqUI may poll several endpoints — wait a moment for the dashboard to stabilize.

### Isolation rules:
- Each browser subagent uses its own agent-browser session (based on worker session ID)
- Backtest operations mutate global state — only ONE subagent should run backtests
- Login/navigation tests are read-only and can run in parallel

### Evidence:
- Take screenshots at key moments (login page, dashboard, backtest results, etc.)
- Save evidence files to the mission's evidence directory
- Check browser console for JavaScript errors (VAL-CROSS-003)

### Report format:
Write a JSON report to `.factory/validation/frontend/user-testing/flows/<group-id>.json` with:
```json
{
  "groupId": "<group-id>",
  "assertions": [
    {
      "id": "VAL-XXX-NNN",
      "status": "pass" | "fail" | "blocked",
      "reason": "description of what was observed",
      "evidence": "screenshot filename or description"
    }
  ],
  "frictions": [],
  "blockers": [],
  "toolsUsed": ["agent-browser"]
}
```

---

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
