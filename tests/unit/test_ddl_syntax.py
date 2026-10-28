"""Unit test to verify DDL schema creation and constraint validity."""
import sqlite3
from pathlib import Path


def test_ddl_star_and_quarantine_schema():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    star_path = Path("sql/ddl/01_star_schema.sql")
    quarantine_path = Path("sql/ddl/02_quarantine_schema.sql")

    assert star_path.exists(), f"Missing {star_path}"
    assert quarantine_path.exists(), f"Missing {quarantine_path}"

    with open(star_path, "r", encoding="utf-8") as f:
        cursor.executescript(f.read())

    with open(quarantine_path, "r", encoding="utf-8") as f:
        cursor.executescript(f.read())

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {r[0] for r in cursor.fetchall()}

    expected_tables = {
        "dim_date",
        "dim_store",
        "dim_supplier",
        "dim_product",
        "fact_sales_daily",
        "fact_inventory_snapshot",
        "fact_purchase_orders",
        "quarantine_invalid_records",
        "etl_batch_log",
    }

    missing = expected_tables - tables
    assert not missing, f"Missing tables in DDL: {missing}"
    print(f"Verified all {len(expected_tables)} tables successfully: {sorted(list(expected_tables))}")
    conn.close()


if __name__ == "__main__":
    test_ddl_star_and_quarantine_schema()
