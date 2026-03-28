#!/usr/bin/env bash
set -euo pipefail

cd /Users/wendy/work/trading-co/quant-dashboard

# Install dependencies (idempotent)
pip install -r requirements.txt

# Verify baseline tests pass
pytest tests/ -v --tb=short
