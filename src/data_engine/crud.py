"""Data Access and CRUD Engine for RetailPulse DI Platform.

Provides transactional Create, Read, Update, and Delete (CRUD) operations,
inventory stock level adjustments, and bulk file (CSV/Excel) ingestion
for SQL Server dimensional star schema tables.
"""
from __future__ import annotations

import io
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from sqlalchemy import text

from config.settings import settings
from config.logging_config import logger
from src.ui.data_access import get_engine, execute_query, invalidate_ui_cache


# ==============================================================================
# 1. Product Catalog CRUD
# ==============================================================================

def get_all_products() -> pd.DataFrame:
    """Retrieves all products joined with their supplier name."""
    sql = """
        SELECT 
            p.product_id,
            p.product_name,
            p.category,
            p.sub_category,
            p.brand,
            p.supplier_id,
            s.supplier_name,
            p.unit_cost_price,
            p.unit_retail_price,
            p.pack_size,
            p.shelf_life_days
        FROM dbo.dim_product p
        LEFT JOIN dbo.dim_supplier s ON p.supplier_id = s.supplier_id
        ORDER BY p.category, p.product_name;
    """
    return execute_query(sql)


def get_all_stores() -> pd.DataFrame:
    """Retrieves all active retail stores from dim_store."""
    sql = """
        SELECT 
            store_id,
            store_name,
            store_format,
            city,
            state,
            square_footage,
            storage_capacity_units
        FROM dbo.dim_store
        ORDER BY store_id;
    """
    df = execute_query(sql)
    if df.empty:
        return pd.DataFrame([
            {"store_id": "STR01", "store_name": "Downtown Metro Flagship", "store_format": "Flagship Urban", "city": "Metropolis", "state": "NY"},
            {"store_id": "STR02", "store_name": "Suburban Mega Center", "store_format": "Suburban Superstore", "city": "Highland", "state": "NJ"},
            {"store_id": "STR03", "store_name": "Westside QuickMart", "store_format": "Express", "city": "Riverdale", "state": "NY"},
        ])
    return df


def create_product(
    product_id: str,
    product_name: str,
    category: str,
    sub_category: str,
    brand: str,
    supplier_id: str,
    unit_cost_price: float,
    unit_retail_price: float,
    pack_size: int,
    shelf_life_days: Optional[int] = None,
) -> Tuple[bool, str]:
    """Inserts a new product into dim_product with business rule validation."""
    product_id = product_id.strip().upper()
    product_name = product_name.strip()
    
    if not product_id or not product_name:
        return False, "Product ID and Product Name cannot be empty."
    if len(product_id) > 10:
        return False, f"Product ID '{product_id}' exceeds maximum length of 10 characters."
    if unit_retail_price <= unit_cost_price:
        return False, f"Unit Retail Price (${unit_retail_price:.2f}) must exceed Cost Price (${unit_cost_price:.2f})."
    if pack_size < 1:
        return False, "Pack size must be at least 1 unit."

    engine = get_engine()
    try:
        with engine.begin() as conn:
            # Check duplicate ID
            check_sql = text("SELECT COUNT(*) FROM dbo.dim_product WHERE product_id = :pid;")
            existing = conn.execute(check_sql, {"pid": product_id}).scalar()
            if existing > 0:
                return False, f"Product ID '{product_id}' already exists."

            insert_sql = text("""
                INSERT INTO dbo.dim_product (
                    product_id, product_name, category, sub_category, brand,
                    supplier_id, unit_cost_price, unit_retail_price, pack_size, shelf_life_days
                ) VALUES (
                    :pid, :pname, :cat, :subcat, :brand,
                    :supid, :cost, :retail, :pack, :shelf
                );
            """)
            conn.execute(insert_sql, {
                "pid": product_id,
                "pname": product_name,
                "cat": category.strip(),
                "subcat": sub_category.strip(),
                "brand": brand.strip(),
                "supid": supplier_id.strip(),
                "cost": round(float(unit_cost_price), 2),
                "retail": round(float(unit_retail_price), 2),
                "pack": int(pack_size),
                "shelf": int(shelf_life_days) if shelf_life_days else None,
            })

            # Seed initial zero-stock snapshot records across all stores for immediate operational availability
            init_inv_sql = text("""
                DECLARE @MaxD INT = (SELECT MAX(date_key) FROM dbo.fact_inventory_snapshot);
                IF @MaxD IS NOT NULL
                BEGIN
                    INSERT INTO dbo.fact_inventory_snapshot (
                        date_key, store_id, product_id, beginning_on_hand_qty, received_qty, sold_qty,
                        ending_on_hand_qty, ending_inventory_value, is_stockout, batch_id, ingested_at
                    )
                    SELECT 
                        @MaxD, s.store_id, :pid, 0, 0, 0, 0, 0.0, 1, 'INIT-NEW', GETUTCDATE()
                    FROM dbo.dim_store s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM dbo.fact_inventory_snapshot inv 
                        WHERE inv.date_key = @MaxD AND inv.store_id = s.store_id AND inv.product_id = :pid
                    );
                END
            """)
            conn.execute(init_inv_sql, {"pid": product_id})

            logger.info("Created product %s (%s)", product_id, product_name)
            invalidate_ui_cache()
            return True, f"Successfully created product {product_id} ({product_name})."
    except Exception as exc:
        logger.error("Failed to create product %s: %s", product_id, exc)
        return False, f"Database error: {exc}"


