"""Automated Pytest reconciliation harness for RetailPulse DI metrics.

Formally reconciles calculations across:
1. Microsoft SQL Server Analytical Views (T-SQL)
2. Python Vectorized Aggregations (Pandas)
3. Target Tolerances defined in METRIC_DEFINITIONS.md
"""
import pyodbc
import pytest
import pandas as pd
from config.settings import settings
from src.analytics.reconcile import MetricReconciliationHarness


@pytest.fixture(scope="module")
def harness():
    """Provides an instance of MetricReconciliationHarness."""
    return MetricReconciliationHarness(db_name=settings.DB_NAME)


def test_reconcile_sales_financial_metrics(harness):
    """
    Test M-01 to M-04: Reconciles Net Sales, COGS, Gross Profit, and Gross Margin %.
    Tolerance: <= 0.01 currency / percentage units.
    """
    results = harness.reconcile_financial_metrics()
    assert len(results) == 4, "Expected 4 financial metric results"

    for res in results:
        assert (
            res.status == "PASS"
        ), f"Financial metric {res.metric_id} ({res.metric_name}) failed: SQL={res.sql_value}, Py={res.python_value}, Delta={res.absolute_delta} > {res.tolerance}"


def test_reconcile_stockout_rate_metrics(harness):
    """
    Test M-06: Reconciles Store-SKU Stockout Rate % across all 150 store-SKU combinations.
    Tolerance: <= 0.01% max delta.
    """
    results = harness.reconcile_stockout_metrics()
    assert len(results) == 1, "Expected 1 stockout summary result"
    res = results[0]
    assert (
        res.status == "PASS"
    ), f"Stockout rate reconciliation failed: SQL={res.sql_value}, Py={res.python_value}, Delta={res.absolute_delta} > {res.tolerance}"


def test_reconcile_rolling_ads_and_dos(harness):
    """
    Test M-05a & M-05b: Reconciles Rolling 30D Average Daily Sales and Days of Supply (DoS).
    Tolerances: ADS <= 0.05 units, DoS <= 0.10 days.
    """
    results = harness.reconcile_days_of_supply(sample_size=1000)
    assert len(results) == 2, "Expected ADS and DoS results"

    for res in results:
        assert (
            res.status == "PASS"
        ), f"Inventory health metric {res.metric_id} ({res.metric_name}) failed: SQL={res.sql_value}, Py={res.python_value}, Delta={res.absolute_delta} > {res.tolerance}"


def test_reconcile_store_inventory_turnover(harness):
    """
    Test M-07: Reconciles Annualized Inventory Turnover per Store.
    Tolerance: <= 0.01 turns.
    """
    results = harness.reconcile_inventory_turnover()
    assert len(results) == 1, "Expected 1 turnover summary result"
    res = results[0]
    assert (
        res.status == "PASS"
    ), f"Store inventory turnover reconciliation failed: SQL={res.sql_value}, Py={res.python_value}, Delta={res.absolute_delta} > {res.tolerance}"


def test_reconcile_supplier_performance(harness):
    """
    Test M-08a & M-08b: Reconciles Lead Times and Fill Rates per Supplier.
    Tolerance: <= 0.01 days / percentage units.
    """
    results = harness.reconcile_supplier_performance()
    assert len(results) == 2, "Expected 2 supplier performance results"

    for res in results:
        assert (
            res.status == "PASS"
        ), f"Supplier metric {res.metric_id} ({res.metric_name}) failed: SQL={res.sql_value}, Py={res.python_value}, Delta={res.absolute_delta} > {res.tolerance}"


def test_reconcile_executive_kpis():
    """
    Verifies that vw_executive_kpis reconciles with fact-level aggregations within 0.01 tolerance.
    """
    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=localhost;"
        f"DATABASE={settings.DB_NAME};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()

    cur.execute("SELECT total_net_sales, total_cogs, total_gross_profit, gross_margin_pct, total_operating_days FROM dbo.vw_executive_kpis")
    exec_row = cur.fetchone()

    cur.execute("SELECT SUM(net_sales_amount), SUM(cogs_amount), SUM(gross_profit_amount), COUNT(DISTINCT date_key) FROM dbo.fact_sales_daily")
    fact_row = cur.fetchone()
    conn.close()

    net_sales_delta = abs(float(exec_row[0]) - float(fact_row[0]))
    cogs_delta = abs(float(exec_row[1]) - float(fact_row[1]))
    gp_delta = abs(float(exec_row[2]) - float(fact_row[2]))
    days_delta = abs(int(exec_row[4]) - int(fact_row[3]))

    assert net_sales_delta <= 0.01, f"Net sales delta {net_sales_delta} exceeds 0.01"
    assert cogs_delta <= 0.01, f"COGS delta {cogs_delta} exceeds 0.01"
    assert gp_delta <= 0.01, f"Gross profit delta {gp_delta} exceeds 0.01"
    assert days_delta == 0, f"Operating days mismatch: {exec_row[4]} != {fact_row[3]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
