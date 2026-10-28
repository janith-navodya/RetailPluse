"""Integration tests verifying pipeline idempotence and primary-key duplicate prevention."""
import pyodbc
import pytest
from config.settings import settings
from src.etl.ingest import SQLServerIngestionPipeline


def test_pipeline_idempotence():
    """
    Test that running an upsert twice on identical records produces ZERO duplicate rows.
    """
    pipeline = SQLServerIngestionPipeline(db_name=settings.DB_NAME)
    conn = pipeline.get_connection()
    cursor = conn.cursor()

    # 1. Capture initial row counts
    cursor.execute("SELECT COUNT(*) FROM dbo.fact_sales_daily")
    initial_sales_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM dbo.fact_inventory_snapshot")
    initial_inv_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM dbo.dim_product")
    initial_product_count = cursor.fetchone()[0]

    assert initial_sales_count > 0, "Initial sales table should not be empty"
    assert initial_inv_count > 0, "Initial inventory table should not be empty"
    assert initial_product_count == 50, "Expected 50 SKUs in dim_product"

    # 2. Extract a sample batch of 100 sales records
    cursor.execute("SELECT TOP 100 * FROM dbo.fact_sales_daily")
    col_names = [desc[0] for desc in cursor.description]
    sample_rows = [dict(zip(col_names, row)) for row in cursor.fetchall()]

    # 3. Re-upsert the identical 100 records
    pipeline._upsert_fact_sales(sample_rows)

    # 4. Verify post-upsert row count is IDENTICAL
    cursor.execute("SELECT COUNT(*) FROM dbo.fact_sales_daily")
    post_sales_count = cursor.fetchone()[0]

    assert post_sales_count == initial_sales_count, (
        f"Idempotency violation! Initial: {initial_sales_count}, Post-upsert: {post_sales_count}"
    )

    # 5. Check for any duplicate primary keys (date_key, store_id, product_id)
    cursor.execute(
        """
        SELECT date_key, store_id, product_id, COUNT(*)
        FROM dbo.fact_sales_daily
        GROUP BY date_key, store_id, product_id
        HAVING COUNT(*) > 1
        """
    )
    duplicate_pks = cursor.fetchall()
    assert len(duplicate_pks) == 0, f"Found duplicate primary keys: {duplicate_pks}"

    conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

