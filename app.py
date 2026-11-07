"""RetailPulse DI: Executive Decision Intelligence & Enterprise Operations Portal.

Main application entrypoint configuring multipage navigation, branding, and global store context.
Run with: streamlit run app.py
"""
import sys
from pathlib import Path

# Ensure project root is always first in sys.path regardless of execution context
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
from src.ui.styles import apply_custom_styles

st.set_page_config(
    page_title="RetailPulse DI | Enterprise Operations",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_custom_styles()

# ==============================================================================
# Modernized Clean Sidebar
# ==============================================================================
with st.sidebar:
    st.markdown("## ⚡ **RetailPulse DI**")
    st.caption("Enterprise Retail Operations & Decision Studio")
    st.markdown("---")

    # Global Store Location Filter
    st.markdown("##### 📍 Active Store Location")
    store_map = {
        "STR01": "Suburban Superstore (STR01)",
        "STR02": "Flagship Urban (STR02)",
        "STR03": "Express Mart (STR03)",
    }
    selected_store_id = st.selectbox(
        "Store",
        options=list(store_map.keys()),
        format_func=lambda x: store_map[x],
        index=0,
        label_visibility="collapsed",
    )
    st.session_state["global_store_id"] = selected_store_id

    st.markdown("---")

# ==============================================================================
# Configure Multipage Navigation Across 3 Clear Workspaces
# ==============================================================================
page_cockpit = st.Page(
    "src/ui/pages/1_executive_cockpit.py",
    title="Executive KPI Cockpit",
    icon="📊",
    default=True,
)

page_uncertainty = st.Page(
    "src/ui/pages/2_forecast_uncertainty.py",
    title="Demand & Uncertainty",
    icon="📈",
)

page_replenishment = st.Page(
    "src/ui/pages/3_replenishment_portal.py",
    title="Replenishment Studio",
    icon="⚡",
)

page_data_hub = st.Page(
    "src/ui/pages/3_data_hub.py",
    title="Master Data Hub (CRUD)",
    icon="📁",
)

page_observability = st.Page(
    "src/ui/pages/4_data_observability.py",
    title="Data Observability & Health",
    icon="🛡️",
)

pg = st.navigation(
    {
        "Executive Dashboards": [page_cockpit, page_uncertainty],
        "Operations & Decisions": [page_replenishment, page_data_hub],
        "System Integrity": [page_observability],
    }
)

pg.run()

# Bottom status indicator
with st.sidebar:
    st.markdown("---")
    st.markdown("🟢 **SQL Server:** `Connected`  \n📡 **Power BI Sync:** `DirectQuery 10s`")
    with st.expander("ℹ️ System Architecture", expanded=False):
        st.caption(
            """
            - **Engine:** Microsoft SQL Server 2025 (`RetailPulseDB`)
            - **Optimization:** HiGHS Mixed-Integer Linear Programming
            - **Forecasting:** LightGBM Quantile Regressors (P10/P50/P90)
            - **Write-Back:** Live DirectQuery Synchronized
            - **Version:** v1.2.0 Production
            """
        )
