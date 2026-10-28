"""Verification test for Microsoft SQL Server Star Schema and Quarantine DDL."""
import pyodbc
from config.settings import settings


def test_mssql_star_schema_tables():
    """Verifies that Microsoft SQL Server has all required dimensional star schema tables."""
    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=localhost;"
        f"DATABASE={settings.DB_NAME};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    cursor.execute(
        f"""
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_CATALOG = '{settings.DB_NAME}';
        """
    )
    tables = {row[0] for row in cursor.fetchall()}

    expected_tables = {
        "dim_date",
        "dim_store",
        "dim_supplier",
        "dim_product",
        "fact_sales_daily",
        "fact_inventory_snapshot",
        "fact_purchase_orders",
        "quarantine_records",
        "etl_batch_log",
    }

    missing = expected_tables - tables
    assert not missing, f"Missing tables in SQL Server RetailPulseDI: {missing}"
    print(f"Verified all {len(expected_tables)} tables in SQL Server successfully: {sorted(list(expected_tables))}")
    conn.close()


if __name__ == "__main__":
    test_mssql_star_schema_tables()

