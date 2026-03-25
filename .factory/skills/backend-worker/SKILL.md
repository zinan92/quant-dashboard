---
name: backend-worker
description: Implements Python backend features — API endpoints, strategy engine, backtest engine, data layer
---

# Backend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Features involving:
- FastAPI API endpoint implementation (FreqTrade-compatible)
- Chan Theory strategy engine (quantitative implementation)
- Backtest engine (signal generation, trade simulation, NAV calculation)
- Data layer (reading market.db, fetching index data via AkShare)
- JWT authentication
- Pydantic schema definitions
- Python unit tests

## Required Skills

None.

## Work Procedure

1. **Read context**: Read `AGENTS.md`, `.factory/library/architecture.md`, and `.factory/library/environment.md` to understand the project structure, API compatibility requirements, and data sources.

2. **Read existing code**: Before writing anything, read all existing files in the relevant directories (app/, src/, tests/) to understand current state and avoid conflicts.

3. **Write tests first (RED)**: For every piece of functionality:
   - Write pytest tests that cover the expected behavior
   - Run `python3 -m pytest tests/ -v --tb=short -x` and confirm they FAIL (red)
   - Cover: happy path, edge cases, error cases

4. **Implement (GREEN)**: Write the implementation code to make tests pass.
   - Run tests again and confirm they PASS (green)
   - For API endpoints: verify response schemas match FreqTrade format exactly
   - For strategy engine: verify signals are generated correctly on test data

5. **Manual verification**: 
   - For API endpoints: use `curl` to test against the running server
   - Start the server: `cd /Users/wendy/work/trading-co/quant-dashboard && python3 -m uvicorn app.main:app --port 8020 &`
   - Test each endpoint with curl and verify response format
   - Stop the server after testing: `lsof -ti :8020 | xargs kill 2>/dev/null || true`

6. **CRITICAL — 404 not 500**: If implementing the API router or catch-all, ensure ANY unimplemented endpoint returns `{"detail": "Not found"}` with status 404, NEVER 500. FreqUI breaks entirely on 500.

7. **CRITICAL — API timestamps**: All timestamps in API responses must be millisecond epoch (multiply seconds by 1000). FreqUI uses JavaScript Date which expects milliseconds.

8. **Run full test suite**: `python3 -m pytest tests/ -v --tb=short -x`

## Example Handoff

```json
{
  "salientSummary": "Implemented 6 FreqTrade-compatible API endpoints (ping, version, show_config, profit, daily, trades) with JWT auth middleware. All return correct schemas verified by curl. pytest: 18 tests passing.",
  "whatWasImplemented": "FastAPI app with JWT auth (login/refresh), system endpoints (ping returns {status:pong}, version, show_config with runmode=webserver), profit endpoint returning NAV metrics from backtest.db, daily endpoint returning per-day P&L array, trades endpoint with pagination. SPA fallback serving frontend/dist/index.html for non-API routes. Catch-all returning 404 JSON for unimplemented /api/v1/* paths.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {"command": "cd /Users/wendy/work/trading-co/quant-dashboard && python3 -m pytest tests/ -v --tb=short -x", "exitCode": 0, "observation": "18 tests passed, 0 failed"},
      {"command": "curl -s http://localhost:8020/api/v1/ping", "exitCode": 0, "observation": "Returns {\"status\":\"pong\"}"},
      {"command": "curl -s -X POST http://localhost:8020/api/v1/token/login -u admin:admin", "exitCode": 0, "observation": "Returns access_token and refresh_token"},
      {"command": "curl -s http://localhost:8020/api/v1/nonexistent", "exitCode": 0, "observation": "Returns 404 JSON, not 500"}
    ],
    "interactiveChecks": []
  },
  "tests": {
    "added": [
      {"file": "tests/test_auth.py", "cases": [
        {"name": "test_login_success", "verifies": "Valid credentials return JWT tokens"},
        {"name": "test_login_invalid", "verifies": "Invalid credentials return 401"},
        {"name": "test_protected_endpoint_no_auth", "verifies": "Protected endpoint returns 401 without token"}
      ]},
      {"file": "tests/test_system.py", "cases": [
        {"name": "test_ping", "verifies": "Ping returns {status: pong}"},
        {"name": "test_show_config", "verifies": "Config has runmode=webserver and all required fields"}
      ]}
    ]
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- The ashare market.db file is missing or inaccessible
- FreqUI expects a response field not documented in AGENTS.md or library files
- Backtest takes longer than 60 seconds for the stock universe
- A dependency (akshare, pyjwt, etc.) fails to install
