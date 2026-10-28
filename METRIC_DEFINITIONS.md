# RETAILPULSE DECISION INTELLIGENCE (DI)
## METRIC DEFINITIONS & CROSS-ENGINE RECONCILIATION HARNESS

---

### 1. Executive Summary & Purpose

A catastrophic failure mode in enterprise decision platforms is **metric drift**: discrepancies where an executive KPI displayed in a BI report (DAX) diverges from the data warehouse SQL view or the analytical feature engineering pipeline in Python.

**The Golden Rule of RetailPulse DI:**
Every metric definition in this platform is formally specified across three execution runtimes:
1. **Relational Database (ANSI SQL Views)**
2. **Analytical Engine (Vectorized Python / Pandas)**
3. **Business Intelligence Layer (Power BI DAX Measures)**

An automated reconciliation test harness (`tests/reconciliation/test_metric_reconciliation.py`) verifies that query outputs across all three implementations match to within **0.01 units or currency** tolerance under identical date/slice parameters.

---

### 2. Core Reconciled Metrics

#### Metric 1: Net Sales Amount
- **Business Description:** Total realized customer sales revenue net of all promotional markdowns, voucher discounts, and price concessions.
- **Mathematical Definition:**
  $$\text{Net Sales} = \sum_{r \in \text{Sales}} \left( \text{quantity\_sold}_r \times \text{unit\_retail\_price}_r - \text{discount\_amount}_r \right)$$

##### Technical Implementations:
- **ANSI SQL View:**
  ```sql
  SELECT 
      SUM(net_sales_amount) AS total_net_sales
  FROM fact_sales_daily;
  ```
- **Vectorized Python:**
  ```python
  total_net_sales = float(df_sales["net_sales_amount"].sum())
  ```
- **Power BI DAX:**
  ```dax
  [Total Net Sales] = 
  SUM(fact_sales_daily[net_sales_amount])
  ```

---

#### Metric 2: Cost of Goods Sold (COGS)
- **Business Description:** Direct wholesale procurement expenditure incurred for the inventory units sold to customers.
- **Mathematical Definition:**
  $$\text{COGS} = \sum_{r \in \text{Sales}} \left( \text{quantity\_sold}_r \times \text{unit\_cost\_price}_r \right)$$

##### Technical Implementations:
- **ANSI SQL View:**
  ```sql
  SELECT 
      SUM(cogs_amount) AS total_cogs
  FROM fact_sales_daily;
  ```
- **Vectorized Python:**
  ```python
  total_cogs = float(df_sales["cogs_amount"].sum())
  ```
- **Power BI DAX:**
  ```dax
  [Total COGS] = 
  SUM(fact_sales_daily[cogs_amount])
  ```

---

#### Metric 3: Gross Profit
- **Business Description:** Realized operational margin generated from sales after deducting wholesale inventory acquisition costs.
- **Mathematical Definition:**
  $$\text{Gross Profit} = \text{Net Sales} - \text{COGS}$$

##### Technical Implementations:
- **ANSI SQL View:**
  ```sql
  SELECT 
      SUM(net_sales_amount) - SUM(cogs_amount) AS gross_profit
  FROM fact_sales_daily;
  ```
- **Vectorized Python:**
  ```python
  gross_profit = float(df_sales["net_sales_amount"].sum() - df_sales["cogs_amount"].sum())
  ```
- **Power BI DAX:**
  ```dax
  [Gross Profit] = 
  [Total Net Sales] - [Total COGS]
  ```

---

#### Metric 4: Gross Margin %
- **Business Description:** Percentage of every sales dollar retained as gross margin. Safe zero-division handling required.
- **Mathematical Definition:**
  $$\text{Gross Margin \%} = \begin{cases} \left( \frac{\text{Gross Profit}}{\text{Net Sales}} \right) \times 100 & \text{if } \text{Net Sales} > 0 \\ 0.00 & \text{if } \text{Net Sales} \le 0 \end{cases}$$

##### Technical Implementations:
- **ANSI SQL View:**
  ```sql
  SELECT 
      CASE 
          WHEN SUM(net_sales_amount) = 0 THEN 0.00
          ELSE ROUND(((SUM(net_sales_amount) - SUM(cogs_amount)) * 100.0) / SUM(net_sales_amount), 2)
      END AS gross_margin_pct
  FROM fact_sales_daily;
  ```
