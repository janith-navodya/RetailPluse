"""RetailPulse DI: Streamlit Database Helper & Order Write-Back Actions.

Implements the write-back execution pipeline for human-in-the-loop purchase order approval:
Updates recommendation state in Microsoft SQL Server for live DirectQuery pickup.
"""
from __future__ import annotations

from typing import Union
import pyodbc
from config.settings import DB_CONFIG
from config.logging_config import logger


def get_db_connection() -> pyodbc.Connection:
    """Creates a direct ODBC connection to SQL Server for write-back execution."""
    driver = DB_CONFIG.get("driver", "ODBC Driver 18 for SQL Server")
    if not driver.startswith("{"):
        driver_str = f"{{{driver}}}"
    else:
        driver_str = driver

    conn_str = (
        f"DRIVER={driver_str};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"Trusted_Connection=yes;"
        f"TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def approve_replenishment_order(recommendation_id: Union[int, str]) -> None:
    """Updates the recommendation state in SQL Server for DirectQuery pickup."""
    conn = get_db_connection()
    cursor = conn.cursor()
    update_query = """
        UPDATE fact_replenishment_recommendation
        SET approval_status = 'APPROVED',
            approved_at = GETDATE()
        WHERE recommendation_id = ?
    """
    cursor.execute(update_query, (str(recommendation_id),))
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("Successfully approved replenishment order %s via DirectQuery write-back.", recommendation_id)
    try:
        from src.ui.data_access import invalidate_ui_cache
        invalidate_ui_cache()
    except Exception:
        pass

