---
name: frontend-worker
description: Handles FreqUI build, deployment, static file serving, and frontend integration verification
---

# Frontend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Features involving:
- Cloning and building FreqUI
- Configuring static file serving from FastAPI
- SPA routing (deep link fallback)
- FreqUI integration testing (verifying it connects to our backend)
- Benchmark comparison display
- Any frontend-facing changes

## Required Skills

- `agent-browser` — MUST invoke for all browser-based verification of FreqUI

## Work Procedure

1. **Read context**: Read `AGENTS.md`, `.factory/library/architecture.md`, and `.factory/library/user-testing.md`.

2. **Read existing code**: Check current state of `quant-dashboard/frontend/` and `quant-dashboard/app/main.py` (SPA routing).

3. **Build FreqUI** (if not already built):
   - Clone: `cd /Users/wendy/work/trading-co/quant-dashboard && git clone https://github.com/freqtrade/frequi.git frontend`
   - Install: `cd frontend && pnpm install`
   - Build: `pnpm run build`
   - Verify `frontend/dist/index.html` exists

4. **Configure static serving**: Ensure FastAPI serves:
   - `/api/v1/*` → API routes (must take precedence)
   - `/assets/*`, `*.js`, `*.css`, `*.ico` → Static files from `frontend/dist/`
   - All other routes → `frontend/dist/index.html` (SPA fallback)

5. **Write tests**: Test that the SPA routing works correctly:
   - API routes return JSON
   - Deep links return HTML (index.html)
   - Static assets return correct MIME types

6. **Manual verification with agent-browser**: This is CRITICAL.
   - Start the backend: `cd /Users/wendy/work/trading-co/quant-dashboard && python3 -m uvicorn app.main:app --port 8020 &`
   - Use `agent-browser` to:
     a. Navigate to http://localhost:8020
     b. Verify login page loads
     c. Enter credentials and log in
     d. Verify dashboard loads without error banners
     e. Navigate to backtest page
     f. Verify strategy dropdown shows chan_theory
     g. Take screenshots at each step
   - Stop the server after testing

7. **Each browser check = one interactiveChecks entry** with the full action sequence and observed result.

## Example Handoff

```json
{
  "salientSummary": "Built FreqUI from source, configured SPA routing in FastAPI. Verified via agent-browser: login works, dashboard connects, strategy dropdown shows chan_theory, backtest page loads. All 5 browser checks passed.",
  "whatWasImplemented": "Cloned FreqUI, built with pnpm (dist/ output 2.3MB). Added StaticFiles mount and SPA fallback route to app/main.py. API routes registered before static mount to ensure precedence. Deep links (/backtest, /trade) correctly serve index.html.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {"command": "cd /Users/wendy/work/trading-co/quant-dashboard/frontend && pnpm run build", "exitCode": 0, "observation": "Build successful, dist/ created"},
      {"command": "curl -s -o /dev/null -w '%{http_code}' http://localhost:8020/backtest", "exitCode": 0, "observation": "200 — SPA fallback working"},
      {"command": "curl -s -o /dev/null -w '%{content_type}' http://localhost:8020/api/v1/ping", "exitCode": 0, "observation": "application/json"}
    ],
    "interactiveChecks": [
      {"action": "Navigate to http://localhost:8020 in browser", "observed": "FreqUI login page with server URL field, username, password inputs"},
      {"action": "Enter http://localhost:8020 as server, admin/admin as credentials, click login", "observed": "Dashboard loads, shows connected state, no error banners"},
      {"action": "Navigate to Backtest page via sidebar", "observed": "Backtest panel with strategy dropdown, date range selector, run button"},
      {"action": "Open strategy dropdown", "observed": "chan_theory listed as available strategy"},
      {"action": "Navigate directly to http://localhost:8020/backtest (deep link)", "observed": "FreqUI loads correctly, shows backtest page"}
    ]
  },
  "tests": {
    "added": [
      {"file": "tests/test_spa_routing.py", "cases": [
        {"name": "test_api_route_returns_json", "verifies": "API routes return application/json"},
        {"name": "test_deep_link_returns_html", "verifies": "Non-API routes return index.html"},
        {"name": "test_static_assets_correct_mime", "verifies": "JS/CSS files have correct content types"}
      ]}
    ]
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- FreqUI build fails (dependency issues, Node.js version incompatibility)
- FreqUI shows persistent connection errors that can't be resolved by fixing API responses
- FreqUI expects endpoints not yet implemented in the backend
- Browser testing reveals that FreqUI's internal routing conflicts with our SPA fallback