def update_product(
    product_id: str,
    product_name: str,
    category: str,
    sub_category: str,
    brand: str,
    supplier_id: str,
    unit_cost_price: float,
    unit_retail_price: float,
    pack_size: int,
    shelf_life_days: Optional[int] = None,
) -> Tuple[bool, str]:
    """Updates an existing product in dim_product."""
    if unit_retail_price <= unit_cost_price:
        return False, f"Unit Retail Price (${unit_retail_price:.2f}) must exceed Cost Price (${unit_cost_price:.2f})."
    if pack_size < 1:
        return False, "Pack size must be at least 1 unit."

    engine = get_engine()
    try:
        with engine.begin() as conn:
            update_sql = text("""
                UPDATE dbo.dim_product
                SET product_name = :pname,
                    category = :cat,
                    sub_category = :subcat,
                    brand = :brand,
                    supplier_id = :supid,
                    unit_cost_price = :cost,
                    unit_retail_price = :retail,
                    pack_size = :pack,
                    shelf_life_days = :shelf
                WHERE product_id = :pid;
            """)
            res = conn.execute(update_sql, {
                "pid": product_id,
                "pname": product_name.strip(),
                "cat": category.strip(),
                "subcat": sub_category.strip(),
                "brand": brand.strip(),
                "supid": supplier_id.strip(),
                "cost": round(float(unit_cost_price), 2),
                "retail": round(float(unit_retail_price), 2),
                "pack": int(pack_size),
                "shelf": int(shelf_life_days) if shelf_life_days else None,
            })
            if res.rowcount == 0:
                return False, f"Product {product_id} not found."
            logger.info("Updated product %s", product_id)
            invalidate_ui_cache()
            return True, f"Successfully updated product {product_id}."
    except Exception as exc:
        logger.error("Failed to update product %s: %s", product_id, exc)
        return False, f"Database error: {exc}"


def delete_product(product_id: str, force_cascade: bool = False) -> Tuple[bool, str]:
    """Deletes or archives a product from dim_product."""
    engine = get_engine()
    try:
        with engine.begin() as conn:
            # Check sales or inventory references
            ref_sql = text("""
                SELECT 
                    (SELECT COUNT(*) FROM dbo.fact_sales_daily WHERE product_id = :pid) +
                    (SELECT COUNT(*) FROM dbo.fact_inventory_snapshot WHERE product_id = :pid) +
                    (SELECT COUNT(*) FROM dbo.fact_purchase_orders WHERE product_id = :pid);
            """)
            ref_count = conn.execute(ref_sql, {"pid": product_id}).scalar()
            
            if ref_count > 0 and not force_cascade:
                return False, (
                    f"Product '{product_id}' is referenced by {ref_count} historical transaction/inventory records. "
                    "Cannot safely delete without cascade confirmation."
                )

            if force_cascade:
                conn.execute(text("DELETE FROM dbo.fact_replenishment_recommendation WHERE product_id = :pid;"), {"pid": product_id})
                conn.execute(text("DELETE FROM dbo.fact_sales_daily WHERE product_id = :pid;"), {"pid": product_id})
                conn.execute(text("DELETE FROM dbo.fact_inventory_snapshot WHERE product_id = :pid;"), {"pid": product_id})
                conn.execute(text("DELETE FROM dbo.fact_purchase_orders WHERE product_id = :pid;"), {"pid": product_id})

            del_sql = text("DELETE FROM dbo.dim_product WHERE product_id = :pid;")
            res = conn.execute(del_sql, {"pid": product_id})
            if res.rowcount == 0:
                return False, f"Product '{product_id}' not found."
            
            logger.info("Deleted product %s (cascade=%s)", product_id, force_cascade)
            invalidate_ui_cache()
            return True, f"Successfully removed product {product_id}."
    except Exception as exc:
        logger.error("Failed to delete product %s: %s", product_id, exc)
        return False, f"Database error: {exc}"


