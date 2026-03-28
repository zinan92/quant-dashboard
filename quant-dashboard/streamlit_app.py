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

from src.adapters.chan_theory_bt import run_single_stock_backtest
from src.backtest.engine import BacktestEngine
from src.data_layer.market_reader import MarketReader
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
# Sidebar: Backtest Configuration
# ---------------------------------------------------------------------------

st.sidebar.title("⚙️ Backtest Configuration")

# Strategy selector
available_strategies = list_strategies()
strategy_name = st.sidebar.selectbox(
    "Strategy",
    options=available_strategies,
    index=0 if "chan_theory" in available_strategies else 0,
    help="Select the trading strategy to backtest",
)

# Date range picker
st.sidebar.subheader("Date Range")

# Default to last 3 months
default_end = datetime.now().date()
default_start = default_end - timedelta(days=90)

start_date = st.sidebar.date_input(
    "Start Date",
    value=default_start,
    min_value=datetime(2025, 11, 1).date(),
    max_value=default_end,
)

end_date = st.sidebar.date_input(
    "End Date",
    value=default_end,
    min_value=start_date,
    max_value=default_end,
)

# Initial capital
initial_capital = st.sidebar.number_input(
    "Initial Capital (¥)",
    min_value=10000.0,
    max_value=100000000.0,
    value=1000000.0,
    step=100000.0,
    format="%.0f",
    help="Starting capital in CNY",
)

# Run backtest button
run_backtest = st.sidebar.button("🚀 Run Backtest", type="primary", use_container_width=True)

