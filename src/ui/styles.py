"""Executive Dark Theme, Animations & DOM Styling Components for RetailPulse DI Platform."""
from typing import Dict, Any, Optional
import streamlit as st
import plotly.graph_objects as go


def apply_custom_styles():
    """Injects high-contrast executive dark theme CSS targeting Streamlit DOM elements."""
    st.markdown(
        """
        <style>
        /* Import clean Inter typography */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

        /* ---------------------------------------------------------------------
           1. Global App Foundations & Typography
           --------------------------------------------------------------------- */
        html, body, [class*="css"], .stApp {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
            color: #F1F5F9 !important;
            background-color: #0E131F !important;
        }

        /* Smooth page rendering */
        .main .block-container {
            padding-top: 1.75rem !important;
            padding-bottom: 3.5rem !important;
            max-width: 1400px;
        }

        /* ---------------------------------------------------------------------
           2. Sidebar Specificity & High-Contrast Navigation
           --------------------------------------------------------------------- */
        section[data-testid="stSidebar"] {
            background-color: #1A2234 !important;
            border-right: 1px solid #334155 !important;
        }

        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] div,
        section[data-testid="stSidebar"] li {
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
            margin: 3px 0 !important;
            padding: 8px 12px !important;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }

        [data-testid="stSidebarNav"] a:hover {
            background-color: #243048 !important;
            color: #00D26A !important;
            transform: translateX(3px) !important;
        }

        [data-testid="stSidebarNav"] a[aria-current="page"] {
            background: linear-gradient(90deg, #243048 0%, #1A2234 100%) !important;
            border-left: 4px solid #00D26A !important;
            color: #FFFFFF !important;
            font-weight: 700 !important;
            box-shadow: 0 2px 8px rgba(0, 210, 106, 0.15) !important;
        }

        /* ---------------------------------------------------------------------
           3. Form Inputs, Selectboxes, Dropdowns & Popovers
           --------------------------------------------------------------------- */
        /* BaseWeb Select Input Container */
        div[data-baseweb="select"] > div {
            background-color: #141B2D !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            color: #F8FAFC !important;
            transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
        }

        div[data-baseweb="select"] > div:hover {
            border-color: #00D26A !important;
        }

        div[data-baseweb="select"] * {
            color: #F8FAFC !important;
        }

        /* Dropdown Popover Menus (renders in portal at body root) */
        div[data-baseweb="popover"],
        div[data-baseweb="menu"],
        ul[role="listbox"] {
            background-color: #1A2234 !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5) !important;
        }

        li[role="option"] {
            background-color: #1A2234 !important;
            color: #E2E8F0 !important;
            transition: background 0.15s ease !important;
        }

        li[role="option"]:hover,
        li[role="option"][aria-selected="true"] {
            background-color: #243048 !important;
            color: #00D26A !important;
            font-weight: 600 !important;
        }

        /* Text & Number Inputs */
        input[type="text"],
        input[type="number"],
        div[data-baseweb="input"] input {
            background-color: #141B2D !important;
            color: #F8FAFC !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
        }

        input[type="text"]:focus,
        input[type="number"]:focus,
        div[data-baseweb="input"] input:focus {
            border-color: #00D26A !important;
            box-shadow: 0 0 0 2px rgba(0, 210, 106, 0.25) !important;
        }

        /* Slider Controls */
        div[data-testid="stSlider"] div[role="slider"] {
            background-color: #00D26A !important;
            border: 2px solid #FFFFFF !important;
            box-shadow: 0 0 10px rgba(0, 210, 106, 0.6) !important;
        }

        /* ---------------------------------------------------------------------
           4. Interactive Buttons & Micro-Animations
           --------------------------------------------------------------------- */
        button[kind="primary"] {
            background: linear-gradient(135deg, #00D26A 0%, #059669 100%) !important;
            color: #08101C !important;
            font-weight: 700 !important;
            border: none !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 14px rgba(0, 210, 106, 0.3) !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        }

        button[kind="primary"]:hover {
            transform: translateY(-2px) scale(1.01) !important;
            box-shadow: 0 6px 20px rgba(0, 210, 106, 0.5) !important;
            color: #000000 !important;
        }

        button[kind="secondary"] {
            background-color: #1E293B !important;
            color: #E2E8F0 !important;
            border: 1px solid #475569 !important;
            border-radius: 8px !important;
            transition: all 0.2s ease-in-out !important;
        }

        button[kind="secondary"]:hover {
            background-color: #2D3B52 !important;
            border-color: #00D26A !important;
            color: #00D26A !important;
            transform: translateY(-1px) !important;
        }

        /* Download Button Styling */
        div[data-testid="stDownloadButton"] > button {
            background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
            color: #FFFFFF !important;
            font-weight: 600 !important;
            border: none !important;
            border-radius: 8px !important;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3) !important;
            transition: all 0.25s ease-in-out !important;
        }

        div[data-testid="stDownloadButton"] > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(37, 99, 235, 0.5) !important;
        }

        /* ---------------------------------------------------------------------
           5. Keyframe Animations
           --------------------------------------------------------------------- */
        @keyframes pulse-danger {
            0% {
                box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.6);
            }
            70% {
                box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
            }
            100% {
                box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
            }
        }

        @keyframes pulse-emerald {
            0%, 100% {
                box-shadow: 0 0 0 0 rgba(0, 210, 106, 0.4);
            }
            50% {
                box-shadow: 0 0 15px rgba(0, 210, 106, 0.3);
            }
        }

        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(12px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes shimmer-border {
            0%, 100% {
                border-left-color: #00D26A;
            }
            50% {
                border-left-color: #38BDF8;
            }
        }

        /* ---------------------------------------------------------------------
           6. Executive Header Banner
           --------------------------------------------------------------------- */
        .header-container {
            padding: 1.35rem 1.75rem;
            background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
            border-radius: 12px;
            color: #F8FAFC;
            margin-bottom: 1.5rem;
            border-left: 6px solid #00D26A;
            border-top: 1px solid #334155;
            border-right: 1px solid #334155;
            border-bottom: 1px solid #334155;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
            animation: shimmer-border 6s infinite ease-in-out, fadeInUp 0.4s ease-out;
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
           7. Glassmorphism Metric Cards
           --------------------------------------------------------------------- */
        .metric-card {
            background: linear-gradient(145deg, #1E293B 0%, #151D2C 100%);
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            animation: fadeInUp 0.4s ease-out;
        }

        .metric-card:hover {
            transform: translateY(-4px);
            border-color: #00D26A;
            box-shadow: 0 12px 24px -4px rgba(0, 0, 0, 0.5), 0 0 12px rgba(0, 210, 106, 0.2);
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
            font-weight: 800;
            color: #F8FAFC;
            line-height: 1.2;
        }

        .metric-delta-positive {
            font-size: 0.85rem;
            font-weight: 600;
            color: #00D26A;
            margin-top: 0.4rem;
        }

        .metric-delta-warning {
            font-size: 0.85rem;
            font-weight: 600;
            color: #F59E0B;
            margin-top: 0.4rem;
        }

        .metric-delta-danger {
            font-size: 0.85rem;
            font-weight: 600;
            color: #EF4444;
            margin-top: 0.4rem;
        }

        /* ---------------------------------------------------------------------
           8. Critical Stockout Alert Banner with Radar Pulse
           --------------------------------------------------------------------- */
        .critical-alert-banner {
            background: linear-gradient(135deg, #450A0A 0%, #2B0707 100%);
            border: 1px solid #DC2626;
            border-left: 6px solid #EF4444;
            border-radius: 10px;
            padding: 1rem 1.35rem;
            margin-bottom: 1.5rem;
            color: #FEE2E2;
            display: flex;
            align-items: center;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(220, 38, 38, 0.25);
            animation: pulse-danger 2.5s infinite, fadeInUp 0.4s ease-out;
        }

        .critical-alert-banner strong {
            color: #FFFFFF;
            margin-right: 0.5rem;
        }

        /* ---------------------------------------------------------------------
           9. Status Badges & Pills
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
            animation: pulse-danger 2s infinite;
        }

        .badge-excess {
            background-color: #1E3A8A;
            color: #BFDBFE;
            border: 1px solid #3B82F6;
        }

        /* ---------------------------------------------------------------------
           10. DataFrames & Tables
           --------------------------------------------------------------------- */
        div[data-testid="stDataFrame"] {
            border: 1px solid #334155 !important;
            border-radius: 10px !important;
            overflow: hidden !important;
            background-color: #141B2D !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
            animation: fadeInUp 0.4s ease-out;
        }

        /* ---------------------------------------------------------------------
           11. Tabs Customization
           --------------------------------------------------------------------- */
        button[data-baseweb="tab"] {
            color: #94A3B8 !important;
            font-weight: 600 !important;
            border-radius: 8px 8px 0 0 !important;
            padding: 8px 16px !important;
            transition: all 0.2s ease !important;
        }

        button[data-baseweb="tab"]:hover {
            color: #00D26A !important;
            background-color: rgba(0, 210, 106, 0.08) !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            color: #FFFFFF !important;
            border-bottom: 3px solid #00D26A !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str, badge: Optional[str] = None):
    """Renders executive banner at the top of each page with optional badge."""
    badge_html = f'<span class="badge badge-healthy" style="float: right; margin-top: 4px;">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="header-container">
            {badge_html}
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
    """Renders a styled KPI card with smooth elevation hover transition."""
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
    """Renders a prominent radar pulsing alert banner for urgent stockout runway risks."""
    detail_text = f" &mdash; {details}" if details else ""
    st.markdown(
        f"""
        <div class="critical-alert-banner">
            <span><strong>⚠️ CRITICAL STOCKOUT ALERT:</strong> {count} SKUs have less than 3 days of supply remaining{detail_text}. Immediate replenishment required.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_plotly_dark_theme(fig: go.Figure, title: str = "", height: int = 350) -> go.Figure:
    """Applies executive dark styling, transparent background, and smooth animations to Plotly charts."""
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20, 27, 45, 0.45)",
        font=dict(family="Inter, sans-serif", color="#F1F5F9", size=12),
        title=dict(
            text=f"<b>{title}</b>" if title else "",
            font=dict(color="#FFFFFF", size=14),
            x=0.0,
            y=0.98,
        ) if title else None,
        height=height,
        margin=dict(l=25, r=25, t=40 if title else 25, b=25),
        xaxis=dict(
            gridcolor="#243048",
            zerolinecolor="#334155",
            showline=True,
            linecolor="#334155",
            tickfont=dict(color="#94A3B8"),
        ),
        yaxis=dict(
            gridcolor="#243048",
            zerolinecolor="#334155",
            showline=True,
            linecolor="#334155",
            tickfont=dict(color="#94A3B8"),
        ),
        legend=dict(
            orientation="h",
            y=-0.22,
            x=0.0,
            font=dict(color="#E2E8F0"),
            bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            bgcolor="#1A2234",
            bordercolor="#00D26A",
            font=dict(color="#FFFFFF", family="Inter, sans-serif"),
        ),
        transition=dict(duration=400, easing="cubic-in-out"),
    )
    return fig
