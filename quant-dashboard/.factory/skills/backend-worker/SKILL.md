---
name: backend-worker
description: Python backend worker for adapter, reporting, and dashboard features
---

# Backend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

Any feature involving Python backend code: data adapters, strategy wrappers, reporting modules, commission models, and Streamlit dashboard code.

## Required Skills

None — this worker uses standard pytest and Python tooling.

## Work Procedure

1. **Read the feature description** carefully. Understand preconditions, expected behavior, and verification steps.

2. **Read AGENTS.md** for mission boundaries. DO NOT modify frozen modules (src/strategy/, src/backtest/, src/data_layer/).

3. **Write tests first** (TDD):
   - Create test file in the appropriate tests/ subdirectory
   - Write failing tests that cover the expected behavior from the feature description
   - Run `pytest tests/ -v` to confirm tests fail (red phase)

4. **Implement the code**:
   - Create/modify source files as specified in the feature description
   - Follow existing code style (type hints, docstrings)
   - Run `pytest tests/ -v` to confirm tests pass (green phase)

5. **Run full test suite**:
   - `pytest tests/ -v` — ALL tests must pass (133 baseline + new)
   - Fix any regressions before proceeding

6. **Manual verification** (if feature involves Streamlit UI):
   - Start: `streamlit run streamlit_app.py --server.port 8501 --server.headless true &`
   - Verify the feature works as described
   - Kill the process when done

7. **Commit** with a descriptive message.

## Example Handoff

```json
{
  "salientSummary": "Implemented data adapter with title-case column conversion, DatetimeIndex, and A-share commission model. 6 new tests pass, all 133 existing tests unaffected.",
  "whatWasImplemented": "Created src/adapters/backtesting_adapter.py with prepare_backtesting_data() for column renaming and DatetimeIndex conversion, and ashare_commission() for A-share fee model (0.03% + 0.1% stamp tax on sells, min ¥5). Created tests/adapters/test_backtesting_adapter.py with 6 test cases.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {"command": "pytest tests/ -v", "exitCode": 0, "observation": "139 passed (133 existing + 6 new)"},
      {"command": "python -c \"from src.adapters.backtesting_adapter import prepare_backtesting_data, ashare_commission; print('OK')\"", "exitCode": 0, "observation": "Module imports successfully"}
    ],
    "interactiveChecks": []
  },
  "tests": {
    "added": [
      {
        "file": "tests/adapters/test_backtesting_adapter.py",
        "cases": [
          {"name": "test_columns_title_case", "verifies": "Output DataFrame has Open/High/Low/Close/Volume columns"},
          {"name": "test_datetime_index", "verifies": "Output has DatetimeIndex, monotonically increasing"},
          {"name": "test_buy_commission_minimum", "verifies": "Buy commission applies ¥5 minimum"},
          {"name": "test_sell_commission_with_stamp_tax", "verifies": "Sell commission includes 0.1% stamp tax"},
          {"name": "test_sell_commission_above_minimum", "verifies": "Large trades exceed minimum fee"},
          {"name": "test_indicator_columns_preserved", "verifies": "Dif/Dea/Macd columns present in output"}
        ]
      }
    ]
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Cannot import from frozen modules (broken dependency)
- backtesting.py API differs from expected (plot() doesn't produce HTML)
- QuantStats API differs from expected (reports.html() signature changed)
- market.db is inaccessible or has unexpected schema
- Existing tests fail before any changes are made
