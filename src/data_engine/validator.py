"""Data validator with Pydantic V2 schema validation and quarantine routing."""
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Set, Optional
import pandas as pd
from pydantic import ValidationError

from src.data_engine.schema import (
    DimDateSchema,
    DimStoreSchema,
    DimSupplierSchema,
    DimProductSchema,
    FactSalesDailySchema,
    FactInventorySnapshotSchema,
    FactPurchaseOrderSchema,
)
from config.logging_config import logger


SCHEMA_REGISTRY = {
    "dim_date": DimDateSchema,
    "dim_store": DimStoreSchema,
    "dim_supplier": DimSupplierSchema,
    "dim_product": DimProductSchema,
    "fact_sales_daily": FactSalesDailySchema,
    "fact_inventory_snapshot": FactInventorySnapshotSchema,
    "fact_purchase_orders": FactPurchaseOrderSchema,
}


class DataValidator:
    """Validates transactional records against schemas and referential integrity."""

    def __init__(self):
        self.known_stores: Set[str] = set()
        self.known_products: Set[str] = set()
        self.known_suppliers: Set[str] = set()
        self.known_date_keys: Set[int] = set()

    def set_reference_dimensions(
        self,
        store_ids: Set[str],
        product_ids: Set[str],
        supplier_ids: Set[str],
        date_keys: Set[int],
    ):
        """Sets loaded dimension key sets for foreign-key validation."""
        self.known_stores = set(store_ids)
        self.known_products = set(product_ids)
        self.known_suppliers = set(supplier_ids)
        self.known_date_keys = set(date_keys)

    def validate_records(
        self,
        source_feed: str,
        records: List[Dict[str, Any]],
        batch_id: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Validates records against the designated schema and referential constraints.
        Returns:
            Tuple of (valid_records, quarantined_records)
        """
        schema_cls = SCHEMA_REGISTRY.get(source_feed)
        if not schema_cls:
            raise ValueError(f"Unknown source feed: {source_feed}")

        valid_records: List[Dict[str, Any]] = []
        quarantined_records: List[Dict[str, Any]] = []
        now_utc = datetime.now(timezone.utc)

        for record in records:
            # Defensive copy to avoid mutating original
            rec_dict = dict(record)

            # 1. Referential integrity pre-check for fact tables
            orphan_violation = self._check_referential_integrity(source_feed, rec_dict)
            if orphan_violation:
                quarantined_records.append(
                    {
                        "source_feed": source_feed,
                        "raw_payload_json": json.dumps(rec_dict, default=str),
                        "violation_category": "ORPHAN_KEY",
                        "violation_details": orphan_violation,
                        "rejected_at": now_utc,
                        "batch_id": batch_id,
                    }
                )
                continue

            # 2. Pydantic schema & domain logic check
            try:
                validated_obj = schema_cls(**rec_dict)
                valid_records.append(validated_obj.model_dump())
            except ValidationError as ve:
                errors_summary = "; ".join(
                    [f"{e['loc']}: {e['msg']}" for e in ve.errors()]
                )
                quarantined_records.append(
                    {
                        "source_feed": source_feed,
                        "raw_payload_json": json.dumps(rec_dict, default=str),
                        "violation_category": "SCHEMA_ERROR",
                        "violation_details": errors_summary,
                        "rejected_at": now_utc,
                        "batch_id": batch_id,
                    }
                )
            except Exception as ex:
                quarantined_records.append(
                    {
                        "source_feed": source_feed,
                        "raw_payload_json": json.dumps(rec_dict, default=str),
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

    def _check_referential_integrity(self, source_feed: str, record: Dict[str, Any]) -> Optional[str]:
        """Validates foreign key references against registered dimensions."""
        if not (self.known_stores or self.known_products or self.known_date_keys):
            return None  # Dimensions not loaded yet (e.g. during initial dimension load)

        if "store_id" in record and self.known_stores:
            if record["store_id"] not in self.known_stores:
                return f"Orphaned store_id: '{record['store_id']}' not found in dim_store"

        if "product_id" in record and self.known_products:
            if record["product_id"] not in self.known_products:
                return f"Orphaned product_id: '{record['product_id']}' not found in dim_product"

        if "supplier_id" in record and self.known_suppliers:
            if record["supplier_id"] not in self.known_suppliers:
                return f"Orphaned supplier_id: '{record['supplier_id']}' not found in dim_supplier"

        if "date_key" in record and self.known_date_keys:
            if record["date_key"] not in self.known_date_keys:
                return f"Orphaned date_key: '{record['date_key']}' not found in dim_date"

        return None

