"""Automated Test Suite for RetailPulse DI Phase 6: Constrained Replenishment Engine.

Tests:
1. Stochastic Safety Stock & ROP Calculator:
   - Analytical accuracy of Var(LTD), sigma_LTD, Safety Stock, ROP.
   - Non-negativity across service level spectrum (50% to 99.9%).
   - Monotonic volatility response (increasing sigma_D / sigma_L strictly raises SS).
   - Status classifications (STOCKOUT_RISK, REORDER_NOW, HEALTHY, EXCESS_STOCK).
2. Constrained Replenishment Optimizer (MILP):
   - Strict budget adherence across budget tiers ($5,000, $20,000, $50,000).
   - Semi-continuous Minimum Order Quantity (MOQ) adherence (Q == 0 or Q >= MOQ).
   - Pack size modularity (Q % pack_size == 0, Q == packs * pack_size).
   - Maximum storage capacity constraint.
   - Boundary condition handling (zero budget, zero candidates).
   - Urgency priority ranking order.
3. Database Persistence & Approval Workflow Engine:
   - Idempotent storage in dbo.fact_replenishment_recommendation.
   - Human-in-the-loop state transitions (PROPOSED -> APPROVED / MODIFIED / REJECTED).
   - Modularity and unit recomputation on MODIFIED status.
   - Query filtering across date, store, and status.
"""
import pytest
import numpy as np
import pandas as pd
from typing import List

from src.decision.safety_stock import StochasticInventoryController, InventoryStatusResult
from src.decision.optimizer import ConstrainedReplenishmentOptimizer, ReplenishmentOrderRecommendation
from src.decision.persistence import ReplenishmentPersistenceEngine


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def inventory_controller() -> StochasticInventoryController:
    return StochasticInventoryController(default_service_level=0.95)


@pytest.fixture
def replenishment_optimizer() -> ConstrainedReplenishmentOptimizer:
    return ConstrainedReplenishmentOptimizer(holding_cost_penalty_rate=0.001)


@pytest.fixture
def persistence_engine() -> ReplenishmentPersistenceEngine:
    return ReplenishmentPersistenceEngine()


@pytest.fixture
def sample_candidates(inventory_controller: StochasticInventoryController) -> List[InventoryStatusResult]:
    """Generates a synthetic portfolio of 6 diverse retail SKUs for deterministic testing."""
    skus_config = [
        # (store_id, product_id, name, cat, sup, pack, moq, cost, retail, on_hand, on_order, mu_d, sig_d, mu_l, sig_l, sl)
        ("STR01", "PRD01", "Whole Milk 1L", "Dairy", "SUP01", 12, 48, 1.20, 2.49, 10, 0, 15.0, 3.0, 2.0, 0.5, 0.95),
        ("STR01", "PRD02", "Greek Yogurt 500g", "Dairy", "SUP01", 6, 24, 2.50, 4.99, 5, 0, 8.0, 2.0, 2.0, 0.5, 0.95),
        ("STR01", "PRD03", "Artisan Sourdough", "Bakery", "SUP02", 10, 20, 1.80, 4.29, 2, 0, 12.0, 4.0, 1.0, 0.2, 0.95),
        ("STR01", "PRD04", "Organic Eggs 12pk", "Dairy", "SUP01", 15, 60, 2.20, 4.59, 100, 0, 10.0, 2.5, 3.0, 0.8, 0.95),
        ("STR01", "PRD05", "Fresh Bananas 1kg", "Produce", "SUP03", 20, 100, 0.80, 1.99, 15, 0, 25.0, 6.0, 2.0, 0.4, 0.95),
        ("STR01", "PRD06", "Ground Coffee 250g", "Pantry", "SUP04", 8, 32, 4.50, 8.99, 0, 0, 6.0, 1.5, 5.0, 1.0, 0.98),
    ]

    candidates = []
    for (st, pid, name, cat, sup, pack, moq, cost, ret, oh, oo, mu_d, sig_d, mu_l, sig_l, sl) in skus_config:
        res = inventory_controller.calculate_sku_inventory_status(
            store_id=st,
            product_id=pid,
            product_name=name,
            category=cat,
            supplier_id=sup,
            pack_size=pack,
            min_order_qty=moq,
            unit_cost_price=cost,
            unit_retail_price=ret,
            on_hand=oh,
            on_order=oo,
            mean_demand=mu_d,
            std_demand=sig_d,
            mean_lead_time=mu_l,
            std_lead_time=sig_l,
            service_level=sl,
        )
        candidates.append(res)
    return candidates


# ==============================================================================
# Unit Tests: Stochastic Safety Stock & ROP Calculator
# ==============================================================================

