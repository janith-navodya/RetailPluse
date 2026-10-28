"""Multi-Item Mixed-Integer Linear Programming (MILP) Replenishment Optimizer.

Formulates and solves the inventory replenishment optimization under:
1. Working Capital Purchase Budget constraint (sum(c_i * Q_i) <= Budget)
2. Supplier Minimum Order Quantity (MOQ) semi-continuous constraint (Q_i == 0 or Q_i >= MOQ_i)
3. Pack Size Modularity integer constraint (Q_i == k_i * pack_size_i, k_i in Z_>=0)
4. Optional warehouse storage capacity constraint
Solves using HiGHS via scipy.optimize.milp with millisecond convergence.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds
from config.logging_config import logger
from src.decision.safety_stock import InventoryStatusResult


@dataclass
class ReplenishmentOrderRecommendation:
    store_id: str
    product_id: str
    product_name: str
    category: str
    supplier_id: str
    pack_size: int
    min_order_qty: int
    unit_cost_price: float
    unit_retail_price: float
    current_on_hand_qty: int
    current_on_order_qty: int
    inventory_position: int
    lead_time_demand_qty: float
    safety_stock_qty: float
    reorder_point_qty: float
    inventory_status: str
    replenishment_deficit: float
    recommended_packs: int
    recommended_units: int
    estimated_cost: float
    stockout_risk_reduction_pct: float
    priority_rank: int


class ConstrainedReplenishmentOptimizer:
    """Solves multi-item replenishment allocations subject to capital, MOQ, and pack size constraints."""

    def __init__(self, holding_cost_penalty_rate: float = 0.001):
        self.holding_cost_penalty_rate = holding_cost_penalty_rate

    def optimize_orders(
        self,
        candidate_items: List[InventoryStatusResult],
        available_budget: float,
        max_storage_units: Optional[float] = None,
    ) -> Tuple[List[ReplenishmentOrderRecommendation], Dict[str, Any]]:
        """
        Solves the MILP allocation.

        Returns:
        - List of ReplenishmentOrderRecommendation for all candidate items.
        - Summary metrics dictionary (budget_allocated, budget_remaining, total_units, solver_status).
        """
        logger.info(
            "Starting replenishment optimization for %d items under budget $%.2f...",
            len(candidate_items),
            available_budget,
        )

        if not candidate_items or available_budget <= 0:
            return [], {
                "budget_allocated": 0.0,
                "budget_remaining": available_budget,
                "total_units_ordered": 0,
                "solver_status": "NO_CANDIDATES",
            }

        N = len(candidate_items)
        # Variable layout:
        # x[0 : N]     = k_i (integer number of packs)
        # x[N : 2*N]   = b_i (binary: 1 if item i is ordered, 0 otherwise)
        # x[2*N : 3*N] = u_i (continuous: fulfilled deficit units)
        num_vars = 3 * N

        c_obj = np.zeros(num_vars)
        integrality = np.zeros(num_vars, dtype=int)
        lb = np.zeros(num_vars)
        ub = np.full(num_vars, np.inf)

        for i, item in enumerate(candidate_items):
            pack = item.pack_size
            cost = item.unit_cost_price
            margin = max(0.50, item.unit_retail_price - cost)
            deficit = max(0.0, item.replenishment_deficit)

            # Objective: Maximize fulfilled margin - small holding cost penalty
            # Minimize: -margin * u_i + (penalty * cost * pack) * k_i
            c_obj[i] = self.holding_cost_penalty_rate * cost * pack
            c_obj[N + i] = 0.0
            c_obj[2 * N + i] = -margin

            # Integrality
            integrality[i] = 1       # k_i is integer
            integrality[N + i] = 1   # b_i is integer (binary)
            integrality[2 * N + i] = 0  # u_i is continuous

            # Bounds
            lb[i] = 0
            lb[N + i] = 0
            ub[N + i] = 1  # Binary 0 or 1
            lb[2 * N + i] = 0
            ub[2 * N + i] = deficit if deficit > 0 else 0.0

        # Construct Linear Constraints
        A_rows = []
        b_l = []
        b_u = []

        # Constraint 1: Working Capital Budget
        # sum_i (cost_i * pack_i * k_i) <= Budget
        budget_row = np.zeros(num_vars)
        for i, item in enumerate(candidate_items):
            budget_row[i] = item.unit_cost_price * item.pack_size
        A_rows.append(budget_row)
        b_l.append(0.0)
        b_u.append(float(available_budget))

        # Constraint 2 & 3: MOQ Semi-Continuous Logic via Big-M
        # (a) pack_i * k_i - MOQ_i * b_i >= 0
        # (b) pack_i * k_i - M_i * b_i <= 0
        for i, item in enumerate(candidate_items):
            pack = item.pack_size
            moq = item.min_order_qty
            cost = item.unit_cost_price
            # Safe Big-M bound
            max_packs_budget = int(available_budget / max(1.0, cost * pack)) + 5
            M = max(moq * 2, max_packs_budget * pack)

            # (a) Lower bound: pack * k_i - MOQ * b_i >= 0
            row_moq = np.zeros(num_vars)
            row_moq[i] = pack
            row_moq[N + i] = -moq
            A_rows.append(row_moq)
            b_l.append(0.0)
            b_u.append(np.inf)

            # (b) Upper bound: pack * k_i - M * b_i <= 0
            row_bigm = np.zeros(num_vars)
            row_bigm[i] = pack
            row_bigm[N + i] = -M
            A_rows.append(row_bigm)
            b_l.append(-np.inf)
            b_u.append(0.0)

            # Constraint 4: Fulfilled Deficit Linking
            # u_i - pack_i * k_i <= 0  ==> u_i <= Q_i
            row_u = np.zeros(num_vars)
            row_u[2 * N + i] = 1.0
            row_u[i] = -pack
            A_rows.append(row_u)
            b_l.append(-np.inf)
            b_u.append(0.0)

        # Optional Constraint 5: Storage Unit Capacity
        if max_storage_units is not None and max_storage_units > 0:
            storage_row = np.zeros(num_vars)
            for i, item in enumerate(candidate_items):
                storage_row[i] = item.pack_size
            A_rows.append(storage_row)
            b_l.append(0.0)
            b_u.append(float(max_storage_units))

        # Solve MILP via HiGHS
        A_mat = np.array(A_rows)
        constraints = LinearConstraint(A_mat, b_l, b_u)
        bounds = Bounds(lb, ub)

        res = milp(c=c_obj, integrality=integrality, constraints=constraints, bounds=bounds)

        if not res.success:
            logger.warning("MILP solver did not find optimal solution: %s", res.status)
            return [], {
                "budget_allocated": 0.0,
                "budget_remaining": available_budget,
                "total_units_ordered": 0,
                "solver_status": f"FAILED_{res.status}",
            }

        k_sol = np.round(res.x[:N]).astype(int)
        u_sol = res.x[2 * N : 3 * N]

        recommendations: List[ReplenishmentOrderRecommendation] = []
        total_cost = 0.0
        total_units = 0

        for i, item in enumerate(candidate_items):
            packs = int(k_sol[i])
            units = int(packs * item.pack_size)
            cost = round(units * item.unit_cost_price, 2)
            deficit = item.replenishment_deficit
            risk_red = min(100.0, round((u_sol[i] / max(1.0, deficit)) * 100.0, 1)) if deficit > 0 else 100.0

            total_cost += cost
            total_units += units

            recommendations.append(
                ReplenishmentOrderRecommendation(
                    store_id=item.store_id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    category=item.category,
                    supplier_id=item.supplier_id,
                    pack_size=item.pack_size,
                    min_order_qty=item.min_order_qty,
                    unit_cost_price=item.unit_cost_price,
                    unit_retail_price=item.unit_retail_price,
                    current_on_hand_qty=item.current_on_hand_qty,
                    current_on_order_qty=item.current_on_order_qty,
                    inventory_position=item.inventory_position,
                    lead_time_demand_qty=item.lead_time_demand,
                    safety_stock_qty=item.safety_stock,
                    reorder_point_qty=item.reorder_point,
                    inventory_status=item.inventory_status,
                    replenishment_deficit=item.replenishment_deficit,
                    recommended_packs=packs,
                    recommended_units=units,
                    estimated_cost=cost,
                    stockout_risk_reduction_pct=risk_red,
                    priority_rank=0,  # Computed below
                )
            )

        # Sort recommendations by urgency:
        # Stockout risk first, then reorder now, ordered by estimated cost / margin
        recommendations.sort(
            key=lambda r: (
                0 if r.inventory_status == "STOCKOUT_RISK" else (1 if r.inventory_status == "REORDER_NOW" else 2),
                -r.stockout_risk_reduction_pct,
                -r.estimated_cost,
            )
        )

        for rank, r in enumerate(recommendations, start=1):
            r.priority_rank = rank

        summary = {
            "budget_allocated": round(total_cost, 2),
            "budget_remaining": round(available_budget - total_cost, 2),
            "total_units_ordered": total_units,
            "total_skus_replenished": sum(1 for r in recommendations if r.recommended_units > 0),
            "solver_status": "OPTIMAL",
        }

        logger.info(
            "Replenishment MILP solved: Allocated $%.2f / $%.2f (%.1f%%) across %d SKUs (%d units).",
            summary["budget_allocated"],
            available_budget,
            (summary["budget_allocated"] / available_budget) * 100.0,
            summary["total_skus_replenished"],
            summary["total_units_ordered"],
        )

        return recommendations, summary
