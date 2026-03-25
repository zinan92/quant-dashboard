#!/bin/bash
set -e

cd /Users/wendy/work/trading-co

# Create project directory if not exists
mkdir -p quant-dashboard/{app,src,tests,data,frontend,strategies}
mkdir -p quant-dashboard/app
mkdir -p quant-dashboard/src/{strategy,backtest,data_layer}
mkdir -p quant-dashboard/tests

# Install Python dependencies if requirements.txt exists
if [ -f quant-dashboard/requirements.txt ]; then
  cd quant-dashboard
  python3 -m pip install -r requirements.txt -q 2>/dev/null || true
  cd ..
fi

# Verify ashare market.db is accessible
if [ ! -f /Users/wendy/work/trading-co/ashare/data/market.db ]; then
  echo "WARNING: ashare market.db not found at expected path"
fi

echo "Init complete. ashare market.db accessible: $(test -f /Users/wendy/work/trading-co/ashare/data/market.db && echo YES || echo NO)"
