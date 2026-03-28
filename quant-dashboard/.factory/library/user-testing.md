# User Testing

## Validation Surface

**Primary surface**: Streamlit web dashboard at http://localhost:8501
**Tool**: agent-browser for UI assertions (dashboard rendering, tab switching, chart visibility)
**Secondary**: pytest for unit/integration assertions (adapter, reporting, cross-feature)

## Validation Concurrency

**agent-browser**: Max concurrent 3 (Streamlit + Bokeh rendering is moderately heavy)
**python/pytest**: Max concurrent 5 (lightweight)

## Setup Requirements

1. `pip install -r requirements.txt` (includes backtesting, quantstats)
2. market.db must be accessible at `/Users/wendy/work/trading-co/ashare/data/market.db`
3. Start Streamlit: `streamlit run streamlit_app.py --server.port 8501 --server.headless true`
4. Wait for healthcheck: `curl -sf http://localhost:8501`