# ==============================================================================
# 2. Supplier Directory CRUD
# ==============================================================================

def get_all_suppliers() -> pd.DataFrame:
    """Retrieves all registered suppliers."""
    sql = """
        SELECT 
            s.supplier_id,
            s.supplier_name,
            s.contact_email,
            s.mean_lead_time_days,
            s.lead_time_std_dev,
            s.min_order_qty,
            s.service_level_target_pct,
            COUNT(p.product_id) AS active_products_count
        FROM dbo.dim_supplier s
        LEFT JOIN dbo.dim_product p ON s.supplier_id = p.supplier_id
        GROUP BY s.supplier_id, s.supplier_name, s.contact_email, s.mean_lead_time_days,
                 s.lead_time_std_dev, s.min_order_qty, s.service_level_target_pct
        ORDER BY s.supplier_name;
    """
    return execute_query(sql)


def create_supplier(
    supplier_id: str,
    supplier_name: str,
    contact_email: str,
    mean_lead_time_days: float,
    lead_time_std_dev: float,
    min_order_qty: int,
    service_level_target_pct: float = 95.0,
) -> Tuple[bool, str]:
    """Inserts a new supplier into dim_supplier."""
    supplier_id = supplier_id.strip().upper()
    supplier_name = supplier_name.strip()
    if not supplier_id or not supplier_name:
        return False, "Supplier ID and Name are required."
    if len(supplier_id) > 10:
        return False, f"Supplier ID '{supplier_id}' exceeds maximum length of 10 characters."
    if mean_lead_time_days < 1.0:
        return False, "Mean lead time must be at least 1 day."
    if min_order_qty < 1:
        return False, "Minimum Order Quantity (MOQ) must be at least 1 unit."

    engine = get_engine()
    try:
        with engine.begin() as conn:
            check_sql = text("SELECT COUNT(*) FROM dbo.dim_supplier WHERE supplier_id = :sid;")
            if conn.execute(check_sql, {"sid": supplier_id}).scalar() > 0:
                return False, f"Supplier ID '{supplier_id}' already exists."

            insert_sql = text("""
                INSERT INTO dbo.dim_supplier (
                    supplier_id, supplier_name, contact_email,
                    mean_lead_time_days, lead_time_std_dev, min_order_qty, service_level_target_pct
                ) VALUES (
                    :sid, :sname, :email, :mean_lt, :std_lt, :moq, :csl
                );
            """)
            conn.execute(insert_sql, {
                "sid": supplier_id,
                "sname": supplier_name,
                "email": contact_email.strip(),
                "mean_lt": round(float(mean_lead_time_days), 1),
                "std_lt": round(float(lead_time_std_dev), 2),
                "moq": int(min_order_qty),
                "csl": round(float(service_level_target_pct), 1),
            })
            logger.info("Created supplier %s (%s)", supplier_id, supplier_name)
            invalidate_ui_cache()
            return True, f"Successfully created supplier {supplier_id} ({supplier_name})."
    except Exception as exc:
        logger.error("Failed to create supplier %s: %s", supplier_id, exc)
        return False, f"Database error: {exc}"


def update_supplier(
    supplier_id: str,
    supplier_name: str,
    contact_email: str,
    mean_lead_time_days: float,
    lead_time_std_dev: float,
    min_order_qty: int,
    service_level_target_pct: float,
) -> Tuple[bool, str]:
    """Updates supplier parameters in dim_supplier."""
    engine = get_engine()
    try:
        with engine.begin() as conn:
            update_sql = text("""
                UPDATE dbo.dim_supplier
                SET supplier_name = :sname,
                    contact_email = :email,
                    mean_lead_time_days = :mean_lt,
                    lead_time_std_dev = :std_lt,
                    min_order_qty = :moq,
                    service_level_target_pct = :csl
                WHERE supplier_id = :sid;
            """)
            res = conn.execute(update_sql, {
                "sid": supplier_id,
                "sname": supplier_name.strip(),
                "email": contact_email.strip(),
                "mean_lt": round(float(mean_lead_time_days), 1),
                "std_lt": round(float(lead_time_std_dev), 2),
                "moq": int(min_order_qty),
                "csl": round(float(service_level_target_pct), 1),
            })
            if res.rowcount == 0:
                return False, f"Supplier '{supplier_id}' not found."
            logger.info("Updated supplier %s", supplier_id)
            invalidate_ui_cache()
            return True, f"Successfully updated supplier {supplier_id}."
    except Exception as exc:
        logger.error("Failed to update supplier %s: %s", supplier_id, exc)
        return False, f"Database error: {exc}"


