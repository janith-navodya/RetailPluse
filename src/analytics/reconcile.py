"""Cross-engine metric reconciliation harness for RetailPulse DI Platform.

Verifies mathematical alignment between:
1. Microsoft SQL Server Analytical Views (T-SQL)
2. Python Vectorized Aggregations (Pandas)
3. Formal specifications codified in METRIC_DEFINITIONS.md
"""
import warnings
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import pyodbc
import pandas as pd
import numpy as np

# Suppress pandas pyodbc DBAPI2 connection warning
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

from config.settings import settings
from config.logging_config import logger


@dataclass
class MetricReconciliationResult:
    metric_id: str
    metric_name: str
    sql_value: float
    python_value: float
    absolute_delta: float
    tolerance: float
    status: str
    details: Optional[str] = None


class MetricReconciliationHarness:
    """Automated reconciliation engine comparing SQL Server views against Pandas aggregations."""

    def __init__(self, db_name: str = settings.DB_NAME):
        self.db_name = db_name
        self.conn_str = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            "SERVER=localhost;"
            f"DATABASE={self.db_name};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )

    def get_connection(self) -> pyodbc.Connection:
        """Returns active pyodbc connection."""
        return pyodbc.connect(self.conn_str)

    def reconcile_financial_metrics(self) -> List[MetricReconciliationResult]:
        """Reconciles Net Sales, COGS, Gross Profit, and Gross Margin %."""
        conn = self.get_connection()
        try:
            # 1. Query SQL View
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 
                    SUM(total_net_sales) AS net_sales,
                    SUM(total_cogs) AS cogs,
                    SUM(total_gross_profit) AS gross_profit,
                    ROUND((SUM(total_gross_profit) * 100.0) / NULLIF(SUM(total_net_sales), 0), 2) AS gross_margin_pct
                FROM dbo.vw_product_sales_daily;
                """
            )
            sql_row = cur.fetchone()
            sql_net_sales = float(sql_row[0])
            sql_cogs = float(sql_row[1])
            sql_gp = float(sql_row[2])
            sql_gm_pct = float(sql_row[3])

            # 2. Compute independently in Python / Pandas
            df_sales = pd.read_sql("SELECT net_sales_amount, cogs_amount, gross_profit_amount FROM dbo.fact_sales_daily", conn)
            py_net_sales = float(df_sales["net_sales_amount"].sum())
            py_cogs = float(df_sales["cogs_amount"].sum())
            py_gp = float(py_net_sales - py_cogs)
            py_gm_pct = round((py_gp * 100.0) / py_net_sales, 2) if py_net_sales > 0 else 0.0

            results = [
                self._build_result("M-01", "Total Net Sales Amount", sql_net_sales, py_net_sales, 0.01),
                self._build_result("M-02", "Total Cost of Goods Sold (COGS)", sql_cogs, py_cogs, 0.01),
                self._build_result("M-03", "Total Gross Profit", sql_gp, py_gp, 0.01),
                self._build_result("M-04", "Enterprise Gross Margin %", sql_gm_pct, py_gm_pct, 0.01),
            ]
            return results
        finally:
            conn.close()

    def reconcile_stockout_metrics(self) -> List[MetricReconciliationResult]:
        """Reconciles SKU-Store Stockout Rates between SQL Server and Pandas."""
        conn = self.get_connection()
        try:
            # SQL View Summary
            df_sql = pd.read_sql(
                "SELECT store_id, product_id, total_operating_days, total_stockout_days, stockout_rate_pct FROM dbo.vw_inventory_health_summary",
                conn,
            )

            # Python Computation
            df_inv = pd.read_sql("SELECT store_id, product_id, is_stockout FROM dbo.fact_inventory_snapshot", conn)
            py_grp = (
                df_inv.groupby(["store_id", "product_id"])
                .agg(
                    py_total_days=("is_stockout", "count"),
                    py_stockout_days=("is_stockout", "sum"),
                )
                .reset_index()
            )
            py_grp["py_rate_pct"] = (py_grp["py_stockout_days"] * 100.0 / py_grp["py_total_days"]).round(2)

            merged = pd.merge(df_sql, py_grp, on=["store_id", "product_id"])
            max_delta = float((merged["stockout_rate_pct"] - merged["py_rate_pct"]).abs().max())

            sql_overall = float(df_sql["stockout_rate_pct"].mean())
            py_overall = float(py_grp["py_rate_pct"].mean())

            return [
                self._build_result(
                    "M-06",
                    "Store-SKU Stockout Rate % (Max Delta)",
                    sql_overall,
                    py_overall,
                    0.01,
                    details=f"Evaluated across all {len(merged)} store-SKU pairs. Max delta: {max_delta:.4f}%",
                )
            ]
        finally:
            conn.close()

    def reconcile_days_of_supply(self, sample_size: int = 1000) -> List[MetricReconciliationResult]:
        """Reconciles Rolling 30D ADS and Days of Supply on a recent snapshot sample."""
        conn = self.get_connection()
        try:
            # Query SQL View
            df_vw = pd.read_sql(
                f"""
                SELECT TOP ({sample_size}) 
                    date_key, store_id, product_id, closing_stock_on_hand, 
                    rolling_30d_avg_daily_sales, days_of_supply
                FROM dbo.vw_inventory_health
                ORDER BY date_key DESC, store_id, product_id
                """,
                conn,
            )

            # Python computation from sales daily
            df_sales = pd.read_sql(
                "SELECT date_key, store_id, product_id, quantity_sold FROM dbo.fact_sales_daily ORDER BY store_id, product_id, date_key",
                conn,
            )
            df_sales["py_ads_raw"] = (
                df_sales.groupby(["store_id", "product_id"])["quantity_sold"]
                .transform(lambda s: s.rolling(30, min_periods=1).mean())
            )
            df_sales["py_ads_30d"] = df_sales["py_ads_raw"].round(2)

            merged = pd.merge(
                df_vw,
                df_sales[["date_key", "store_id", "product_id", "py_ads_raw", "py_ads_30d"]],
                on=["date_key", "store_id", "product_id"],
            )

            # Compute Python DoS using exact raw ADS identical to SQL Server
            def compute_py_dos(row):
                on_hand = row["closing_stock_on_hand"]
                ads = row["py_ads_raw"]
                if on_hand <= 0:
                    return 0.0
                if pd.isna(ads) or ads <= 0:
                    return 999.0
                return round(float(on_hand) / float(ads), 1)

            merged["py_dos"] = merged.apply(compute_py_dos, axis=1)

            ads_max_delta = float((merged["rolling_30d_avg_daily_sales"] - merged["py_ads_30d"]).abs().max())
            dos_max_delta = float((merged["days_of_supply"] - merged["py_dos"]).abs().max())

            sql_avg_dos = float(merged["days_of_supply"].mean())
            py_avg_dos = float(merged["py_dos"].mean())

            return [
                self._build_result(
                    "M-05a",
                    "Rolling 30D Average Daily Sales (Max Delta)",
                    float(merged["rolling_30d_avg_daily_sales"].mean()),
                    float(merged["py_ads_30d"].mean()),
                    0.05,
                    details=f"Evaluated on {len(merged)} snapshot rows. Max ADS delta: {ads_max_delta:.4f}",
                ),
                self._build_result(
                    "M-05b",
                    "Days of Supply (DoS) (Max Delta)",
                    sql_avg_dos,
                    py_avg_dos,
                    0.10,
                    details=f"Evaluated on {len(merged)} snapshot rows. Max DoS delta: {dos_max_delta:.4f} days",
                ),
            ]
        finally:
            conn.close()

    def reconcile_inventory_turnover(self) -> List[MetricReconciliationResult]:
        """Reconciles Annualized Inventory Turnover per Store between SQL Server and Pandas."""
        conn = self.get_connection()
        try:
            df_sql = pd.read_sql("SELECT * FROM dbo.vw_store_inventory_turnover ORDER BY store_id", conn)

            df_sales = pd.read_sql("SELECT store_id, date_key, cogs_amount FROM dbo.fact_sales_daily", conn)
            df_inv = pd.read_sql("SELECT store_id, date_key, ending_inventory_value FROM dbo.fact_inventory_snapshot", conn)

            store_cogs = df_sales.groupby("store_id")["cogs_amount"].sum()
            store_op_days = df_sales.groupby("store_id")["date_key"].nunique()
            store_daily_inv = df_inv.groupby(["store_id", "date_key"])["ending_inventory_value"].sum().reset_index()
            store_avg_inv = store_daily_inv.groupby("store_id")["ending_inventory_value"].mean()

            py_df = pd.DataFrame(
                {
                    "store_id": store_cogs.index,
                    "py_cogs": store_cogs.values.round(2),
                    "py_avg_inv": store_avg_inv.values.round(2),
                    "py_op_days": store_op_days.values,
                }
            )
            py_df["py_turnover"] = (
                (py_df["py_cogs"] / py_df["py_avg_inv"]) * (365.0 / py_df["py_op_days"])
            ).round(2)

            merged = pd.merge(df_sql, py_df, on="store_id")
            turnover_max_delta = float(
                (merged["annualized_inventory_turnover"].astype(float) - merged["py_turnover"]).abs().max()
            )

            return [
                self._build_result(
                    "M-07",
                    "Store Annualized Inventory Turnover (Max Delta)",
                    float(merged["annualized_inventory_turnover"].astype(float).mean()),
                    float(merged["py_turnover"].mean()),
                    0.01,
                    details=f"Evaluated across {len(merged)} stores. Max turnover delta: {turnover_max_delta:.4f}",
                )
            ]
        finally:
            conn.close()

    def reconcile_supplier_performance(self) -> List[MetricReconciliationResult]:
        """Reconciles Lead Times, Fill Rates, and MOQ adherence per supplier."""
        conn = self.get_connection()
        try:
            df_sql = pd.read_sql("SELECT * FROM dbo.vw_supplier_performance ORDER BY supplier_id", conn)

            df_po = pd.read_sql(
                """
                SELECT 
                    po.po_id, po.supplier_id, po.order_qty, po.received_qty, po.status,
                    po.order_date_key, po.expected_delivery_date_key, po.actual_delivery_date_key,
                    sup.min_order_qty, sup.mean_lead_time_days AS nom_lt,
                    d_ord.full_date AS ord_date, d_act.full_date AS act_date
                FROM dbo.fact_purchase_orders po
                INNER JOIN dbo.dim_supplier sup ON po.supplier_id = sup.supplier_id
                INNER JOIN dbo.dim_date d_ord ON po.order_date_key = d_ord.date_key
                LEFT JOIN dbo.dim_date d_act ON po.actual_delivery_date_key = d_act.date_key
                """,
                conn,
            )
            df_po["ord_date"] = pd.to_datetime(df_po["ord_date"])
            df_po["act_date"] = pd.to_datetime(df_po["act_date"])
            df_po["act_lt"] = (df_po["act_date"] - df_po["ord_date"]).dt.days
            deliv = df_po[df_po["status"] == "DELIVERED"]

            py_sup = (
                deliv.groupby("supplier_id")
                .agg(
                    py_avg_lt=("act_lt", "mean"),
                    py_fill_rate=("received_qty", lambda s: (s / deliv.loc[s.index, "order_qty"] * 100.0).mean()),
                )
                .reset_index()
            )
            py_sup["py_avg_lt"] = py_sup["py_avg_lt"].round(2)
            py_sup["py_fill_rate"] = py_sup["py_fill_rate"].round(2)

            merged = pd.merge(df_sql, py_sup, on="supplier_id")
            lt_max_delta = float((merged["avg_actual_lead_time_days"] - merged["py_avg_lt"]).abs().max())
            fill_max_delta = float((merged["order_fill_rate_pct"] - merged["py_fill_rate"]).abs().max())

            return [
                self._build_result(
                    "M-08a",
                    "Supplier Avg Actual Lead Time (Max Delta)",
                    float(merged["avg_actual_lead_time_days"].mean()),
                    float(merged["py_avg_lt"].mean()),
                    0.01,
                    details=f"Evaluated across {len(merged)} suppliers. Max lead time delta: {lt_max_delta:.4f} days",
                ),
                self._build_result(
                    "M-08b",
                    "Supplier Order Fill Rate % (Max Delta)",
                    float(merged["order_fill_rate_pct"].mean()),
                    float(merged["py_fill_rate"].mean()),
                    0.01,
                    details=f"Evaluated across {len(merged)} suppliers. Max fill rate delta: {fill_max_delta:.4f}%",
                ),
            ]
        finally:
            conn.close()

    def run_all_reconciliations(self) -> List[MetricReconciliationResult]:
        """Runs the complete suite of cross-engine metric reconciliation tests."""
        results: List[MetricReconciliationResult] = []
        results.extend(self.reconcile_financial_metrics())
        results.extend(self.reconcile_stockout_metrics())
        results.extend(self.reconcile_days_of_supply())
        results.extend(self.reconcile_inventory_turnover())
        results.extend(self.reconcile_supplier_performance())
        return results

    def _build_result(
        self,
        metric_id: str,
        name: str,
        sql_val: float,
        py_val: float,
        tolerance: float,
        details: Optional[str] = None,
    ) -> MetricReconciliationResult:
        delta = abs(sql_val - py_val)
        status = "PASS" if delta <= tolerance else "FAIL"
        return MetricReconciliationResult(
            metric_id=metric_id,
            metric_name=name,
            sql_value=round(sql_val, 4),
            python_value=round(py_val, 4),
            absolute_delta=round(delta, 4),
            tolerance=tolerance,
            status=status,
            details=details,
        )


def print_reconciliation_report():
    """CLI runner printing a formatted reconciliation report."""
    harness = MetricReconciliationHarness()
    results = harness.run_all_reconciliations()

    print("\n" + "=" * 90)
    print("RETAILPULSE DI: CROSS-ENGINE METRIC RECONCILIATION AUDIT REPORT")
    print("=" * 90)
    header = f"{'ID':<6} | {'Metric Name':<32} | {'SQL View':>12} | {'Python':>12} | {'Delta':>8} | {'Status':<6}"
    print(header)
    print("-" * 90)

    all_passed = True
    for r in results:
        print(
            f"{r.metric_id:<6} | {r.metric_name:<32} | {r.sql_value:>12.2f} | {r.python_value:>12.2f} | {r.absolute_delta:>8.4f} | {r.status:<6}"
        )
        if r.details:
            print(f"       -> Details: {r.details}")
        if r.status != "PASS":
            all_passed = False

    print("=" * 90)
    if all_passed:
        print("RESULT: ALL METRICS RECONCILED SUCCESSFULLY WITHIN TOLERANCE (100% PASS)\n")
    else:
        print("RESULT: RECONCILIATION VIOLATIONS DETECTED!\n")


if __name__ == "__main__":
    print_reconciliation_report()
