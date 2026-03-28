"""Streamlit dashboard for A-Share quantitative trading showcase.

This dashboard provides a professional quantitative trading interface with:
- Strategy selection and backtest parameter configuration
- Two-tab layout: Portfolio Overview and Stock Analysis
- Portfolio Overview: Performance metrics, QuantStats tearsheet, trade history
- Stock Analysis: Per-stock backtesting.py Bokeh charts with interactive visualization
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.adapters.backtesting_adapter import get_stock_names
from src.adapters.chan_theory_bt import run_single_stock_backtest
from src.backtest.engine import BacktestEngine
from src.data_layer.market_reader import MarketReader
from src.i18n import t
from src.reporting.tearsheet import generate_portfolio_tearsheet
from src.strategy.base import list_strategies

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="A-Share Quant Dashboard — Chan Theory",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Language selection (must be initialized before any other widgets)
# ---------------------------------------------------------------------------

if "lang" not in st.session_state:
    st.session_state["lang"] = "en"

# ---------------------------------------------------------------------------
# Sidebar: Backtest Configuration
# ---------------------------------------------------------------------------

# Language selector at the top of sidebar
lang = st.sidebar.selectbox(
    t("Language", st.session_state["lang"]),
    options=["English", "中文"],
    index=0 if st.session_state["lang"] == "en" else 1,
    key="lang_selector",
)

# Update session state based on selection
if lang == "English":
    st.session_state["lang"] = "en"
else:
    st.session_state["lang"] = "zh"

st.sidebar.divider()

st.sidebar.title(t("⚙️ Backtest Configuration", st.session_state["lang"]))

# Strategy selector
available_strategies = list_strategies()
strategy_name = st.sidebar.selectbox(
    t("Strategy", st.session_state["lang"]),
    options=available_strategies,
    index=0 if "chan_theory" in available_strategies else 0,
    help=t("Select the trading strategy to backtest", st.session_state["lang"]),
)

# Date range picker
st.sidebar.subheader(t("Date Range", st.session_state["lang"]))

# Default to last 3 months
default_end = datetime.now().date()
default_start = default_end - timedelta(days=90)

start_date = st.sidebar.date_input(
    t("Start Date", st.session_state["lang"]),
    value=default_start,
    min_value=datetime(2021, 1, 1).date(),
    max_value=default_end,
)

end_date = st.sidebar.date_input(
    t("End Date", st.session_state["lang"]),
    value=default_end,
    min_value=start_date,
    max_value=default_end,
)

# Initial capital
initial_capital = st.sidebar.number_input(
    t("Initial Capital (¥)", st.session_state["lang"]),
    min_value=10000.0,
    max_value=100000000.0,
    value=1000000.0,
    step=100000.0,
    format="%.0f",
    help=t("Initial capital in RMB", st.session_state["lang"]),
)

# Run backtest button
run_backtest = st.sidebar.button(
    t("🚀 Run Backtest", st.session_state["lang"]), 
    type="primary", 
    use_container_width=True
)

st.sidebar.divider()
st.sidebar.caption(t("📊 A-Share Quant Dashboard — Chan Theory Showcase", st.session_state["lang"]))

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.title(t("📈 A-Share Quant Dashboard", st.session_state["lang"]))
st.markdown(t("**Strategy:** Chan Theory — Mechanical fractal detection based on MACD divergence", st.session_state["lang"]))

# ---------------------------------------------------------------------------
# Run backtest when button is clicked
# ---------------------------------------------------------------------------

if run_backtest:
    # Store the backtest parameters in session state
    st.session_state["last_run"] = {
        "strategy": strategy_name,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "initial_capital": initial_capital,
    }

    # Initialize data readers
    reader = MarketReader()

    # Get stock universe
    with st.spinner(t("Loading stock list...", st.session_state["lang"])):
        symbols = reader.get_available_pairs()
        st.info(t("Loaded {count} stocks from market.db", st.session_state["lang"]).format(count=len(symbols)))

    # Initialize backtest engine
    with st.spinner(t("Initializing backtest engine...", st.session_state["lang"])):
        engine = BacktestEngine(
            strategy=strategy_name,
            symbols=symbols,
            start_date=st.session_state["last_run"]["start_date"],
            end_date=st.session_state["last_run"]["end_date"],
            initial_capital=initial_capital,
            market_reader=reader,
        )

    # Run backtest with progress bar
    progress_bar = st.progress(0.0, text=t("Running backtest... {percent}%", st.session_state["lang"]).format(percent=0))

    # We'll poll the engine's progress during execution
    import threading
    import time

    result_container = {}

    def run_backtest_thread() -> None:
        result_container["result"] = engine.run(persist=True)

    thread = threading.Thread(target=run_backtest_thread)
    thread.start()

    # Poll for progress
    while thread.is_alive():
        percent = int(engine.progress * 100)
        progress_bar.progress(
            engine.progress, 
            text=t("Running backtest... {percent}%", st.session_state["lang"]).format(percent=percent)
        )
        time.sleep(0.1)

    thread.join()
    progress_bar.progress(1.0, text=t("Backtest complete!", st.session_state["lang"]))
    time.sleep(0.5)
    progress_bar.empty()

    # Store result in session state
    st.session_state["result"] = result_container["result"]

    st.success(
        t("✅ Backtest complete! Executed {count} trades.", st.session_state["lang"]).format(
            count=result_container['result'].metrics['trade_count']
        )
    )

# ---------------------------------------------------------------------------
# Display results if available
# ---------------------------------------------------------------------------

if "result" in st.session_state and "last_run" in st.session_state:
    result = st.session_state["result"]
    params = st.session_state["last_run"]

    st.divider()

    # -----------------------------------------------------------------------
    # Two-Tab Layout
    # -----------------------------------------------------------------------

    tab1, tab2 = st.tabs([
        t("📊 Portfolio Overview", st.session_state["lang"]), 
        t("📈 Stock Analysis", st.session_state["lang"])
    ])

    # =======================================================================
    # Tab 1: Portfolio Overview
    # =======================================================================

    with tab1:
        # -------------------------------------------------------------------
        # Performance Metrics Cards
        # -------------------------------------------------------------------

        st.subheader(t("📊 Performance Summary", st.session_state["lang"]))

        metrics = result.metrics

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            total_return_pct = metrics["profit_total"] * 100
            st.metric(
                t("Total Return", st.session_state["lang"]),
                f"{total_return_pct:.2f}%",
                delta=f"¥{metrics['profit_total_abs']:,.0f}",
            )

        with col2:
            # Calculate CAGR from total return and date range
            start_dt = datetime.strptime(params["start_date"], "%Y-%m-%d")
            end_dt = datetime.strptime(params["end_date"], "%Y-%m-%d")
            years = (end_dt - start_dt).days / 365.25
            if years > 0:
                cagr = ((1 + metrics["profit_total"]) ** (1 / years) - 1) * 100
            else:
                cagr = 0.0
            st.metric(t("CAGR", st.session_state["lang"]), f"{cagr:.2f}%")

        with col3:
            st.metric(t("Sharpe Ratio", st.session_state["lang"]), f"{metrics['sharpe']:.3f}")

        with col4:
            st.metric(t("Sortino Ratio", st.session_state["lang"]), f"{metrics['sortino']:.3f}")

        with col5:
            max_dd_pct = abs(metrics["max_drawdown"]) * 100
            st.metric(t("Max Drawdown", st.session_state["lang"]), f"-{max_dd_pct:.2f}%")

        with col6:
            win_rate_pct = metrics["winrate"] * 100
            st.metric(t("Win Rate", st.session_state["lang"]), f"{win_rate_pct:.1f}%")

        st.divider()

        # -------------------------------------------------------------------
        # QuantStats Tearsheet
        # -------------------------------------------------------------------

        st.subheader(t("📈 Portfolio Tearsheet (QuantStats)", st.session_state["lang"]))

        with st.spinner(t("Generating QuantStats tearsheet...", st.session_state["lang"])):
            reader = MarketReader()
            tearsheet_html = generate_portfolio_tearsheet(result, reader, lang=st.session_state["lang"])

        # Embed the tearsheet HTML
        components.html(tearsheet_html, height=3000, scrolling=True)

        st.divider()

        # -------------------------------------------------------------------
        # Trade History Table (Expandable)
        # -------------------------------------------------------------------

        with st.expander(t("📋 Trade History", st.session_state["lang"]), expanded=False):
            if result.trades:
                trades_data = []
                for trade in result.trades:
                    # Calculate hold days
                    entry_dt = datetime.strptime(trade.entry_date, "%Y-%m-%d")
                    exit_dt = datetime.strptime(trade.exit_date, "%Y-%m-%d")
                    hold_days = (exit_dt - entry_dt).days

                    trades_data.append(
                        {
                            t("Stock", st.session_state["lang"]): trade.symbol,
                            t("Entry Date", st.session_state["lang"]): trade.entry_date,
                            t("Exit Date", st.session_state["lang"]): trade.exit_date,
                            t("Entry Price", st.session_state["lang"]): f"¥{trade.entry_price:.2f}",
                            t("Exit Price", st.session_state["lang"]): f"¥{trade.exit_price:.2f}",
                            t("P&L", st.session_state["lang"]): f"¥{trade.pnl:,.2f}",
                            t("P&L %", st.session_state["lang"]): f"{trade.pnl_pct * 100:.2f}%",
                            t("Hold Days", st.session_state["lang"]): hold_days,
                        }
                    )

                trades_df = pd.DataFrame(trades_data)
                st.dataframe(trades_df, use_container_width=True, height=400)
            else:
                st.info(t("No trades executed during backtest period.", st.session_state["lang"]))

    # =======================================================================
    # Tab 2: Stock Analysis
    # =======================================================================

    with tab2:
        st.subheader(t("📈 Stock Analysis", st.session_state["lang"]))

        # Get list of stocks that had trades
        if result.trades:
            traded_stocks = sorted(list(set(trade.symbol for trade in result.trades)))

            # Get stock names for dropdown
            reader = MarketReader()
            stock_names = get_stock_names(traded_stocks, reader)

            # Create dropdown options with format "TICKER - 股票名称"
            stock_options = []
            stock_display_map = {}  # Maps display text to symbol
            for symbol in traded_stocks:
                if symbol in stock_names:
                    display_text = f"{symbol} - {stock_names[symbol]}"
                else:
                    display_text = symbol
                stock_options.append(display_text)
                stock_display_map[display_text] = symbol

            # Stock selector dropdown
            selected_display = st.selectbox(
                t("Select a stock to analyze:", st.session_state["lang"]),
                options=stock_options,
                index=0,
                help=t("Select a stock that was traded during the backtest", st.session_state["lang"]),
            )

            # Get actual symbol from display text
            selected_stock = stock_display_map[selected_display]

            if selected_stock:
                st.markdown(t("**Analyzing:** ", st.session_state["lang"]) + selected_display)

                with st.spinner(
                    t("Running single-stock backtest for {stock}...", st.session_state["lang"]).format(stock=selected_display)
                ):
                    try:
                        stats_dict, bokeh_html = run_single_stock_backtest(
                            symbol=selected_stock,
                            start_date=params["start_date"],
                            end_date=params["end_date"],
                            initial_capital=params["initial_capital"],
                            reader=reader,
                        )

                        # Display Bokeh chart
                        st.markdown(t("#### Interactive Backtest Chart", st.session_state["lang"]))
                        components.html(bokeh_html, height=800, scrolling=False)

                        st.divider()

                        # Display per-stock metrics
                        st.markdown(t("#### Performance Metrics", st.session_state["lang"]))

                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            return_pct = stats_dict.get("Return [%]", 0.0)
                            st.metric(t("Return", st.session_state["lang"]), f"{return_pct:.2f}%")

                        with col2:
                            num_trades = stats_dict.get("# Trades", 0)
                            st.metric(t("# Trades", st.session_state["lang"]), f"{num_trades}")

                        with col3:
                            sharpe = stats_dict.get("Sharpe Ratio", 0.0)
                            st.metric(t("Sharpe Ratio", st.session_state["lang"]), f"{sharpe:.3f}")

                        with col4:
                            max_dd = stats_dict.get("Max. Drawdown [%]", 0.0)
                            st.metric(t("Max Drawdown", st.session_state["lang"]), f"{max_dd:.2f}%")

                        st.divider()

                        # Display stock-specific trade table
                        st.markdown(t("#### Trade History for This Stock", st.session_state["lang"]))

                        stock_trades = [
                            trade for trade in result.trades if trade.symbol == selected_stock
                        ]

                        if stock_trades:
                            trades_data = []
                            for trade in stock_trades:
                                entry_dt = datetime.strptime(trade.entry_date, "%Y-%m-%d")
                                exit_dt = datetime.strptime(trade.exit_date, "%Y-%m-%d")
                                hold_days = (exit_dt - entry_dt).days

                                trades_data.append(
                                    {
                                        t("Entry Date", st.session_state["lang"]): trade.entry_date,
                                        t("Exit Date", st.session_state["lang"]): trade.exit_date,
                                        t("Entry Price", st.session_state["lang"]): f"¥{trade.entry_price:.2f}",
                                        t("Exit Price", st.session_state["lang"]): f"¥{trade.exit_price:.2f}",
                                        t("P&L", st.session_state["lang"]): f"¥{trade.pnl:,.2f}",
                                        t("P&L %", st.session_state["lang"]): f"{trade.pnl_pct * 100:.2f}%",
                                        t("Hold Days", st.session_state["lang"]): hold_days,
                                    }
                                )

                            trades_df = pd.DataFrame(trades_data)
                            st.dataframe(trades_df, use_container_width=True)
                        else:
                            st.info(
                                t("No trades found for {stock}", st.session_state["lang"]).format(stock=selected_stock)
                            )

                    except Exception as e:
                        st.error(
                            t("Error running backtest for {stock}: {error}", st.session_state["lang"]).format(
                                stock=selected_stock, error=str(e)
                            )
                        )
        else:
            st.info(t("No trades executed. Please run backtest first.", st.session_state["lang"]))

else:
    # Welcome message when no backtest has been run yet
    st.info(t("👈 Configure backtest parameters in the sidebar, then click **Run Backtest** to begin.", st.session_state["lang"]))
    st.markdown(t("## Welcome to A-Share Quant Dashboard!", st.session_state["lang"]))
    st.markdown(t("""
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
""", st.session_state["lang"]))
