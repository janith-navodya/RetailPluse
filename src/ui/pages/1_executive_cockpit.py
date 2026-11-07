"""Page 1: Executive KPI & Inventory Health Cockpit for RetailPulse DI Platform."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.ui.styles import (
    apply_custom_styles,
    render_header,
    render_metric_card,
    render_critical_alert,
    apply_plotly_dark_theme,
)
from src.ui.data_access import get_executive_kpis, get_latest_inventory_health

# Safe page configuration supporting both standalone and st.navigation
try:
    st.set_page_config(page_title="Executive Cockpit | RetailPulse DI", page_icon="📊", layout="wide")
except Exception:
    pass

apply_custom_styles()

render_header(
    title="Executive KPI & Inventory Health Cockpit",
    subtitle="Continuous monitoring of working capital efficiency, supply runway, and portfolio stockout exposure.",
    badge="Live Telemetry",
)

# Load data
kpis = get_executive_kpis()
df_health = get_latest_inventory_health()

# Top Critical Stockout Alert Banner
if not df_health.empty:
    critical_skus = df_health[(df_health["days_of_supply"] < 3.0) | (df_health["closing_stock_on_hand"] == 0)]
    if not critical_skus.empty:
        critical_count = len(critical_skus)
        render_critical_alert(
            count=critical_count,
            details=f"{critical_count} critical items with < 3 days of supply remaining across fleet",
        )

# Top KPI Metric Cards
col1, col2, col3, col4 = st.columns(4)

with col1:
    render_metric_card(
        label="Total Gross Margin",
        value=f"{kpis['gross_margin_pct']:.2f}%",
        delta=f"Net Profit: Rs. {kpis['total_gross_profit']:,.0f}",
        delta_type="positive" if kpis['gross_margin_pct'] >= 35.0 else "warning",
    )

with col2:
    avg_dos = df_health["days_of_supply"].dropna().mean() if not df_health.empty else 28.5
    render_metric_card(
        label="Average Days of Supply",
        value=f"{avg_dos:.1f} days",
        delta="Target Runway: 25 - 45 days",
        delta_type="positive" if 20 <= avg_dos <= 50 else "warning",
    )

with col3:
    render_metric_card(
        label="Active Stockout Count",
        value=f"{kpis['active_stockouts']} SKUs",
        delta=f"Stockout Rate: {kpis['overall_stockout_rate_pct']:.1f}%",
        delta_type="danger" if kpis['active_stockouts'] > 5 else "warning",
    )

with col4:
    render_metric_card(
        label="Excess Working Capital",
        value=f"Rs. {kpis['excess_working_capital']:,.0f}",
        delta="Trapped Capital in >45D Supply",
        delta_type="warning" if kpis['excess_working_capital'] > 20000 else "positive",
    )

st.markdown("<br>", unsafe_allow_html=True)

# Interactive Filters Section
st.markdown("### 🎛️ Inventory Fleet Filtering & Analysis")

if df_health.empty:
    st.warning("No inventory health snapshot found. Utilizing standby diagnostic mode.")
    st.stop()

filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1, 1, 1, 1.2])

with filter_col1:
    categories = ["ALL"] + sorted(df_health["category"].dropna().unique().tolist())
    selected_category = st.selectbox("Product Category", categories, index=0)

with filter_col2:
    suppliers = ["ALL"] + sorted(df_health["supplier_name"].dropna().unique().tolist())
    selected_supplier = st.selectbox("Supplier Cohort", suppliers, index=0)

with filter_col3:
    status_options = ["ALL", "STOCKOUT_RISK", "REORDER_NOW", "HEALTHY", "EXCESS_STOCK"]
    selected_status = st.selectbox("Health Status", status_options, index=0)

with filter_col4:
    search_query = st.text_input("🔍 Search SKU or Product Name", placeholder="e.g. PRD01 or Milk")

# Filter dataframe
filtered_df = df_health.copy()
active_store = st.session_state.get("global_store_id")
if active_store and "store_id" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["store_id"] == active_store]

if selected_category != "ALL":
    filtered_df = filtered_df[filtered_df["category"] == selected_category]
if selected_supplier != "ALL":
    filtered_df = filtered_df[filtered_df["supplier_name"] == selected_supplier]
if selected_status != "ALL":
    filtered_df = filtered_df[filtered_df["inventory_status"] == selected_status]
if search_query.strip():
    q = search_query.strip().lower()
    filtered_df = filtered_df[
        filtered_df["product_id"].str.lower().str.contains(q)
        | filtered_df["product_name"].str.lower().str.contains(q)
    ]

# Summary filter status chip
total_filtered_capital = filtered_df["ending_inventory_value"].sum() if not filtered_df.empty else 0.0
st.caption(
    f"Showing **{len(filtered_df)}** of **{len(df_health)}** SKUs &mdash; "
    f"Filtered Capital Value: **Rs. {total_filtered_capital:,.2f}**"
)

if filtered_df.empty:
    st.info("ℹ️ No items match the specified filters. Try selecting 'ALL' or clearing search.")
    st.stop()

# Tabbed Analytics Views
tab_charts, tab_table, tab_critical = st.tabs([
    "📊 Fleet Analytics & Distributions",
    "📋 SKU Inventory Table & CSV Export",
    "🚨 Critical Stockout Exposure (<7D)",
])

with tab_charts:
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        fig_dos = px.histogram(
            filtered_df,
            x="days_of_supply",
            nbins=20,
            color="inventory_status",
            color_discrete_map={
                "STOCKOUT_RISK": "#EF4444",
                "REORDER_NOW": "#F59E0B",
                "HEALTHY": "#10B981",
                "EXCESS_STOCK": "#3B82F6",
            },
            labels={"days_of_supply": "Days of Supply (Days)", "count": "SKU Count"},
        )
        fig_dos.add_vline(x=14.0, line_dash="dash", line_color="#EF4444", annotation_text="Critical (14D)", annotation_position="top left")
        fig_dos.add_vline(x=45.0, line_dash="dash", line_color="#3B82F6", annotation_text="Excess (45D)", annotation_position="top right")
        apply_plotly_dark_theme(fig_dos, title="Days of Supply (DoS) Fleet Profile", height=380)
        st.plotly_chart(fig_dos, width="stretch")

    with chart_col2:
        capital_by_cat = (
            filtered_df.groupby(["category", "inventory_status"])["ending_inventory_value"]
            .sum()
            .reset_index()
        )
        fig_cap = px.bar(
            capital_by_cat,
            x="category",
            y="ending_inventory_value",
            color="inventory_status",
            color_discrete_map={
                "STOCKOUT_RISK": "#EF4444",
                "REORDER_NOW": "#F59E0B",
                "HEALTHY": "#10B981",
                "EXCESS_STOCK": "#3B82F6",
            },
            labels={"ending_inventory_value": "Capital (Rs.)", "category": "Category"},
        )
        apply_plotly_dark_theme(fig_cap, title="Deployed Working Capital by Health Status", height=380)
        st.plotly_chart(fig_cap, width="stretch")

with tab_table:
    export_col1, export_col2 = st.columns([3, 1])
    with export_col1:
        st.markdown(f"##### Fleet SKU Inventory Details ({len(filtered_df)} Items)")
    with export_col2:
        csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Export Table as CSV",
            data=csv_bytes,
            file_name="Fleet_Inventory_Health.csv",
            mime="text/csv",
            width="stretch",
        )

    display_df = filtered_df[[
        "store_id",
        "product_id",
        "product_name",
        "category",
        "supplier_name",
        "closing_stock_on_hand",
        "safety_stock",
        "reorder_point",
        "days_of_supply",
        "ending_inventory_value",
        "inventory_status",
    ]].copy()

    display_df = display_df.rename(columns={
        "store_id": "Store",
        "product_id": "SKU",
        "product_name": "Product Name",
        "category": "Category",
        "supplier_name": "Supplier",
        "closing_stock_on_hand": "On Hand",
        "safety_stock": "Safety Stock",
        "reorder_point": "Reorder Point",
        "days_of_supply": "Days of Supply",
        "ending_inventory_value": "Capital (Rs.)",
        "inventory_status": "Status",
    })

    st.dataframe(
        display_df.style.format({
            "Safety Stock": "{:.1f}",
            "Reorder Point": "{:.1f}",
            "Days of Supply": "{:.1f}d",
            "Capital (Rs.)": "Rs. {:,.2f}",
        }),
        width="stretch",
        height=400,
    )

with tab_critical:
    critical_subset = filtered_df[
        (filtered_df["days_of_supply"] < 7.0) | (filtered_df["inventory_status"] == "STOCKOUT_RISK")
    ].sort_values("days_of_supply")

    if critical_subset.empty:
        st.success("✅ No SKUs currently at critical stockout risk under this filter selection.")
    else:
        st.markdown(f"##### High-Priority Action List: {len(critical_subset)} Items Requiring Replenishment")
        crit_display = critical_subset[[
            "product_id", "product_name", "category", "supplier_name",
            "closing_stock_on_hand", "reorder_point", "days_of_supply", "inventory_status"
        ]].rename(columns={
            "product_id": "SKU",
            "product_name": "Product Name",
            "category": "Category",
            "supplier_name": "Supplier",
            "closing_stock_on_hand": "Current Stock",
            "reorder_point": "Reorder Point",
            "days_of_supply": "Runway (Days)",
            "inventory_status": "Urgency Status",
        })
        st.dataframe(
            crit_display.style.format({"Runway (Days)": "{:.1f}d", "Reorder Point": "{:.1f}"}),
            width="stretch",
            height=320,
        )