class TestStochasticSafetyStock:
    """Verifies inventory theory formulas, non-negativity, and classification states."""

    def test_safety_stock_analytical_correctness(self, inventory_controller: StochasticInventoryController):
        """Validates Var(LTD) = mu_L * sigma_D^2 + mu_D^2 * sigma_L^2 and SS = Z * sigma_LTD."""
        res = inventory_controller.calculate_sku_inventory_status(
            store_id="STR01",
            product_id="PRD_TEST",
            product_name="Test Product",
            category="Test",
            supplier_id="SUP01",
            pack_size=10,
            min_order_qty=20,
            unit_cost_price=5.00,
            unit_retail_price=10.00,
            on_hand=15,
            on_order=0,
            mean_demand=10.0,
            std_demand=2.0,
            mean_lead_time=4.0,
            std_lead_time=1.0,
            service_level=0.95,
        )

        # Expected calculations:
        # Var(LTD) = (4.0 * 2.0^2) + (10.0^2 * 1.0^2) = (4.0 * 4.0) + (100.0 * 1.0) = 16.0 + 100.0 = 116.0
        # sigma_LTD = sqrt(116.0) ~= 10.7703
        # Z for 0.95 ~= 1.64485
        # SS = 1.64485 * 10.7703 ~= 17.715
        # LTD = 10.0 * 4.0 = 40.0
        # ROP = 40.0 + 17.715 = 57.715
        expected_sigma_ltd = np.sqrt(4.0 * 4.0 + 100.0 * 1.0)
        assert abs(res.sigma_ltd - round(expected_sigma_ltd, 2)) <= 0.05
        assert res.lead_time_demand == 40.0
        assert res.safety_stock > 17.0 and res.safety_stock < 18.0
        assert res.reorder_point > 57.0 and res.reorder_point < 58.0
        assert res.inventory_status == "STOCKOUT_RISK"  # on_hand=15 <= SS (17.7)

    def test_safety_stock_non_negativity_across_service_levels(self, inventory_controller: StochasticInventoryController):
        """Verifies SS >= 0 across service levels from 50% to 99.9%."""
        levels = [0.50, 0.70, 0.85, 0.90, 0.95, 0.975, 0.99, 0.999]
        for sl in levels:
            res = inventory_controller.calculate_sku_inventory_status(
                store_id="STR01",
                product_id="PRD_SL",
                product_name="Service Level Test",
                category="General",
                supplier_id="SUP01",
                pack_size=5,
                min_order_qty=10,
                unit_cost_price=2.00,
                unit_retail_price=4.00,
                on_hand=20,
                on_order=0,
                mean_demand=5.0,
                std_demand=1.5,
                mean_lead_time=3.0,
                std_lead_time=0.5,
                service_level=sl,
            )
            assert res.safety_stock >= 0.0, f"Safety stock must be non-negative for SL {sl}"
            assert res.reorder_point >= res.lead_time_demand

    def test_monotonic_volatility_response(self, inventory_controller: StochasticInventoryController):
        """Ensures that higher demand variance or lead time variance strictly increases safety stock."""
        base = inventory_controller.calculate_sku_inventory_status(
            store_id="STR01", product_id="P1", product_name="Base", category="Test", supplier_id="S1",
            pack_size=1, min_order_qty=1, unit_cost_price=1.0, unit_retail_price=2.0,
            on_hand=50, on_order=0, mean_demand=10.0, std_demand=2.0, mean_lead_time=3.0, std_lead_time=0.5,
        )
        high_demand_var = inventory_controller.calculate_sku_inventory_status(
            store_id="STR01", product_id="P1", product_name="Base", category="Test", supplier_id="S1",
            pack_size=1, min_order_qty=1, unit_cost_price=1.0, unit_retail_price=2.0,
            on_hand=50, on_order=0, mean_demand=10.0, std_demand=5.0, mean_lead_time=3.0, std_lead_time=0.5,
        )
        high_lt_var = inventory_controller.calculate_sku_inventory_status(
            store_id="STR01", product_id="P1", product_name="Base", category="Test", supplier_id="S1",
            pack_size=1, min_order_qty=1, unit_cost_price=1.0, unit_retail_price=2.0,
            on_hand=50, on_order=0, mean_demand=10.0, std_demand=2.0, mean_lead_time=3.0, std_lead_time=2.0,
        )

        assert high_demand_var.safety_stock > base.safety_stock
        assert high_lt_var.safety_stock > base.safety_stock

    def test_inventory_status_categorization(self, inventory_controller: StochasticInventoryController):
        """Verifies deterministic mapping to STOCKOUT_RISK, REORDER_NOW, HEALTHY, and EXCESS_STOCK."""
        # Baseline: mean_demand=10, mean_lead=3 -> LTD = 30. sigma_D=2, sigma_L=0.5 -> Var(LTD)=3*4+100*0.25=37. sigma=6.08.
        # SS = 1.645 * 6.08 ~= 10.0. ROP ~= 40.0.
        calc = lambda oh: inventory_controller.calculate_sku_inventory_status(
            store_id="STR01", product_id="P", product_name="N", category="C", supplier_id="S",
            pack_size=1, min_order_qty=1, unit_cost_price=1.0, unit_retail_price=2.0,
            on_hand=oh, on_order=0, mean_demand=10.0, std_demand=2.0, mean_lead_time=3.0, std_lead_time=0.5,
        )

        risk_res = calc(8)     # on_hand <= SS (~10)
        assert risk_res.inventory_status == "STOCKOUT_RISK"
        assert risk_res.replenishment_deficit > 0

        reorder_res = calc(25) # SS < on_hand <= ROP (~40)
        assert reorder_res.inventory_status == "REORDER_NOW"
        assert reorder_res.replenishment_deficit > 0

        healthy_res = calc(45) # ROP < on_hand < ROP + 2*SS (~60)
        assert healthy_res.inventory_status == "HEALTHY"
        assert healthy_res.replenishment_deficit == 0.0

        excess_res = calc(80)  # on_hand >= ROP + 2*SS (~60)
        assert excess_res.inventory_status == "EXCESS_STOCK"
        assert excess_res.replenishment_deficit == 0.0


