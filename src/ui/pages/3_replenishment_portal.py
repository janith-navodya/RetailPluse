"""Page 3: Constrained Replenishment Engine & Decision Portal for RetailPulse DI Platform."""
import streamlit as st
import pandas as pd
import numpy as np

from src.ui.styles import apply_custom_styles, render_header, render_metric_card
from src.ui.data_access import get_latest_inventory_health
from src.decision.safety_stock import StochasticInventoryController, InventoryStatusResult
from src.decision.optimizer import ConstrainedReplenishmentOptimizer, ReplenishmentOrderRecommendation
from src.decision.persistence import ReplenishmentPersistenceEngine

st.set_page_config(page_title="Replenishment Portal | RetailPulse DI", page_icon="🛒", layout="wide")
apply_custom_styles()

render_header(
    title="Constrained Replenishment Engine & Decision Portal",
    subtitle="Mixed-Integer Linear Programming (MILP) replenishment allocations under working capital and MOQ constraints."
)

persistence = ReplenishmentPersistenceEngine()
df_health = get_latest_inventory_health()

if df_health.empty:
    st.error("No inventory data found in database.")
    st.stop()

# Sidebar Optimization Controls
st.sidebar.markdown("### Optimization Parameters")
store_options = sorted(df_health["store_id"].unique().tolist())
selected_store = st.sidebar.selectbox("Store Location", store_options, index=0)

budget_input = st.sidebar.slider(
    "Working Capital Budget ($)",
    min_value=1000.0,
    max_value=50000.0,
    value=15000.0,
    step=1000.0,
    format="$%d",
)

service_level_input = st.sidebar.selectbox(
    "Target Cycle Service Level (CSL)",
    options=[0.90, 0.95, 0.98, 0.99],
    index=1,
    format_func=lambda x: f"{int(x * 100)}% Service Level",
)

apply_storage_cap = st.sidebar.checkbox("Enforce Physical Storage Limit", value=False)
max_storage_val = None
if apply_storage_cap:
    max_storage_val = st.sidebar.number_input("Max Storage Units Capacity", min_value=100, max_value=5000, value=1200)

run_button = st.sidebar.button("Solve Replenishment MILP", type="primary", width="stretch")

# Prepare Candidate SKUs
store_skus = df_health[df_health["store_id"] == selected_store]
controller = StochasticInventoryController(default_service_level=service_level_input)
candidates = []

for _, r in store_skus.iterrows():
    mu_d = float(r["rolling_30d_avg_daily_sales"]) if pd.notna(r["rolling_30d_avg_daily_sales"]) else 5.0
    sig_d = max(1.0, mu_d * 0.35)
    cand = controller.calculate_sku_inventory_status(
        store_id=r["store_id"],
        product_id=r["product_id"],
        product_name=r["product_name"],
        category=r["category"],
        supplier_id=r["supplier_id"],
        pack_size=int(r["pack_size"]),
        min_order_qty=int(r["min_order_qty"]),
        unit_cost_price=float(r["unit_cost_price"]),
        unit_retail_price=float(r["unit_retail_price"]),
        on_hand=int(r["closing_stock_on_hand"]),
        on_order=0,
        mean_demand=mu_d,
        std_demand=sig_d,
        mean_lead_time=float(r["mean_lead_time_days"]),
        std_lead_time=float(r["lead_time_std_dev"]),
        service_level=service_level_input,
    )
    candidates.append(cand)

# Session state management for recommendations
if "current_recommendations" not in st.session_state or run_button:
    optimizer = ConstrainedReplenishmentOptimizer()
    recs, summary = optimizer.optimize_orders(
        candidates,
        available_budget=budget_input,
        max_storage_units=max_storage_val,
    )
    st.session_state["current_recommendations"] = recs
    st.session_state["optimization_summary"] = summary
    st.session_state["active_date_key"] = 20251231

recs = st.session_state.get("current_recommendations", [])
summary = st.session_state.get("optimization_summary", {})
active_date_key = st.session_state.get("active_date_key", 20251231)

# Summary Metric Cards
c1, c2, c3, c4 = st.columns(4)
alloc = summary.get("budget_allocated", 0.0)
rem = summary.get("budget_remaining", 0.0)
pct_util = (alloc / max(1.0, budget_input)) * 100.0

with c1:
    render_metric_card(
        label="Budget Allocated",
        value=f"${alloc:,.2f}",
        delta=f"Remaining: ${rem:,.2f} ({pct_util:.1f}% used)",
        delta_type="positive" if pct_util <= 100.0 else "danger",
    )
with c2:
    total_units = summary.get("total_units_ordered", 0)
    render_metric_card(
        label="Total Replenishment Units",
        value=f"{total_units:,} units",
        delta=f"Across {summary.get('total_skus_replenished', 0)} SKUs",
    )
with c3:
    stockout_cands = sum(1 for c in candidates if c.inventory_status == "STOCKOUT_RISK")
    stockout_mitigated = sum(1 for r in recs if r.inventory_status == "STOCKOUT_RISK" and r.recommended_units > 0)
    render_metric_card(
        label="Stockout Risks Mitigated",
        value=f"{stockout_mitigated} / {stockout_cands}",
        delta="High Priority Allocation",
        delta_type="positive" if stockout_mitigated >= stockout_cands else "warning",
    )
