# User Testing Guide — A-Share Quant Dashboard

## Environment Setup

- **Server**: Streamlit on port 8020
- **Start command**: `cd /Users/wendy/work/trading-co/quant-dashboard && python3 -m streamlit run streamlit_app.py --server.port 8020 --server.headless true`
- **Healthcheck**: `curl -sf http://localhost:8020/_stcore/health` → `ok`
- **No authentication required**: Streamlit app is open to any visitor

## CSI 300 Data

- CSI 300 data is fetched via AkShare when the IndexFetcher is called
- Stored in `data/index_cache.db`
- Available automatically in the Streamlit app when benchmarks are rendered

## Validation Concurrency

### Surface: Browser (Streamlit)
- Max concurrent validators: 1
- Streamlit uses session state per browser tab, but the backtest engine runs in a thread
- Running multiple validators simultaneously could cause race conditions with shared resources
- Serialize all browser-based tests

## Flow Validator Guidance: Browser (Streamlit)

### Isolation rules
- Only one browser validator at a time
- Each test session uses Streamlit's session state isolated per tab, but underlying data is shared
- The backtest can take a long time — wait for it to complete before asserting on results

### Testing approach
- Use `agent-browser` skill for all browser-based assertions
- **URL**: http://localhost:8020
- **No login required**: The Streamlit app loads directly without authentication
- **Backtest flow**:
  1. Navigate to http://localhost:8020
  2. The sidebar has: Strategy dropdown (should show "chan_theory"), date range pickers, initial capital, "Run Backtest" button
  3. Click "Run Backtest" button — a progress bar appears
  4. Wait for backtest to complete (may take 10-30 seconds)
  5. Results appear below with: Performance Summary, NAV chart, Drawdown chart, Trade List, etc.

### Key UI elements to verify
- **Strategy dropdown (VAL-UI-003)**: In the sidebar, the Strategy selectbox should list "chan_theory"
- **Controls (VAL-UI-001)**: Sidebar has Strategy selector, Start Date, End Date, Initial Capital, "Run Backtest" button
- **Progress (VAL-UI-004)**: After clicking "Run Backtest", a progress bar or spinner appears
- **Performance metrics (VAL-UI-007)**: After completion, the "Performance Summary" section shows 6 metric cards:
  - Total Return
  - Sortino Ratio  ← IMPORTANT: This was previously CAGR, now fixed to Sortino
  - Sharpe Ratio
  - Max Drawdown
  - Win Rate
  - Trade Count
- **NAV chart (VAL-UI-005)**: Interactive Plotly chart showing strategy equity curve
- **Benchmarks (VAL-BENCH-001, VAL-BENCH-002)**: On the NAV chart, CSI 300 and ChiNext lines with different colors/styles
- **Trade list (VAL-UI-006)**: Table showing Stock, Entry Date, Exit Date, Entry Price, Exit Price, P&L, P&L%, Hold Days
- **End-to-end (VAL-CROSS-001)**: Complete flow from selection through results with all metrics + charts + trades
- **Accessibility (VAL-CROSS-002)**: App loads in any browser without installation

### Known issues from previous rounds
- Round 1 (streamlit-pivot): VAL-UI-007 FAILED because "Sortino Ratio" was displayed as "CAGR". This has been fixed in commit 017652f — the CAGR metric card was replaced with Sortino Ratio.
- VAL-CROSS-001 FAILED because Sortino was missing (transitive dependency on VAL-UI-007). Now that Sortino is added, this should pass.
