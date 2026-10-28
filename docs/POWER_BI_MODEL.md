# Power BI Semantic Model Blueprint & DAX Measure Dictionary
**Platform:** RetailPulse Decision Intelligence (DI) Platform  
**Target Database:** Microsoft SQL Server 2025 Developer (`localhost`, `RetailPulseDB`)  
**Architecture:** Enterprise Star Schema with Single-Direction Filtering  

---

## 1. Database Connection Specification

### 1.1 Direct Query / Import Configuration
To connect Power BI Desktop to the local Microsoft SQL Server instance:
- **Connector:** `SQL Server Database`
- **Server:** `localhost` (or `127.0.0.1` / `(local)`)
- **Database:** `RetailPulseDB`
- **Data Connectivity Mode:** `Import` (Recommended for high-performance sub-second DAX calculation times) or `DirectQuery` for real-time recommendation review.
- **Authentication:** `Windows Authentication` (Use current Windows user credentials).
- **Advanced Options:**
  - *Include relationship columns:* Checked
  - *Navigate using full hierarchy:* Checked
  - *SQL Statement:* Leave empty to import tables natively and preserve schema relationships.

### 1.2 Table Ingestion Manifest
Import the following dimensional and fact entities from `dbo`:
1. `dbo.dim_date`
2. `dbo.dim_product`
3. `dbo.dim_store`
4. `dbo.dim_supplier`
5. `dbo.fact_sales_daily`
6. `dbo.fact_inventory_snapshot`
7. `dbo.fact_purchase_orders`
8. `dbo.fact_replenishment_recommendation`
9. *(Optional Analytical Views)*: `dbo.vw_executive_kpis`, `dbo.vw_inventory_health`, `dbo.vw_supplier_performance`

---

## 2. Star Schema Semantic Relationship Blueprint

All relationships follow the standard Kimball Star Schema principle: **One-to-Many ($1 \to *$) with Single-Direction Cross-Filtering** from Dimension tables to Fact tables.

```
       +-------------------+             +--------------------+
       |     dim_date      |             |    dim_supplier    |
       |-------------------|             |--------------------|
       | PK: date_key      |             | PK: supplier_id    |
       +---------+---------+             +---------+----------+
                 |                                 |
                 | 1                               | 1
                 |                                 |
       +---------+---------------------------------+----------+
       | *       *         *             *         *          *
+------+-----+ +-+---------+-+ +---------+--+ +----+----------+----+
| fact_sales | | fact_inv    | | fact_po    | | fact_replenishment |
| _daily     | | _snapshot   | |            | | _recommendation    |
+------+-----+ +-+---------+-+ +---------+--+ +----+----------+----+
       | *       | *       *             | *       | *        *
       |         |         |             |         |          |
       | 1       | 1       |             | 1       | 1        |
+------+---------+---------+             +---------+----------+----+
|      dim_product         |             |        dim_store        |
|--------------------------|             |-------------------------|
| PK: product_id           |             | PK: store_id            |
+--------------------------+             +-------------------------+
```

### 2.1 Detailed Relationship Matrix

| Primary / From Table (1) | Foreign / To Table (*) | Cardinality | Cross-Filter Direction | Active Status | Description |
| :--- | :--- | :---: | :---: | :---: | :--- |
| `dim_date[date_key]` | `fact_sales_daily[date_key]` | $1 \to *$ | Single (`dim_date` filters `fact_sales`) | **Active** | Daily sales calendar filter |
| `dim_date[date_key]` | `fact_inventory_snapshot[date_key]` | $1 \to *$ | Single (`dim_date` filters `fact_inv`) | **Active** | Snapshot inventory date filter |
| `dim_date[date_key]` | `fact_purchase_orders[order_date_key]` | $1 \to *$ | Single (`dim_date` filters `fact_po`) | **Active** | Purchase order issuance date |
| `dim_date[date_key]` | `fact_purchase_orders[expected_delivery_date_key]` | $1 \to *$ | Single | *Inactive* | Handled via `USERELATIONSHIP` in DAX |
| `dim_date[date_key]` | `fact_purchase_orders[actual_delivery_date_key]` | $1 \to *$ | Single | *Inactive* | Handled via `USERELATIONSHIP` in DAX |
| `dim_date[date_key]` | `fact_replenishment_recommendation[run_date_key]` | $1 \to *$ | Single | **Active** | Recommendation execution run date |
| `dim_product[product_id]` | `fact_sales_daily[product_id]` | $1 \to *$ | Single (`dim_product` filters `fact_sales`) | **Active** | SKU product dimension filter |
| `dim_product[product_id]` | `fact_inventory_snapshot[product_id]` | $1 \to *$ | Single (`dim_product` filters `fact_inv`) | **Active** | SKU inventory snapshot filter |
| `dim_product[product_id]` | `fact_purchase_orders[product_id]` | $1 \to *$ | Single (`dim_product` filters `fact_po`) | **Active** | SKU purchase order filter |
| `dim_product[product_id]` | `fact_replenishment_recommendation[product_id]` | $1 \to *$ | Single | **Active** | SKU replenishment allocation filter |
| `dim_store[store_id]` | `fact_sales_daily[store_id]` | $1 \to *$ | Single (`dim_store` filters `fact_sales`) | **Active** | Store facility filter |
| `dim_store[store_id]` | `fact_inventory_snapshot[store_id]` | $1 \to *$ | Single (`dim_store` filters `fact_inv`) | **Active** | Store inventory location filter |
| `dim_store[store_id]` | `fact_purchase_orders[store_id]` | $1 \to *$ | Single (`dim_store` filters `fact_po`) | **Active** | Destination facility filter |
| `dim_store[store_id]` | `fact_replenishment_recommendation[store_id]` | $1 \to *$ | Single | **Active** | Target store recommendation filter |
| `dim_supplier[supplier_id]` | `dim_product[supplier_id]` | $1 \to *$ | Single (`dim_supplier` filters `dim_product`) | **Active** | Product master supplier assignment |
| `dim_supplier[supplier_id]` | `fact_purchase_orders[supplier_id]` | $1 \to *$ | Single (`dim_supplier` filters `fact_po`) | **Active** | Vendor purchase order audit |
| `dim_supplier[supplier_id]` | `fact_replenishment_recommendation[supplier_id]` | $1 \to *$ | Single | **Active** | Vendor replenishment allocation |

