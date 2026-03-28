"""Internationalization (i18n) support for the Streamlit dashboard.

Provides translation functionality for English and Chinese languages.
"""

from __future__ import annotations

# Comprehensive translations dictionary mapping English keys to Chinese values
TRANSLATIONS = {
    # Page title and headers
    "page_title": "A股量化交易仪表盘 — 缠论",
    "dashboard_title": "📈 A股量化交易仪表盘",
    "strategy_subtitle": "**策略:** 缠论 (Chan Theory) — 基于MACD背驰的机械化分形检测",

    # Sidebar configuration section
    "sidebar_title": "⚙️ 回测配置",
    "sidebar_caption": "📊 A股量化仪表盘 — 缠论策略展示",
    "language": "语言",

    # Sidebar controls
    "strategy": "策略",
    "strategy_help": "选择要回测的交易策略",
    "date_range": "日期范围",
    "start_date": "开始日期",
    "end_date": "结束日期",
    "initial_capital": "初始资金 (¥)",
    "initial_capital_help": "起始资金（人民币）",
    "run_backtest": "🚀 运行回测",

    # Tab names
    "tab_portfolio_overview": "📊 投资组合概览",
    "tab_stock_analysis": "📈 个股分析",

    # Performance metrics
    "performance_summary": "📊 业绩摘要",
    "total_return": "总收益率",
    "cagr": "年化收益率",
    "sharpe_ratio": "夏普比率",
    "sortino_ratio": "索提诺比率",
    "max_drawdown": "最大回撤",
    "win_rate": "胜率",

    # Portfolio Overview tab
    "portfolio_tearsheet": "📈 投资组合分析报告 (QuantStats)",
    "trade_history": "📋 交易历史",

    # Trade table columns
    "stock": "股票",
    "entry_date": "买入日期",
    "exit_date": "卖出日期",
    "entry_price": "买入价",
    "exit_price": "卖出价",
    "pnl": "盈亏",
    "pnl_pct": "收益率%",
    "hold_days": "持有天数",

    # Stock Analysis tab
    "stock_analysis_title": "📈 个股分析",
    "select_stock": "选择要分析的股票:",
    "select_stock_help": "选择回测期间交易过的股票",
    "analyzing": "**分析中:** ",
    "interactive_chart": "#### 交互式回测图表",
    "performance_metrics": "#### 业绩指标",
    "return": "收益率",
    "num_trades": "交易次数",
    "trade_history_stock": "#### 该股票的交易历史",

    # Messages and notifications
    "loading_stocks": "加载股票列表...",
    "stocks_loaded": "已从 market.db 加载 {count} 只股票",
    "initializing_engine": "初始化回测引擎...",
    "running_backtest_progress": "运行回测中... {percent}%",
    "backtest_complete_progress": "回测完成!",
    "backtest_complete_message": "✅ 回测完成! 执行了 {count} 笔交易。",
    "no_trades": "回测期间未执行任何交易。",
    "no_trades_run_first": "回测期间未执行任何交易。请先运行回测。",
    "generating_tearsheet": "生成 QuantStats 分析报告...",
    "running_single_backtest": "为 {stock} 运行单股回测...",
    "backtest_error": "为 {stock} 运行回测时出错: {error}",
    "no_trades_for_stock": "未找到 {stock} 的交易记录",

    # Welcome message
    "welcome_configure": "👈 在侧边栏配置回测参数，然后点击 **运行回测** 开始。",
    "welcome_title": "## 欢迎使用A股量化交易仪表盘!",
    "welcome_description": """
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
