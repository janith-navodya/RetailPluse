"""Executive Dark Theme & DOM Styling Components for RetailPulse DI Platform."""
import streamlit as st


def apply_custom_styles():
    """Injects high-contrast executive dark theme CSS targeting Streamlit DOM elements."""
    st.markdown(
        """
        <style>
        /* Import clean inter-like typography */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: #F1F5F9;
        }

        /* ---------------------------------------------------------------------
           1. Sidebar Specificity & High-Contrast Navigation
           --------------------------------------------------------------------- */
        section[data-testid="stSidebar"] {
            background-color: #1A2234 !important;
            border-right: 1px solid #334155 !important;
        }

        section[data-testid="stSidebar"] * {
            color: #E2E8F0 !important;
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] strong {
            color: #FFFFFF !important;
        }

        section[data-testid="stSidebar"] .stCaption,
        section[data-testid="stSidebar"] small {
            color: #94A3B8 !important;
        }

        /* Sidebar Navigation Item States */
        [data-testid="stSidebarNav"] a {
            color: #E2E8F0 !important;
            border-radius: 8px !important;
            margin: 2px 0 !important;
            transition: all 0.15s ease-in-out !important;
        }

        [data-testid="stSidebarNav"] a:hover {
            background-color: #243048 !important;
            color: #00D26A !important;
        }

        [data-testid="stSidebarNav"] a[aria-current="page"] {
            background-color: #243048 !important;
            border-left: 4px solid #00D26A !important;
            color: #FFFFFF !important;
            font-weight: 600 !important;
        }

        /* ---------------------------------------------------------------------
           2. Executive Header Banner
           --------------------------------------------------------------------- */
        .header-container {
            padding: 1.25rem 1.75rem;
            background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
            border-radius: 12px;
            color: #F8FAFC;
            margin-bottom: 1.5rem;
            border-left: 6px solid #00D26A;
            border-top: 1px solid #334155;
            border-right: 1px solid #334155;
            border-bottom: 1px solid #334155;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
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
            margin-top: 0.35rem;
            margin-bottom: 0;
        }

        /* ---------------------------------------------------------------------
           3. Dark Glassmorphism Metric Cards
           --------------------------------------------------------------------- */
        .metric-card {
            background-color: #1E293B;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.25), 0 2px 4px -1px rgba(0, 0, 0, 0.15);
            transition: transform 0.15s ease-in-out, box-shadow 0.15s ease-in-out, border-color 0.15s ease-in-out;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            border-color: #475569;
            box-shadow: 0 8px 16px -2px rgba(0, 0, 0, 0.35);
        }
        .metric-label {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #94A3B8;
            margin-bottom: 0.4rem;
        }
        .metric-value {
            font-size: 1.85rem;
            font-weight: 700;
            color: #F8FAFC;
            line-height: 1.2;
        }
        .metric-delta-positive {
            font-size: 0.85rem;
            font-weight: 600;
            color: #00D26A;
            margin-top: 0.35rem;
        }
        .metric-delta-warning {
            font-size: 0.85rem;
            font-weight: 600;
            color: #F59E0B;
            margin-top: 0.35rem;
        }
        .metric-delta-danger {
            font-size: 0.85rem;
            font-weight: 600;
            color: #EF4444;
            margin-top: 0.35rem;
        }

        /* ---------------------------------------------------------------------
           4. Critical Stockout Alert Banner
           --------------------------------------------------------------------- */
        .critical-alert-banner {
            background-color: #450A0A;
            border: 1px solid #DC2626;
            border-left: 6px solid #EF4444;
            border-radius: 8px;
            padding: 0.9rem 1.25rem;
            margin-bottom: 1.5rem;
            color: #FEE2E2;
            display: flex;
            align-items: center;
            font-weight: 500;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }
        .critical-alert-banner strong {
            color: #FFFFFF;
            margin-right: 0.5rem;
        }

        /* ---------------------------------------------------------------------
           5. Status Badges
           --------------------------------------------------------------------- */
        .badge {
            display: inline-block;
            padding: 0.25rem 0.65rem;
            font-size: 0.75rem;
            font-weight: 600;
            border-radius: 9999px;
            text-align: center;
        }
        .badge-healthy {
            background-color: #064E3B;
            color: #A7F3D0;
            border: 1px solid #059669;
        }
        .badge-reorder {
            background-color: #78350F;
            color: #FDE68A;
            border: 1px solid #D97706;
        }
        .badge-stockout {
            background-color: #7F1D1D;
            color: #FECACA;
            border: 1px solid #DC2626;
        }
        .badge-excess {
            background-color: #1E3A8A;
            color: #BFDBFE;
            border: 1px solid #3B82F6;
        }
        .badge-approved {
            background-color: #064E3B;
            color: #A7F3D0;
            border: 1px solid #059669;
        }
        .badge-modified {
            background-color: #78350F;
            color: #FDE68A;
            border: 1px solid #D97706;
        }
        .badge-rejected {
            background-color: #7F1D1D;
            color: #FECACA;
            border: 1px solid #DC2626;
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


def render_critical_alert(count: int, details: str = ""):
    """Renders a prominent top alert banner for urgent stockout runway risks."""
    detail_text = f" &mdash; {details}" if details else ""
    st.markdown(
        f"""
        <div class="critical-alert-banner">
            <span><strong>⚠️ CRITICAL STOCKOUT ALERT:</strong> {count} SKUs have less than 3 days of supply remaining{detail_text}. Immediate replenishment required.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
