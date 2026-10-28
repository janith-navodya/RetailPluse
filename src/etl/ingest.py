"""Enterprise ETL ingestion and dead-letter quarantine pipeline targeting Microsoft SQL Server."""
import os
import sys
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone, date
from typing import Dict, Any, List, Tuple, Set, Optional
import pandas as pd
import pyodbc
from pydantic import ValidationError

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import settings
from config.logging_config import logger
from src.data_engine.schema import (
    DimDateSchema,
    DimStoreSchema,
    DimSupplierSchema,
    DimProductSchema,
    FactSalesDailySchema,
    FactInventorySnapshotSchema,
    FactPurchaseOrderSchema,
)

SCHEMA_REGISTRY = {
    "dim_date": DimDateSchema,
    "dim_store": DimStoreSchema,
    "dim_supplier": DimSupplierSchema,
    "dim_product": DimProductSchema,
    "fact_sales_daily": FactSalesDailySchema,
    "fact_inventory_snapshot": FactInventorySnapshotSchema,
    "fact_purchase_orders": FactPurchaseOrderSchema,
}


class SQLServerIngestionPipeline:
    """Ingests raw CSV feeds into Microsoft SQL Server Star Schema with dead-letter quarantine."""

    def __init__(self, db_name: str = settings.DB_NAME):
        self.db_name = db_name
        self.conn_str = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            "SERVER=localhost;"
            f"DATABASE={self.db_name};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )
        self.known_stores: Set[str] = set()
        self.known_products: Set[str] = set()
        self.known_suppliers: Set[str] = set()
        self.known_dates: Set[int] = set()

    def get_connection(self) -> pyodbc.Connection:
        """Returns active pyodbc connection with autocommit disabled."""
        conn = pyodbc.connect(self.conn_str, autocommit=False)
        return conn

    def run_ingestion(
        self,
        raw_dir: Path = settings.RAW_DATA_DIR,
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Orchestrates end-to-end extraction, Pydantic validation, quarantine, and T-SQL upsert."""
        if batch_id is None:
            batch_id = f"BATCH-{uuid.uuid4().hex[:12].upper()}"

        start_time = datetime.now(timezone.utc)
        logger.info("================================================================================")
        logger.info("STARTING SQL SERVER ETL PIPELINE: Batch ID %s | Database: %s", batch_id, self.db_name)
        logger.info("================================================================================")

        self._log_batch_start(batch_id, "sql_server_retail_etl", start_time)

        total_processed = 0
        total_loaded = 0
        total_quarantined = 0

        try:
            # 1. Ingest Dimensions
            p_date, l_date, q_date = self._ingest_dim_date(raw_dir / "dim_date.csv", batch_id)
            p_store, l_store, q_store = self._ingest_dim_store(raw_dir / "dim_store.csv", batch_id)
            p_sup, l_sup, q_sup = self._ingest_dim_supplier(raw_dir / "dim_supplier.csv", batch_id)
            p_prod, l_prod, q_prod = self._ingest_dim_product(raw_dir / "dim_product.csv", batch_id)

            # Refresh loaded dimension key sets for referential validation
            self._load_reference_dimensions()

            # 2. Ingest Fact Tables
            p_sales, l_sales, q_sales = self._ingest_fact_sales(raw_dir / "raw_sales_daily.csv", batch_id)
            p_inv, l_inv, q_inv = self._ingest_fact_inventory(raw_dir / "raw_inventory_snapshot.csv", batch_id)
            p_pos, l_pos, q_pos = self._ingest_fact_pos(raw_dir / "raw_purchase_orders.csv", batch_id)

            total_processed = p_date + p_store + p_sup + p_prod + p_sales + p_inv + p_pos
            total_loaded = l_date + l_store + l_sup + l_prod + l_sales + l_inv + l_pos
            total_quarantined = q_date + q_store + q_sup + q_prod + q_sales + q_inv + q_pos

            # Complete batch log
            end_time = datetime.now(timezone.utc)
            self._log_batch_completion(
                batch_id=batch_id,
                status="COMPLETED",
                processed=total_processed,
                loaded=total_loaded,
                quarantined=total_quarantined,
                end_time=end_time,
            )

            logger.info("================================================================================")
            logger.info("ETL PIPELINE COMPLETED: Processed=%d, Loaded=%d, Quarantined=%d", total_processed, total_loaded, total_quarantined)
            logger.info("================================================================================")

            return {
                "batch_id": batch_id,
                "status": "COMPLETED",
                "processed": total_processed,
                "loaded": total_loaded,
                "quarantined": total_quarantined,
            }

        except Exception as exc:
            logger.error("ETL pipeline fatal error in batch %s: %s", batch_id, exc, exc_info=True)
            self._log_batch_completion(
                batch_id=batch_id,
                status="FAILED",
                processed=total_processed,
                loaded=total_loaded,
                quarantined=total_quarantined,
                end_time=datetime.now(timezone.utc),
            )
            raise

    # -------------------------------------------------------------------------
    # Dimension Ingestion Handlers
    # -------------------------------------------------------------------------
    def _ingest_dim_date(self, csv_path: Path, batch_id: str) -> Tuple[int, int, int]:
        df = pd.read_csv(csv_path)
        valid, quarantined = self._validate_records("dim_date", df.to_dict(orient="records"), batch_id)
        self._upsert_dim_date(valid)
        self._insert_quarantine(quarantined)
        return len(df), len(valid), len(quarantined)

    def _ingest_dim_store(self, csv_path: Path, batch_id: str) -> Tuple[int, int, int]:
        df = pd.read_csv(csv_path)
        valid, quarantined = self._validate_records("dim_store", df.to_dict(orient="records"), batch_id)
        self._upsert_dim_store(valid)
        self._insert_quarantine(quarantined)
        return len(df), len(valid), len(quarantined)

    def _ingest_dim_supplier(self, csv_path: Path, batch_id: str) -> Tuple[int, int, int]:
        df = pd.read_csv(csv_path)
        valid, quarantined = self._validate_records("dim_supplier", df.to_dict(orient="records"), batch_id)
        self._upsert_dim_supplier(valid)
        self._insert_quarantine(quarantined)
        return len(df), len(valid), len(quarantined)

    def _ingest_dim_product(self, csv_path: Path, batch_id: str) -> Tuple[int, int, int]:
        df = pd.read_csv(csv_path)
        valid, quarantined = self._validate_records("dim_product", df.to_dict(orient="records"), batch_id)
        self._upsert_dim_product(valid)
        self._insert_quarantine(quarantined)
        return len(df), len(valid), len(quarantined)

    # -------------------------------------------------------------------------
    # Fact Ingestion Handlers
    # -------------------------------------------------------------------------
    def _ingest_fact_sales(self, csv_path: Path, batch_id: str) -> Tuple[int, int, int]:
        df = pd.read_csv(csv_path)
        records = df.to_dict(orient="records")
        valid, quarantined = self._validate_records("fact_sales_daily", records, batch_id)
        self._upsert_fact_sales(valid)
        self._insert_quarantine(quarantined)
        return len(records), len(valid), len(quarantined)

    def _ingest_fact_inventory(self, csv_path: Path, batch_id: str) -> Tuple[int, int, int]:
        df = pd.read_csv(csv_path)
        records = df.to_dict(orient="records")
        valid, quarantined = self._validate_records("fact_inventory_snapshot", records, batch_id)
        self._upsert_fact_inventory(valid)
        self._insert_quarantine(quarantined)
        return len(records), len(valid), len(quarantined)

    def _ingest_fact_pos(self, csv_path: Path, batch_id: str) -> Tuple[int, int, int]:
        df = pd.read_csv(csv_path)
        # Handle NaN delivery dates in CSV
        df["actual_delivery_date_key"] = df["actual_delivery_date_key"].apply(lambda v: None if pd.isna(v) else int(v))
        records = df.to_dict(orient="records")
        valid, quarantined = self._validate_records("fact_purchase_orders", records, batch_id)
        self._upsert_fact_pos(valid)
        self._insert_quarantine(quarantined)
        return len(records), len(valid), len(quarantined)

    # -------------------------------------------------------------------------
    # Two-Stage Validation Engine (Referential Integrity + Pydantic Domain V2)
    # -------------------------------------------------------------------------
    def _validate_records(
        self,
        source_feed: str,
        records: List[Dict[str, Any]],
        batch_id: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        schema_cls = SCHEMA_REGISTRY[source_feed]
        valid_records = []
        quarantined_records = []
        now_utc = datetime.now(timezone.utc)

        for rec in records:
            # Clean NaN / null values from CSV pandas parsing
            rec_copy = {k: (None if pd.isna(v) else v) for k, v in rec.items()}

            # 1. Referential integrity pre-checks (for fact tables)
            orphan_err = self._check_orphan_foreign_keys(source_feed, rec_copy)
            if orphan_err:
                quarantined_records.append(
                    {
                        "source_feed": source_feed,
                        "raw_payload_json": json.dumps(rec_copy, default=str),
                        "violation_category": "ORPHAN_KEY",
                        "violation_details": orphan_err,
                        "rejected_at": now_utc,
                        "batch_id": batch_id,
                    }
                )
                continue

            # 2. Pydantic schema validation
            try:
                # Ensure date format conversion if passed as string
                if "full_date" in rec_copy and isinstance(rec_copy["full_date"], str):
                    rec_copy["full_date"] = date.fromisoformat(rec_copy["full_date"])
                if "ingested_at" in rec_copy and isinstance(rec_copy["ingested_at"], str):
                    rec_copy["ingested_at"] = datetime.fromisoformat(rec_copy["ingested_at"])
                if "shelf_life_days" in rec_copy and rec_copy["shelf_life_days"] is not None:
                    rec_copy["shelf_life_days"] = int(rec_copy["shelf_life_days"])
                if "actual_delivery_date_key" in rec_copy and rec_copy["actual_delivery_date_key"] is not None:
                    rec_copy["actual_delivery_date_key"] = int(rec_copy["actual_delivery_date_key"])

                val_obj = schema_cls(**rec_copy)
                valid_records.append(val_obj.model_dump())
            except ValidationError as ve:
                err_details = "; ".join([f"{e['loc']}: {e['msg']}" for e in ve.errors()])
                quarantined_records.append(
                    {
                        "source_feed": source_feed,
                        "raw_payload_json": json.dumps(rec, default=str),
                        "violation_category": "SCHEMA_ERROR",
                        "violation_details": err_details,
                        "rejected_at": now_utc,
                        "batch_id": batch_id,
                    }
                )
            except Exception as ex:
                quarantined_records.append(
                    {
                        "source_feed": source_feed,
                        "raw_payload_json": json.dumps(rec, default=str),
                        "violation_category": "DOMAIN_VIOLATION",
                        "violation_details": str(ex),
                        "rejected_at": now_utc,
                        "batch_id": batch_id,
                    }
                )

        logger.info(
            "Feed '%s': Validated %d records (%d valid, %d quarantined)",
            source_feed,
            len(records),
            len(valid_records),
            len(quarantined_records),
        )
        return valid_records, quarantined_records

    def _check_orphan_foreign_keys(self, source_feed: str, rec: Dict[str, Any]) -> Optional[str]:
        if not (self.known_stores or self.known_products or self.known_dates):
            return None  # Dimensions not loaded yet

        if "store_id" in rec and self.known_stores:
            if str(rec["store_id"]) not in self.known_stores:
                return f"Orphaned store_id: '{rec['store_id']}' not in dbo.dim_store"

        if "product_id" in rec and self.known_products:
            if str(rec["product_id"]) not in self.known_products:
                return f"Orphaned product_id: '{rec['product_id']}' not in dbo.dim_product"

        if "supplier_id" in rec and self.known_suppliers:
            if str(rec["supplier_id"]) not in self.known_suppliers:
                return f"Orphaned supplier_id: '{rec['supplier_id']}' not in dbo.dim_supplier"

        if "date_key" in rec and self.known_dates:
            try:
                dk = int(rec["date_key"])
                if dk not in self.known_dates:
                    return f"Orphaned date_key: '{dk}' not in dbo.dim_date"
            except (ValueError, TypeError):
                return f"Malformed date_key: '{rec['date_key']}'"

        return None

    def _load_reference_dimensions(self):
        """Loads dimension key sets from SQL Server for referential integrity checks."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT store_id FROM dbo.dim_store")
        self.known_stores = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT product_id FROM dbo.dim_product")
        self.known_products = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT supplier_id FROM dbo.dim_supplier")
        self.known_suppliers = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT date_key FROM dbo.dim_date")
        self.known_dates = {row[0] for row in cursor.fetchall()}
        conn.close()

    # -------------------------------------------------------------------------
    # T-SQL Idempotent Upsert Implementations (MERGE / IF NOT EXISTS)
    # -------------------------------------------------------------------------
    def _upsert_dim_date(self, records: List[Dict[str, Any]]):
        if not records:
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.fast_executemany = True

        sql = """
            MERGE dbo.dim_date AS target
            USING (SELECT ? AS date_key, ? AS full_date, ? AS day_of_week, ? AS day_name, 
                          ? AS day_of_month, ? AS month_num, ? AS month_name, ? AS quarter, 
                          ? AS year, ? AS is_weekend, ? AS is_holiday) AS source
            ON (target.date_key = source.date_key)
            WHEN NOT MATCHED THEN
                INSERT (date_key, full_date, day_of_week, day_name, day_of_month, month_num, month_name, quarter, year, is_weekend, is_holiday)
                VALUES (source.date_key, source.full_date, source.day_of_week, source.day_name, source.day_of_month, source.month_num, source.month_name, source.quarter, source.year, source.is_weekend, source.is_holiday);
        """
        params = [
            (
                r["date_key"], str(r["full_date"]), r["day_of_week"], r["day_name"],
                r["day_of_month"], r["month_num"], r["month_name"], r["quarter"],
                r["year"], r["is_weekend"], r["is_holiday"]
            )
            for r in records
        ]
        cursor.executemany(sql, params)
        conn.commit()
        conn.close()

    def _upsert_dim_store(self, records: List[Dict[str, Any]]):
        if not records:
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.fast_executemany = True

        sql = """
            MERGE dbo.dim_store AS target
            USING (SELECT ? AS store_id, ? AS store_name, ? AS store_format, ? AS city, 
                          ? AS state, ? AS square_footage, ? AS storage_capacity_units) AS source
            ON (target.store_id = source.store_id)
            WHEN MATCHED THEN
                UPDATE SET target.store_name = source.store_name, target.store_format = source.store_format,
                           target.city = source.city, target.state = source.state,
                           target.square_footage = source.square_footage, target.storage_capacity_units = source.storage_capacity_units
            WHEN NOT MATCHED THEN
                INSERT (store_id, store_name, store_format, city, state, square_footage, storage_capacity_units)
                VALUES (source.store_id, source.store_name, source.store_format, source.city, source.state, source.square_footage, source.storage_capacity_units);
        """
        params = [
            (
                r["store_id"], r["store_name"], r["store_format"], r["city"],
                r["state"], r["square_footage"], r["storage_capacity_units"]
            )
            for r in records
        ]
        cursor.executemany(sql, params)
        conn.commit()
        conn.close()

    def _upsert_dim_supplier(self, records: List[Dict[str, Any]]):
        if not records:
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.fast_executemany = True

        sql = """
            MERGE dbo.dim_supplier AS target
            USING (SELECT ? AS supplier_id, ? AS supplier_name, ? AS contact_email, 
                          ? AS mean_lead_time_days, ? AS lead_time_std_dev, ? AS min_order_qty, 
                          ? AS service_level_target_pct) AS source
            ON (target.supplier_id = source.supplier_id)
            WHEN MATCHED THEN
                UPDATE SET target.supplier_name = source.supplier_name, target.contact_email = source.contact_email,
                           target.mean_lead_time_days = source.mean_lead_time_days, target.lead_time_std_dev = source.lead_time_std_dev,
                           target.min_order_qty = source.min_order_qty, target.service_level_target_pct = source.service_level_target_pct
            WHEN NOT MATCHED THEN
                INSERT (supplier_id, supplier_name, contact_email, mean_lead_time_days, lead_time_std_dev, min_order_qty, service_level_target_pct)
                VALUES (source.supplier_id, source.supplier_name, source.contact_email, source.mean_lead_time_days, source.lead_time_std_dev, source.min_order_qty, source.service_level_target_pct);
        """
        params = [
            (
                r["supplier_id"], r["supplier_name"], r["contact_email"],
                r["mean_lead_time_days"], r["lead_time_std_dev"], r["min_order_qty"],
                r["service_level_target_pct"]
            )
            for r in records
        ]
        cursor.executemany(sql, params)
        conn.commit()
        conn.close()

    def _upsert_dim_product(self, records: List[Dict[str, Any]]):
        if not records:
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.fast_executemany = True

        sql = """
            MERGE dbo.dim_product AS target
            USING (SELECT ? AS product_id, ? AS product_name, ? AS category, ? AS sub_category, 
                          ? AS brand, ? AS supplier_id, ? AS unit_cost_price, ? AS unit_retail_price, 
                          ? AS pack_size, ? AS shelf_life_days) AS source
            ON (target.product_id = source.product_id)
            WHEN MATCHED THEN
                UPDATE SET target.product_name = source.product_name, target.category = source.category,
                           target.sub_category = source.sub_category, target.brand = source.brand,
                           target.supplier_id = source.supplier_id, target.unit_cost_price = source.unit_cost_price,
                           target.unit_retail_price = source.unit_retail_price, target.pack_size = source.pack_size,
                           target.shelf_life_days = source.shelf_life_days
            WHEN NOT MATCHED THEN
                INSERT (product_id, product_name, category, sub_category, brand, supplier_id, unit_cost_price, unit_retail_price, pack_size, shelf_life_days)
                VALUES (source.product_id, source.product_name, source.category, source.sub_category, source.brand, source.supplier_id, source.unit_cost_price, source.unit_retail_price, source.pack_size, source.shelf_life_days);
        """
        params = [
            (
                r["product_id"], r["product_name"], r["category"], r["sub_category"],
                r["brand"], r["supplier_id"], r["unit_cost_price"], r["unit_retail_price"],
                r["pack_size"], r["shelf_life_days"]
            )
            for r in records
        ]
        cursor.executemany(sql, params)
        conn.commit()
        conn.close()

    def _upsert_fact_sales(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        logger.info("Executing idempotent bulk MERGE into dbo.fact_sales_daily (%d records)...", len(records))
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.fast_executemany = True

        # Process in batches of 10,000 for optimal memory and network throughput
        batch_size = 10000
        sql = """
            MERGE dbo.fact_sales_daily AS target
            USING (SELECT ? AS date_key, ? AS store_id, ? AS product_id, ? AS quantity_sold, 
                          ? AS gross_sales_amount, ? AS discount_amount, ? AS net_sales_amount, 
                          ? AS cogs_amount, ? AS gross_profit_amount, ? AS is_promotional, 
                          ? AS batch_id, ? AS ingested_at) AS source
            ON (target.date_key = source.date_key AND target.store_id = source.store_id AND target.product_id = source.product_id)
            WHEN MATCHED THEN
                UPDATE SET target.quantity_sold = source.quantity_sold,
                           target.gross_sales_amount = source.gross_sales_amount,
                           target.discount_amount = source.discount_amount,
                           target.net_sales_amount = source.net_sales_amount,
                           target.cogs_amount = source.cogs_amount,
                           target.gross_profit_amount = source.gross_profit_amount,
                           target.is_promotional = source.is_promotional,
                           target.batch_id = source.batch_id,
                           target.ingested_at = source.ingested_at
            WHEN NOT MATCHED THEN
                INSERT (date_key, store_id, product_id, quantity_sold, gross_sales_amount, discount_amount, net_sales_amount, cogs_amount, gross_profit_amount, is_promotional, batch_id, ingested_at)
                VALUES (source.date_key, source.store_id, source.product_id, source.quantity_sold, source.gross_sales_amount, source.discount_amount, source.net_sales_amount, source.cogs_amount, source.gross_profit_amount, source.is_promotional, source.batch_id, source.ingested_at);
        """
        for i in range(0, len(records), batch_size):
            chunk = records[i : i + batch_size]
            params = [
                (
                    r["date_key"], r["store_id"], r["product_id"], r["quantity_sold"],
                    r["gross_sales_amount"], r["discount_amount"], r["net_sales_amount"],
                    r["cogs_amount"], r["gross_profit_amount"], r["is_promotional"],
                    r["batch_id"], str(r["ingested_at"])[:19]
                )
                for r in chunk
            ]
            cursor.executemany(sql, params)
            conn.commit()

        conn.close()
        logger.info("dbo.fact_sales_daily: Successfully merged %d records", len(records))
        return len(records)

    def _upsert_fact_inventory(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        logger.info("Executing idempotent bulk MERGE into dbo.fact_inventory_snapshot (%d records)...", len(records))
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.fast_executemany = True

        batch_size = 10000
        sql = """
            MERGE dbo.fact_inventory_snapshot AS target
            USING (SELECT ? AS date_key, ? AS store_id, ? AS product_id, ? AS beginning_on_hand_qty, 
                          ? AS received_qty, ? AS sold_qty, ? AS ending_on_hand_qty, 
                          ? AS ending_inventory_value, ? AS is_stockout, ? AS batch_id, ? AS ingested_at) AS source
            ON (target.date_key = source.date_key AND target.store_id = source.store_id AND target.product_id = source.product_id)
            WHEN MATCHED THEN
                UPDATE SET target.beginning_on_hand_qty = source.beginning_on_hand_qty,
                           target.received_qty = source.received_qty,
                           target.sold_qty = source.sold_qty,
                           target.ending_on_hand_qty = source.ending_on_hand_qty,
                           target.ending_inventory_value = source.ending_inventory_value,
                           target.is_stockout = source.is_stockout,
                           target.batch_id = source.batch_id,
                           target.ingested_at = source.ingested_at
            WHEN NOT MATCHED THEN
                INSERT (date_key, store_id, product_id, beginning_on_hand_qty, received_qty, sold_qty, ending_on_hand_qty, ending_inventory_value, is_stockout, batch_id, ingested_at)
                VALUES (source.date_key, source.store_id, source.product_id, source.beginning_on_hand_qty, source.received_qty, source.sold_qty, source.ending_on_hand_qty, source.ending_inventory_value, source.is_stockout, source.batch_id, source.ingested_at);
        """
        for i in range(0, len(records), batch_size):
            chunk = records[i : i + batch_size]
            params = [
                (
                    r["date_key"], r["store_id"], r["product_id"], r["beginning_on_hand_qty"],
                    r["received_qty"], r["sold_qty"], r["ending_on_hand_qty"],
                    r["ending_inventory_value"], r["is_stockout"], r["batch_id"], str(r["ingested_at"])[:19]
                )
                for r in chunk
            ]
            cursor.executemany(sql, params)
            conn.commit()

        conn.close()
        logger.info("dbo.fact_inventory_snapshot: Successfully merged %d records", len(records))
        return len(records)

    def _upsert_fact_pos(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.fast_executemany = True

        sql = """
            MERGE dbo.fact_purchase_orders AS target
            USING (SELECT ? AS po_id, ? AS order_date_key, ? AS expected_delivery_date_key, 
                          ? AS actual_delivery_date_key, ? AS store_id, ? AS product_id, 
                          ? AS supplier_id, ? AS order_qty, ? AS received_qty, 
                          ? AS unit_cost_price, ? AS total_cost_amount, ? AS status, 
                          ? AS batch_id, ? AS ingested_at) AS source
            ON (target.po_id = source.po_id)
            WHEN MATCHED THEN
                UPDATE SET target.order_date_key = source.order_date_key,
                           target.expected_delivery_date_key = source.expected_delivery_date_key,
                           target.actual_delivery_date_key = source.actual_delivery_date_key,
                           target.store_id = source.store_id, target.product_id = source.product_id,
                           target.supplier_id = source.supplier_id, target.order_qty = source.order_qty,
                           target.received_qty = source.received_qty, target.unit_cost_price = source.unit_cost_price,
                           target.total_cost_amount = source.total_cost_amount, target.status = source.status,
                           target.batch_id = source.batch_id, target.ingested_at = source.ingested_at
            WHEN NOT MATCHED THEN
                INSERT (po_id, order_date_key, expected_delivery_date_key, actual_delivery_date_key, store_id, product_id, supplier_id, order_qty, received_qty, unit_cost_price, total_cost_amount, status, batch_id, ingested_at)
                VALUES (source.po_id, source.order_date_key, source.expected_delivery_date_key, source.actual_delivery_date_key, source.store_id, source.product_id, source.supplier_id, source.order_qty, source.received_qty, source.unit_cost_price, source.total_cost_amount, source.status, source.batch_id, source.ingested_at);
        """
        params = [
            (
                r["po_id"], r["order_date_key"], r["expected_delivery_date_key"],
                r["actual_delivery_date_key"], r["store_id"], r["product_id"],
                r["supplier_id"], r["order_qty"], r["received_qty"],
                r["unit_cost_price"], r["total_cost_amount"], r["status"],
                r["batch_id"], str(r["ingested_at"])[:19]
            )
            for r in records
        ]
        cursor.executemany(sql, params)
        conn.commit()
        conn.close()
        logger.info("dbo.fact_purchase_orders: Successfully merged %d records", len(records))
        return len(records)

    def _insert_quarantine(self, quarantined_records: List[Dict[str, Any]]):
        if not quarantined_records:
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.fast_executemany = True

        sql = """
            INSERT INTO dbo.quarantine_records (
                source_feed, raw_payload_json, violation_category, violation_details, rejected_at, batch_id
            ) VALUES (?, ?, ?, ?, ?, ?);
        """
        params = [
            (
                q["source_feed"], q["raw_payload_json"], q["violation_category"],
                q["violation_details"], str(q["rejected_at"])[:19], q["batch_id"]
            )
            for q in quarantined_records
        ]
        cursor.executemany(sql, params)
        conn.commit()
        conn.close()
        logger.warning("Quarantine: Isolated %d invalid records into dbo.quarantine_records", len(quarantined_records))

    def _log_batch_start(self, batch_id: str, pipeline_name: str, start_time: datetime):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO dbo.etl_batch_log (
                batch_id, pipeline_name, status, records_processed, records_loaded, records_quarantined, started_at
            ) VALUES (?, ?, 'STARTED', 0, 0, 0, ?);
            """,
            (batch_id, pipeline_name, start_time.strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        conn.close()

    def _log_batch_completion(
        self,
        batch_id: str,
        status: str,
        processed: int,
        loaded: int,
        quarantined: int,
        end_time: datetime,
    ):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE dbo.etl_batch_log
            SET status = ?, records_processed = ?, records_loaded = ?, records_quarantined = ?, completed_at = ?
            WHERE batch_id = ?;
            """,
            (status, processed, loaded, quarantined, end_time.strftime("%Y-%m-%d %H:%M:%S"), batch_id),
        )
        conn.commit()
        conn.close()

    def _get_total_loaded_count(self) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        counts = []
        for tbl in ["dim_date", "dim_store", "dim_supplier", "dim_product", "fact_sales_daily", "fact_inventory_snapshot", "fact_purchase_orders"]:
            cursor.execute(f"SELECT COUNT(*) FROM dbo.{tbl};")
            counts.append(cursor.fetchone()[0])
        conn.close()
        return sum(counts)


if __name__ == "__main__":
    pipeline = SQLServerIngestionPipeline()
    pipeline.run_ingestion()