with c4:
    solver_status = summary.get("solver_status", "OPTIMAL")
    render_metric_card(
        label="MILP Solver Engine",
        value="HiGHS Simplex",
        delta=f"Status: {solver_status}",
        delta_type="positive" if "OPTIMAL" in solver_status else "danger",
    )

st.markdown("<br>", unsafe_allow_html=True)

# Replenishment Order Table
st.markdown("##### Optimized Purchase Order Allocation Schedule")
st.caption(
    "Mathematical guarantees: 1) Strict budget adherence, 2) Semi-continuous MOQ adherence (order = 0 or >= MOQ), "
    "3) Pack size integer modularity (order = k * pack_size)."
)

if not recs:
    st.info("No candidate items require reordering under current inventory positions.")
    st.stop()

# Convert recs to DataFrame
table_data = []
for r in recs:
    moq_check = "PASS (0 units)" if r.recommended_units == 0 else (
        "PASS (>= MOQ)" if r.recommended_units >= r.min_order_qty else "FAIL"
    )
    pack_check = "PASS" if r.recommended_units % r.pack_size == 0 else "FAIL"

    table_data.append({
        "Rank": r.priority_rank,
        "SKU": r.product_id,
        "Product Name": r.product_name,
        "Category": r.category,
        "Status": r.inventory_status,
        "On Hand": r.current_on_hand_qty,
        "ROP": r.reorder_point_qty,
        "Deficit": r.replenishment_deficit,
        "Pack Size": r.pack_size,
        "MOQ": r.min_order_qty,
        "Rec. Packs": r.recommended_packs,
        "Rec. Units": r.recommended_units,
        "Unit Cost": r.unit_cost_price,
        "Total Cost": r.estimated_cost,
        "MOQ Compliant": moq_check,
        "Pack Compliant": pack_check,
    })

df_table = pd.DataFrame(table_data)

st.dataframe(
    df_table.style.format({
        "ROP": "{:.1f}",
        "Deficit": "{:.1f}",
        "Unit Cost": "${:.2f}",
        "Total Cost": "${:,.2f}",
    }),
    width="stretch",
    height=400,
)

# Workflow Approval Section
st.markdown("---")
st.markdown("### Manager Approval & Database Write-Back Workflow")

st.caption(
    "Submit generated recommendations to Microsoft SQL Server (`dbo.fact_replenishment_recommendation`). "
    "Managers can approve, modify order quantities, or reject recommendations."
)

col_act1, col_act2 = st.columns([1, 1])

with col_act1:
    st.markdown("##### Batch Commit to Database")
    if st.button("Save Fresh Recommendations Batch (PROPOSED)", type="secondary", width="stretch"):
        count = persistence.persist_recommendations(recs, run_date_key=active_date_key)
        st.success(f"Successfully persisted {count} recommendations to SQL Server table dbo.fact_replenishment_recommendation.")

with col_act2:
    st.markdown("##### Quick Action: Bulk Approve All Positive Orders")
    if st.button("Approve All Recommended Purchase Orders", type="primary", width="stretch"):
        persistence.persist_recommendations(recs, run_date_key=active_date_key)
        approved_count = 0
        for r in recs:
            if r.recommended_units > 0:
                rec_id = f"REC-{active_date_key}-{r.store_id}-{r.product_id}"
                persistence.update_recommendation_status(rec_id, "APPROVED")
                approved_count += 1
        st.success(f"Approved {approved_count} purchase orders in SQL Server database.")

# Single Item Modification / Review
st.markdown("##### Single Recommendation Review & Quantity Override")
rec_ids = [f"REC-{active_date_key}-{r.store_id}-{r.product_id}" for r in recs if r.recommended_units > 0]

if rec_ids:
    rev_c1, rev_c2, rev_c3 = st.columns([2, 1, 1])
    with rev_c1:
        target_rec_id = st.selectbox("Select Recommendation to Review", rec_ids, index=0)
        # Find matching rec
        chosen_rec = next(r for r in recs if f"REC-{active_date_key}-{r.store_id}-{r.product_id}" == target_rec_id)
        st.write(
            f"**Item:** {chosen_rec.product_name} | **Current Units:** {chosen_rec.recommended_units} | "
            f"**Unit Cost:** ${chosen_rec.unit_cost_price:.2f} | **Pack Size:** {chosen_rec.pack_size}"
        )

    with rev_c2:
        new_packs = st.number_input(
            "Modify Pack Count",
            min_value=0,
            max_value=200,
            value=chosen_rec.recommended_packs,
            step=1,
        )
        new_units = new_packs * chosen_rec.pack_size
        st.write(f"New Order: **{new_units} units** (${new_units * chosen_rec.unit_cost_price:,.2f})")

    with rev_c3:
        st.write("")
        st.write("")
        btn_apply = st.button("Apply Status & Units Override", width="stretch")
        if btn_apply:
            if new_units != chosen_rec.recommended_units:
                persistence.update_recommendation_status(target_rec_id, "MODIFIED", modified_units=new_units)
                st.success(f"Updated {target_rec_id} to MODIFIED with {new_units} units.")
            else:
                persistence.update_recommendation_status(target_rec_id, "APPROVED")
                st.success(f"Marked {target_rec_id} as APPROVED.")

