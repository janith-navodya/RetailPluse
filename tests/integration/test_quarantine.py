"""Integration tests verifying dead-letter quarantine routing and violation taxonomy."""
import json
import pyodbc
import pytest
from config.settings import settings


@pytest.fixture(scope="module")
def db_conn():
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


def test_quarantine_records_structure_and_categories(db_conn):
    """Verifies that corrupted records are captured with correct taxonomy and intact payloads."""
    cursor = db_conn.cursor()

    # Query all quarantined records
    cursor.execute(
        """
        SELECT quarantine_id, source_feed, raw_payload_json, violation_category, violation_details, batch_id
        FROM dbo.quarantine_records
        """
    )
    records = cursor.fetchall()

    assert len(records) > 0, "Quarantine table should contain records from the controlled test feed"

    categories = {r[3] for r in records}
    feeds = {r[1] for r in records}

    # Verify feeds present
    assert "fact_sales_daily" in feeds, "Expected fact_sales_daily corruptions"
    assert "fact_inventory_snapshot" in feeds, "Expected fact_inventory_snapshot corruptions"

    # Verify violation categories present
    assert "SCHEMA_ERROR" in categories or "ORPHAN_KEY" in categories or "DOMAIN_VIOLATION" in categories

    for q_id, feed, raw_json, cat, details, batch_id in records:
        assert raw_json, f"Raw JSON missing for quarantine_id {q_id}"
        parsed = json.loads(raw_json)
        assert isinstance(parsed, dict), "Raw payload must be valid JSON object"
        assert details, f"Violation details must not be empty for {q_id}"
        assert batch_id, f"Batch ID must be tracked for lineage on {q_id}"

        # If orphan key, verify the payload actually had an orphaned key
        if cat == "ORPHAN_KEY":
            assert (
                parsed.get("product_id") == "PRD999"
                or parsed.get("store_id") == "STR999"
                or parsed.get("supplier_id") == "SUP999"
                or parsed.get("date_key") == 99999999
            ), f"Expected orphan key in payload: {parsed}"

        # If schema error for negative sales, verify gross_sales_amount < 0
        if "gross_sales_amount" in details or "net_sales_amount" in details:
            assert parsed.get("gross_sales_amount", 0) < 0 or parsed.get("net_sales_amount", 0) < 0


def test_etl_batch_log_reconciliation(db_conn):
    """Verifies that the etl_batch_log matches the sum of loaded and quarantined records."""
    cursor = db_conn.cursor()

    cursor.execute(
        """
        SELECT TOP 1 batch_id, status, records_processed, records_loaded, records_quarantined 
        FROM dbo.etl_batch_log 
        ORDER BY started_at DESC
        """
    )
    batch = cursor.fetchone()

    assert batch is not None, "Batch log must contain at least one run"
    batch_id, status, processed, loaded, quarantined = batch

    assert status == "COMPLETED"
    assert processed == loaded + quarantined, (
        f"Record count mismatch in batch {batch_id}: Processed ({processed}) != Loaded ({loaded}) + Quarantined ({quarantined})"
    )
    assert quarantined == 60, f"Expected exactly 60 injected corruptions (45 sales + 15 inv), got {quarantined}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
