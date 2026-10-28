"""Automated metric reconciliation test harness at root test path.
Delegates directly to tests.reconciliation.test_metric_reconciliation.
"""
from tests.reconciliation.test_metric_reconciliation import (
    harness,
    test_reconcile_sales_financial_metrics,
    test_reconcile_stockout_rate_metrics,
    test_reconcile_rolling_ads_and_dos,
    test_reconcile_store_inventory_turnover,
    test_reconcile_supplier_performance,
    test_reconcile_executive_kpis,
)

__all__ = [
    "harness",
    "test_reconcile_sales_financial_metrics",
    "test_reconcile_stockout_rate_metrics",
    "test_reconcile_rolling_ads_and_dos",
    "test_reconcile_store_inventory_turnover",
    "test_reconcile_supplier_performance",
    "test_reconcile_executive_kpis",
]
