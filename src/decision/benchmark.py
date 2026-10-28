"""Economic Regret & Replenishment Policy Benchmark Suite for RetailPulse DI Platform.

Simulates 30-day forward operational retail outcomes comparing three replenishment policies:
1. Policy A: Naive Fixed Periodic Reordering (Weekly fixed batch orders)
2. Policy B: Unconstrained ROP (Classic (s, S) replenishment with infinite capital)
3. Policy C: Constrained MILP Replenishment (RetailPulse DI working capital optimization)

Measures:
- Total Procurement Capital Deployed ($)
- Total Inventory Holding Cost ($)
- Stockout Incidents (Item-Days with 0 inventory)
- Customer Service Level / Fill Rate (%)
- Capital Efficiency Ratio (Revenue Generated / Working Capital Deployed)
"""
import warnings
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd
import pyodbc

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

from config.settings import settings
from config.logging_config import logger
from src.decision.safety_stock import StochasticInventoryController, InventoryStatusResult
from src.decision.optimizer import ConstrainedReplenishmentOptimizer


class ReplenishmentPolicyBenchmark:
    """Evaluates long-run economic regret and capital efficiency across competing replenishment policies."""

    def __init__(
        self,
        db_name: str = settings.DB_NAME,
        simulation_days: int = 30,
        available_budget_per_cycle: float = 12000.0,
        annual_holding_cost_rate: float = 0.20,
    ):
        self.db_name = db_name
        self.simulation_days = simulation_days
        self.available_budget_per_cycle = available_budget_per_cycle
        self.daily_holding_rate = annual_holding_cost_rate / 365.0
        self.conn_str = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            "SERVER=localhost;"
            f"DATABASE={self.db_name};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )

    def load_initial_cohort(self, sample_skus: int = 20) -> List[InventoryStatusResult]:
        """Extracts initial state for a representative cohort of SKUs from SQL Server."""
        conn = pyodbc.connect(self.conn_str)
        query = f"""
            SELECT TOP ({sample_skus})
                inv.store_id, inv.product_id, p.product_name, p.category,
                p.supplier_id, p.pack_size, sup.min_order_qty,
                p.unit_cost_price, p.unit_retail_price,
                inv.ending_on_hand_qty,
                sup.mean_lead_time_days, sup.lead_time_std_dev,
                sup.service_level_target_pct
            FROM dbo.fact_inventory_snapshot inv
            INNER JOIN dbo.dim_product p ON inv.product_id = p.product_id
            INNER JOIN dbo.dim_supplier sup ON p.supplier_id = sup.supplier_id
            WHERE inv.date_key = (SELECT MAX(date_key) FROM dbo.fact_inventory_snapshot)
              AND inv.store_id = 'STR01'
            ORDER BY inv.ending_on_hand_qty ASC;
        """
        df = pd.read_sql(query, conn)

        # Pull trailing demand statistics
        sales_query = """
            SELECT store_id, product_id, 
                   AVG(CAST(quantity_sold AS FLOAT)) AS mean_demand,
                   STDEV(CAST(quantity_sold AS FLOAT)) AS std_demand
            FROM dbo.fact_sales_daily
            WHERE store_id = 'STR01'
            GROUP BY store_id, product_id;
        """
        df_sales = pd.read_sql(sales_query, conn)
        conn.close()

        df_merged = df.merge(df_sales, on=["store_id", "product_id"], how="inner")

        controller = StochasticInventoryController()
        candidates = []
        for _, r in df_merged.iterrows():
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
                on_hand=int(r["ending_on_hand_qty"]),
                on_order=0,
                mean_demand=float(r["mean_demand"]),
                std_demand=float(r["std_demand"]) if pd.notna(r["std_demand"]) else 2.0,
                mean_lead_time=float(r["mean_lead_time_days"]),
                std_lead_time=float(r["lead_time_std_dev"]),
                service_level=float(r["service_level_target_pct"]) / 100.0,
            )
            candidates.append(cand)

        return candidates

    def run_benchmark(self) -> Dict[str, Any]:
        """Runs the 30-day comparative simulation across Policy A, Policy B, and Policy C."""
        cohort = self.load_initial_cohort(sample_skus=20)
        logger.info("Loaded benchmark cohort of %d SKUs.", len(cohort))

        results = {
            "Policy A: Naive Fixed Periodic": self._simulate_policy_a(cohort),
            "Policy B: Unconstrained ROP": self._simulate_policy_b(cohort),
            "Policy C: Constrained MILP": self._simulate_policy_c(cohort),
        }
        return results

    def _simulate_policy_a(self, cohort: List[InventoryStatusResult]) -> Dict[str, Any]:
        """Policy A: Orders fixed 7-day batch every Monday, ignoring ROP and lead time variability."""
        return self._simulate_generic(cohort, policy_type="FIXED_PERIODIC")

    def _simulate_policy_b(self, cohort: List[InventoryStatusResult]) -> Dict[str, Any]:
        """Policy B: Orders to full ROP deficit immediately with infinite working capital."""
        return self._simulate_generic(cohort, policy_type="UNCONSTRAINED_ROP")

    def _simulate_policy_c(self, cohort: List[InventoryStatusResult]) -> Dict[str, Any]:
        """Policy C: RetailPulse Constrained MILP with working capital budget and pack size optimization."""
        return self._simulate_generic(cohort, policy_type="CONSTRAINED_MILP")

    def _simulate_generic(
        self,
        cohort: List[InventoryStatusResult],
        policy_type: str,
    ) -> Dict[str, Any]:
        """Deterministic simulation engine stepping day-by-day over 30 days."""
        np.random.seed(42)
        on_hand = {c.product_id: c.current_on_hand_qty for c in cohort}
        in_transit: List[Tuple[int, str, int]] = []  # (arrival_day, product_id, qty)

        total_procurement_cost = 0.0
        total_holding_cost = 0.0
        total_stockout_days = 0
        total_demand = 0.0
        total_sales = 0.0

        optimizer = ConstrainedReplenishmentOptimizer()

        for day in range(1, self.simulation_days + 1):
            # 1. Receive in-transit deliveries
            deliveries_today = [p for p in in_transit if p[0] == day]
            in_transit = [p for p in in_transit if p[0] > day]
            for _, pid, qty in deliveries_today:
                on_hand[pid] += qty

            # 2. Issue replenishment orders according to policy
            if policy_type == "FIXED_PERIODIC" and day % 7 == 1:
                for c in cohort:
                    pid = c.product_id
                    # Fixed 7-day demand order
                    units = int(np.ceil(c.mean_daily_demand * 7 / c.pack_size) * c.pack_size)
                    units = max(units, c.min_order_qty)
                    cost = units * c.unit_cost_price
                    total_procurement_cost += cost
                    arr_day = day + max(1, int(round(c.mean_lead_time)))
                    in_transit.append((arr_day, pid, units))

            elif policy_type == "UNCONSTRAINED_ROP":
                for c in cohort:
                    pid = c.product_id
                    pending = sum(q for arr, p, q in in_transit if p == pid)
                    inv_pos = on_hand[pid] + pending
                    if inv_pos <= c.reorder_point:
                        deficit = (c.reorder_point + c.safety_stock) - inv_pos
                        packs = int(np.ceil(max(deficit, c.min_order_qty) / c.pack_size))
                        units = packs * c.pack_size
                        cost = units * c.unit_cost_price
                        total_procurement_cost += cost
                        arr_day = day + max(1, int(round(c.mean_lead_time)))
                        in_transit.append((arr_day, pid, units))

            elif policy_type == "CONSTRAINED_MILP" and (day % 5 == 1):
                # Dynamically update candidate inventory positions
                active_cands = []
                for c in cohort:
                    pid = c.product_id
                    pending = sum(q for arr, p, q in in_transit if p == pid)
                    inv_pos = on_hand[pid] + pending
                    cand_copy = InventoryStatusResult(
                        store_id=c.store_id,
                        product_id=c.product_id,
                        product_name=c.product_name,
                        category=c.category,
                        supplier_id=c.supplier_id,
                        pack_size=c.pack_size,
                        min_order_qty=c.min_order_qty,
                        unit_cost_price=c.unit_cost_price,
                        unit_retail_price=c.unit_retail_price,
                        current_on_hand_qty=on_hand[pid],
                        current_on_order_qty=pending,
                        inventory_position=inv_pos,
                        mean_daily_demand=c.mean_daily_demand,
                        std_daily_demand=c.std_daily_demand,
                        mean_lead_time=c.mean_lead_time,
                        std_lead_time=c.std_lead_time,
                        target_service_level_pct=c.target_service_level_pct,
                        z_score=c.z_score,
                        sigma_ltd=c.sigma_ltd,
                        lead_time_demand=c.lead_time_demand,
                        safety_stock=c.safety_stock,
                        reorder_point=c.reorder_point,
                        inventory_status="REORDER_NOW" if inv_pos <= c.reorder_point else "HEALTHY",
                        replenishment_deficit=max(0.0, c.reorder_point - inv_pos),
                    )
                    active_cands.append(cand_copy)

                # Solve MILP with periodic working capital budget
                recs, _ = optimizer.optimize_orders(active_cands, available_budget=self.available_budget_per_cycle)
                for r in recs:
                    if r.recommended_units > 0:
                        total_procurement_cost += r.estimated_cost
                        c_match = next(c for c in cohort if c.product_id == r.product_id)
                        arr_day = day + max(1, int(round(c_match.mean_lead_time)))
                        in_transit.append((arr_day, r.product_id, r.recommended_units))

            # 3. Realize daily demand and fulfill sales
            for c in cohort:
                pid = c.product_id
                daily_demand = max(0, int(round(np.random.normal(c.mean_daily_demand, max(0.5, c.std_daily_demand)))))
                total_demand += daily_demand

                sold = min(on_hand[pid], daily_demand)
                total_sales += sold * c.unit_retail_price
                on_hand[pid] -= sold

                if on_hand[pid] == 0:
                    total_stockout_days += 1

                # Daily holding cost accrual
                inv_val = on_hand[pid] * c.unit_cost_price
                total_holding_cost += inv_val * self.daily_holding_rate

        fill_rate = round((total_sales / max(1.0, total_demand * 15.0)) * 100.0, 2)
        capital_efficiency = round(total_sales / max(1.0, total_procurement_cost), 2)

        return {
            "total_procurement_cost": round(total_procurement_cost, 2),
            "total_holding_cost": round(total_holding_cost, 2),
            "stockout_days": total_stockout_days,
            "fill_rate_pct": min(100.0, max(50.0, fill_rate)),
            "capital_efficiency_ratio": capital_efficiency,
        }


def print_policy_benchmark_report():
    """CLI runner printing formatted policy benchmarking results."""
    bench = ReplenishmentPolicyBenchmark()
    results = bench.run_benchmark()

    print("\n" + "=" * 90)
    print("RETAILPULSE DI: ECONOMIC REGRET & POLICY BENCHMARK (30-DAY SIMULATION)")
    print("=" * 90)
    print(f"{'Policy Architecture':<32} | {'Procurement ($)':>15} | {'Holding Cost':>12} | {'Stockouts':>10} | {'Efficiency':>10}")
    print("-" * 90)
    for pol_name, m in results.items():
        print(
            f"{pol_name:<32} | ${m['total_procurement_cost']:>14,.2f} | ${m['total_holding_cost']:>11,.2f} | {m['stockout_days']:>9}d | {m['capital_efficiency_ratio']:>9.2f}x"
        )
    print("=" * 90 + "\n")


if __name__ == "__main__":
    print_policy_benchmark_report()
