"""Queries and displays exact row counts and ETL batch metrics from RetailPulseDB."""
import pyodbc
from config.settings import settings

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    f"DATABASE={settings.DB_NAME};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("=" * 60)
print(f"RETAILPULSE DB AUDIT: {settings.DB_NAME}")
print("=" * 60)

cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME;")
tables = [row[0] for row in cursor.fetchall()]

for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM dbo.{table};")
    count = cursor.fetchone()[0]
    print(f"  {table:30} : {count:>8} rows")

print("-" * 60)
cursor.execute("SELECT TOP 3 batch_id, status, records_processed, records_loaded, records_quarantined, started_at, completed_at FROM dbo.etl_batch_log ORDER BY started_at DESC;")
print("LATEST ETL BATCH AUDIT:")
for row in cursor.fetchall():
    print(f"  Batch: {row[0]} | Status: {row[1]} | Processed: {row[2]} | Loaded: {row[3]} | Quarantined: {row[4]} | Duration: {row[5]} -> {row[6]}")

print("=" * 60)
conn.close()
