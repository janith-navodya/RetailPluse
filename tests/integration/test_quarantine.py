"""Integration tests verifying dead-letter quarantine routing and violation taxonomy."""
import json
import sqlite3
import pytest
from config.settings import settings


def test_quarantine_records_structure_and_categories():
    """Verifies that corrupted records are captured with correct taxonomy and intact payloads."""
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()

    # Query all quarantined records
    cursor.execute(
        """
        SELECT quarantine_id, source_feed, raw_payload_json, violation_category, violation_details, batch_id
        FROM quarantine_invalid_records
        """
    )
    records = cursor.fetchall()
    conn.close()

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
            assert parsed.get("product_id") == "PRD999" or parsed.get("store_id") == "STR999"

        # If schema error for negative sales, verify gross_sales_amount < 0
        if "gross_sales_amount" in details or "net_sales_amount" in details:
            assert parsed.get("gross_sales_amount", 0) < 0 or parsed.get("net_sales_amount", 0) < 0


def test_etl_batch_log_reconciliation():
    """Verifies that the etl_batch_log matches the sum of loaded and quarantined records."""
    conn = sqlite3.connect(settings.DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT batch_id, status, records_processed, records_loaded, records_quarantined 
        FROM etl_batch_log 
        ORDER BY started_at DESC 
        LIMIT 1
        """
    )
    batch = cursor.fetchone()
    conn.close()

    assert batch is not None, "Batch log must contain at least one run"
    batch_id, status, processed, loaded, quarantined = batch

    assert status == "COMPLETED"
    assert processed == loaded + quarantined, (
        f"Record count mismatch in batch {batch_id}: Processed ({processed}) != Loaded ({loaded}) + Quarantined ({quarantined})"
    )
    assert quarantined == 45, f"Expected exactly 45 injected corruptions, got {quarantined}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