- **Vectorized Python:**
  ```python
  net_sales = df_sales["net_sales_amount"].sum()
  cogs = df_sales["cogs_amount"].sum()
  gross_margin_pct = round(float(((net_sales - cogs) * 100.0) / net_sales), 2) if net_sales > 0 else 0.00
  ```
- **Power BI DAX:**
  ```dax
  [Gross Margin %] = 
  DIVIDE([Gross Profit] * 100.0, [Total Net Sales], 0.00)
  ```

---

#### Metric 5: Average Daily Sales (ADS - Rolling 30 Days)
- **Business Description:** The unweighted arithmetic mean of daily unit sales over the trailing 30 calendar days for a specific SKU-store pair.
- **Mathematical Definition:**
  $$\text{ADS}_{i, s, t} = \frac{1}{30} \sum_{\tau = t-29}^{t} \text{quantity\_sold}_{i, s, \tau}$$

##### Technical Implementations:
- **ANSI SQL View:**
  ```sql
  SELECT 
      date_key,
      store_id,
      product_id,
      AVG(quantity_sold) OVER (
          PARTITION BY store_id, product_id 
          ORDER BY date_key 
          ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
      ) AS ads_30d
  FROM fact_sales_daily;
  ```
- **Vectorized Python:**
  ```python
  df_sales["ads_30d"] = (
      df_sales.groupby(["store_id", "product_id"])["quantity_sold"]
      .transform(lambda s: s.rolling(window=30, min_periods=1).mean())
  )
  ```
- **Power BI DAX:**
  ```dax
  [ADS 30D] = 
  VAR CurrentDate = MAX(dim_date[full_date])
  VAR PeriodStart = CurrentDate - 29
  RETURN
  CALCULATE(
      DIVIDE(SUM(fact_sales_daily[quantity_sold]), 30, 0),
      DATESBETWEEN(dim_date[full_date], PeriodStart, CurrentDate)
  )
  ```

---

#### Metric 6: Days of Supply (DoS)
- **Business Description:** The estimated operational runway (in days) before on-hand inventory reaches zero at current sales velocity.
- **Mathematical Definition:**
  $$\text{DoS}_{i, s, t} = \begin{cases} \frac{\text{ending\_on\_hand\_qty}_{i, s, t}}{\text{ADS}_{i, s, t}} & \text{if } \text{ADS}_{i, s, t} > 0 \\ 999.0 & \text{if } \text{ADS}_{i, s, t} = 0 \text{ and } \text{ending\_on\_hand\_qty} > 0 \\ 0.0 & \text{if } \text{ending\_on\_hand\_qty} = 0 \end{cases}$$

##### Technical Implementations:
- **ANSI SQL View:**
  ```sql
  SELECT 
      inv.date_key,
      inv.store_id,
      inv.product_id,
      inv.ending_on_hand_qty,
      ads.ads_30d,
      CASE 
          WHEN inv.ending_on_hand_qty = 0 THEN 0.0
          WHEN ads.ads_30d = 0 THEN 999.0
          ELSE ROUND(CAST(inv.ending_on_hand_qty AS REAL) / ads.ads_30d, 1)
      END AS days_of_supply
  FROM fact_inventory_snapshot inv
  JOIN vw_ads_30d ads 
    ON inv.date_key = ads.date_key 
   AND inv.store_id = ads.store_id 
   AND inv.product_id = ads.product_id;
  ```
- **Vectorized Python:**
  ```python
  def calculate_dos(on_hand: float, ads: float) -> float:
      if on_hand <= 0:
          return 0.0
      if ads <= 0:
          return 999.0
      return round(on_hand / ads, 1)
  ```
- **Power BI DAX:**
  ```dax
  [Days of Supply] = 
  VAR OnHand = SUM(fact_inventory_snapshot[ending_on_hand_qty])
  VAR ADS = [ADS 30D]
  RETURN
  SWITCH(
      TRUE(),
      OnHand <= 0, 0.0,
      ADS <= 0, 999.0,
      ROUND(DIVIDE(OnHand, ADS, 0), 1)
  )
  ```

---

#### Metric 7: Stockout Rate %
- **Business Description:** The percentage of store operating days on which the closing inventory for a product was zero. Directly measures demand censoring prevalence.
- **Mathematical Definition:**
  $$\text{Stockout Rate \%} = \left( \frac{\sum_{t=1}^N \mathbb{I}(\text{ending\_on\_hand\_qty}_t = 0)}{N} \right) \times 100$$

