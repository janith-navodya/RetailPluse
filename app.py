"""RetailPulse DI: Executive Decision Intelligence Portal.

Main application entrypoint configuring multipage navigation, branding, and system status.
Run with: streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="RetailPulse Decision Intelligence Portal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar System Health & Branding
with st.sidebar:
    st.markdown("## ⚡ **RetailPulse DI**")
    st.markdown("*Autonomous Decision Intelligence for Retail Replenishment*")
    st.markdown("---")

    st.markdown("### 🖥️ **System Environment**")
    st.markdown(
        """
        - **Target Engine:** Microsoft SQL Server 2025
        - **Database:** `RetailPulseDB`
        - **Auth:** Windows Integrated (`localhost`)
        - **Optimization:** HiGHS MILP Simplex
        - **ML Pipeline:** Quantile Regressors (P10/P50/P90)
        - **Schema:** Star Schema Dimensional Model
        """
    )
    st.markdown("---")
    st.caption("RetailPulse Platform v1.0.0 | Production Release")

# Configure Multipage Navigation
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
    title="Replenishment Engine",
    icon="🛒",
)

page_observability = st.Page(
    "src/ui/pages/4_data_observability.py",
    title="Data Observability & Audit",
    icon="🔍",
)

pg = st.navigation(
    {
        "Operational Dashboards": [page_cockpit, page_uncertainty],
        "Decision Automation": [page_replenishment],
        "System Integrity": [page_observability],
    }
)

pg.run()