st.sidebar.divider()
st.sidebar.caption("📊 A-Share Quant Dashboard — Chan Theory Strategy Showcase")

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.title("📈 A-Share Quantitative Trading Dashboard")
st.markdown(
    "**Strategy:** Chan Theory (缠论) — Mechanical fractal detection with MACD divergence signals"
)

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
    with st.spinner("Loading stock universe..."):
        symbols = reader.get_available_pairs()
        st.info(f"Loaded {len(symbols)} stocks from market.db")

    # Initialize backtest engine
    with st.spinner("Initializing backtest engine..."):
        engine = BacktestEngine(
            strategy=strategy_name,
            symbols=symbols,
            start_date=st.session_state["last_run"]["start_date"],
            end_date=st.session_state["last_run"]["end_date"],
            initial_capital=initial_capital,
            market_reader=reader,
        )

    # Run backtest with progress bar
    progress_bar = st.progress(0.0, text="Running backtest...")

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
        progress_bar.progress(engine.progress, text=f"Running backtest... {int(engine.progress * 100)}%")
        time.sleep(0.1)

    thread.join()
    progress_bar.progress(1.0, text="Backtest complete!")
    time.sleep(0.5)
    progress_bar.empty()

    # Store result in session state
    st.session_state["result"] = result_container["result"]

    st.success(
        f"✅ Backtest complete! {result_container['result'].metrics['trade_count']} trades executed."
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

    tab1, tab2 = st.tabs(["📊 Portfolio Overview", "📈 Stock Analysis"])

    # =======================================================================
    # Tab 1: Portfolio Overview
    # =======================================================================

    with tab1:
        # -------------------------------------------------------------------
        # Performance Metrics Cards
        # -------------------------------------------------------------------

        st.subheader("📊 Performance Summary")

        metrics = result.metrics

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        with col1:
            total_return_pct = metrics["profit_total"] * 100
            st.metric(
                "Total Return",
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
            st.metric("CAGR", f"{cagr:.2f}%")

        with col3:
            st.metric("Sharpe Ratio", f"{metrics['sharpe']:.3f}")

        with col4:
            st.metric("Sortino Ratio", f"{metrics['sortino']:.3f}")

        with col5:
            max_dd_pct = abs(metrics["max_drawdown"]) * 100
            st.metric("Max Drawdown", f"-{max_dd_pct:.2f}%")

        with col6:
            win_rate_pct = metrics["winrate"] * 100
            st.metric("Win Rate", f"{win_rate_pct:.1f}%")

        st.divider()

        # -------------------------------------------------------------------
        # QuantStats Tearsheet
        # -------------------------------------------------------------------

        st.subheader("📈 Portfolio Tearsheet (QuantStats)")

        with st.spinner("Generating QuantStats tearsheet..."):
            reader = MarketReader()
            tearsheet_html = generate_portfolio_tearsheet(result, reader)

        # Embed the tearsheet HTML
        components.html(tearsheet_html, height=3000, scrolling=True)

        st.divider()

        # -------------------------------------------------------------------
        # Trade History Table (Expandable)
        # -------------------------------------------------------------------

        with st.expander("📋 Trade History", expanded=False):
            if result.trades:
                trades_data = []
                for trade in result.trades:
                    # Calculate hold days
                    entry_dt = datetime.strptime(trade.entry_date, "%Y-%m-%d")
                    exit_dt = datetime.strptime(trade.exit_date, "%Y-%m-%d")
                    hold_days = (exit_dt - entry_dt).days

                    trades_data.append(
                        {
                            "Stock": trade.symbol,
                            "Entry Date": trade.entry_date,
                            "Exit Date": trade.exit_date,
                            "Entry Price": f"¥{trade.entry_price:.2f}",
                            "Exit Price": f"¥{trade.exit_price:.2f}",
                            "P&L": f"¥{trade.pnl:,.2f}",
                            "P&L%": f"{trade.pnl_pct * 100:.2f}%",
                            "Hold Days": hold_days,
                        }
                    )

                trades_df = pd.DataFrame(trades_data)
                st.dataframe(trades_df, use_container_width=True, height=400)
            else:
                st.info("No trades executed during this backtest period.")

    # =======================================================================
    # Tab 2: Stock Analysis
    # =======================================================================

    with tab2:
        st.subheader("📈 Individual Stock Analysis")

        # Get list of stocks that had trades
        if result.trades:
            traded_stocks = sorted(list(set(trade.symbol for trade in result.trades)))

            # Stock selector dropdown
            selected_stock = st.selectbox(
                "Select a stock to analyze:",
                options=traded_stocks,
                index=0,
                help="Choose a stock that was traded during the backtest",
            )

            if selected_stock:
                st.markdown(f"**Analyzing:** {selected_stock}")

                with st.spinner(f"Running single-stock backtest for {selected_stock}..."):
                    try:
                        reader = MarketReader()
                        stats_dict, bokeh_html = run_single_stock_backtest(
                            symbol=selected_stock,
                            start_date=params["start_date"],
                            end_date=params["end_date"],
                            initial_capital=params["initial_capital"],
                            reader=reader,
                        )

                        # Display Bokeh chart
                        st.markdown("#### Interactive Backtest Chart")
                        components.html(bokeh_html, height=800, scrolling=False)

                        st.divider()

                        # Display per-stock metrics
                        st.markdown("#### Performance Metrics")

                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            return_pct = stats_dict.get("Return [%]", 0.0)
                            st.metric("Return", f"{return_pct:.2f}%")

                        with col2:
                            num_trades = stats_dict.get("# Trades", 0)
                            st.metric("# Trades", f"{num_trades}")

                        with col3:
                            sharpe = stats_dict.get("Sharpe Ratio", 0.0)
                            st.metric("Sharpe Ratio", f"{sharpe:.3f}")

                        with col4:
                            max_dd = stats_dict.get("Max. Drawdown [%]", 0.0)
                            st.metric("Max Drawdown", f"{max_dd:.2f}%")

                        st.divider()

                        # Display stock-specific trade table
                        st.markdown("#### Trade History for this Stock")

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
                                        "Entry Date": trade.entry_date,
                                        "Exit Date": trade.exit_date,
                                        "Entry Price": f"¥{trade.entry_price:.2f}",
                                        "Exit Price": f"¥{trade.exit_price:.2f}",
                                        "P&L": f"¥{trade.pnl:,.2f}",
                                        "P&L%": f"{trade.pnl_pct * 100:.2f}%",
                                        "Hold Days": hold_days,
                                    }
                                )

                            trades_df = pd.DataFrame(trades_data)
                            st.dataframe(trades_df, use_container_width=True)
                        else:
                            st.info(f"No trades found for {selected_stock}")

                    except Exception as e:
                        st.error(f"Error running backtest for {selected_stock}: {str(e)}")
        else:
            st.info("No trades executed during this backtest period. Run a backtest first.")

else:
    # Welcome message when no backtest has been run yet
    st.info("👈 Configure your backtest parameters in the sidebar and click **Run Backtest** to start.")
    st.markdown(
        """
        ## Welcome to the A-Share Quant Dashboard!

        This dashboard showcases the **Chan Theory (缠论)** quantitative trading strategy applied to A-share stocks.

        ### Features:
        - 📊 **Performance Metrics**: Total Return, CAGR, Sharpe Ratio, Max Drawdown, Win Rate, Trade Count
        - 📈 **Interactive NAV Chart**: Compare strategy performance against CSI 300 and ChiNext benchmarks
        - 📉 **Drawdown Chart**: Visualize underwater periods
        - 📋 **Trade List**: Detailed trade-by-trade breakdown
        - 🔥 **Monthly Returns Heatmap**: See seasonality patterns
        - 🏆 **Per-Stock Performance**: Identify top performers

        ### Getting Started:
        1. Select a strategy (currently **chan_theory**)
        2. Choose your backtest date range
        3. Set your initial capital
        4. Click **Run Backtest**

        The backtest will analyze signals across the entire stock universe and execute simulated trades.
        """
    )
