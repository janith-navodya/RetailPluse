"""Stochastic Safety Stock & Reorder Point (ROP) Calculator for RetailPulse DI Platform.

Calculates dynamic safety stock and reorder points under simultaneous
demand volatility and supplier lead-time uncertainty using classical inventory theory:
    sigma_LTD = sqrt( mu_L * sigma_D^2 + mu_D^2 * sigma_L^2 )
    Safety Stock = Z * sigma_LTD
    Reorder Point (ROP) = (mu_D * mu_L) + Safety Stock
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from scipy.stats import norm
from config.logging_config import logger


@dataclass
class InventoryStatusResult:
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
    mean_daily_demand: float
    std_daily_demand: float
    mean_lead_time: float
    std_lead_time: float
    target_service_level_pct: float
    z_score: float
    sigma_ltd: float
    lead_time_demand: float
    safety_stock: float
    reorder_point: float
    inventory_status: str
    replenishment_deficit: float


class StochasticInventoryController:
    """Computes dynamic safety stock, ROP, and inventory health classifications."""

    def __init__(self, default_service_level: float = 0.95):
        self.default_service_level = default_service_level

    def calculate_sku_inventory_status(
        self,
        store_id: str,
        product_id: str,
        product_name: str,
        category: str,
        supplier_id: str,
        pack_size: int,
        min_order_qty: int,
        unit_cost_price: float,
        unit_retail_price: float,
        on_hand: int,
        on_order: int,
        mean_demand: float,
        std_demand: float,
        mean_lead_time: float,
        std_lead_time: float,
        service_level: Optional[float] = None,
    ) -> InventoryStatusResult:
        """Evaluates inventory health and reorder requirements for a single SKU-store pair."""
        sl = service_level if service_level is not None else self.default_service_level
        sl = max(0.50, min(0.999, sl))
        z = float(norm.ppf(sl))

        mu_d = max(0.01, float(mean_demand))
        sigma_d = max(0.01, float(std_demand))
        mu_l = max(1.0, float(mean_lead_time))
        sigma_l = max(0.0, float(std_lead_time))

        # Combined lead-time demand volatility:
        # Var(LTD) = E[L] * Var(D) + (E[D])^2 * Var(L)
        variance_ltd = (mu_l * (sigma_d ** 2)) + ((mu_d ** 2) * (sigma_l ** 2))
        sigma_ltd = float(np.sqrt(variance_ltd))

        safety_stock = float(np.maximum(0.0, z * sigma_ltd))
        lead_time_demand = float(mu_d * mu_l)
        reorder_point = float(lead_time_demand + safety_stock)

        inv_position = int(on_hand + on_order)

        # Inventory Status Classification
        if inv_position <= safety_stock:
            status = "STOCKOUT_RISK"
        elif inv_position <= reorder_point:
            status = "REORDER_NOW"
        elif inv_position >= (reorder_point + (2.0 * safety_stock)):
            status = "EXCESS_STOCK"
        else:
            status = "HEALTHY"

        deficit = float(np.maximum(0.0, reorder_point - inv_position))

        return InventoryStatusResult(
            store_id=store_id,
            product_id=product_id,
            product_name=product_name,
            category=category,
            supplier_id=supplier_id,
            pack_size=pack_size,
            min_order_qty=min_order_qty,
            unit_cost_price=round(unit_cost_price, 2),
            unit_retail_price=round(unit_retail_price, 2),
            current_on_hand_qty=int(on_hand),
            current_on_order_qty=int(on_order),
            inventory_position=inv_position,
            mean_daily_demand=round(mu_d, 2),
            std_daily_demand=round(sigma_d, 2),
            mean_lead_time=round(mu_l, 1),
            std_lead_time=round(sigma_l, 2),
            target_service_level_pct=round(sl * 100.0, 1),
            z_score=round(z, 3),
            sigma_ltd=round(sigma_ltd, 2),
            lead_time_demand=round(lead_time_demand, 1),
            safety_stock=round(safety_stock, 1),
            reorder_point=round(reorder_point, 1),
            inventory_status=status,
            replenishment_deficit=round(deficit, 1),
        )

    def evaluate_fleet_inventory(
        self,
        df_inventory_snapshot: pd.DataFrame,
        df_products: pd.DataFrame,
        df_suppliers: pd.DataFrame,
        df_forecasts: pd.DataFrame,
    ) -> List[InventoryStatusResult]:
        """Evaluates all SKU-store combinations across the fleet."""
        # Join metadata
        merged = df_inventory_snapshot.merge(df_products, on="product_id", how="inner")
        merged = merged.merge(df_suppliers, on="supplier_id", how="inner")
        merged = merged.merge(df_forecasts, on=["store_id", "product_id"], how="left")

        results = []
        for _, row in merged.iterrows():
            res = self.calculate_sku_inventory_status(
                store_id=row["store_id"],
                product_id=row["product_id"],
                product_name=row["product_name"],
                category=row["category"],
                supplier_id=row["supplier_id"],
                pack_size=int(row["pack_size"]),
                min_order_qty=int(row["min_order_qty"]),
                unit_cost_price=float(row["unit_cost_price"]),
                unit_retail_price=float(row["unit_retail_price"]),
                on_hand=int(row["ending_on_hand_qty"]),
                on_order=int(row.get("on_order_qty", 0)),
                mean_demand=float(row.get("forecast_demand", row.get("mean_daily_demand", 5.0))),
                std_demand=float(row.get("forecast_std", row.get("std_daily_demand", 2.0))),
                mean_lead_time=float(row["mean_lead_time_days"]),
                std_lead_time=float(row.get("lead_time_std_dev", 0.5)),
                service_level=float(row.get("service_level_target_pct", 95.0)) / 100.0,
            )
            results.append(res)

        return results

