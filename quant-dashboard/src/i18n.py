"""Internationalization (i18n) support for the Streamlit dashboard.

Provides translation functionality for English and Chinese languages.
"""

from __future__ import annotations

# Comprehensive translations dictionary mapping English text to Chinese translations
TRANSLATIONS = {
    # Page title and headers
    "A-Share Quant Dashboard — Chan Theory": "A股量化交易仪表盘 — 缠论",
    "📈 A-Share Quant Dashboard": "📈 A股量化交易仪表盘",
    "**Strategy:** Chan Theory — Mechanical fractal detection based on MACD divergence": "**策略:** 缠论 (Chan Theory) — 基于MACD背驰的机械化分形检测",

    # Sidebar configuration section
    "⚙️ Backtest Configuration": "⚙️ 回测配置",
    "📊 A-Share Quant Dashboard — Chan Theory Showcase": "📊 A股量化仪表盘 — 缠论策略展示",
    "Language": "语言",

    # Sidebar controls
    "Strategy": "策略",
    "Select the trading strategy to backtest": "选择要回测的交易策略",
    "Date Range": "日期范围",
    "Start Date": "开始日期",
    "End Date": "结束日期",
    "Initial Capital (¥)": "初始资金 (¥)",
    "Initial capital in RMB": "起始资金（人民币）",
    "🚀 Run Backtest": "🚀 运行回测",

    # Tab names
    "📊 Portfolio Overview": "📊 投资组合概览",
    "📈 Stock Analysis": "📈 个股分析",

    # Performance metrics
    "📊 Performance Summary": "📊 业绩摘要",
    "Total Return": "总收益率",
    "CAGR": "年化收益率",
    "Sharpe Ratio": "夏普比率",
    "Sortino Ratio": "索提诺比率",
    "Max Drawdown": "最大回撤",
    "Win Rate": "胜率",

    # Portfolio Overview tab
    "📈 Portfolio Tearsheet (QuantStats)": "📈 投资组合分析报告 (QuantStats)",
    "📋 Trade History": "📋 交易历史",

    # Trade table columns
    "Stock": "股票",
    "Entry Date": "买入日期",
    "Exit Date": "卖出日期",
    "Entry Price": "买入价",
    "Exit Price": "卖出价",
    "P&L": "盈亏",
    "P&L %": "收益率%",
    "Hold Days": "持有天数",

    # Stock Analysis tab
    "📈 Stock Analysis": "📈 个股分析",
    "Select a stock to analyze:": "选择要分析的股票:",
    "Select a stock that was traded during the backtest": "选择回测期间交易过的股票",
    "**Analyzing:** ": "**分析中:** ",
    "#### Interactive Backtest Chart": "#### 交互式回测图表",
    "#### Performance Metrics": "#### 业绩指标",
    "Return": "收益率",
    "# Trades": "交易次数",
    "#### Trade History for This Stock": "#### 该股票的交易历史",

    # Messages and notifications
    "Loading stock list...": "加载股票列表...",
    "Loaded {count} stocks from market.db": "已从 market.db 加载 {count} 只股票",
    "Initializing backtest engine...": "初始化回测引擎...",
    "Running backtest... {percent}%": "运行回测中... {percent}%",
    "Backtest complete!": "回测完成!",
    "✅ Backtest complete! Executed {count} trades.": "✅ 回测完成! 执行了 {count} 笔交易。",
    "No trades executed during backtest period.": "回测期间未执行任何交易。",
    "No trades executed. Please run backtest first.": "回测期间未执行任何交易。请先运行回测。",
    "Generating QuantStats tearsheet...": "生成 QuantStats 分析报告...",
    "Running single-stock backtest for {stock}...": "为 {stock} 运行单股回测...",
    "Error running backtest for {stock}: {error}": "为 {stock} 运行回测时出错: {error}",
    "No trades found for {stock}": "未找到 {stock} 的交易记录",

    # Welcome message
    "👈 Configure backtest parameters in the sidebar, then click **Run Backtest** to begin.": "👈 在侧边栏配置回测参数，然后点击 **运行回测** 开始。",
    "## Welcome to A-Share Quant Dashboard!": "## 欢迎使用A股量化交易仪表盘!",
    """
This dashboard showcases the **Chan Theory** quantitative trading strategy applied to A-Share markets.

### Features:
- 📊 **Performance Metrics**: Total return, CAGR, Sharpe ratio, max drawdown, win rate, trade count
- 📈 **Interactive NAV Chart**: Strategy performance vs CSI 300 and ChiNext benchmarks
- 📉 **Drawdown Chart**: Visualize underwater periods
- 📋 **Trade List**: Trade-by-trade breakdown
- 🔥 **Monthly Returns Heatmap**: See seasonal patterns
- 🏆 **Per-Stock Performance**: Identify best performers

### Quick Start:
1. Select strategy (currently **Chan Theory**)
2. Choose backtest date range
3. Set initial capital
4. Click **Run Backtest**

The backtest will analyze signals across the stock universe and execute simulated trades.
""": """
本仪表盘展示应用于A股市场的**缠论 (Chan Theory)** 量化交易策略。

### 功能特性:
- 📊 **业绩指标**: 总收益率、年化收益率、夏普比率、最大回撤、胜率、交易次数
- 📈 **交互式净值图表**: 策略表现与沪深300、创业板指基准对比
- 📉 **回撤图表**: 可视化水下期间
- 📋 **交易列表**: 逐笔交易明细
- 🔥 **月度收益热力图**: 查看季节性模式
- 🏆 **个股业绩**: 识别表现最佳的股票

### 快速开始:
1. 选择策略（当前为 **缠论**）
2. 选择回测日期范围
3. 设置初始资金
4. 点击 **运行回测**

回测将分析整个股票池的信号并执行模拟交易。
""",
}


def t(key: str, lang: str = "en") -> str:
    """Translate a key to the specified language.

    Args:
        key: Translation key (English text or identifier)
        lang: Target language code ('en' for English, 'zh' for Chinese)

    Returns:
        Translated string. Returns the key itself if lang is 'en' or key not found.

    Examples:
        >>> t("Total Return", "zh")
        '总收益率'
        >>> t("Total Return", "en")
        'Total Return'
        >>> t("unknown_key", "zh")
        'unknown_key'
    """
    if lang == "zh":
        return TRANSLATIONS.get(key, key)
    return key
