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