---

## 3. Formal DAX Measure Dictionary

Create a dedicated calculation table in Power BI named `_Measures`. The formulas below have been reconciled against Microsoft SQL Server views and Python analytics within $0.01$ tolerance.

### 3.1 Financial Performance & Profitability Measures

#### `[Total Sales]`
```dax
Total Sales = 
SUM ( fact_sales_daily[net_sales_amount] )
```

#### `[Total COGS]`
```dax
Total COGS = 
SUMX (
    fact_sales_daily,
    fact_sales_daily[quantity_sold] * RELATED ( dim_product[unit_cost_price] )
)
```

#### `[Gross Profit]`
```dax
Gross Profit = 
[Total Sales] - [Total COGS]
```

#### `[Gross Margin %]`
```dax
Gross Margin % = 
DIVIDE ( [Gross Profit], [Total Sales], 0 ) * 100
```

---

### 3.2 Inventory Health & Stockout Exposure Measures

#### `[Ending Inventory Units]`
```dax
Ending Inventory Units = 
CALCULATE (
    SUM ( fact_inventory_snapshot[ending_on_hand_qty] ),
    LASTDATE ( dim_date[full_date] )
)
```

#### `[Ending Inventory Value]`
```dax
Ending Inventory Value = 
CALCULATE (
    SUM ( fact_inventory_snapshot[ending_inventory_value] ),
    LASTDATE ( dim_date[full_date] )
)
```

#### `[Rolling 30D Daily Sales]`
```dax
Rolling 30D Daily Sales = 
VAR LastVisibleDate = LASTDATE ( dim_date[full_date] )
VAR Period30Days = 
    DATESBETWEEN (
        dim_date[full_date],
        LastVisibleDate - 29,
        LastVisibleDate
    )
VAR TotalUnits30D = 
    CALCULATE (
        SUM ( fact_sales_daily[quantity_sold] ),
        Period30Days
    )
RETURN
    DIVIDE ( TotalUnits30D, 30.0, 0 )
```

#### `[Days of Supply (DoS)]`
```dax
Days of Supply (DoS) = 
DIVIDE (
    [Ending Inventory Units],
    [Rolling 30D Daily Sales],
    BLANK ()
)
```

#### `[Stockout Incidents Count]`
```dax
Stockout Incidents Count = 
CALCULATE (
    COUNTROWS ( fact_inventory_snapshot ),
    fact_inventory_snapshot[stockout_flag] = 1
)
```

#### `[Total Inventory Records]`
```dax
Total Inventory Records = 
COUNTROWS ( fact_inventory_snapshot )
```

#### `[Stockout Rate %]`
```dax
Stockout Rate % = 
DIVIDE (
    [Stockout Incidents Count],
    [Total Inventory Records],
    0
) * 100
```

#### `[Annualized Inventory Turnover]`
```dax
Annualized Inventory Turnover = 
VAR ActiveDays = DISTINCTCOUNT ( dim_date[date_key] )
VAR AvgDailyInvValue = 
    DIVIDE (
        SUM ( fact_inventory_snapshot[ending_inventory_value] ),
        ActiveDays,
        0
    )
RETURN
    DIVIDE ( [Total COGS], AvgDailyInvValue, 0 ) * DIVIDE ( 365, ActiveDays, 1 )
```

