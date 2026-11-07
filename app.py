"""Run with: streamlit run app.py"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backtest import BacktestConfig, evaluate_split, monthly_pnl
from data import DATA_PATH, download_prices, load_prices
from strategy import statistical_summary, explain_statistics

DISCLAIMER = (
    "Exploratory research simulation • Yahoo CL=F and BZ=F are continuous futures "
    "proxies. Rolls, contract selection and price adjustments can distort spreads "
    "and P&L. These results are not verified executable or live-trading performance."
)


def make_charts(indicators, daily, entry=1.5, exit_band=0.25, stop_z=3.0):
    prices = go.Figure()
    for column, color in [("WTI", "#3b82f6"), ("Brent", "#f59e0b")]:
        prices.add_scatter(x=indicators.index, y=indicators[column], name=column,
                           line=dict(color=color))
    prices.update_layout(title="Daily closing prices", yaxis_title="USD per barrel")

    spread = go.Figure()
    spread.add_scatter(x=indicators.index, y=indicators["spread"], name="Brent − WTI",
                       line=dict(color="#8b5cf6"))
    spread.add_scatter(x=indicators.index, y=indicators["rolling_mean"], name="Rolling mean",
                       line=dict(dash="dot", color="#94a3b8"))
    previous = daily["position"].shift(1, fill_value=0)
    for mask, label, symbol, color in [
        ((daily["position"] == 1) & (previous != 1), "Long spread executed", "triangle-up", "#10b981"),
        ((daily["position"] == -1) & (previous != -1), "Short spread executed", "triangle-down", "#ef4444"),
        ((daily["position"] == 0) & (previous != 0), "Exit executed", "x", "#64748b"),
    ]:
        spread.add_scatter(x=indicators.index[mask], y=indicators.loc[mask, "spread"],
                           name=label, mode="markers", marker=dict(symbol=symbol, size=10, color=color))
    spread.update_layout(title="Spread and executed trades", yaxis_title="USD per barrel")

    zscore = go.Figure()
    zscore.add_scatter(x=indicators.index, y=indicators["zscore"], name="Z-score",
                       line=dict(color="#3b82f6"))
    for threshold in [-entry, entry]:
        zscore.add_hline(y=threshold, line_dash="dash", line_color="#ef4444")
    for threshold in [-stop_z, stop_z]:
        zscore.add_hline(y=threshold, line_dash="dot", line_color="#f59e0b")
    zscore.add_hrect(y0=-exit_band, y1=exit_band, fillcolor="#10b981", opacity=0.12, line_width=0)
    zscore.add_hline(y=0, line_color="#94a3b8")
    zscore.update_layout(title="Rolling spread Z-score", yaxis_title="Standard deviations")

    pnl = go.Figure()
    for column, name, color in [("cumulative_gross", "Gross P&L", "#94a3b8"),
                                ("cumulative_net", "Net P&L", "#10b981")]:
        pnl.add_scatter(x=daily.index, y=daily[column], name=name, line=dict(color=color))
    pnl.update_layout(title="Illustrative cumulative P&L", yaxis_title="USD")
    correlation = go.Figure()
    correlation.add_scatter(x=indicators.index, y=indicators["rolling_correlation"],
                            name="60-day price correlation", line=dict(color="#8b5cf6"))
    correlation.update_layout(title="60-observation rolling price correlation",
                              yaxis_title="Pearson correlation", yaxis_range=[-1, 1])
    monthly = monthly_pnl(daily)
    month_chart = go.Figure(go.Bar(x=monthly.index, y=monthly["net_pnl"], name="Monthly net P&L",
                                  marker_color=["#10b981" if n >= 0 else "#ef4444"
                                                for n in monthly["net_pnl"]]))
    month_chart.update_layout(title="Monthly net P&L (mark to market)", yaxis_title="USD")
    figures = dict(prices=prices, spread=spread, zscore=zscore, pnl=pnl,
                   correlation=correlation, monthly=month_chart)
    for figure in figures.values():
        figure.update_layout(template="plotly_white", height=390, hovermode="x unified",
                             margin=dict(l=20, r=20, t=55, b=30),
                             legend=dict(orientation="h", y=-0.2))
    return figures


def main():
    st.set_page_config(page_title="WTI–Brent Spread Research", page_icon="📊", layout="wide")
    st.title("WTI–Brent Crude Oil Spread Trading")
    st.subheader("Using Mean Reversion")
    st.caption(DISCLAIMER)
    with st.sidebar:
        st.header("Research settings")
        window = st.number_input("Rolling window (observations)", 5, 120, 20)
        entry = st.number_input("Entry Z-score", 0.5, 5.0, 1.5, 0.25)
        exit_band = st.number_input("Exit band around zero", 0.0, 1.0, 0.25, 0.05)
        stop_z = st.number_input("Stop-loss Z-score (absolute)", 0.75, 10.0, 3.0, 0.25)
        max_holding = st.number_input("Maximum holding days", 1, 120, 15)
        quantity = st.number_input("Contracts per leg", 1, 20, 1)
        commission = st.number_input("Commission / contract / leg ($)", 0.0, 50.0, 2.5, 0.5)
        slippage = st.number_input("Slippage ticks / leg / execution", 0.0, 20.0, 1.0, 0.5)
        refresh = st.button("Download / refresh Yahoo prices", type="primary")
        st.caption("One tick = $0.01/barrel = $10 per contract on each leg.")
    if not exit_band < entry < stop_z:
        st.error("Require exit band < entry threshold < stop-loss Z-score.")
        st.stop()
    try:
        if refresh or not DATA_PATH.exists():
            with st.spinner("Downloading five years of daily Yahoo prices…"):
                prices = download_prices()
        else:
            prices = load_prices()
        segments = evaluate_split(prices, BacktestConfig(int(quantity), commission, slippage),
                                  window=int(window), entry=entry, exit_band=exit_band,
                                  stop_z=stop_z, max_holding=int(max_holding))
        stats = statistical_summary(prices)
    except Exception as exc:
        st.error(f"Unable to complete the analysis: {exc}")
        st.info("Allow Yahoo Finance access and retry, or run `python data.py` first. "
                "No sample prices or invented results are shown.")
        st.stop()
    st.caption(f"{len(prices):,} matched daily observations • {stats['start']} to {stats['end']} "
               "• raw daily Close • missing pairs dropped • cached CSV until refreshed")
    st.info("Long spread = buy Brent and sell WTI. Short spread = sell Brent and buy WTI. "
            "Signals execute at the next available daily close. P&L starts after execution.")
    st.subheader("Chronological validation: 70% training / 30% testing")
    st.caption("Parameters are fixed across both segments; no automated tuning. Training ends flat, "
               "testing starts flat. Earlier training prices warm up trailing test indicators. "
               "The full history was inspected previously, so this is retrospective holdout analysis, "
               "not a pristine unseen experiment. Repeated test-driven tuning compromises validation.")
    comparison = []
    for name, result in segments.items():
        dates = result["daily"].index
        comparison.append(dict(segment=name, start=str(dates[0].date()), end=str(dates[-1].date()),
                               observations=len(dates), **result["metrics"]))
    st.dataframe(pd.DataFrame(comparison), hide_index=True, width="stretch")
    selected = st.radio("Show segment", ["Training", "Testing"], index=1, horizontal=True)
    result = segments[selected]
    indicators, daily, trades, metrics = (result[k] for k in ["indicators", "daily", "trades", "metrics"])
    st.subheader(f"{selected} performance")
    first = st.columns(4)
    for column, (label, value) in zip(first, [
        ("Gross P&L", f"${metrics['gross_pnl']:,.0f}"),
        ("Estimated costs", f"${metrics['transaction_costs']:,.0f}"),
        ("Net P&L", f"${metrics['net_pnl']:,.0f}"),
        ("Maximum drawdown", f"${metrics['max_drawdown_usd']:,.0f}"),
    ]):
        column.metric(label, value)
    second = st.columns(4)
    for column, (label, key) in zip(second, [("Sharpe (252 days)", "sharpe_ratio"),
                                            ("Profit factor", "profit_factor"),
                                            ("Win rate", "win_rate"),
                                            ("Closed trades", "number_of_trades")]):
        value = metrics[key]
        formatted = "N/A" if value is None else (
            f"{value:.1%}" if key == "win_rate" else
            str(value) if key == "number_of_trades" else f"{value:.2f}")
        column.metric(label, formatted)
    st.caption("Sharpe uses daily net P&L scaled by fixed $100,000 reference capital, "
               "zero interest, and 252 observations/year. Profit factor and win rate use "
               "closed trades after costs. N/A means the denominator is undefined. "
               "Any open trade is liquidated at the final close with exit costs.")
    charts = make_charts(indicators, daily, entry, exit_band, stop_z)
    price_tab, stats_tab, trades_tab, costs_tab = st.tabs(
        ["Charts", "Statistical analysis", "Trades & downloads", "Slippage sensitivity"])
    with price_tab:
        for chart in charts.values():
            st.plotly_chart(chart, width="stretch")
    with stats_tab:
        st.caption("Full-sample descriptive statistics only; these do not fit or filter the strategy.")
        st.metric("Mean spread ($/barrel)", f"{stats['spread_mean']:.2f}")
        st.metric("Spread standard deviation ($/barrel)", f"{stats['spread_std']:.2f}")
        for sentence in explain_statistics(stats):
            st.write(sentence)
        st.dataframe(pd.DataFrame([stats]), hide_index=True)
    with trades_tab:
        st.write(f"Completed-trade summary — {selected}")
        st.dataframe(pd.DataFrame([result["summary"]]), hide_index=True)
        st.caption("Holding days are matched trading intervals from executed entry to exit. "
                   "Both legs’ entry and exit prices are execution-day Yahoo proxy closes, not verified fills. Slippage is deducted separately as a cash cost. Monthly P&L uses daily mark-to-market.")
        st.dataframe(trades, hide_index=True, width="stretch")
        for label, frame, filename, index in [
            ("Cleaned prices CSV", prices, "prices.csv", True),
            ("Daily backtest CSV", daily, "backtest.csv", True),
            ("Trade ledger CSV", trades, f"{selected.lower()}_trades.csv", False),
            ("Monthly P&L CSV", result["monthly"], f"{selected.lower()}_monthly.csv", True),
        ]:
            st.download_button(label, frame.to_csv(index=index), filename, "text/csv")
    with costs_tab:
        st.caption("Same fixed signals and commissions in every scenario; only slippage changes. "
                   "Ticks are charged per contract, per leg, per execution. Includes exit costs.")
        for name, segment in segments.items():
            st.write(name)
            st.dataframe(segment["sensitivity"], hide_index=True, width="stretch")
    with st.expander("Assumptions and limitations"):
        st.write("Equal contract quantities; 1,000 barrels per contract on both legs. "
                 "Default costs: $2.50 commission plus one $10 tick of slippage per leg "
                 "per execution ($50 total for a one-pair round trip). No margin, financing, "
                 "liquidity constraints, or actual roll transactions are modeled. "
                 "Contract expiries may be mismatched. A continuous-series price change "
                 "can reflect a roll instead of a tradable gain. Stops are next-close signals, "
                 "not guaranteed fills or dollar-loss caps. Chronological testing uses fixed "
                 "parameters, but previously inspected data are not a pristine unseen sample. "
                 "Changing settings repeatedly risks overfitting.")


if __name__ == "__main__":
    main()