##### Technical Implementations:
- **ANSI SQL View:**
  ```sql
  SELECT 
      store_id,
      product_id,
      COUNT(*) AS total_operating_days,
      SUM(CASE WHEN ending_on_hand_qty = 0 THEN 1 ELSE 0 END) AS stockout_days,
      ROUND((SUM(CASE WHEN ending_on_hand_qty = 0 THEN 1.0 ELSE 0.0 END) * 100.0) / COUNT(*), 2) AS stockout_rate_pct
  FROM fact_inventory_snapshot
  GROUP BY store_id, product_id;
  ```
- **Vectorized Python:**
  ```python
  stockout_days = int((df_inventory["ending_on_hand_qty"] == 0).sum())
  total_days = len(df_inventory)
  stockout_rate_pct = round((stockout_days * 100.0) / total_days, 2) if total_days > 0 else 0.0
  ```
- **Power BI DAX:**
  ```dax
  [Stockout Rate %] = 
  VAR StockoutDays = CALCULATE(COUNTROWS(fact_inventory_snapshot), fact_inventory_snapshot[is_stockout] = 1)
  VAR TotalDays = COUNTROWS(fact_inventory_snapshot)
  RETURN
  DIVIDE(StockoutDays * 100.0, TotalDays, 0.00)
  ```

---

#### Metric 8: Inventory Turnover (Annualized)
- **Business Description:** Measures the frequency with which aggregate inventory is sold and replaced over a 365-day operating period.
- **Mathematical Definition:**
  $$\text{Inventory Turnover} = \frac{\sum_{t \in \text{Year}} \text{COGS}_t}{\frac{1}{N} \sum_{t \in \text{Year}} \text{ending\_inventory\_value}_t}$$

##### Technical Implementations:
- **ANSI SQL View:**
  ```sql
  SELECT 
      store_id,
      ROUND(SUM(cogs_amount) / NULLIF(AVG(ending_inventory_value), 0), 2) AS inventory_turnover
  FROM vw_daily_inventory_valuation
  GROUP BY store_id;
  ```
- **Vectorized Python:**
  ```python
  total_cogs = df_sales["cogs_amount"].sum()
  avg_inv_val = df_inventory["ending_inventory_value"].mean()
  inv_turnover = round(float(total_cogs / avg_inv_val), 2) if avg_inv_val > 0 else 0.0
  ```
- **Power BI DAX:**
  ```dax
  [Inventory Turnover] = 
  VAR TotalCOGS = [Total COGS]
  VAR AvgInventoryValue = AVERAGE(fact_inventory_snapshot[ending_inventory_value])
  RETURN
  DIVIDE(TotalCOGS, AvgInventoryValue, 0.00)
  ```

---

### 3. Automated Reconciliation Test Matrix

| Metric ID | Metric Name | Comparison Tolerance | Verification Script Target | Pass Criteria |
| :--- | :--- | :--- | :--- | :--- |
| `M-01` | Total Net Sales | $\pm \$0.01$ | `tests/reconciliation/test_metric_reconciliation.py` | $| \text{SQL} - \text{Python} | \le 0.01$ |
| `M-02` | Total COGS | $\pm \$0.01$ | `tests/reconciliation/test_metric_reconciliation.py` | $| \text{SQL} - \text{Python} | \le 0.01$ |
| `M-03` | Gross Profit | $\pm \$0.01$ | `tests/reconciliation/test_metric_reconciliation.py` | $| \text{SQL} - \text{Python} | \le 0.01$ |
| `M-04` | Gross Margin % | $\pm 0.01\%$ | `tests/reconciliation/test_metric_reconciliation.py` | $| \text{SQL} - \text{Python} | \le 0.01$ |
| `M-05` | Days of Supply | $\pm 0.1 \text{ days}$ | `tests/reconciliation/test_metric_reconciliation.py` | Max absolute delta $\le 0.1$ |
| `M-06` | Stockout Rate % | $\pm 0.01\%$ | `tests/reconciliation/test_metric_reconciliation.py` | $| \text{SQL} - \text{Python} | \le 0.01$ |
| `M-07` | Inventory Turnover | $\pm 0.01$ | `tests/reconciliation/test_metric_reconciliation.py` | $| \text{SQL} - \text{Python} | \le 0.01$ |

---
*Document Version: 1.0.0*  
*Author: RetailPulse Architecture Team*
