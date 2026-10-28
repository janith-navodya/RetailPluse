"""Page 2: Demand Forecast & Uncertainty Visualizer for RetailPulse DI Platform."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from src.ui.styles import (
    apply_custom_styles,
    render_header,
    render_metric_card,
    apply_plotly_dark_theme,
)
from src.ui.data_access import (
    get_latest_inventory_health,
    get_sku_demand_history,
    generate_forecast_fan,
    get_model_benchmark_table,
)

# Safe page configuration supporting both standalone and st.navigation
try:
    st.set_page_config(page_title="Demand Uncertainty | RetailPulse DI", page_icon="📈", layout="wide")
except Exception:
    pass

apply_custom_styles()

render_header(
    title="Demand Forecast & Uncertainty Visualizer",
    subtitle="Latent demand reconstruction under stockout censoring, quantile fan projections, and evaluation benchmarks.",
    badge="ML Quantiles (P10/P50/P90)",
)

df_health = get_latest_inventory_health()
if df_health.empty:
    st.error("No inventory data found in database.")
    st.stop()

# SKU Selector Controls
col_sel1, col_sel2, col_sel3 = st.columns([1, 2, 1.2])

with col_sel1:
    stores = sorted(df_health["store_id"].unique().tolist())
    selected_store = st.selectbox("Store Location", stores, index=0)

with col_sel2:
    skus_for_store = df_health[df_health["store_id"] == selected_store]
    if skus_for_store.empty:
        skus_for_store = df_health
    sku_options = {
        row["product_id"]: f"{row['product_id']} — {row['product_name']} ({row['category']})"
        for _, row in skus_for_store.iterrows()
    }
    selected_sku = st.selectbox(
        "Select Product (SKU)",
        options=list(sku_options.keys()),
        format_func=lambda x: sku_options[x],
        index=0,
    )

with col_sel3:
    history_days = st.selectbox("Historical Lookback Horizon", [30, 60, 90, 120, 180], index=2)

# What-If Simulation Controls in an expander
with st.expander("⚡ Interactive What-If Scenario Simulator (Demand Surge & Lead-Time)", expanded=True):
    sim_col1, sim_col2 = st.columns(2)
    with sim_col1:
        lead_time_forecast = st.slider("Lead Time Horizon (Days)", min_value=3, max_value=21, value=7, step=1)
    with sim_col2:
        demand_surge_pct = st.slider(
            "Simulate Demand Shock / Promotional Surge (%)",
            min_value=-50,
            max_value=100,
            value=0,
            step=5,
            format="%+d%%",
            help="Simulates sudden changes in market demand or promotional lifts to evaluate quantile uncertainty expansion.",
        )

# Fetch historical data
df_history = get_sku_demand_history(selected_store, selected_sku, days=history_days)
sku_matches = skus_for_store[skus_for_store["product_id"] == selected_sku]
sku_info = sku_matches.iloc[0] if not sku_matches.empty else df_health.iloc[0]

# Metrics row for selected SKU
m1, m2, m3, m4 = st.columns(4)
with m1:
    render_metric_card(
        label="Closing Stock on Hand",
        value=f"{sku_info['closing_stock_on_hand']} units",
        delta=f"Status: {sku_info['inventory_status']}",
        delta_type="danger" if sku_info['inventory_status'] == "STOCKOUT_RISK" else "positive",
    )
with m2:
    render_metric_card(
        label="30D Avg Daily Sales",
        value=f"{sku_info['rolling_30d_avg_daily_sales']:.1f} / day",
        delta=f"Days of Supply: {sku_info['days_of_supply']:.1f}d",
    )
with m3:
    render_metric_card(
        label="Supplier SLA & Lead Time",
        value=f"{sku_info['mean_lead_time_days']:.1f} ± {sku_info['lead_time_std_dev']:.1f} days",
        delta=f"Supplier: {sku_info['supplier_name']}",
    )
with m4:
    censored_days = int((df_history["is_stockout"] == 1).sum()) if not df_history.empty and "is_stockout" in df_history.columns else 0
    render_metric_card(
        label="Censored Stockout Days",
        value=f"{censored_days} days in window",
        delta="Imputed via Moving Baselines" if censored_days > 0 else "Clean Record",
        delta_type="warning" if censored_days > 0 else "positive",
    )

st.markdown("<br>", unsafe_allow_html=True)

# Main Tabbed Analysis
tab_vis, tab_eval = st.tabs([
    "📈 Demand History & Quantile Fan Projections",
    "🔬 Model Architecture & Evaluation Benchmarks",
])

with tab_vis:
    # Chart 1: Raw Sales vs Uncensored Latent Demand Overlay
    st.markdown("##### Historical Observed Sales vs Uncensored Latent Demand")
    st.caption(
        "When inventory drops to zero (stockout), observed sales collapse to zero, masking true consumer demand. "
        "RetailPulse reconstructs latent demand to prevent severe down-forecasting bias."
    )

    if not df_history.empty:
        fig_hist = go.Figure()

        # Raw sales line
        fig_hist.add_trace(go.Scatter(
            x=df_history["full_date"],
            y=df_history["raw_sales"],
            mode="lines+markers",
            name="Observed Sales (Censored)",
            line=dict(color="#64748B", width=2),
            marker=dict(size=4),
        ))

        # Uncensored demand line
        fig_hist.add_trace(go.Scatter(
            x=df_history["full_date"],
            y=df_history["uncensored_demand"],
            mode="lines",
            name="Reconstructed Latent Demand",
            line=dict(color="#00D26A", width=2.5, dash="dash"),
        ))

        # Highlight stockout days
        stockouts_df = df_history[df_history["is_stockout"] == 1]
        if not stockouts_df.empty:
            fig_hist.add_trace(go.Scatter(
                x=stockouts_df["full_date"],
                y=stockouts_df["uncensored_demand"],
                mode="markers",
                name="Stockout Imputation Event",
                marker=dict(color="#EF4444", size=9, symbol="x"),
            ))

        fig_hist.update_layout(
            xaxis_title="Date",
            yaxis_title="Units Demand / Sales",
            hovermode="x unified",
        )
        apply_plotly_dark_theme(fig_hist, title="Historical Observed Sales vs. Reconstructed Latent Demand", height=380)
        st.plotly_chart(fig_hist, width="stretch")
    else:
        st.info("No historical sales records found for this SKU.")

    # Chart 2: Quantile Forecast Uncertainty Fan Chart
    st.markdown("##### Lead-Time Demand Uncertainty Fan Chart (P10 - P50 - P90)")
    st.caption(
        f"Quantile regression projections over a **{lead_time_forecast}-day** horizon under "
        f"**{demand_surge_pct:+d}%** simulated demand surge. "
        "P10 serves as conservative lower bound, P50 as median operational baseline, and P90 as risk-hedging safety buffer."
    )

    df_fan = generate_forecast_fan(
        df_history,
        lead_time_days=lead_time_forecast,
        demand_shock_pct=demand_surge_pct,
    )

    if not df_fan.empty:
        fig_fan = go.Figure()

        # P90 upper bound
        fig_fan.add_trace(go.Scatter(
            x=df_fan["forecast_date"],
            y=df_fan["p90_risk_mitigating"],
            mode="lines",
            name="P90 Risk-Hedging Bound",
            line=dict(width=0),
            showlegend=False,
        ))

        # P10 lower bound with fill to P90
        fig_fan.add_trace(go.Scatter(
            x=df_fan["forecast_date"],
            y=df_fan["p10_conservative"],
            mode="lines",
            name="80% Confidence Interval (P10 - P90)",
            fill="tonexty",
            fillcolor="rgba(0, 210, 106, 0.18)",
            line=dict(width=0),
        ))

        # P50 median
        fig_fan.add_trace(go.Scatter(
            x=df_fan["forecast_date"],
            y=df_fan["p50_median"],
            mode="lines+markers",
            name="P50 Median Forecast",
            line=dict(color="#38BDF8", width=3),
            marker=dict(size=6, color="#38BDF8"),
        ))

        fig_fan.update_layout(
            xaxis_title="Forecast Date Horizon",
            yaxis_title="Projected Daily Demand (Units)",
            hovermode="x unified",
        )
        apply_plotly_dark_theme(fig_fan, title=f"Quantile Projection Fan Chart ({selected_sku})", height=360)
        st.plotly_chart(fig_fan, width="stretch")

        # Quantile Summary Metrics & Export
        q_col1, q_col2, q_col3 = st.columns([1, 1, 1])
        total_p50 = df_fan["p50_median"].sum()
        total_p90 = df_fan["p90_risk_mitigating"].sum()
        safety_gap = total_p90 - total_p50

        with q_col1:
            st.metric("Expected Lead-Time Demand (P50)", f"{total_p50:.1f} units")
        with q_col2:
            st.metric("Risk-Hedging Demand (P90)", f"{total_p90:.1f} units")
        with q_col3:
            st.metric("Recommended Safety Buffer", f"+{safety_gap:.1f} units")

        # Forecast CSV Download Button
        csv_forecast = df_fan.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Daily Quantile Projections (CSV)",
            data=csv_forecast,
            file_name=f"Quantile_Forecast_{selected_sku}_{lead_time_forecast}D.csv",
            mime="text/csv",
        )

with tab_eval:
    st.markdown("##### Walk-Forward Model Evaluation Suite")
    st.caption("Chronological rolling-origin evaluation on 730 days of retail transactions across all store-SKU combinations.")

    df_bench = get_model_benchmark_table()

    st.dataframe(
        df_bench.style.format({
            "WAPE (%)": "{:.2f}%",
            "MAE (Units)": "{:.2f}",
            "Forecast Bias (%)": "{:+.2f}%",
            "Pinball Loss (P90)": "{:.2f}",
        }),
        width="stretch",
        hide_index=True,
    )

    st.info(
        "**Core Takeaway:** Training machine learning models on raw sales leads to an empirical **-17.19% under-forecasting bias** "
        "because models learn that stockouts imply zero customer interest. "
        "Reconstructing latent demand via moving baselines eliminates this bias (**+0.20%**) and slashes WAPE by **8.82 percentage points**."
    )
