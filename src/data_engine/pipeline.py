"""End-to-end ingestion and quarantine pipeline with idempotent upserts."""
import uuid
import json
import sqlite3
from datetime import datetime, timezone, date
from typing import Dict, Any, List, Optional
import pandas as pd

from config.settings import settings
from config.logging_config import logger
from src.data_engine.database import db_manager
from src.data_engine.validator import DataValidator
from src.data_engine.generator import RetailDataGenerator


class IngestionPipeline:
    """Orchestrates data validation, quarantine routing, and idempotent loading."""

    def __init__(self, db_path: str = str(settings.DB_PATH)):
        self.db_path = db_path
        self.validator = DataValidator()

    def run_full_pipeline(
        self,
        batch_id: Optional[str] = None,
        inject_corruptions: bool = settings.INJECT_CORRUPTIONS,
    ) -> Dict[str, Any]:
        """Executes full end-to-end ingestion cycle."""
        if batch_id is None:
            batch_id = f"BATCH-{uuid.uuid4().hex[:12].upper()}"

        start_time = datetime.now(timezone.utc)
        logger.info("================================================================================")
        logger.info("STARTING INGESTION PIPELINE: Batch ID %s", batch_id)
        logger.info("================================================================================")

        # 1. Ensure tables exist
        db_manager.run_migrations()

        # 2. Record batch start in etl_batch_log
        self._log_batch_start(batch_id, "full_retail_ingestion", start_time)

        total_processed = 0
        total_loaded = 0
        total_quarantined = 0

        try:
            # 3. Generate synthetic retail dataset
            generator = RetailDataGenerator()
            dates, stores, suppliers, products = generator.generate_dimensions()

            # 4. Ingest Dimension Tables (Must precede facts)
            # A. Dim Date
            v_dates, q_dates = self.validator.validate_records("dim_date", dates, batch_id)
            self._upsert_records("dim_date", v_dates, ["date_key"])
            self._insert_quarantine(q_dates)

            # B. Dim Store
            v_stores, q_stores = self.validator.validate_records("dim_store", stores, batch_id)
            self._upsert_records("dim_store", v_stores, ["store_id"])
            self._insert_quarantine(q_stores)

            # C. Dim Supplier
            v_suppliers, q_suppliers = self.validator.validate_records("dim_supplier", suppliers, batch_id)
            self._upsert_records("dim_supplier", v_suppliers, ["supplier_id"])
            self._insert_quarantine(q_suppliers)

            # D. Dim Product
            v_products, q_products = self.validator.validate_records("dim_product", products, batch_id)
            self._upsert_records("dim_product", v_products, ["product_id"])
            self._insert_quarantine(q_products)

            # Register reference dimensions for foreign-key checking
            self.validator.set_reference_dimensions(
                store_ids={s["store_id"] for s in v_stores},
                product_ids={p["product_id"] for p in v_products},
                supplier_ids={s["supplier_id"] for s in v_suppliers},
                date_keys={d["date_key"] for d in v_dates},
            )

            # 5. Generate and Ingest Fact Tables
            sales, inventory, pos = generator.generate_facts(
                dates=v_dates,
                stores=v_stores,
                suppliers=v_suppliers,
                products=v_products,
                batch_id=batch_id,
                inject_corruptions=inject_corruptions,
            )

            # A. Fact Sales Daily
            v_sales, q_sales = self.validator.validate_records("fact_sales_daily", sales, batch_id)
            self._upsert_records("fact_sales_daily", v_sales, ["date_key", "store_id", "product_id"])
            self._insert_quarantine(q_sales)

            # B. Fact Inventory Snapshot
            v_inv, q_inv = self.validator.validate_records("fact_inventory_snapshot", inventory, batch_id)
            self._upsert_records("fact_inventory_snapshot", v_inv, ["date_key", "store_id", "product_id"])
            self._insert_quarantine(q_inv)

            # C. Fact Purchase Orders
            v_pos, q_pos = self.validator.validate_records("fact_purchase_orders", pos, batch_id)
            self._upsert_records("fact_purchase_orders", v_pos, ["po_id"])
            self._insert_quarantine(q_pos)

            # Calculate totals
            total_processed = (
                len(dates) + len(stores) + len(suppliers) + len(products)
                + len(sales) + len(inventory) + len(pos)
            )
            total_loaded = (
                len(v_dates) + len(v_stores) + len(v_suppliers) + len(v_products)
                + len(v_sales) + len(v_inv) + len(v_pos)
            )
            total_quarantined = (
                len(q_dates) + len(q_stores) + len(q_suppliers) + len(q_products)
                + len(q_sales) + len(q_inv) + len(q_pos)
            )

            # 6. Complete Batch Log
            end_time = datetime.now(timezone.utc)
            self._log_batch_completion(
                batch_id=batch_id,
                status="COMPLETED",
                processed=total_processed,
                loaded=total_loaded,
                quarantined=total_quarantined,
                end_time=end_time,
            )

            # 7. Export clean processed parquet/csv partitions for BI/Streamlit
            self._export_processed_files(v_dates, v_stores, v_suppliers, v_products, v_sales, v_inv, v_pos)

            logger.info("================================================================================")
            logger.info("PIPELINE COMPLETED: Processed=%d, Loaded=%d, Quarantined=%d", total_processed, total_loaded, total_quarantined)
            logger.info("================================================================================")

            return {
                "batch_id": batch_id,
                "status": "COMPLETED",
                "processed": total_processed,
                "loaded": total_loaded,
                "quarantined": total_quarantined,
            }

        except Exception as exc:
            logger.error("Pipeline failure in batch %s: %s", batch_id, exc, exc_info=True)
            self._log_batch_completion(
                batch_id=batch_id,
                status="FAILED",
                processed=total_processed,
                loaded=total_loaded,
                quarantined=total_quarantined,
                end_time=datetime.now(timezone.utc),
            )
            raise

    def _upsert_records(self, table_name: str, records: List[Dict[str, Any]], key_columns: List[str]):
        """Idempotently inserts or updates records using composite primary keys."""
        if not records:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Extract column list
        columns = list(records[0].keys())
        col_names = ", ".join(columns)
        placeholders = ", ".join([f":{col}" for col in columns])

        # SQLite idempotent upsert syntax: INSERT OR REPLACE
        sql = f"INSERT OR REPLACE INTO {table_name} ({col_names}) VALUES ({placeholders})"

        # Convert date/datetime objects to ISO strings for SQLite storage
        clean_records = []
        for r in records:
            cr = {}
            for k, v in r.items():
                if isinstance(v, (datetime, date)):
                    cr[k] = v.isoformat()
                else:
                    cr[k] = v
            clean_records.append(cr)

        cursor.executemany(sql, clean_records)
        conn.commit()
        conn.close()
        logger.info("Table '%s': Committed %d records idempotently", table_name, len(records))

    def _insert_quarantine(self, quarantined_records: List[Dict[str, Any]]):
        """Persists rejected records to quarantine_invalid_records dead-letter table."""
        if not quarantined_records:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        sql = """
            INSERT INTO quarantine_invalid_records (
                source_feed, raw_payload_json, violation_category, violation_details, rejected_at, batch_id
            ) VALUES (:source_feed, :raw_payload_json, :violation_category, :violation_details, :rejected_at, :batch_id)
        """
        clean_records = []
        for r in quarantined_records:
            cr = dict(r)
            if isinstance(cr["rejected_at"], datetime):
                cr["rejected_at"] = cr["rejected_at"].isoformat()
            clean_records.append(cr)

        cursor.executemany(sql, clean_records)
        conn.commit()
        conn.close()
        logger.warning("Quarantine: Isolated %d invalid records", len(quarantined_records))

    def _log_batch_start(self, batch_id: str, pipeline_name: str, start_time: datetime):
        """Initializes batch execution log record."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO etl_batch_log (
                batch_id, pipeline_name, status, records_processed, records_loaded, records_quarantined, started_at
            ) VALUES (?, ?, 'STARTED', 0, 0, 0, ?)
            """,
            (batch_id, pipeline_name, start_time.isoformat()),
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
        """Updates batch execution log upon completion."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE etl_batch_log
            SET status = ?, records_processed = ?, records_loaded = ?, records_quarantined = ?, completed_at = ?
            WHERE batch_id = ?
            """,
            (status, processed, loaded, quarantined, end_time.isoformat(), batch_id),
        )
        conn.commit()
        conn.close()

    def _export_processed_files(
        self,
        dates: List[Dict],
        stores: List[Dict],
        suppliers: List[Dict],
        products: List[Dict],
        sales: List[Dict],
        inventory: List[Dict],
        pos: List[Dict],
    ):
        """Exports parquet partitions to data/processed for Power BI and downstream models."""
        try:
            pd.DataFrame(dates).to_parquet(settings.PROCESSED_DATA_DIR / "dim_date.parquet", index=False)
            pd.DataFrame(stores).to_parquet(settings.PROCESSED_DATA_DIR / "dim_store.parquet", index=False)
            pd.DataFrame(suppliers).to_parquet(settings.PROCESSED_DATA_DIR / "dim_supplier.parquet", index=False)
            pd.DataFrame(products).to_parquet(settings.PROCESSED_DATA_DIR / "dim_product.parquet", index=False)
            pd.DataFrame(sales).to_parquet(settings.PROCESSED_DATA_DIR / "fact_sales_daily.parquet", index=False)
            pd.DataFrame(inventory).to_parquet(settings.PROCESSED_DATA_DIR / "fact_inventory_snapshot.parquet", index=False)
            pd.DataFrame(pos).to_parquet(settings.PROCESSED_DATA_DIR / "fact_purchase_orders.parquet", index=False)
            logger.info("Exported processed tables to Parquet at: %s", settings.PROCESSED_DATA_DIR)
        except Exception as ex:
            logger.warning("Parquet export skipped or encountered notice: %s", ex)


if __name__ == "__main__":
    pipeline = IngestionPipeline()
    pipeline.run_full_pipeline()
