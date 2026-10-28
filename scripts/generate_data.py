"""Synthetic retail data generator producing raw CSV feeds with censored demand and corruptions.

Simulates 730 days of physical inventory movements, supplier lead-time variance,
pack sizes, MOQs, out-of-stock events (censored demand), and controlled corruptions.
"""
import os
import sys
import random
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd

from config.settings import settings
from config.logging_config import logger


def generate_all_raw_data(
    output_dir: Path = settings.RAW_DATA_DIR,
    simulation_days: int = settings.SIMULATION_DAYS,
    seed: int = settings.RANDOM_SEED,
    inject_corruptions: bool = settings.INJECT_CORRUPTIONS,
) -> Dict[str, Path]:
    """Generates synthetic multi-echelon retail datasets and saves them as CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    random.seed(seed)
    np.random.seed(seed)

    start_date = datetime.strptime(settings.START_DATE, "%Y-%m-%d").date()
    logger.info("Generating raw retail datasets (%d days) into %s...", simulation_days, output_dir)

    # -------------------------------------------------------------------------
    # 1. Dimension: dim_date (Extended to cover future purchase order deliveries)
    # -------------------------------------------------------------------------
    dates = []
    # Extend date calendar by 90 days beyond simulation horizon to cover pending PO arrivals
    total_calendar_days = simulation_days + 90
    for d in range(total_calendar_days):
        curr = start_date + timedelta(days=d)
        d_key = int(curr.strftime("%Y%m%d"))
        dow = curr.isoweekday()
        dates.append(
            {
                "date_key": d_key,
                "full_date": curr.isoformat(),
                "day_of_week": dow,
                "day_name": curr.strftime("%A"),
                "day_of_month": curr.day,
                "month_num": curr.month,
                "month_name": curr.strftime("%B"),
                "quarter": (curr.month - 1) // 3 + 1,
                "year": curr.year,
                "is_weekend": 1 if dow in (6, 7) else 0,
                "is_holiday": 1 if (curr.month == 12 and curr.day in (24, 25, 31)) or (curr.month == 11 and curr.day == 28) else 0,
            }
        )
    df_date = pd.DataFrame(dates)
    date_csv = output_dir / "dim_date.csv"
    df_date.to_csv(date_csv, index=False)

    # -------------------------------------------------------------------------
    # 2. Dimension: dim_store
    # -------------------------------------------------------------------------
    stores = [
        {
            "store_id": "STR01",
            "store_name": "Downtown Metro Flagship",
            "store_format": "Flagship Urban",
            "city": "New York",
            "state": "NY",
            "square_footage": 18000,
            "storage_capacity_units": 15000,
        },
        {
            "store_id": "STR02",
            "store_name": "Suburban Mega Center",
            "store_format": "Suburban Superstore",
            "city": "Edison",
            "state": "NJ",
            "square_footage": 45000,
            "storage_capacity_units": 35000,
        },
        {
            "store_id": "STR03",
            "store_name": "Westside QuickMart",
            "store_format": "Express",
            "city": "Hoboken",
            "state": "NJ",
            "square_footage": 5500,
            "storage_capacity_units": 4000,
        },
    ]
    df_store = pd.DataFrame(stores)
    store_csv = output_dir / "dim_store.csv"
    df_store.to_csv(store_csv, index=False)

    # -------------------------------------------------------------------------
    # 3. Dimension: dim_supplier
    # -------------------------------------------------------------------------
    suppliers = []
    for i in range(1, settings.NUM_SUPPLIERS + 1):
        sup_id = f"SUP{i:02d}"
        mean_lt = round(random.uniform(2.5, 9.0), 1)
        suppliers.append(
            {
                "supplier_id": sup_id,
                "supplier_name": f"Vendor {i:02d} Distribution Corp",
                "contact_email": f"orders@vendor{i:02d}.com",
                "mean_lead_time_days": mean_lt,
                "lead_time_std_dev": round(mean_lt * random.uniform(0.15, 0.35), 2),
                "min_order_qty": random.choice([24, 48, 72, 100]),
                "service_level_target_pct": round(random.uniform(92.0, 98.5), 1),
            }
        )
    df_supplier = pd.DataFrame(suppliers)
    supplier_csv = output_dir / "dim_supplier.csv"
    df_supplier.to_csv(supplier_csv, index=False)

    # -------------------------------------------------------------------------
    # 4. Dimension: dim_product
    # -------------------------------------------------------------------------
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
        for _ in range(10):  # 10 SKUs per category = 50 total SKUs
            prod_id = f"PRD{sku_counter:02d}"
            sub_cat = random.choice(subcats)
            assigned_supplier = random.choice(suppliers)["supplier_id"]

            if cat_name == "Electronics":
                unit_cost = round(random.uniform(25.0, 140.0), 2)
                unit_retail = round(unit_cost * random.uniform(1.4, 1.85), 2)
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
                    "product_name": f"{sub_cat} Item {prod_id}",
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

    df_product = pd.DataFrame(products)
    product_csv = output_dir / "dim_product.csv"
    df_product.to_csv(product_csv, index=False)

    # -------------------------------------------------------------------------
    # 5. Fact Tables Simulation (Physical Stock Dynamics & Censored Sales)
    # -------------------------------------------------------------------------
    sup_lookup = {s["supplier_id"]: s for s in suppliers}
    now_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    batch_id = f"RAW-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"

    inventory_state: Dict[Tuple[str, str], int] = {}
    pending_orders: Dict[Tuple[str, str], List[Tuple[int, int, str]]] = {}

    for s in stores:
        for p in products:
            pair = (s["store_id"], p["product_id"])
            inventory_state[pair] = p["pack_size"] * random.randint(4, 12)
            pending_orders[pair] = []

    sales_records = []
    inventory_records = []
    purchase_orders = []
    po_counter = 1

    for d_idx in range(simulation_days):
        d_row = dates[d_idx]
        curr_date = start_date + timedelta(days=d_idx)
        d_key = d_row["date_key"]
        is_weekend = d_row["is_weekend"]
        doy = curr_date.timetuple().tm_yday

        dow_mult = 1.35 if is_weekend else 0.90
        season_mult = 1.0 + 0.15 * np.sin(2 * np.pi * doy / 365)

        for s in stores:
            s_id = s["store_id"]
            store_scale = 1.4 if s_id == "STR01" else (1.2 if s_id == "STR02" else 0.7)

            for p in products:
                p_id = p["product_id"]
                pair = (s_id, p_id)
                supplier = sup_lookup[p["supplier_id"]]

                # Deliver due purchase orders
                beg_on_hand = inventory_state[pair]
                received_today = 0
                remaining_pos = []
                for deliv_key, qty, po_id in pending_orders[pair]:
                    if deliv_key <= d_key:
                        received_today += qty
                        for po in purchase_orders:
                            if po["po_id"] == po_id and po["status"] == "IN_TRANSIT":
                                po["status"] = "DELIVERED"
                                po["received_qty"] = qty
                                po["actual_delivery_date_key"] = d_key
                    else:
                        remaining_pos.append((deliv_key, qty, po_id))
                pending_orders[pair] = remaining_pos

                avail_stock = beg_on_hand + received_today

                # Latent customer demand D_t
                is_promo = 1 if random.random() < 0.08 else 0
                promo_lift = random.uniform(1.4, 2.1) if is_promo else 1.0

                if p["category"] == "Electronics":
                    demand = max(1, np.random.poisson(2.0 * store_scale * promo_lift)) if random.random() < 0.35 else 0
                elif p["category"] == "Perishables":
                    demand = max(1, np.random.poisson(14.0 * store_scale * dow_mult * season_mult * promo_lift))
                else:
                    demand = max(0, np.random.poisson(7.0 * store_scale * dow_mult * season_mult * promo_lift))

                # Realized Sales Y_t = min(avail_stock, demand) [Censored Demand!]
                sold_qty = min(avail_stock, demand)
                end_on_hand = avail_stock - sold_qty
                inventory_state[pair] = end_on_hand
                is_stockout = 1 if end_on_hand == 0 else 0

                unit_cost = p["unit_cost_price"]
                unit_retail = p["unit_retail_price"]
                discount_rate = random.uniform(0.10, 0.20) if is_promo else 0.0
                gross_sales = round(sold_qty * unit_retail, 2)
                discount_amt = round(gross_sales * discount_rate, 2)
                net_sales = round(gross_sales - discount_amt, 2)
                cogs = round(sold_qty * unit_cost, 2)
                gross_profit = round(net_sales - cogs, 2)

                sales_records.append(
                    {
                        "date_key": d_key,
                        "store_id": s_id,
                        "product_id": p_id,
                        "quantity_sold": sold_qty,
                        "gross_sales_amount": gross_sales,
                        "discount_amount": discount_amt,
                        "net_sales_amount": net_sales,
                        "cogs_amount": cogs,
                        "gross_profit_amount": gross_profit,
                        "is_promotional": is_promo,
                        "batch_id": batch_id,
                        "ingested_at": now_utc_str,
                    }
                )

                end_inv_val = round(end_on_hand * unit_cost, 2)
                inventory_records.append(
                    {
                        "date_key": d_key,
                        "store_id": s_id,
                        "product_id": p_id,
                        "beginning_on_hand_qty": beg_on_hand,
                        "received_qty": received_today,
                        "sold_qty": sold_qty,
                        "ending_on_hand_qty": end_on_hand,
                        "ending_inventory_value": end_inv_val,
                        "is_stockout": is_stockout,
                        "batch_id": batch_id,
                        "ingested_at": now_utc_str,
                    }
                )

                # Reorder trigger
                pipeline_qty = sum(po[1] for po in pending_orders[pair])
                inv_position = end_on_hand + pipeline_qty
                reorder_point = p["pack_size"] * 3

                if inv_position <= reorder_point:
                    moq = max(supplier["min_order_qty"], p["pack_size"] * 4)
                    packs = int(np.ceil(moq / p["pack_size"]))
                    order_qty = packs * p["pack_size"]

                    lead_days = max(1, int(round(np.random.normal(supplier["mean_lead_time_days"], max(0.5, supplier["lead_time_std_dev"])))))
                    exp_deliv = curr_date + timedelta(days=lead_days)
                    exp_deliv_key = int(exp_deliv.strftime("%Y%m%d"))
                    po_id = f"PO-{d_key}-{po_counter:04d}"
                    po_counter += 1

                    po_rec = {
                        "po_id": po_id,
                        "order_date_key": d_key,
                        "expected_delivery_date_key": exp_deliv_key,
                        "actual_delivery_date_key": None,
                        "store_id": s_id,
                        "product_id": p_id,
                        "supplier_id": p["supplier_id"],
                        "order_qty": order_qty,
                        "received_qty": 0,
                        "unit_cost_price": unit_cost,
                        "total_cost_amount": round(order_qty * unit_cost, 2),
                        "status": "IN_TRANSIT",
                        "batch_id": batch_id,
                        "ingested_at": now_utc_str,
                    }
                    purchase_orders.append(po_rec)
                    pending_orders[pair].append((exp_deliv_key, order_qty, po_id))

    # -------------------------------------------------------------------------
    # 6. Inject Controlled Corruptions for Quarantine Pipeline
    # -------------------------------------------------------------------------
    if inject_corruptions:
        logger.warning("Injecting controlled corruptions into raw sales and inventory...")
        # 1. Negative price corruption (15 records)
        for i in range(15):
            idx = random.randint(0, len(sales_records) - 1)
            sales_records[idx] = dict(sales_records[idx])
            sales_records[idx]["gross_sales_amount"] = -50.00
            sales_records[idx]["net_sales_amount"] = -50.00

        # 2. Missing/Orphaned Foreign Keys (15 records)
        for i in range(15):
            idx = random.randint(0, len(sales_records) - 1)
            sales_records[idx] = dict(sales_records[idx])
            sales_records[idx]["product_id"] = "PRD999"  # Non-existent SKU

        # 3. Malformed Dates (15 records)
        for i in range(15):
            idx = random.randint(0, len(sales_records) - 1)
            sales_records[idx] = dict(sales_records[idx])
            sales_records[idx]["date_key"] = 99999999  # Invalid future/unregistered date

        # 4. Inventory physical balance mismatch (15 records)
        for i in range(15):
            idx = random.randint(0, len(inventory_records) - 1)
            inventory_records[idx] = dict(inventory_records[idx])
            inventory_records[idx]["ending_on_hand_qty"] = inventory_records[idx]["beginning_on_hand_qty"] + 999

    # Save facts to CSV
    sales_csv = output_dir / "raw_sales_daily.csv"
    inv_csv = output_dir / "raw_inventory_snapshot.csv"
    po_csv = output_dir / "raw_purchase_orders.csv"

    pd.DataFrame(sales_records).to_csv(sales_csv, index=False)
    pd.DataFrame(inventory_records).to_csv(inv_csv, index=False)
    pd.DataFrame(purchase_orders).to_csv(po_csv, index=False)

    logger.info("Successfully generated raw CSVs:")
    logger.info("  - %s: %d rows", date_csv.name, len(df_date))
    logger.info("  - %s: %d rows", store_csv.name, len(df_store))
    logger.info("  - %s: %d rows", supplier_csv.name, len(df_supplier))
    logger.info("  - %s: %d rows", product_csv.name, len(df_product))
    logger.info("  - %s: %d rows", sales_csv.name, len(sales_records))
    logger.info("  - %s: %d rows", inv_csv.name, len(inventory_records))
    logger.info("  - %s: %d rows", po_csv.name, len(purchase_orders))

    return {
        "dim_date": date_csv,
        "dim_store": store_csv,
        "dim_supplier": supplier_csv,
        "dim_product": product_csv,
        "raw_sales_daily": sales_csv,
        "raw_inventory_snapshot": inv_csv,
        "raw_purchase_orders": po_csv,
    }


if __name__ == "__main__":
    generate_all_raw_data()