def delete_supplier(supplier_id: str) -> Tuple[bool, str]:
    """Deletes a supplier if no products are associated with it."""
    engine = get_engine()
    try:
        with engine.begin() as conn:
            count_sql = text("SELECT COUNT(*) FROM dbo.dim_product WHERE supplier_id = :sid;")
            linked = conn.execute(count_sql, {"sid": supplier_id}).scalar()
            if linked > 0:
                return False, f"Cannot delete supplier '{supplier_id}': {linked} products are currently linked to this supplier."

            del_sql = text("DELETE FROM dbo.dim_supplier WHERE supplier_id = :sid;")
            res = conn.execute(del_sql, {"sid": supplier_id})
            if res.rowcount == 0:
                return False, f"Supplier '{supplier_id}' not found."
            invalidate_ui_cache()
            return True, f"Successfully removed supplier {supplier_id}."
    except Exception as exc:
        return False, f"Database error: {exc}"


# ==============================================================================
# 3. Live Inventory Stock Adjustments (Physical Audit Corrections)
# ==============================================================================

def adjust_inventory_stock(
    store_id: str,
    product_id: str,
    new_on_hand_qty: int,
    reason: str = "Physical Audit Count",
) -> Tuple[bool, str]:
    """Adjusts on-hand stock in the latest inventory snapshot with proper financial valuation."""
    if new_on_hand_qty < 0:
        return False, "On-hand inventory cannot be negative."

    engine = get_engine()
    try:
        with engine.begin() as conn:
            # 1. Get latest date_key and product cost price
            latest_date = conn.execute(text("SELECT MAX(date_key) FROM dbo.fact_inventory_snapshot;")).scalar()
            if not latest_date:
                return False, "No inventory snapshots found in database."

            cost_sql = text("SELECT unit_cost_price FROM dbo.dim_product WHERE product_id = :pid;")
            cost = conn.execute(cost_sql, {"pid": product_id}).scalar()
            if cost is None:
                return False, f"Product '{product_id}' not found."

            new_value = round(float(new_on_hand_qty) * float(cost), 2)
            is_stockout = 1 if new_on_hand_qty == 0 else 0

            # 2. Update snapshot
            update_sql = text("""
                UPDATE dbo.fact_inventory_snapshot
                SET ending_on_hand_qty = :qty,
                    ending_inventory_value = :val,
                    is_stockout = :stockout,
                    batch_id = :batch,
                    ingested_at = :now
                WHERE date_key = :date_key AND store_id = :sid AND product_id = :pid;
            """)
            batch_label = f"ADJ-{reason[:10].replace(' ', '_').upper()}"
            res = conn.execute(update_sql, {
                "qty": int(new_on_hand_qty),
                "val": new_value,
                "stockout": is_stockout,
                "batch": batch_label,
                "now": datetime.now(timezone.utc),
                "date_key": latest_date,
                "sid": store_id,
                "pid": product_id,
            })

            # 3. If no row existed for this date/store/prod, insert fresh row
            if res.rowcount == 0:
                insert_sql = text("""
                    INSERT INTO dbo.fact_inventory_snapshot (
                        date_key, store_id, product_id,
                        beginning_on_hand_qty, received_qty, sold_qty,
                        ending_on_hand_qty, ending_inventory_value, is_stockout,
                        batch_id, ingested_at
                    ) VALUES (
                        :date_key, :sid, :pid,
                        :qty, 0, 0,
                        :qty, :val, :stockout,
                        :batch, :now
                    );
                """)
                conn.execute(insert_sql, {
                    "date_key": latest_date,
                    "sid": store_id,
                    "pid": product_id,
                    "qty": int(new_on_hand_qty),
                    "val": new_value,
                    "stockout": is_stockout,
                    "batch": batch_label,
                    "now": datetime.now(timezone.utc),
                })

            logger.info("Adjusted stock for %s at %s to %d units (%s)", product_id, store_id, new_on_hand_qty, reason)
            invalidate_ui_cache()
            return True, f"Successfully adjusted {product_id} at {store_id} to {new_on_hand_qty} units (${new_value:,.2f})."
    except Exception as exc:
        logger.error("Failed to adjust inventory: %s", exc)
        return False, f"Database error: {exc}"


