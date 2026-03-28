<div align="center">

# quant-dashboard

**A股缠论量化回测看板 — 从信号生成到组合分析的完整闭环**

[![Python](https://img.shields.io/badge/python-3.13+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/streamlit-1.31+-FF4B4B.svg)](https://streamlit.io)
[![Tests](https://img.shields.io/badge/tests-177%20passed-brightgreen.svg)]()

</div>

---

## 痛点

缠论（Chan Theory）是中文量化圈最流行的技术分析框架之一，但大多数实现要么只有信号生成没有回测，要么依赖第三方平台无法自定义。想要完整跑通「分型 → 笔 → 中枢 → 背驰 → 买卖点 → 组合回测 → 绩效报告」的全流程，往往需要拼凑多个工具。

## 解决方案

quant-dashboard 是一个本地运行的 Streamlit 看板，内置完整的缠论策略引擎和组合回测系统。一键启动即可对 ~1,940 只 A 股进行缠论信号扫描、多股组合回测，并生成专业级 QuantStats 绩效报告。中英文双语界面，支持交互式 Bokeh K 线图分析单个股票的买卖点。

## 架构

```
┌──────────────┐     ┌──────────────┐     ┌───────────────┐
│  AKShare      │────▶│  market.db   │────▶│  MarketReader  │
│  (数据采集)    │     │  (SQLite)    │     │  (只读访问)     │
└──────────────┘     └──────────────┘     └───────┬───────┘
                                                  │
                                                  ▼
┌──────────────┐     ┌──────────────┐     ┌───────────────┐
│  策略引擎      │────▶│  回测引擎     │────▶│  backtest.db   │
│  (缠论信号)    │     │  (组合管理)   │     │  (结果持久化)   │
└──────────────┘     └──────────────┘     └───────────────┘
                           │
                           ▼
                     ┌──────────────┐
                     │  Streamlit    │
                     │  看板 (8020)  │
                     └──────────────┘
                      ┌─────┴─────┐
                      ▼           ▼
               Portfolio    Stock Analysis
               Overview     (Bokeh 交互图)
               (QuantStats)
```

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/zinan92/quant-dashboard.git
cd quant-dashboard/quant-dashboard

# 2. 安装依赖 (Python ≥ 3.13)
pip install -r requirements.txt

# 3. 准备市场数据（需要 ashare 项目的 market.db）
# 默认路径: ~/work/trading-co/ashare/data/market.db
# 或设置 DB_PATH 环境变量指向你的 market.db

# 4. 启动看板
streamlit run streamlit_app.py --server.port 8020
```

## 功能一览

| 功能 | 说明 | 状态 |
|------|------|------|
| 缠论信号引擎 | 分型→笔→中枢→MACD背驰→一/二/三买卖点 | ✅ 已完成 |
| 组合回测 | 多股并行回测，最大5仓位，30%仓位约束，100股整手 | ✅ 已完成 |
| QuantStats 绩效报告 | 收益曲线、回撤分析、月度热力图，基准对标沪深300 | ✅ 已完成 |
| 单股 Bokeh 交互图 | 选股后展示 K 线 + 买卖信号 + 绩效指标 | ✅ 已完成 |
| 中英文双语 | 侧栏切换语言，全界面 i18n | ✅ 已完成 |
| A股佣金模型 | 0.03% 佣金 + 0.1% 印花税（卖出） + ¥5 最低佣金 | ✅ 已完成 |
| 回测结果持久化 | SQLite 存储历史回测记录 | ✅ 已完成 |
| 策略插件化 | YAML 配置 + 注册机制，可扩展新策略 | ✅ 已完成 |

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 运行时 | Python 3.13+ | 核心语言 |
| 看板 | Streamlit | Web UI 框架 |
| 图表 | backtesting.py (Bokeh) | 单股交互式 K 线图 |
| 绩效 | QuantStats, Plotly | 组合绩效报告 |
| 策略 | 缠论自研引擎 | 分型/笔/中枢/背驰/买卖点 |
| 数据 | pandas, SQLite, AKShare | 市场数据存储与读取 |
| 质量 | pytest (177 tests), mypy, Ruff | 代码质量保障 |

## 项目结构

```
quant-dashboard/
├── streamlit_app.py              # 主看板入口 (双 Tab 布局)
├── src/
│   ├── strategy/
│   │   ├── base.py               # 策略基类 + 注册机制
│   │   └── chan_theory.py         # 缠论实现 (分型→笔→中枢→背驰→信号)
│   ├── backtest/
│   │   ├── engine.py             # 回测引擎 (日线遍历 + 信号执行)
│   │   ├── portfolio.py          # 组合管理 (仓位/佣金/交易记录)
│   │   ├── metrics.py            # 绩效指标计算
│   │   └── store.py              # 回测结果 SQLite 持久化
│   ├── data_layer/
│   │   ├── market_reader.py      # market.db 只读访问
│   │   └── index_fetcher.py      # 沪深300 基准数据获取
│   ├── adapters/
│   │   ├── backtesting_adapter.py # backtesting.py 数据适配
│   │   └── chan_theory_bt.py      # 缠论 → backtesting.py 桥接
│   ├── reporting/
│   │   └── tearsheet.py          # QuantStats HTML 报告生成
│   └── i18n.py                   # 中英文翻译
├── strategies/
│   └── chan_theory.yaml           # 缠论策略配置
├── tests/                         # 177 个测试
├── seed_csi300.py                 # 沪深300数据初始化脚本
├── requirements.txt
└── pyproject.toml
```

## 配置

| 变量 | 说明 | 必填 | 默认值 |
|------|------|------|--------|
| 数据库路径 | market.db 位置 | 是 | `~/work/trading-co/ashare/data/market.db` |
| 端口 | Streamlit 服务端口 | 否 | `8020` |

## 测试

```bash
# 运行全部测试
pytest tests/ -v

# 类型检查
mypy src/ --ignore-missing-imports

# 代码风格
ruff check src/
```

## For AI Agents

本节面向需要将此项目作为工具或依赖集成的 AI Agent。

### 结构化元数据

```yaml
name: quant-dashboard
description: A-share Chan Theory backtesting dashboard with portfolio analytics
version: 0.1.0
runtime: python>=3.13
ui_url: http://localhost:8020
health_check: GET http://localhost:8020/_stcore/health
install_command: pip install -r requirements.txt
start_command: streamlit run streamlit_app.py --server.port 8020 --server.headless true
dependencies:
  - market.db (from quant-data-pipeline / ashare)
  - AKShare (for CSI 300 benchmark data)
capabilities:
  - run Chan Theory backtest on ~1940 A-share stocks
  - generate QuantStats portfolio tearsheet with CSI 300 benchmark
  - produce per-stock interactive Bokeh charts with buy/sell signals
  - persist backtest results to SQLite for historical comparison
  - bilingual UI (English / Chinese)
input_format: Streamlit UI (sidebar parameters)
output_format: HTML dashboard with embedded Bokeh/Plotly/QuantStats charts
```

### Agent 调用示例

```python
import subprocess

# 启动看板服务
proc = subprocess.Popen(
    ["streamlit", "run", "streamlit_app.py",
     "--server.port", "8020", "--server.headless", "true"],
    cwd="quant-dashboard"
)

# 健康检查
import httpx
resp = httpx.get("http://localhost:8020/_stcore/health")
assert resp.status_code == 200
```

```python
# 直接调用回测引擎（无需 UI）
from src.data_layer.market_reader import MarketReader
from src.backtest.engine import BacktestEngine

reader = MarketReader()
symbols = reader.get_available_pairs()

engine = BacktestEngine(
    strategy="chan_theory",
    symbols=symbols,
    start_date="2025-01-01",
    end_date="2026-03-25",
    initial_capital=1_000_000,
    market_reader=reader,
)
result = engine.run(persist=True)

print(f"Total Return: {result.metrics['profit_total']:.2%}")
print(f"Sharpe: {result.metrics['sharpe']:.3f}")
print(f"Trades: {result.metrics['trade_count']}")
```

## 相关项目

| 项目 | 说明 | 链接 |
|------|------|------|
| quant-data-pipeline | 量化数据管道（提供 market.db） | [GitHub](https://github.com/zinan92/quant-data-pipeline) |
| qualitative-data-pipeline | 定性数据管道（新闻/事件情报） | [GitHub](https://github.com/zinan92/qualitative-data-pipeline) |
| trading-copilot | 交易方法论 Chat 终端 | [GitHub](https://github.com/zinan92/trading-copilot) |

## License

Private — internal use only.
