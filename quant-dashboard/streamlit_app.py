"""Streamlit dashboard for A-Share quantitative trading showcase.

This dashboard provides a complete quantitative trading showcase interface with:
- Strategy selection and backtest parameter configuration
- Performance metrics display (Total Return, CAGR, Sharpe, MaxDD, Win Rate, etc.)
- NAV chart with benchmark overlays (CSI 300 and ChiNext)
- Drawdown chart
- Trade list table
- Monthly returns heatmap
- Per-stock performance bar chart
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.backtest.engine import BacktestEngine
from src.data_layer.index_fetcher import IndexFetcher
from src.data_layer.market_reader import MarketReader
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
    index_fetcher = IndexFetcher()

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
    # Performance Summary Cards
    # -----------------------------------------------------------------------

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
        st.metric("Sortino Ratio", f"{metrics['sortino']:.3f}")

    with col3:
        st.metric("Sharpe Ratio", f"{metrics['sharpe']:.3f}")

    with col4:
        max_dd_pct = abs(metrics["max_drawdown"]) * 100
        st.metric("Max Drawdown", f"-{max_dd_pct:.2f}%")

    with col5:
        win_rate_pct = metrics["winrate"] * 100
        st.metric("Win Rate", f"{win_rate_pct:.1f}%")

    with col6:
        st.metric("Trade Count", f"{metrics['trade_count']}")

    st.divider()

    # -----------------------------------------------------------------------
    # NAV Chart with Benchmark Overlays
    # -----------------------------------------------------------------------

    st.subheader("📈 Net Asset Value — Strategy vs Benchmarks")

    # Convert NAV history to DataFrame
    nav_df = pd.DataFrame(result.nav_history)

    # Fetch benchmark data
    reader = MarketReader()
    index_fetcher = IndexFetcher()

    # ChiNext (399006.SZ) from market.db
    chinext_df = reader.get_index_klines(
        "399006.SZ",
        timeframe="DAY",
        start_date=params["start_date"],
        end_date=params["end_date"],
    )

    # CSI 300 (000300) from index_cache.db
    csi300_df = index_fetcher.get_csi300(
        start_date=params["start_date"],
        end_date=params["end_date"],
    )

    # Normalize benchmarks to same starting NAV as strategy
    if not chinext_df.empty:
        chinext_df["normalized_nav"] = (
            chinext_df["close"] / chinext_df["close"].iloc[0] * params["initial_capital"]
        )

    if not csi300_df.empty:
        csi300_df["normalized_nav"] = (
            csi300_df["close"] / csi300_df["close"].iloc[0] * params["initial_capital"]
        )

    # Create Plotly figure
    fig = go.Figure()

    # Add strategy NAV line
    fig.add_trace(
        go.Scatter(
            x=nav_df["date"],
            y=nav_df["nav"],
            mode="lines",
            name="Chan Theory",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="<b>Chan Theory</b><br>Date: %{x}<br>NAV: ¥%{y:,.0f}<extra></extra>",
        )
    )

    # Add CSI 300 benchmark
    if not csi300_df.empty:
        fig.add_trace(
            go.Scatter(
                x=csi300_df["date"],
                y=csi300_df["normalized_nav"],
                mode="lines",
                name="CSI 300 (沪深300)",
                line=dict(color="#ff7f0e", width=2, dash="dash"),
                hovertemplate="<b>CSI 300</b><br>Date: %{x}<br>NAV: ¥%{y:,.0f}<extra></extra>",
            )
        )

    # Add ChiNext benchmark
    if not chinext_df.empty:
        fig.add_trace(
            go.Scatter(
                x=chinext_df["date"],
                y=chinext_df["normalized_nav"],
                mode="lines",
                name="ChiNext (创业板指)",
                line=dict(color="#2ca02c", width=2, dash="dot"),
                hovertemplate="<b>ChiNext</b><br>Date: %{x}<br>NAV: ¥%{y:,.0f}<extra></extra>",
            )
        )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Net Asset Value (¥)",
        hovermode="x unified",
        height=500,
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Drawdown Chart
    # -----------------------------------------------------------------------

    st.subheader("📉 Drawdown Chart")

    # Calculate drawdown series
    nav_series = np.array(nav_df["nav"])
    peak = nav_series[0]
    drawdowns = []

    for nav in nav_series:
        if nav > peak:
            peak = nav
        dd = (nav - peak) / peak if peak > 0 else 0
        drawdowns.append(dd * 100)  # Convert to percentage

    drawdown_df = pd.DataFrame({"date": nav_df["date"], "drawdown": drawdowns})

    fig_dd = go.Figure()

    fig_dd.add_trace(
        go.Scatter(
            x=drawdown_df["date"],
            y=drawdown_df["drawdown"],
            mode="lines",
            name="Drawdown",
            line=dict(color="#d62728", width=2),
            fill="tozeroy",
            fillcolor="rgba(214, 39, 40, 0.3)",
            hovertemplate="<b>Drawdown</b><br>Date: %{x}<br>DD: %{y:.2f}%<extra></extra>",
        )
    )

    fig_dd.update_layout(
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        hovermode="x unified",
        height=300,
        template="plotly_white",
    )

    st.plotly_chart(fig_dd, use_container_width=True)

    # -----------------------------------------------------------------------
    # Trade List Table
    # -----------------------------------------------------------------------

    st.subheader("📋 Trade List")

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

    # -----------------------------------------------------------------------
    # Monthly Returns Heatmap
    # -----------------------------------------------------------------------

    st.subheader("🔥 Monthly Returns Heatmap")

    # Calculate monthly returns from daily NAV
    nav_with_date = nav_df.copy()
    nav_with_date["date"] = pd.to_datetime(nav_with_date["date"])
    nav_with_date["year"] = nav_with_date["date"].dt.year
    nav_with_date["month"] = nav_with_date["date"].dt.month

    # Group by year-month and get first/last NAV
    monthly_grouped = (
        nav_with_date.groupby(["year", "month"])
        .agg({"nav": ["first", "last"]})
        .reset_index()
    )
    monthly_grouped.columns = ["year", "month", "start_nav", "end_nav"]
    monthly_grouped["return"] = (
        (monthly_grouped["end_nav"] - monthly_grouped["start_nav"])
        / monthly_grouped["start_nav"]
        * 100
    )

    if not monthly_grouped.empty:
        # Pivot for heatmap
        years = sorted(monthly_grouped["year"].unique())
        months = list(range(1, 13))

        heatmap_data = []
        for month in months:
            row = []
            for year in years:
                val = monthly_grouped[
                    (monthly_grouped["year"] == year) & (monthly_grouped["month"] == month)
                ]["return"]
                row.append(val.iloc[0] if not val.empty else None)
            heatmap_data.append(row)

        month_labels = [calendar.month_abbr[m] for m in months]

        fig_heatmap = go.Figure(
            data=go.Heatmap(
                z=heatmap_data,
                x=years,
                y=month_labels,
                colorscale="RdYlGn",
                zmid=0,
                text=[[f"{v:.1f}%" if v is not None else "" for v in row] for row in heatmap_data],
                texttemplate="%{text}",
                textfont={"size": 10},
                hovertemplate="Year: %{x}<br>Month: %{y}<br>Return: %{z:.2f}%<extra></extra>",
            )
        )

        fig_heatmap.update_layout(
            xaxis_title="Year",
            yaxis_title="Month",
            height=400,
            template="plotly_white",
        )

        st.plotly_chart(fig_heatmap, use_container_width=True)
    else:
        st.info("Insufficient data for monthly returns heatmap.")

    # -----------------------------------------------------------------------
    # Per-Stock Performance Bar Chart
    # -----------------------------------------------------------------------

    st.subheader("🏆 Per-Stock Performance")

    if result.trades:
        # Aggregate P&L by stock
        stock_pnl = {}
        for trade in result.trades:
            if trade.symbol not in stock_pnl:
                stock_pnl[trade.symbol] = 0.0
            stock_pnl[trade.symbol] += trade.pnl

        # Sort by P&L descending
        sorted_stocks = sorted(stock_pnl.items(), key=lambda x: x[1], reverse=True)

        # Limit to top 30 for readability
        display_stocks = sorted_stocks[:30]

        stock_symbols = [s[0] for s in display_stocks]
        stock_pnls = [s[1] for s in display_stocks]

        # Color code: green for profit, red for loss
        colors = ["#2ca02c" if pnl > 0 else "#d62728" for pnl in stock_pnls]

        fig_stock = go.Figure(
            data=go.Bar(
                x=stock_symbols,
                y=stock_pnls,
                marker_color=colors,
                hovertemplate="<b>%{x}</b><br>P&L: ¥%{y:,.2f}<extra></extra>",
            )
        )

        fig_stock.update_layout(
            xaxis_title="Stock Symbol",
            yaxis_title="Total P&L (¥)",
            height=400,
            template="plotly_white",
            showlegend=False,
        )

        st.plotly_chart(fig_stock, use_container_width=True)
    else:
        st.info("No trades executed during this backtest period.")

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