# ==============================================================================
# Unit Tests: Constrained Replenishment Optimizer (MILP)
# ==============================================================================

class TestConstrainedReplenishmentOptimizer:
    """Verifies MILP formulation, budget constraints, MOQ, and pack size modularity."""

    @pytest.mark.parametrize("budget", [500.0, 2000.0, 10000.0])
    def test_budget_constraint_adherence(
        self,
        replenishment_optimizer: ConstrainedReplenishmentOptimizer,
        sample_candidates: List[InventoryStatusResult],
        budget: float,
    ):
        """Asserts that total allocated spend sum(Q_i * cost_i) <= available_budget under various tiers."""
        recs, summary = replenishment_optimizer.optimize_orders(sample_candidates, available_budget=budget)

        assert summary["solver_status"] == "OPTIMAL"
        assert summary["budget_allocated"] <= budget + 1e-4
        assert summary["budget_remaining"] >= -1e-4

        calculated_cost = sum(r.recommended_units * r.unit_cost_price for r in recs)
        assert abs(calculated_cost - summary["budget_allocated"]) <= 0.05

    def test_supplier_moq_semi_continuous_compliance(
        self,
        replenishment_optimizer: ConstrainedReplenishmentOptimizer,
        sample_candidates: List[InventoryStatusResult],
    ):
        """Asserts that for every SKU, either order quantity is 0 OR quantity >= supplier min_order_qty."""
        recs, _ = replenishment_optimizer.optimize_orders(sample_candidates, available_budget=5000.0)

        for r in recs:
            if r.recommended_units > 0:
                assert r.recommended_units >= r.min_order_qty, (
                    f"SKU {r.product_id} ordered {r.recommended_units} units, violating MOQ {r.min_order_qty}"
                )

    def test_pack_size_modularity_constraint(
        self,
        replenishment_optimizer: ConstrainedReplenishmentOptimizer,
        sample_candidates: List[InventoryStatusResult],
    ):
        """Asserts that ordered units are exact integer multiples of supplier pack_size: Q_i = k_i * pack_i."""
        recs, _ = replenishment_optimizer.optimize_orders(sample_candidates, available_budget=5000.0)

        for r in recs:
            if r.recommended_units > 0:
                assert r.recommended_units % r.pack_size == 0, (
                    f"SKU {r.product_id} units {r.recommended_units} is not a multiple of pack size {r.pack_size}"
                )
                assert r.recommended_units == r.recommended_packs * r.pack_size

    def test_storage_capacity_constraint(
        self,
        replenishment_optimizer: ConstrainedReplenishmentOptimizer,
        sample_candidates: List[InventoryStatusResult],
    ):
        """Asserts that total ordered units sum(Q_i) <= max_storage_units when physical capacity is bounded."""
        max_storage = 150
        recs, summary = replenishment_optimizer.optimize_orders(
            sample_candidates, available_budget=20000.0, max_storage_units=max_storage
        )

        assert summary["solver_status"] == "OPTIMAL"
        assert summary["total_units_ordered"] <= max_storage

    def test_zero_budget_and_empty_candidates_handling(
        self,
        replenishment_optimizer: ConstrainedReplenishmentOptimizer,
        sample_candidates: List[InventoryStatusResult],
    ):
        """Verifies clean handling of edge cases without throwing unhandled exceptions."""
        recs_zero, summary_zero = replenishment_optimizer.optimize_orders(sample_candidates, available_budget=0.0)
        assert len(recs_zero) == 0
        assert summary_zero["budget_allocated"] == 0.0

        recs_empty, summary_empty = replenishment_optimizer.optimize_orders([], available_budget=5000.0)
        assert len(recs_empty) == 0
        assert summary_empty["total_units_ordered"] == 0

    def test_priority_ranking_urgency_ordering(
        self,
        replenishment_optimizer: ConstrainedReplenishmentOptimizer,
        sample_candidates: List[InventoryStatusResult],
    ):
        """Asserts that items with STOCKOUT_RISK are ranked with higher priority than REORDER_NOW and HEALTHY."""
        recs, _ = replenishment_optimizer.optimize_orders(sample_candidates, available_budget=5000.0)

        # Check ranking monotonicity
        ranks = [r.priority_rank for r in recs]
        assert ranks == list(range(1, len(recs) + 1))

        # First item must have critical stockout risk
        first_item = recs[0]
        assert first_item.inventory_status == "STOCKOUT_RISK"


