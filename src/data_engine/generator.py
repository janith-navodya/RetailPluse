"""Calibrated synthetic retail data generator simulating physical supply chain dynamics."""
import uuid
import random
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

from config.settings import settings
from config.logging_config import logger


class RetailDataGenerator:
    """Generates synthetic multi-echelon retail data with censored demand and corruptions."""

    def __init__(self, seed: int = settings.RANDOM_SEED):
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
        self.start_date = datetime.strptime(settings.START_DATE, "%Y-%m-%d").date()
        self.simulation_days = settings.SIMULATION_DAYS

    def generate_dimensions(self) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
        """Generates dim_date, dim_store, dim_supplier, dim_product."""
        logger.info("Generating dimension entities...")

        # 1. Dim Date
        dates = []
        for d in range(self.simulation_days):
            curr_date = self.start_date + timedelta(days=d)
            date_key = int(curr_date.strftime("%Y%m%d"))
            day_of_week = curr_date.isoweekday()  # 1=Mon, 7=Sun
            dates.append(
                {
                    "date_key": date_key,
                    "full_date": curr_date,
                    "day_of_week": day_of_week,
                    "day_name": curr_date.strftime("%A"),
                    "day_of_month": curr_date.day,
                    "month_num": curr_date.month,
                    "month_name": curr_date.strftime("%B"),
                    "quarter": (curr_date.month - 1) // 3 + 1,
                    "year": curr_date.year,
                    "is_weekend": 1 if day_of_week in (6, 7) else 0,
                    "is_holiday": 1 if (curr_date.month == 12 and curr_date.day in (24, 25, 31)) or (curr_date.month == 11 and curr_date.day == 28) else 0,
                }
            )

        # 2. Dim Store
        stores = [
            {
                "store_id": "STR01",
                "store_name": "Downtown Metro Flagship",
                "store_format": "Flagship Urban",
                "city": "Metropolis",
                "state": "NY",
                "square_footage": 18000,
                "storage_capacity_units": 15000,
            },
            {
                "store_id": "STR02",
                "store_name": "Suburban Mega Center",
                "store_format": "Suburban Superstore",
                "city": "Highland",
                "state": "NJ",
                "square_footage": 45000,
                "storage_capacity_units": 35000,
            },
            {
                "store_id": "STR03",
                "store_name": "Westside QuickMart",
                "store_format": "Express",
                "city": "Riverdale",
                "state": "NY",
                "square_footage": 5500,
                "storage_capacity_units": 4000,
            },
        ]

        # 3. Dim Supplier
        suppliers = []
        for i in range(1, settings.NUM_SUPPLIERS + 1):
            sup_id = f"SUP{i:02d}"
            mean_lt = round(random.uniform(2.5, 9.0), 1)
            suppliers.append(
                {
                    "supplier_id": sup_id,
                    "supplier_name": f"Global Vendor {i:02d} Logistics",
                    "contact_email": f"procurement@vendor{i:02d}.com",
                    "mean_lead_time_days": mean_lt,
                    "lead_time_std_dev": round(mean_lt * random.uniform(0.15, 0.35), 2),
                    "min_order_qty": random.choice([24, 48, 72, 100]),
                    "service_level_target_pct": round(random.uniform(92.0, 98.5), 1),
                }
            )

        # 4. Dim Product (50 SKUs across 5 categories)
        categories = [
            ("Perishables", ["Dairy", "Bakery", "Produce"], 7),
            ("Ambient Grocery", ["Canned Goods", "Pasta", "Condiments"], 180),
            ("Beverages & Snacks", ["Soda", "Chips", "Juice"], 90),
            ("Electronics", ["Audio", "Cables", "Accessories"], None),
            ("Household", ["Detergent", "Paper Goods", "Cleaners"], None),
        ]

        products = []
        sku_counter = 1
        for cat_name, subcats, shelf_life in categories:
            for _ in range(10):  # 10 SKUs per category = 50 SKUs total
                prod_id = f"PRD{sku_counter:02d}"
                sub_cat = random.choice(subcats)
                assigned_supplier = random.choice(suppliers)["supplier_id"]

                if cat_name == "Electronics":
                    unit_cost = round(random.uniform(25.0, 140.0), 2)
                    unit_retail = round(unit_cost * random.uniform(1.4, 1.9), 2)
                    pack_size = random.choice([2, 4, 6])
                elif cat_name == "Perishables":
                    unit_cost = round(random.uniform(1.20, 6.50), 2)
                    unit_retail = round(unit_cost * random.uniform(1.3, 1.6), 2)
                    pack_size = random.choice([6, 12])
                else:
                    unit_cost = round(random.uniform(2.50, 18.00), 2)
                    unit_retail = round(unit_cost * random.uniform(1.35, 1.75), 2)
                    pack_size = random.choice([6, 12, 24])

                products.append(
                    {
                        "product_id": prod_id,
                        "product_name": f"{sub_cat} SKU-{prod_id}",
                        "category": cat_name,
                        "sub_category": sub_cat,
                        "brand": f"Brand-{random.choice(['Alpha', 'Apex', 'Prime', 'Valor', 'Select'])}",
                        "supplier_id": assigned_supplier,
                        "unit_cost_price": unit_cost,
                        "unit_retail_price": unit_retail,
                        "pack_size": pack_size,
                        "shelf_life_days": shelf_life,
                    }
                )
                sku_counter += 1

        return dates, stores, suppliers, products

    def generate_facts(
        self,
        dates: List[Dict],
        stores: List[Dict],
        suppliers: List[Dict],
        products: List[Dict],
        batch_id: str,
        inject_corruptions: bool = settings.INJECT_CORRUPTIONS,
    ) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Simulates physical store sales, purchase order transit, and closing inventory."""
        logger.info("Simulating 730-day inventory movements and transactional sales...")

        prod_lookup = {p["product_id"]: p for p in products}
        sup_lookup = {s["supplier_id"]: s for s in suppliers}
        store_lookup = {s["store_id"]: s for s in stores}

        sales_records = []
        inventory_records = []
        purchase_orders = []

        now_utc = datetime.now(timezone.utc)
        po_counter = 1

        # Track active pipeline per store-product:
        # on_hand inventory and pending incoming orders: list of (delivery_date_key, qty, po_id)
        inventory_state: Dict[Tuple[str, str], int] = {}
        pending_orders: Dict[Tuple[str, str], List[Tuple[int, int, str]]] = {}

        # Initialize on-hand inventory
        for s in stores:
            for p in products:
                pair = (s["store_id"], p["product_id"])
                # Start with 5-15 days of stock
                base_qty = p["pack_size"] * random.randint(4, 12)
                inventory_state[pair] = base_qty
                pending_orders[pair] = []

        # Iterate chronologically day by day
        for date_info in dates:
            curr_date = date_info["full_date"]
            curr_date_key = date_info["date_key"]
            is_weekend = date_info["is_weekend"]
            day_of_year = curr_date.timetuple().tm_yday

            # Day-of-week demand multiplier
            dow_multiplier = 1.35 if is_weekend else 0.90
            # Seasonal annual wave
            seasonal_multiplier = 1.0 + 0.15 * np.sin(2 * np.pi * day_of_year / 365)

            for store in stores:
                s_id = store["store_id"]
                store_scale = 1.4 if s_id == "STR01" else (1.2 if s_id == "STR02" else 0.7)

                for product in products:
                    p_id = product["product_id"]
                    pair = (s_id, p_id)
                    supplier = sup_lookup[product["supplier_id"]]

                    # 1. Receive in-transit purchase orders due today
                    beginning_on_hand = inventory_state[pair]
                    received_today = 0
                    remaining_pending = []
                    for deliv_date_key, order_qty, po_id in pending_orders[pair]:
                        if deliv_date_key <= curr_date_key:
                            received_today += order_qty
                            # Update PO record to DELIVERED
                            for po in purchase_orders:
                                if po["po_id"] == po_id and po["status"] == "IN_TRANSIT":
                                    po["status"] = "DELIVERED"
                                    po["received_qty"] = order_qty
                                    po["actual_delivery_date_key"] = curr_date_key
                        else:
                            remaining_pending.append((deliv_date_key, order_qty, po_id))
                    pending_orders[pair] = remaining_pending

                    available_stock = beginning_on_hand + received_today

                    # 2. Simulate latent customer demand D_t
                    is_promo = 1 if random.random() < 0.08 else 0
                    promo_lift = random.uniform(1.4, 2.1) if is_promo else 1.0

                    if product["category"] == "Electronics":
                        # Intermittent demand (many zeros, occasional purchases)
                        if random.random() < 0.35:
                            demand = max(1, np.random.poisson(2.0 * store_scale * promo_lift))
                        else:
                            demand = 0
                    elif product["category"] == "Perishables":
                        demand = max(1, np.random.poisson(14.0 * store_scale * dow_multiplier * seasonal_multiplier * promo_lift))
                    else:
                        demand = max(0, np.random.poisson(7.0 * store_scale * dow_multiplier * seasonal_multiplier * promo_lift))

                    # 3. Realize sales Y_t = min(available_stock, demand) -> CENSORED DEMAND
                    sold_qty = min(available_stock, demand)
                    ending_on_hand = available_stock - sold_qty
                    inventory_state[pair] = ending_on_hand
                    is_stockout = 1 if ending_on_hand == 0 else 0

                    # Financials
                    unit_retail = product["unit_retail_price"]
                    unit_cost = product["unit_cost_price"]
                    discount_rate = random.uniform(0.10, 0.20) if is_promo else 0.0
                    gross_sales = round(sold_qty * unit_retail, 2)
                    discount_amount = round(gross_sales * discount_rate, 2)
                    net_sales = round(gross_sales - discount_amount, 2)
                    cogs = round(sold_qty * unit_cost, 2)
                    gross_profit = round(net_sales - cogs, 2)

                    # Sales record (recorded even if sold_qty == 0 to maintain continuous series)
                    sales_records.append(
                        {
                            "date_key": curr_date_key,
                            "store_id": s_id,
                            "product_id": p_id,
                            "quantity_sold": sold_qty,
                            "gross_sales_amount": gross_sales,
                            "discount_amount": discount_amount,
                            "net_sales_amount": net_sales,
                            "cogs_amount": cogs,
                            "gross_profit_amount": gross_profit,
                            "is_promotional": is_promo,
                            "batch_id": batch_id,
                            "ingested_at": now_utc,
                        }
                    )

                    # Inventory snapshot record
                    ending_inv_val = round(ending_on_hand * unit_cost, 2)
                    inventory_records.append(
                        {
                            "date_key": curr_date_key,
                            "store_id": s_id,
                            "product_id": p_id,
                            "beginning_on_hand_qty": beginning_on_hand,
                            "received_qty": received_today,
                            "sold_qty": sold_qty,
                            "ending_on_hand_qty": ending_on_hand,
                            "ending_inventory_value": ending_inv_val,
                            "is_stockout": is_stockout,
                            "batch_id": batch_id,
                            "ingested_at": now_utc,
                        }
                    )

                    # 4. Replenishment policy: Reorder Point trigger
                    pipeline_qty = sum(po[1] for po in pending_orders[pair])
                    inventory_position = ending_on_hand + pipeline_qty

                    # Dynamic Reorder Point estimation: ROP = ADS * LeadTime + SafetyStock
                    reorder_point = product["pack_size"] * 3
                    if inventory_position <= reorder_point:
                        # Order to replenish to target stock, satisfying pack size and MOQ
                        min_order = max(supplier["min_order_qty"], product["pack_size"] * 4)
                        # Round up to multiple of pack size
                        packs_to_order = int(np.ceil(min_order / product["pack_size"]))
                        order_qty = packs_to_order * product["pack_size"]

                        # Stochastic lead time
                        lead_days = max(1, int(round(np.random.normal(supplier["mean_lead_time_days"], max(0.5, supplier["lead_time_std_dev"])))))
                        exp_deliv_date = curr_date + timedelta(days=lead_days)
                        exp_deliv_key = int(exp_deliv_date.strftime("%Y%m%d"))
                        po_id = f"PO-{curr_date_key}-{po_counter:04d}"
                        po_counter += 1

                        po_record = {
                            "po_id": po_id,
                            "order_date_key": curr_date_key,
                            "expected_delivery_date_key": exp_deliv_key,
                            "actual_delivery_date_key": None,
                            "store_id": s_id,
                            "product_id": p_id,
                            "supplier_id": product["supplier_id"],
                            "order_qty": order_qty,
                            "received_qty": 0,
                            "unit_cost_price": unit_cost,
                            "total_cost_amount": round(order_qty * unit_cost, 2),
                            "status": "IN_TRANSIT",
                            "batch_id": batch_id,
                            "ingested_at": now_utc,
                        }
                        purchase_orders.append(po_record)
                        pending_orders[pair].append((exp_deliv_key, order_qty, po_id))

        # 5. Inject controlled corruptions if requested (for testing dead-letter quarantine)
        if inject_corruptions:
            sales_records, inventory_records = self._inject_anomalies(sales_records, inventory_records)

        logger.info(
            "Generation complete: %d sales records, %d inventory records, %d purchase orders",
            len(sales_records),
            len(inventory_records),
            len(purchase_orders),
        )
        return sales_records, inventory_records, purchase_orders

    def _inject_anomalies(
        self,
        sales: List[Dict],
        inventory: List[Dict],
    ) -> Tuple[List[Dict], List[Dict]]:
        """Injects controlled malformed records into sales and inventory feeds."""
        logger.warning("Injecting controlled corruptions to stress-test quarantine...")
        # A. Negative price corruption (15 records)
        for i in range(15):
            idx = random.randint(0, len(sales) - 1)
            sales[idx] = dict(sales[idx])
            sales[idx]["gross_sales_amount"] = -25.00
            sales[idx]["net_sales_amount"] = -25.00

        # B. Orphaned foreign keys (15 records)
        for i in range(15):
            idx = random.randint(0, len(sales) - 1)
            sales[idx] = dict(sales[idx])
            sales[idx]["product_id"] = "PRD999"  # Non-existent SKU

        # C. Physical balance mismatch in inventory (15 records)
        for i in range(15):
            idx = random.randint(0, len(inventory) - 1)
            inventory[idx] = dict(inventory[idx])
            inventory[idx]["ending_on_hand_qty"] = inventory[idx]["beginning_on_hand_qty"] + 999  # Math violation

        return sales, inventory
