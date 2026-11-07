"""Smoke & Integration Test Suite for RetailPulse DI Streamlit Decision Portal.

Verifies:
1. Data access layer queries execute cleanly against SQL Server.
2. Forecast fan calculation maintains mathematical quantile monotonicity (P10 <= P50 <= P90).
3. All 4 Streamlit page modules compile and execute without uncaught runtime exceptions via AppTest.
4. Model evaluation and quarantine feeds return valid structures.
"""
from pathlib import Path
import pytest
import pandas as pd
import numpy as np
from streamlit.testing.v1 import AppTest

ROOT_DIR = Path(__file__).parent.parent.resolve()

from src.ui.data_access import (
    get_executive_kpis,
    get_latest_inventory_health,
    get_sku_demand_history,
    generate_forecast_fan,
    get_model_benchmark_table,
    get_quarantine_stats,
    get_quarantine_feed,
)


# ==============================================================================
# Unit & Data Layer Verification
# ==============================================================================

class TestUIDataAccess:
    """Verifies that the Streamlit data access layer queries SQL Server cleanly."""

    @pytest.mark.database
    def test_executive_kpis_contract(self):
        """Validates that executive KPIs dictionary contains all expected metrics."""
        kpis = get_executive_kpis()
        assert isinstance(kpis, dict)
        required_keys = [
            "total_net_sales", "total_cogs", "total_gross_profit",
            "gross_margin_pct", "overall_stockout_rate_pct",
            "annualized_inventory_turnover", "active_stockouts", "excess_working_capital"
        ]
        for k in required_keys:
            assert k in kpis
            assert isinstance(kpis[k], (int, float))
            assert kpis[k] >= 0.0

    @pytest.mark.database
    def test_latest_inventory_health_structure(self):
        """Validates that inventory health query returns enriched columns."""
        df = get_latest_inventory_health()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        required_cols = [
            "store_id", "product_id", "closing_stock_on_hand", "days_of_supply",
            "inventory_status", "safety_stock", "reorder_point"
        ]
        for col in required_cols:
            assert col in df.columns

        # Verify status domain
        allowed_statuses = {"STOCKOUT_RISK", "REORDER_NOW", "HEALTHY", "EXCESS_STOCK"}
        unique_statuses = set(df["inventory_status"].unique())
        assert unique_statuses.issubset(allowed_statuses)

    @pytest.mark.database
    def test_sku_demand_history_and_uncensoring(self):
        """Validates historical time-series extraction and latent demand overlay."""
        df = get_sku_demand_history(store_id="STR01", product_id="PRD01", days=60)
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "raw_sales" in df.columns
        assert "uncensored_demand" in df.columns
        assert "is_stockout" in df.columns

        # Uncensored demand must always be >= observed raw sales
        assert (df["uncensored_demand"] >= df["raw_sales"]).all()

    def test_forecast_fan_monotonicity(self):
        """Asserts that generated quantile forecasts maintain P10 <= P50 <= P90."""
        # Create mock history
        dates = pd.date_range("2025-01-01", periods=30, freq="D")
        mock_history = pd.DataFrame({
            "full_date": dates,
            "raw_sales": np.random.randint(5, 20, size=30),
            "uncensored_demand": np.random.uniform(8.0, 22.0, size=30),
            "stock_on_hand": np.random.randint(0, 50, size=30),
            "is_stockout": np.zeros(30, dtype=int),
        })

        df_fan = generate_forecast_fan(mock_history, lead_time_days=10)
        assert len(df_fan) == 10
        assert (df_fan["p10_conservative"] <= df_fan["p50_median"]).all()
        assert (df_fan["p50_median"] <= df_fan["p90_risk_mitigating"]).all()

    @pytest.mark.database
    def test_quarantine_feed_and_stats(self):
        """Validates that quarantine telemetry and dead-letter feed return valid records."""
        stats = get_quarantine_stats()
        assert stats["total_processed"] > 0
        assert stats["clean_loaded"] > 0
        assert stats["quarantined_records"] >= 0
        assert 0.0 <= stats["quarantine_rate_pct"] <= 100.0

        df_q = get_quarantine_feed(limit=10)
        assert isinstance(df_q, pd.DataFrame)
        if not df_q.empty:
            assert "violation_category" in df_q.columns
            assert "violation_details" in df_q.columns


# ==============================================================================
# Streamlit AppTest Smoke Suite
# ==============================================================================

class TestStreamlitAppSmoke:
    """Verifies that Streamlit pages compile and render without runtime exceptions."""

    @pytest.mark.database
    def test_app_main_navigation_smoke(self):
        """Smoke test for main navigation entrypoint app.py."""
        at = AppTest.from_file(str(ROOT_DIR / "app.py"))
        at.run(timeout=20)
        assert len(at.exception) == 0, f"app.py raised unhandled exceptions: {at.exception}"

    @pytest.mark.database
    def test_page1_executive_cockpit_smoke(self):
        """Smoke test for Page 1: Executive Cockpit."""
        at = AppTest.from_file(str(ROOT_DIR / "src/ui/pages/1_executive_cockpit.py"))
        at.run(timeout=20)
        assert len(at.exception) == 0, f"Page 1 raised unhandled exceptions: {at.exception}"

    @pytest.mark.database
    def test_page2_forecast_uncertainty_smoke(self):
        """Smoke test for Page 2: Demand Forecast & Uncertainty Visualizer."""
        at = AppTest.from_file(str(ROOT_DIR / "src/ui/pages/2_forecast_uncertainty.py"))
        at.run(timeout=20)
        assert len(at.exception) == 0, f"Page 2 raised unhandled exceptions: {at.exception}"

    @pytest.mark.database
    def test_page3_replenishment_portal_smoke(self):
        """Smoke test for Page 3: Constrained Replenishment Portal."""
        at = AppTest.from_file(str(ROOT_DIR / "src/ui/pages/3_replenishment_portal.py"))
        at.run(timeout=20)
        assert len(at.exception) == 0, f"Page 3 raised unhandled exceptions: {at.exception}"

    @pytest.mark.database
    def test_page4_data_observability_smoke(self):
        """Smoke test for Page 4: Data Observability & Audit."""
        at = AppTest.from_file(str(ROOT_DIR / "src/ui/pages/4_data_observability.py"))
        at.run(timeout=20)
        assert len(at.exception) == 0, f"Page 4 raised unhandled exceptions: {at.exception}"

    @pytest.mark.database
    def test_page_data_hub_smoke(self):
        """Smoke test for Master Data Hub (CRUD & File Operations)."""
        at = AppTest.from_file(str(ROOT_DIR / "src/ui/pages/3_data_hub.py"))
        at.run(timeout=20)
        assert len(at.exception) == 0, f"Data Hub raised unhandled exceptions: {at.exception}"