# ==============================================================================
# Integration Tests: Database Persistence & Approval Workflow
# ==============================================================================

class TestReplenishmentPersistence:
    """Verifies roundtrip SQL Server persistence and workflow state transitions."""

    @pytest.mark.database
    def test_idempotent_persistence_and_query(
        self,
        persistence_engine: ReplenishmentPersistenceEngine,
        replenishment_optimizer: ConstrainedReplenishmentOptimizer,
        sample_candidates: List[InventoryStatusResult],
    ):
        """Asserts that order recommendations can be persisted, re-run idempotently, and queried."""
        recs, _ = replenishment_optimizer.optimize_orders(sample_candidates, available_budget=5000.0)
        test_date_key = 20251231

        # First persistence run
        inserted_1 = persistence_engine.persist_recommendations(recs, run_date_key=test_date_key)
        assert inserted_1 == len(recs)

        # Query back
        df_saved = persistence_engine.query_recommendations(run_date_key=test_date_key)
        assert len(df_saved) == len(recs)
        assert all(df_saved["approval_status"] == "PROPOSED")

        # Second persistence run (idempotent overwrite)
        inserted_2 = persistence_engine.persist_recommendations(recs, run_date_key=test_date_key)
        assert inserted_2 == len(recs)

        df_saved_2 = persistence_engine.query_recommendations(run_date_key=test_date_key)
        assert len(df_saved_2) == len(recs), "Idempotent run must not duplicate records"

    @pytest.mark.database
    def test_approval_state_transitions(
        self,
        persistence_engine: ReplenishmentPersistenceEngine,
        replenishment_optimizer: ConstrainedReplenishmentOptimizer,
        sample_candidates: List[InventoryStatusResult],
    ):
        """Tests transitions: PROPOSED -> APPROVED, PROPOSED -> MODIFIED, and PROPOSED -> REJECTED."""
        recs, _ = replenishment_optimizer.optimize_orders(sample_candidates, available_budget=5000.0)
        test_date_key = 20251230

        persistence_engine.persist_recommendations(recs, run_date_key=test_date_key)

        rec_to_approve = f"REC-{test_date_key}-{recs[0].store_id}-{recs[0].product_id}"
        rec_to_modify = f"REC-{test_date_key}-{recs[1].store_id}-{recs[1].product_id}"
        rec_to_reject = f"REC-{test_date_key}-{recs[2].store_id}-{recs[2].product_id}"

        # 1. Approve
        ok_app = persistence_engine.update_recommendation_status(rec_to_approve, "APPROVED")
        assert ok_app is True

        # 2. Modify order units
        new_units = recs[1].recommended_units + recs[1].pack_size
        ok_mod = persistence_engine.update_recommendation_status(
            rec_to_modify, "MODIFIED", modified_units=new_units
        )
        assert ok_mod is True

        # 3. Reject
        ok_rej = persistence_engine.update_recommendation_status(rec_to_reject, "REJECTED")
        assert ok_rej is True

        # Verify in database
        df_updated = persistence_engine.query_recommendations(run_date_key=test_date_key)
        row_app = df_updated[df_updated["recommendation_id"] == rec_to_approve].iloc[0]
        row_mod = df_updated[df_updated["recommendation_id"] == rec_to_modify].iloc[0]
        row_rej = df_updated[df_updated["recommendation_id"] == rec_to_reject].iloc[0]

        assert row_app["approval_status"] == "APPROVED"
        assert row_mod["approval_status"] == "MODIFIED"
        assert row_mod["recommended_units"] == new_units
        assert row_mod["estimated_cost"] == round(new_units * row_mod["unit_cost_price"], 2)
        assert row_rej["approval_status"] == "REJECTED"

        # Invalid status check
        with pytest.raises(ValueError):
            persistence_engine.update_recommendation_status(rec_to_approve, "INVALID_STATUS")
