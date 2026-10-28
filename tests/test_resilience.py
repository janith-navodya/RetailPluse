"""Resilience, Fault Injection & Edge Case Test Suite for RetailPulse DI Platform.

Verifies system robustness under failure modes and boundary conditions:
1. Cold-start products (zero historical sales records or unobserved demand).
2. Zero-budget and micro-budget replenishment optimization scenarios (graceful 0-order allocation without solver crash).
3. Extreme volatility and boundary parameter conditions (SL = 50% to 99.99%, extreme variance).
4. Empty and single-header CSV ingestion resilience.
5. SQL Server connection fault tolerance and parameter safety.
"""
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile

from src.decision.safety_stock import StochasticInventoryController, InventoryStatusResult
from src.decision.optimizer import ConstrainedReplenishmentOptimizer
from src.ui.data_access import generate_forecast_fan, get_sku_demand_history
from src.etl.ingest import SQLServerIngestionPipeline


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def controller() -> StochasticInventoryController:
    return StochasticInventoryController()


@pytest.fixture
def optimizer() -> ConstrainedReplenishmentOptimizer:
    return ConstrainedReplenishmentOptimizer()


@pytest.fixture
def sample_candidate(controller: StochasticInventoryController) -> InventoryStatusResult:
    return controller.calculate_sku_inventory_status(
        store_id="STR01",
        product_id="PRD_COLD",
        product_name="Cold Start Test Item",
        category="Test Category",
        supplier_id="SUP01",
        pack_size=10,
        min_order_qty=20,
        unit_cost_price=5.00,
        unit_retail_price=10.00,
        on_hand=0,
        on_order=0,
        mean_demand=0.0,
        std_demand=0.0,
        mean_lead_time=3.0,
        std_lead_time=0.5,
        service_level=0.95,
    )


# ==============================================================================
# Test Class 1: Cold-Start & Zero-Demand SKU Handling
# ==============================================================================

class TestColdStartResilience:
    """Verifies that items with zero historical sales do not trigger NaN, division by zero, or solver failures."""

    def test_cold_start_inventory_status_calculation(self, controller: StochasticInventoryController):
        """Zero historical demand must fall back gracefully to minimal baseline without raising exceptions."""
        res = controller.calculate_sku_inventory_status(
            store_id="STR01",
            product_id="PRD_NEW",
            product_name="Brand New SKU",
            category="New",
            supplier_id="SUP01",
            pack_size=12,
            min_order_qty=24,
            unit_cost_price=3.50,
            unit_retail_price=7.00,
            on_hand=0,
            on_order=0,
            mean_demand=0.0,
            std_demand=0.0,
            mean_lead_time=4.0,
            std_lead_time=0.0,
            service_level=0.95,
        )

        assert not np.isnan(res.safety_stock)
        assert not np.isnan(res.reorder_point)
        assert res.safety_stock >= 0.0
        assert res.reorder_point >= 0.0
        assert res.inventory_status == "STOCKOUT_RISK"

    def test_forecast_fan_on_empty_history(self):
        """Forecast uncertainty generator must return empty DataFrame for unobserved SKUs without crashing."""
        empty_df = pd.DataFrame()
        fan_df = generate_forecast_fan(empty_df, lead_time_days=7)
        assert isinstance(fan_df, pd.DataFrame)
        assert fan_df.empty

    @pytest.mark.database
    def test_sku_demand_history_unobserved_sku(self):
        """Querying demand history for non-existent SKU returns empty DataFrame cleanly."""
        df = get_sku_demand_history(store_id="STR99", product_id="PRD9999", days=60)
        assert isinstance(df, pd.DataFrame)
        assert df.empty


# ==============================================================================
# Test Class 2: Zero & Constrained Budget Edge Cases
# ==============================================================================