# ==============================================================================
# 4. Bulk CSV / Excel File Importer
# ==============================================================================

def validate_and_import_file(
    file_bytes: bytes,
    filename: str,
    target_dataset: str,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Validates and imports uploaded CSV or Excel spreadsheets into SQL Server tables."""
    # 1. Parse file into DataFrame
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            return False, "Unsupported file format. Please upload a CSV (.csv) or Excel (.xlsx) file.", {}
    except Exception as exc:
        return False, f"Failed to parse file: {exc}", {}

    if df.empty:
        return False, "Uploaded file contains no rows.", {}

    # Standardize column headers
    df.columns = [c.strip().lower() for c in df.columns]

    stats = {
        "total_rows": len(df),
        "imported_rows": 0,
        "rejected_rows": 0,
        "sample_preview": df.head(5).to_dict(orient="records"),
    }

    engine = get_engine()

    # 2. Ingest based on target dataset
    if target_dataset == "Products":
        required_cols = {"product_id", "product_name", "category", "unit_cost_price", "unit_retail_price", "supplier_id"}
        missing = required_cols - set(df.columns)
        if missing:
            return False, f"Missing required columns for Products: {sorted(missing)}", stats

        success_count = 0
        for _, row in df.iterrows():
            ok, _ = create_product(
                product_id=str(row["product_id"]),
                product_name=str(row["product_name"]),
                category=str(row.get("category", "General")),
                sub_category=str(row.get("sub_category", "Standard")),
                brand=str(row.get("brand", "Generic")),
                supplier_id=str(row["supplier_id"]),
                unit_cost_price=float(row["unit_cost_price"]),
                unit_retail_price=float(row["unit_retail_price"]),
                pack_size=int(row.get("pack_size", 1)),
                shelf_life_days=int(row["shelf_life_days"]) if pd.notna(row.get("shelf_life_days")) else None,
            )
            if ok:
                success_count += 1

        stats["imported_rows"] = success_count
        stats["rejected_rows"] = len(df) - success_count
        return True, f"Successfully imported {success_count} / {len(df)} products.", stats

    elif target_dataset == "Suppliers":
        required_cols = {"supplier_id", "supplier_name", "contact_email", "mean_lead_time_days", "min_order_qty"}
        missing = required_cols - set(df.columns)
        if missing:
            return False, f"Missing required columns for Suppliers: {sorted(missing)}", stats

        success_count = 0
        for _, row in df.iterrows():
            ok, _ = create_supplier(
                supplier_id=str(row["supplier_id"]),
                supplier_name=str(row["supplier_name"]),
                contact_email=str(row["contact_email"]),
                mean_lead_time_days=float(row["mean_lead_time_days"]),
                lead_time_std_dev=float(row.get("lead_time_std_dev", 1.0)),
                min_order_qty=int(row["min_order_qty"]),
                service_level_target_pct=float(row.get("service_level_target_pct", 95.0)),
            )
            if ok:
                success_count += 1

        stats["imported_rows"] = success_count
        stats["rejected_rows"] = len(df) - success_count
        return True, f"Successfully imported {success_count} / {len(df)} suppliers.", stats

    elif target_dataset == "Inventory Count Audit":
        required_cols = {"store_id", "product_id", "ending_on_hand_qty"}
        missing = required_cols - set(df.columns)
        if missing:
            return False, f"Missing required columns for Inventory Count: {sorted(missing)}", stats

        success_count = 0
        for _, row in df.iterrows():
            ok, _ = adjust_inventory_stock(
                store_id=str(row["store_id"]),
                product_id=str(row["product_id"]),
                new_on_hand_qty=int(row["ending_on_hand_qty"]),
                reason=f"Bulk File Upload ({filename[:15]})",
            )
            if ok:
                success_count += 1

        stats["imported_rows"] = success_count
        stats["rejected_rows"] = len(df) - success_count
        return True, f"Successfully applied {success_count} / {len(df)} stock count updates.", stats

    return False, f"Unsupported dataset type: {target_dataset}", stats
