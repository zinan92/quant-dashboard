# User Testing

**What belongs here:** Testing surface, required testing skills/tools, resource cost classification per surface.

---

## Validation Surface

**Primary surface:** Web browser at http://localhost:8020 (Streamlit app)
**Tool:** `agent-browser` for browser-based validation
**No auth required:** Streamlit app has no login — loads directly.

### What to test via browser:
- Streamlit app loads at http://localhost:8020 with sidebar controls
- Strategy selector dropdown shows chan_theory
- Date picker and Run Backtest button visible
- Clicking Run Backtest shows progress, then results
- NAV chart renders with strategy equity curve
- Benchmark overlays (CSI 300, ChiNext) visible on NAV chart
- Trade list table displays individual trades
- Performance metrics section shows Sharpe, Sortino, Max Drawdown, Win Rate
- App is accessible from any browser without installation

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

## Flow Validator Guidance: agent-browser (Streamlit)

**App URL:** http://localhost:8020
**Auth:** None required — Streamlit app loads directly, no login needed.
**Testing tool:** `agent-browser` skill (invoke via Skill tool at start of session)

### Streamlit App Layout:
- **Sidebar (left):** Backtest Configuration panel with:
  - "Strategy" dropdown (should list `chan_theory`)
  - "Start Date" and "End Date" date pickers
  - "Initial Capital" number input
  - "🚀 Run Backtest" button (blue/primary)
- **Main area (center):** Title "📈 A-Share Quantitative Trading Dashboard"
  - Before running a backtest: shows welcome message with instructions
  - After running: shows results sections

### How to run a backtest:
1. Navigate to http://localhost:8020
2. In the sidebar, verify "chan_theory" is selected in Strategy dropdown
3. Leave date range and initial capital at defaults (or adjust if needed)
4. Click "🚀 Run Backtest" button
5. Main area shows progress spinner/bar with percentage
6. Wait for completion (usually 10-30 seconds for full universe)
7. Results appear in order:
   a. "📊 Performance Summary" — 6 metric cards (Total Return, CAGR, Sharpe Ratio, Max Drawdown, Win Rate, Trade Count)
   b. "📈 Net Asset Value" — Plotly chart with strategy curve + CSI 300 + ChiNext benchmark lines
   c. "📉 Drawdown Chart" — drawdown visualization
   d. "📋 Trade List" — table of individual trades
   e. "🔥 Monthly Returns Heatmap"
   f. "🏆 Per-Stock Performance" — bar chart

### Streamlit interaction quirks:
- Streamlit reruns the whole script on every widget interaction — this is normal behavior
- The sidebar's Strategy dropdown is a `st.selectbox` — click it to see options
- Date inputs are `st.date_input` — click to open calendar widget
- The "Run Backtest" button triggers a full rerun — wait for the spinner to complete
- Progress bar shows percentage during backtest execution
- After the backtest completes, scroll down to see all result sections
- If the page shows "Please wait..." it's running Streamlit's initial load — wait a moment

### Isolation rules:
- Each browser subagent uses its own agent-browser session
- Only ONE subagent should click "Run Backtest" (modifies session state)
- Read-only checks (page loads, UI element presence) can run in parallel

### Evidence:
- Take screenshots at key moments
- Save evidence files to the mission's evidence directory
- Check for any Streamlit error banners (red boxes with error messages)

### Report format:
Write a JSON report to `.factory/validation/streamlit-pivot/user-testing/flows/<group-id>.json` with:
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

## Discovered Testing Knowledge (Streamlit-Pivot Milestone)

### Streamlit internal scrolling
- Streamlit uses an internal scroll container with `[data-testid='stMain']` and `overflow-y: auto`. Regular page scrolling does not work in agent-browser. Must use `--selector [data-testid=stMain]` to scroll the content area.

### Backtest speed on Streamlit
- Backtest for 422 stocks completes in under 1 second via Streamlit. The `st.progress()` bar and spinners flash too quickly to capture in screenshots. Post-completion status messages (info + success) serve as evidence of the progress flow.

### Performance metrics displayed
- The Streamlit dashboard shows 6 metric cards: Total Return, CAGR, Sharpe Ratio, Max Drawdown, Win Rate, Trade Count.
- Sortino ratio is NOT displayed — the validation contract requires it but CAGR is shown in its place.

### Streamlit startup
- Start with: `python3 -m streamlit run streamlit_app.py --server.port 8020 --server.headless true`
- The `streamlit` command may not be in PATH — use `python3 -m streamlit` instead.
- Healthcheck: `curl -sf http://localhost:8020/_stcore/health`