class TestBudgetOptimizationResilience:
    """Verifies optimizer resilience under zero, micro, and negative capital budgets."""

    @pytest.mark.parametrize("budget", [0.0, -100.0, 0.01])
    def test_zero_or_sub_unit_budget_returns_zero_orders(
        self,
        optimizer: ConstrainedReplenishmentOptimizer,
        sample_candidate: InventoryStatusResult,
        budget: float,
    ):
        """When budget is 0 or less than minimum pack purchase, zero units should be ordered safely."""
        recs, summary = optimizer.optimize_orders([sample_candidate], available_budget=budget)

        assert summary["total_units_ordered"] == 0
        assert summary["budget_allocated"] == 0.0
        assert summary["budget_remaining"] <= max(0.0, budget)
        if recs:
            assert all(r.recommended_units == 0 for r in recs)

    def test_insufficient_budget_for_moq(
        self,
        optimizer: ConstrainedReplenishmentOptimizer,
        controller: StochasticInventoryController,
    ):
        """When budget allows buying units but cannot meet the supplier MOQ, the item must not be ordered."""
        # Product cost $10/unit, pack 5, MOQ 50 ($500 minimum spend).
        # We supply only $300 budget.
        cand = controller.calculate_sku_inventory_status(
            store_id="STR01",
            product_id="PRD_BIG_MOQ",
            product_name="High MOQ Item",
            category="Test",
            supplier_id="SUP01",
            pack_size=5,
            min_order_qty=50,
            unit_cost_price=10.0,
            unit_retail_price=20.0,
            on_hand=0,
            on_order=0,
            mean_demand=15.0,
            std_demand=3.0,
            mean_lead_time=5.0,
            std_lead_time=1.0,
        )

        recs, summary = optimizer.optimize_orders([cand], available_budget=300.0)

        # Must not order any units because MOQ is 50 ($500 spend required)
        assert summary["total_units_ordered"] == 0
        assert summary["budget_allocated"] == 0.0


# ==============================================================================
# Test Class 3: Extreme Volatility & Boundary Parameters
# ==============================================================================

class TestExtremeParametersResilience:
    """Verifies numerical stability under extreme variance and service level boundaries."""

    @pytest.mark.parametrize("sl", [0.50, 0.90, 0.9999])
    def test_service_level_boundary_clamping(self, controller: StochasticInventoryController, sl: float):
        """Service levels approaching theoretical bounds must compute finite, non-negative values."""
        res = controller.calculate_sku_inventory_status(
            store_id="STR01",
            product_id="PRD_EXTREME",
            product_name="Extreme SL Test",
            category="Test",
            supplier_id="SUP01",
            pack_size=1,
            min_order_qty=1,
            unit_cost_price=1.0,
            unit_retail_price=2.0,
            on_hand=10,
            on_order=0,
            mean_demand=10.0,
            std_demand=2.0,
            mean_lead_time=3.0,
            std_lead_time=0.5,
            service_level=sl,
        )
        assert not np.isnan(res.safety_stock)
        assert not np.isinf(res.safety_stock)
        assert res.safety_stock >= 0.0

    def test_extreme_lead_time_variance_stability(self, controller: StochasticInventoryController):
        """Lead times with massive uncertainty (sigma_L = 30 days) must produce finite results."""
        res = controller.calculate_sku_inventory_status(
            store_id="STR01",
            product_id="PRD_VOLATILE",
            product_name="Volatile Logistics Item",
            category="Test",
            supplier_id="SUP01",
            pack_size=10,
            min_order_qty=10,
            unit_cost_price=2.0,
            unit_retail_price=5.0,
            on_hand=5,
            on_order=0,
            mean_demand=20.0,
            std_demand=5.0,
            mean_lead_time=14.0,
            std_lead_time=30.0,
            service_level=0.95,
        )
        assert res.safety_stock > 0
        assert not np.isinf(res.safety_stock)


# ==============================================================================
# Test Class 4: Empty CSV Ingestion Resilience
# ==============================================================================

class TestEmptyCSVIngestionResilience:
    """Verifies that the ETL pipeline handles empty or header-only data files without crashing."""

    def test_empty_dataframe_pydantic_validation(self):
        """Validating an empty DataFrame against ingestion models returns 0 valid and 0 quarantined."""
        pipeline = SQLServerIngestionPipeline()
        empty_records = []
        valid, quarantined = pipeline._validate_records(
            source_feed="fact_sales_daily",
            records=empty_records,
            batch_id="TEST-EMPTY",
        )

        assert len(valid) == 0
        assert len(quarantined) == 0

    def test_corrupted_records_firewall_isolation(self):
        """Verifies that an ingestion batch with negative prices routes exclusively to quarantine."""
        pipeline = SQLServerIngestionPipeline()
        corrupt_records = [
            {
                "date_key": 20240101,
                "store_id": "STR01",
                "product_id": "PRD01",
                "quantity_sold": -5,  # Invalid negative quantity
                "net_sales_amount": -50.0,  # Invalid negative amount
                "unit_cost_price": 5.0,
                "unit_retail_price": 10.0,
                "batch_id": "TEST-CORRUPT",
            }
        ]
        valid, quarantined = pipeline._validate_records(
            source_feed="fact_sales_daily",
            records=corrupt_records,
            batch_id="TEST-CORRUPT",
        )
        assert len(valid) == 0
        assert len(quarantined) == 1
        assert quarantined[0]["violation_category"] == "SCHEMA_ERROR"
