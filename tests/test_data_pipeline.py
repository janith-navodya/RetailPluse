"""Integration test suite for RetailPulse DI Data Pipeline targeting Microsoft SQL Server.

Verifies:
1. All 9 Star Schema and ETL metadata tables exist in RetailPulseDB.
2. Dead-letter quarantine table correctly isolates and tags corrupt records.
3. Pipeline idempotency: re-running upsert produces zero duplicate primary keys.
4. ETL batch reconciliation: Processed = Loaded + Quarantined.
"""
import json
import pyodbc
import pytest
from config.settings import settings
from src.etl.ingest import SQLServerIngestionPipeline


@pytest.fixture(scope="module")
def db_conn():
    """Provides an active pyodbc connection to RetailPulseDB."""
    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=localhost;"
        f"DATABASE={settings.DB_NAME};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, autocommit=True)
    yield conn
    conn.close()


def test_schema_tables_exist(db_conn):
    """Test 1: Verify all 9 required Star Schema and pipeline tables exist."""
    cursor = db_conn.cursor()
    cursor.execute(
        """
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
        """
    )
    existing_tables = {row[0] for row in cursor.fetchall()}

    expected_tables = {
        "dim_date",
        "dim_store",
        "dim_supplier",
        "dim_product",
        "fact_sales_daily",
        "fact_inventory_snapshot",
        "fact_purchase_orders",
        "etl_batch_log",
        "quarantine_records",
    }

    missing_tables = expected_tables - existing_tables
    assert not missing_tables, f"Missing tables in {settings.DB_NAME}: {missing_tables}"


def test_quarantine_records_taxonomy_and_payloads(db_conn):
    """Test 2: Verify dead-letter quarantine table isolates corrupt records with valid taxonomy."""
    cursor = db_conn.cursor()
    cursor.execute(
        """
        SELECT quarantine_id, source_feed, raw_payload_json, violation_category, violation_details, batch_id
        FROM dbo.quarantine_records
        """
    )
    records = cursor.fetchall()

    assert len(records) > 0, "Quarantine table dbo.quarantine_records should contain quarantined records"

    feeds = {r[1] for r in records}
    categories = {r[3] for r in records}

    # Verify feeds represented in quarantine
    assert "fact_sales_daily" in feeds, "Expected fact_sales_daily corruptions"
    assert "fact_inventory_snapshot" in feeds, "Expected fact_inventory_snapshot corruptions"

    # Verify standard violation taxonomy
    valid_taxonomies = {"SCHEMA_ERROR", "ORPHAN_KEY", "DOMAIN_VIOLATION"}
    for cat in categories:
        assert cat in valid_taxonomies, f"Unexpected violation category: {cat}"

    # Verify each quarantined record contains valid json, details, and batch_id
    for q_id, feed, raw_json, cat, details, batch_id in records:
        assert raw_json, f"Missing raw payload JSON for quarantine ID {q_id}"
        payload = json.loads(raw_json)
        assert isinstance(payload, dict), f"Payload is not a valid JSON dictionary: {payload}"
        assert details, f"Violation details must not be empty for quarantine ID {q_id}"
        assert batch_id, f"Lineage batch ID missing for quarantine ID {q_id}"

        # Deep validation based on violation type
        if cat == "ORPHAN_KEY":
            assert (
                payload.get("product_id") == "PRD999"
                or payload.get("store_id") == "STR999"
                or payload.get("supplier_id") == "SUP999"
                or payload.get("date_key") == 99999999
            ), f"Expected orphan key in payload: {payload}"
        elif "negative" in details.lower() or "greater than or equal to 0" in details.lower():
            gross = payload.get("gross_sales_amount")
            net = payload.get("net_sales_amount")
            assert (gross is not None and float(gross) < 0) or (net is not None and float(net) < 0)


def test_pipeline_idempotence(db_conn):
    """Test 3: Verify idempotency - re-running upsert produces identical row count and 0 duplicate PKs."""
    pipeline = SQLServerIngestionPipeline(db_name=settings.DB_NAME)
    cursor = db_conn.cursor()

    # Capture initial row counts
    cursor.execute("SELECT COUNT(*) FROM dbo.fact_sales_daily")
    initial_sales_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM dbo.fact_inventory_snapshot")
    initial_inv_count = cursor.fetchone()[0]

    assert initial_sales_count > 0, "Initial sales table should not be empty"
    assert initial_inv_count > 0, "Initial inventory table should not be empty"

    # Fetch 100 existing records from fact_sales_daily
    cursor.execute("SELECT TOP 100 * FROM dbo.fact_sales_daily")
    columns = [col[0] for col in cursor.description]
    sample_rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    # Re-upsert the sample 100 records using the pipeline MERGE method
    re_upserted = pipeline._upsert_fact_sales(sample_rows)
    assert re_upserted == 100, f"Expected 100 upserted rows, got {re_upserted}"

    # Verify post-upsert row count is completely unchanged
    cursor.execute("SELECT COUNT(*) FROM dbo.fact_sales_daily")
    post_sales_count = cursor.fetchone()[0]
    assert post_sales_count == initial_sales_count, (
        f"Idempotency violation! Initial: {initial_sales_count}, After re-upsert: {post_sales_count}"
    )

    # Verify ZERO duplicate primary keys (date_key, store_id, product_id)
    cursor.execute(
        """
        SELECT date_key, store_id, product_id, COUNT(*)
        FROM dbo.fact_sales_daily
        GROUP BY date_key, store_id, product_id
        HAVING COUNT(*) > 1
        """
    )
    duplicate_pks = cursor.fetchall()
    assert len(duplicate_pks) == 0, f"Found duplicate primary keys in fact_sales_daily: {duplicate_pks}"


def test_etl_batch_log_reconciliation(db_conn):
    """Test 4: Verify etl_batch_log records Processed = Loaded + Quarantined."""
    cursor = db_conn.cursor()
    cursor.execute(
        """
        SELECT TOP 1 batch_id, status, records_processed, records_loaded, records_quarantined
        FROM dbo.etl_batch_log
        WHERE status = 'COMPLETED'
        ORDER BY started_at DESC
        """
    )
    batch = cursor.fetchone()
    assert batch is not None, "Expected at least one COMPLETED batch in dbo.etl_batch_log"

    batch_id, status, processed, loaded, quarantined = batch
    assert status == "COMPLETED"
    assert processed == loaded + quarantined, (
        f"Reconciliation error in batch {batch_id}: Processed ({processed}) != Loaded ({loaded}) + Quarantined ({quarantined})"
    )
    assert quarantined > 0, f"Expected quarantined records > 0, got {quarantined}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
