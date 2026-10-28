"""Custom CSS styling and executive theme components for RetailPulse DI Platform."""
import streamlit as st


def apply_custom_styles():
    """Injects custom CSS styling for executive decision dashboards."""
    st.markdown(
        """
        <style>
        /* Import clean inter-like typography */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Executive Header Banner */
        .header-container {
            padding: 1.2rem 1.5rem;
            background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
            border-radius: 12px;
            color: #F8FAFC;
            margin-bottom: 1.5rem;
            border-left: 6px solid #38BDF8;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        .header-title {
            font-size: 1.75rem;
            font-weight: 700;
            margin: 0;
            color: #FFFFFF;
            letter-spacing: -0.025em;
        }
        .header-subtitle {
            font-size: 0.95rem;
            color: #94A3B8;
            margin-top: 0.25rem;
            margin-bottom: 0;
        }

        /* KPI Metric Cards */
        .metric-card {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 1.25rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
            transition: transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .metric-label {
            font-size: 0.825rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748B;
            margin-bottom: 0.4rem;
        }
        .metric-value {
            font-size: 1.85rem;
            font-weight: 700;
            color: #0F172A;
            line-height: 1.2;
        }
        .metric-delta-positive {
            font-size: 0.85rem;
            font-weight: 600;
            color: #10B981;
            margin-top: 0.25rem;
        }
        .metric-delta-warning {
            font-size: 0.85rem;
            font-weight: 600;
            color: #F59E0B;
            margin-top: 0.25rem;
        }
        .metric-delta-danger {
            font-size: 0.85rem;
            font-weight: 600;
            color: #EF4444;
            margin-top: 0.25rem;
        }

        /* Status Badges */
        .badge {
            display: inline-block;
            padding: 0.25rem 0.65rem;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 9999px;
            text-align: center;
        }
        .badge-healthy {
            background-color: #DEF7EC;
            color: #03543F;
            border: 1px solid #BCF0DA;
        }
        .badge-reorder {
            background-color: #FEF3C7;
            color: #92400E;
            border: 1px solid #FDE68A;
        }
        .badge-stockout {
            background-color: #FDE8E8;
            color: #9B1C1C;
            border: 1px solid #FBD5D5;
        }
        .badge-excess {
            background-color: #E1EFFE;
            color: #1E429F;
            border: 1px solid #C3DDFD;
        }
        .badge-approved {
            background-color: #D1FAE5;
            color: #065F46;
            border: 1px solid #A7F3D0;
        }
        .badge-modified {
            background-color: #FEF3C7;
            color: #92400E;
            border: 1px solid #FDE68A;
        }
        .badge-rejected {
            background-color: #FEE2E2;
            color: #991B1B;
            border: 1px solid #FECACA;
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background-color: #F8FAFC;
            border-right: 1px solid #E2E8F0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str):
    """Renders executive banner at the top of each page."""
    st.markdown(
        f"""
        <div class="header-container">
            <h1 class="header-title">{title}</h1>
            <p class="header-subtitle">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(
    label: str,
    value: str,
    delta: str = "",
    delta_type: str = "positive",
):
    """Renders a styled KPI card."""
    delta_class = "metric-delta-positive"
    if delta_type == "warning":
        delta_class = "metric-delta-warning"
    elif delta_type == "danger":
        delta_class = "metric-delta-danger"

    delta_html = f'<div class="{delta_class}">{delta}</div>' if delta else ""

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )
