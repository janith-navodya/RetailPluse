"""Page 2: Demand Forecast & Uncertainty Visualizer for RetailPulse DI Platform."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from src.ui.styles import apply_custom_styles, render_header, render_metric_card
from src.ui.data_access import (
    get_latest_inventory_health,
    get_sku_demand_history,
    generate_forecast_fan,
    get_model_benchmark_table,
)

st.set_page_config(page_title="Demand Uncertainty | RetailPulse DI", page_icon="📈", layout="wide")
apply_custom_styles()

render_header(
    title="Demand Forecast & Uncertainty Visualizer",
    subtitle="Latent demand reconstruction under stockout censoring, quantile fan projections, and evaluation benchmarks."
)

df_health = get_latest_inventory_health()
if df_health.empty:
    st.error("No inventory data found in database.")
    st.stop()

# SKU Selector Controls
col_sel1, col_sel2, col_sel3 = st.columns([1, 2, 1])

with col_sel1:
    stores = sorted(df_health["store_id"].unique().tolist())
    selected_store = st.selectbox("Store", stores, index=0)

with col_sel2:
    skus_for_store = df_health[df_health["store_id"] == selected_store]
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
    lead_time_forecast = st.slider("Lead Time Horizon (Days)", min_value=3, max_value=21, value=7, step=1)

# Fetch historical data
df_history = get_sku_demand_history(selected_store, selected_sku, days=90)
sku_info = skus_for_store[skus_for_store["product_id"] == selected_sku].iloc[0]

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
    censored_days = int((df_history["is_stockout"] == 1).sum()) if not df_history.empty else 0
    render_metric_card(
        label="Historical Censored Days",
        value=f"{censored_days} days (90D)",
        delta="Imputed via Moving Baselines",
        delta_type="warning" if censored_days > 0 else "positive",
    )

st.markdown("<br>", unsafe_allow_html=True)

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
        line=dict(color="#0284C7", width=2, dash="dash"),
    ))

    # Highlight stockout days
    stockouts_df = df_history[df_history["is_stockout"] == 1]
    if not stockouts_df.empty:
        fig_hist.add_trace(go.Scatter(
            x=stockouts_df["full_date"],
            y=stockouts_df["uncensored_demand"],
            mode="markers",
            name="Stockout Imputation Event",
            marker=dict(color="#EF4444", size=8, symbol="x"),
        ))

    fig_hist.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="Date",
        yaxis_title="Units Demand / Sales",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0.0),
    )
    st.plotly_chart(fig_hist, use_container_width=True)
else:
    st.info("No historical sales records found for this SKU.")

# Chart 2: Quantile Forecast Uncertainty Fan Chart
st.markdown("##### Lead-Time Demand Uncertainty Fan Chart (P10 - P50 - P90)")
st.caption(
    "Quantile regression projections for stochastic replenishment control. "
    "P10 serves as conservative lower bound, P50 as median operational baseline, and P90 as risk-hedging safety buffer."
)

df_fan = generate_forecast_fan(df_history, lead_time_days=lead_time_forecast)
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
        fillcolor="rgba(14, 165, 233, 0.18)",
        line=dict(width=0),
    ))

    # P50 median
    fig_fan.add_trace(go.Scatter(
        x=df_fan["forecast_date"],
        y=df_fan["p50_median"],
        mode="lines+markers",
        name="P50 Median Forecast",
        line=dict(color="#0284C7", width=3),
        marker=dict(size=6),
    ))

    fig_fan.update_layout(
        height=350,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="Forecast Horizon Date",
        yaxis_title="Projected Daily Demand (Units)",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1, x=0.0),
    )
    st.plotly_chart(fig_fan, use_container_width=True)

# Section 3: Model Evaluation Benchmark
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
    use_container_width=True,
    hide_index=True,
)

st.info(
    "**Core Takeaway:** Training machine learning models on raw sales leads to an empirical **-17.19% under-forecasting bias** "
    "because models learn that stockouts imply zero customer interest. "
    "Reconstructing latent demand via moving baselines eliminates this bias (**+0.20%**) and slashes WAPE by **8.82 percentage points**."
)
