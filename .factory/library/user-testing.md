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

## Flow Validator Guidance: shell (data-infra-fix)

**Testing surface:** Shell commands — sqlite3 queries, code inspection (grep/read), CLI script execution
**Tool:** No special skill needed — use Execute, Read, Grep tools directly
**Project root:** `/Users/wendy/work/trading-co/ashare`
**Database:** `data/market.db` (SQLite, use `sqlite3 data/market.db "<query>"` from project root)
**Python venv:** `.venv/bin/python` from project root

### What to test:
- Code inspection: Check source files for specific values (retention days, INDEX_LIST contents, config defaults, cleanup invocation patterns)
- Database queries: Verify trade_calendar date range/count, watchlist/stock_sectors row counts, pre-expansion stock preservation
- CLI execution: Run pytest collect, run expansion script

### Isolation rules:
- All assertions are read-only (code inspection + database SELECT queries + non-destructive CLI commands)
- No shared mutable state between assertions
- **Exception:** VAL-INFRA-013 (expansion script) could modify the database if run — but the expansion was already run during implementation. Verify the script exists and runs without error in a safe way (--help, dry-run, or just check exit code if it's idempotent).
- All subagents can run in parallel since they only read

### Evidence format:
Write a JSON report to `.factory/validation/data-infra-fix/user-testing/flows/<group-id>.json` with:
```json
{
  "groupId": "<group-id>",
  "assertions": [
    {
      "id": "VAL-INFRA-NNN",
      "status": "pass" | "fail" | "blocked",
      "reason": "description of what was observed",
      "evidence": "command output or code snippet"
    }
  ],
  "frictions": [],
  "blockers": [],
  "toolsUsed": ["sqlite3", "grep", "python"]
}
```

---

## Flow Validator Guidance: shell (historical-backfill)

**Testing surface:** Shell commands — sqlite3 queries, code inspection (grep/read), CLI script execution
**Tool:** No special skill needed — use Execute, Read, Grep tools directly
**Project root:** `/Users/wendy/work/trading-co/ashare`
**Database:** `data/market.db` (SQLite, use `sqlite3 data/market.db "<query>"` from project root)
**Python venv:** `.venv/bin/python` from project root
**Mission dir:** `/Users/wendy/.factory/missions/5ccfbb11-945c-4b92-969a-cfbdf3f9d668`

### What to test:
- **Database queries**: Verify stock/index/concept/industry data completeness, row counts, date ranges, null checks
- **Code inspection**: Check backfill scripts for TuShare API usage, rate limiting, resume logic, error handling
- **CLI execution**: Verify backfill scripts can be invoked from command line (check --help or import without error)

### Key data state (as of this run):
- 423 distinct stocks in klines (DAY), 1938 in watchlist
- 8 indices all present (7 with 1264 rows, 899050.BJ with 789 rows)
- Stock data ranges: 2021-01-04 to 2026-03-25
- Concept daily: only 2026-01-29 to 2026-03-25 (~2 months, 396 codes)
- Industry daily: only 2026-01-29 to 2026-03-25 (~2 months, 90 codes)
- Most stocks have only 50-199 rows (NOT full 5-year backfill)

### Database conventions:
- `symbol_type` is 'STOCK' or 'INDEX' (uppercase)
- `timeframe` is 'DAY' or 'MINS_30' (uppercase)
- `trade_time` is datetime format 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD'
- `concept_daily.trade_date` and `industry_daily.trade_date` are string format 'YYYYMMDD'

### Isolation rules:
- All assertions are read-only (database SELECT + code inspection + non-destructive CLI)
- No shared mutable state — all subagents can run in parallel
- Do NOT run backfill scripts that would modify the database — just verify they exist and can import

### Evidence format:
Write a JSON report to `.factory/validation/historical-backfill/user-testing/flows/<group-id>.json` with:
```json
{
  "groupId": "<group-id>",
  "assertions": [
    {
      "id": "VAL-BACKFILL-NNN",
      "status": "pass" | "fail" | "blocked",
      "reason": "description of what was observed",
      "evidence": "command output or code snippet"
    }
  ],
  "frictions": [],
  "blockers": [],
  "toolsUsed": ["sqlite3", "grep", "python"]
}
```

---

## Flow Validator Guidance: pytest (backtest-adapters)

**Testing surface:** Python unit tests via pytest
**Tool:** No special skill needed — use Execute tool with `.venv/bin/python -m pytest`
**Project root:** `/Users/wendy/work/trading-co/quant-dashboard`
**Python venv:** `.venv/bin/python` from project root
**Database:** `/Users/wendy/work/trading-co/ashare/data/market.db` (read-only SQLite, symlinked to `data/market.db`)
**Mission dir:** `/Users/wendy/.factory/missions/5ccfbb11-945c-4b92-969a-cfbdf3f9d668`

### What to test:
- Run specific existing tests that validate each assertion in the validation contract
- Verify test output confirms the assertion's expected behavior
- For assertions not covered by existing tests, write and run targeted test scripts

### Key test files:
- `tests/adapters/test_backtesting_adapter.py` — VAL-ADAPTER-001 through VAL-ADAPTER-005, VAL-ADAPTER-009
- `tests/adapters/test_chan_theory_bt.py` — VAL-ADAPTER-006, VAL-ADAPTER-007, VAL-ADAPTER-008
- `tests/reporting/test_tearsheet.py` — VAL-REPORT-001 through VAL-REPORT-005

### Isolation rules:
- All assertions are read-only (unit tests + database SELECT queries)
- No shared mutable state between assertions — subagents can run in parallel
- backtesting.py tests use class variables on ChanTheoryBTStrategy — must be serialized within a subagent

### Evidence format:
Write a JSON report to `.factory/validation/backtest-adapters/user-testing/flows/<group-id>.json` with:
```json
{
  "groupId": "<group-id>",
  "assertions": [
    {
      "id": "VAL-XXX-NNN",
      "status": "pass" | "fail" | "blocked",
      "reason": "description of what was observed",
      "evidence": "test output or command result"
    }
  ],
  "frictions": [],
  "blockers": [],
  "toolsUsed": ["pytest"]
}
```

---

## Discovered Testing Knowledge (Historical-Backfill Milestone)

### stock_basic JOIN key
- `klines.symbol_code` uses plain codes (e.g., `000001`)
- `stock_basic.ts_code` uses exchange-suffixed codes (e.g., `000001.SZ`)
- **Must JOIN on `stock_basic.symbol`** (which is plain code) when cross-referencing with klines
- Using `stock_basic.ts_code` for JOIN will silently return 0 matches

### Backfill state (round 3, 2026-03-26)
- 55 pre-2021 expanded universe stocks still not backfilled (only ~148-152 rows from 2025-07/08)
- 162 watchlist stocks with no kline data at all
- Total 214 of 1614 pre-2021 watchlist stocks missing early data

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

## Flow Validator Guidance: agent-browser (dashboard-rewrite)

**App URL:** http://localhost:8020
**Auth:** None required — Streamlit app loads directly, no login needed.
**Testing tool:** `agent-browser` skill (invoke via Skill tool at start of session)
**Session naming:** Use `--session "3b6187199a80__browser"` for browser sessions.

### Dashboard-Rewrite Layout (NEW — 2-tab design):
- **Sidebar (left):** Backtest Configuration panel with:
  - "Strategy" dropdown (should list `chan_theory`)
  - "Start Date" and "End Date" date pickers
  - "Initial Capital" number input
  - "🚀 Run Backtest" button
- **Main area (center):** Two tabs: "Portfolio Overview" and "Stock Analysis"
  - Before running: may show welcome message or empty state
  - After running backtest:
    - **Tab 1 "Portfolio Overview":** 6 metric cards (Total Return, CAGR, Sharpe, Sortino, Max Drawdown, Win Rate), embedded QuantStats HTML tearsheet via `st.components.v1.html()`, expandable trade history
    - **Tab 2 "Stock Analysis":** Stock dropdown for traded stocks, backtesting.py Bokeh chart embedded via `st.components.v1.html()`, per-stock metrics

### Key testing steps for dashboard-rewrite:
1. Navigate to http://localhost:8020
2. Verify sidebar controls (strategy selector, dates, capital, run button)
3. Verify two tabs visible: "Portfolio Overview" and "Stock Analysis"
4. Click "🚀 Run Backtest" in sidebar
5. Wait for backtest completion (under 2 seconds typically)
6. Check Portfolio Overview tab: metric cards + QuantStats tearsheet iframe
7. Switch to Stock Analysis tab: stock dropdown + Bokeh chart
8. Switch back to Portfolio Overview: verify results preserved (no re-run)

### Important notes:
- The dashboard uses `st.components.v1.html()` for both QuantStats and Bokeh charts — these render as iframes
- No st.pyplot() calls should exist in the source code
- Charts are embedded HTML, not native Streamlit elements
- Scrolling within Streamlit: use `--selector [data-testid=stMain]` for main area scrolling
- Backtest is very fast (<2s) — you may not see the progress bar

### Isolation rules:
- One browser session is sufficient — all assertions are sequential
- Backtest modifies session_state but only within one browser tab

### Evidence format:
Write a JSON report to `.factory/validation/dashboard-rewrite/user-testing/flows/<group-id>.json`

## Flow Validator Guidance: shell (dashboard-rewrite)

**Testing surface:** Shell commands — pytest, python -c, git diff, grep
**Tool:** No special skill needed — use Execute, Read, Grep tools directly
**Project root:** `/Users/wendy/work/trading-co/quant-dashboard`
**Mission dir:** `/Users/wendy/.factory/missions/5ccfbb11-945c-4b92-969a-cfbdf3f9d668`

### What to test:
- VAL-CROSS-002: `cd /Users/wendy/work/trading-co/quant-dashboard && python3 -m pytest tests/ -v --tb=short` exits 0
- VAL-CROSS-003: `cd /Users/wendy/work/trading-co/quant-dashboard && python3 -c "from src.backtest.engine import BacktestEngine; from src.strategy.chan_theory import ChanTheoryStrategy; print('OK')"`
- VAL-CROSS-004: `cd /Users/wendy/work/trading-co/quant-dashboard && git diff HEAD -- src/backtest/engine.py` shows no changes
- VAL-CROSS-005: `cd /Users/wendy/work/trading-co/quant-dashboard && python3 -m pytest tests/adapters/ tests/reporting/ -v --tb=short` shows ≥8 new tests passing
- VAL-DASH-007 (code part): `grep -n 'st.pyplot' /Users/wendy/work/trading-co/quant-dashboard/streamlit_app.py` returns no matches

### Isolation rules:
- All assertions are read-only — can run in any order or parallel
- No shared mutable state

### Evidence format:
Write a JSON report to `.factory/validation/dashboard-rewrite/user-testing/flows/shell-assertions.json`

---

## Flow Validator Guidance: agent-browser (ux-enhancements)

**App URL:** http://localhost:8020
**Auth:** None required — Streamlit app loads directly, no login needed.
**Testing tool:** `agent-browser` skill (invoke via Skill tool at start of session)

### UX Enhancements Layout:
The ux-enhancements milestone adds:
1. **Date range fix** — Start date min_value is 2021-01-01 (not 2025-11-01)
2. **Stock names** — Stock dropdown shows "TICKER - 股票名称" format
3. **Language switcher** — Sidebar has English/中文 selector at top
4. **i18n** — All UI text translates between English and Chinese

### Sidebar layout (top to bottom):
1. Language selector dropdown: `["English", "中文"]`
2. Divider
3. "⚙️ Backtest Configuration" (translated in Chinese mode)
4. Strategy dropdown
5. Date Range subheader
6. Start Date picker (min_value=2021-01-01)
7. End Date picker
8. Initial Capital input
9. "🚀 Run Backtest" button

### Testing workflow for UX assertions:
1. Navigate to http://localhost:8020
2. **VAL-UX-003**: Check sidebar for language selector. Should be a dropdown with "English" and "中文" options.
3. **VAL-UX-001**: Check start date picker. Try to select 2021-01-01 — it should be allowed (min_value is 2021-01-01).
4. **VAL-UX-004**: Ensure "English" is selected. Verify all UI labels are in English: tab names ("📊 Portfolio Overview", "📈 Stock Analysis"), sidebar ("Strategy", "Start Date", "End Date"), button ("🚀 Run Backtest").
5. **VAL-UX-005**: Switch language to "中文". Verify all UI labels change to Chinese: tab names ("📊 投资组合概览", "📈 个股分析"), sidebar ("策略", "开始日期", "结束日期"), button ("🚀 运行回测").
6. Run a backtest (click the Run Backtest button, wait for completion).
7. **VAL-UX-006**: With 中文 selected, scroll to the QuantStats tearsheet iframe. Verify it shows Chinese section headers/labels.
8. **VAL-UX-007**: Switch back to English. The QuantStats tearsheet should show English labels.
9. **VAL-UX-002**: Switch to Stock Analysis tab. Check the stock dropdown — it should show format "000001 - 平安银行" (ticker + Chinese name).

### Scrolling in Streamlit:
- Use `--selector "[data-testid=stMain]"` for scrolling the main content area
- QuantStats tearsheet is embedded in an iframe via `st.components.v1.html()`

### Important quirks:
- Language switching causes a Streamlit rerun — the page reloads
- After switching language, you may need to re-run the backtest (session_state["backtest_result"] may persist but the page rerenders)
- The language selector is at the TOP of the sidebar, before other controls
- Stock names are loaded from `stock_basic` table in market.db

### Isolation rules:
- Single browser session — all assertions are sequential (language switching is global)
- Backtest modifies session_state — only one browser instance

### Evidence format:
Write a JSON report to `.factory/validation/ux-enhancements/user-testing/flows/<group-id>.json` with:
```json
{
  "groupId": "<group-id>",
  "assertions": [
    {
      "id": "VAL-UX-NNN",
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

## Flow Validator Guidance: shell (ux-enhancements)

**Testing surface:** Python unit test — verify stock names loaded from database
**Tool:** Execute tool with Python
**Project root:** `/Users/wendy/work/trading-co/quant-dashboard`
**Database:** `/Users/wendy/work/trading-co/ashare/data/market.db`

### What to test:
- VAL-UX-008: Stock names are fetched from `stock_basic` table in market.db. Run:
  ```
  cd /Users/wendy/work/trading-co/quant-dashboard && python3 -c "
  from src.adapters.backtesting_adapter import get_stock_names
  from src.data_layer.market_reader import MarketReader
  reader = MarketReader()
  names = get_stock_names(reader)
  # Check that at least some names are returned and they're non-empty
  assert len(names) > 0, f'Expected stock names, got {len(names)}'
  # Check a known ticker has a name
  assert '000001' in names or any('000001' in k for k in names), 'Missing 000001'
  print(f'Got {len(names)} stock names')
  # Show a sample
  for k, v in list(names.items())[:5]:
      print(f'  {k} -> {v}')
  print('VAL-UX-008: PASS')
  "
  ```

### Isolation rules:
- Read-only — no shared state

### Evidence format:
Write a JSON report to `.factory/validation/ux-enhancements/user-testing/flows/shell-ux.json`