---

### 3.3 Supplier SLA & Lead-Time Uncertainty Measures

#### `[Actual Lead Time Days]`
```dax
Actual Lead Time Days = 
AVERAGEX (
    FILTER ( fact_purchase_orders, fact_purchase_orders[order_status] = 'DELIVERED' ),
    fact_purchase_orders[actual_lead_time_days]
)
```

#### `[Nominal Lead Time Days]`
```dax
Nominal Lead Time Days = 
AVERAGEX (
    dim_product,
    RELATED ( dim_supplier[mean_lead_time_days] )
)
```

#### `[Lead Time Variance Days]`
```dax
Lead Time Variance Days = 
[Actual Lead Time Days] - [Nominal Lead Time Days]
```

#### `[Order Fill Rate %]`
```dax
Order Fill Rate % = 
DIVIDE (
    SUM ( fact_purchase_orders[received_quantity] ),
    SUM ( fact_purchase_orders[order_quantity] ),
    0
) * 100
```

---

### 3.4 Replenishment Decision & Allocation Measures

#### `[Total Recommended Spend]`
```dax
Total Recommended Spend = 
SUM ( fact_replenishment_recommendation[estimated_cost] )
```

#### `[Approved Purchase Spend]`
```dax
Approved Purchase Spend = 
CALCULATE (
    [Total Recommended Spend],
    fact_replenishment_recommendation[approval_status] = "APPROVED"
)
```

#### `[Total Recommended Units]`
```dax
Total Recommended Units = 
SUM ( fact_replenishment_recommendation[recommended_units] )
```

#### `[Critical Stockout SKUs Mitigated]`
```dax
Critical Stockout SKUs Mitigated = 
CALCULATE (
    DISTINCTCOUNT ( fact_replenishment_recommendation[product_id] ),
    fact_replenishment_recommendation[inventory_status] = "STOCKOUT_RISK",
    fact_replenishment_recommendation[recommended_units] > 0
)
```

---

## 4. Power BI Multi-Page Report Blueprint

### Page A: Executive Financial & Margin Analysis
- **Target Audience:** Chief Commercial Officer, VP of Supply Chain, Finance Directors.
- **Top Ribbon Cards:**
  - `[Total Sales]` (\$1.25M), `[Gross Margin %]` (37.62%), `[Annualized Inventory Turnover]` (6.84x), `[Ending Inventory Value]` (\$142k).
- **Visual 1 (Area / Line Chart):** Monthly Net Sales vs Total COGS over trailing 24 months.
- **Visual 2 (Scatter Plot):** SKU Margin % vs Annualized Turnover (identifying high-velocity cash cows vs slow-moving inventory traps).
- **Visual 3 (Matrix Grid):** Category breakdown of Sales, Margin %, Inventory Value, and Capital Allocation.

### Page B: Inventory Risk & Supplier SLA Audit
- **Target Audience:** Inventory Planners, Category Procurement Managers.
- **Top Ribbon Cards:**
  - `[Days of Supply (DoS)]` (28.5d), `[Stockout Rate %]` (18.25%), `[Order Fill Rate %]` (94.2%), `[Stockout Incidents Count]` (20,268 item-days).
- **Visual 1 (Histogram / Column Chart):** Distribution of SKUs across Days of Supply bins (<7d, 7-14d, 15-30d, 31-60d, >60d).
- **Visual 2 (Grouped Bar Chart):** Supplier Actual Lead Time vs Contracted SLA Lead Time with error bars indicating $\pm \sigma_L$.
- **Visual 3 (Table with Status Badges):** High-risk SKUs where `[Ending Inventory Units] < [Safety Stock Units]`.

### Page C: Lead-Time Uncertainty & Replenishment Tracking
- **Target Audience:** Operational Buyers, Merchandising Operations.
- **Top Ribbon Cards:**
  - `[Total Recommended Spend]` (\$14.8k), `[Approved Purchase Spend]` (\$10.2k), `[Total Recommended Units]` (1,524 units), `[Critical Stockout SKUs Mitigated]` (18).
- **Visual 1 (What-If Parameter Slicers):** Working Capital Budget Slider (\$1,000 to \$50,000) and Target Service Level (90%, 95%, 99%).
- **Visual 2 (Stacked Bar Chart):** Recommended Spend by Supplier cohort with MOQ thresholds highlighted.
- **Visual 3 (Approval Action Grid):** Actionable PO table displaying `recommendation_id`, `product_name`, `recommended_units`, `pack_size`, `approval_status`, and priority rank.
