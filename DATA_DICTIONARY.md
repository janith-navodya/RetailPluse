# RETAILPULSE DECISION INTELLIGENCE (DI)
## ENTERPRISE DATA DICTIONARY & DIMENSIONAL STAR SCHEMA

---

### 1. Architectural Overview & Design Principles

The analytical data foundation of **RetailPulse DI** adheres strictly to Ralph Kimball's Dimensional Modeling standards. It utilizes a canonical **Star Schema** optimized for high-performance aggregate rollups, intuitive BI slicing, and zero joins across normalized OLTP tables.

#### Key Design Principles:
- **Surrogate & Natural Keys:** Fact tables link to dimensions via standardized natural business keys (`product_id`, `store_id`, `supplier_id`) and integer date surrogate keys (`date_key` format `YYYYMMDD`).
- **Granularity Guarantee:** The atomic grain of `fact_sales_daily` and `fact_inventory_snapshot` is strictly **one row per Product, per Store, per Day**.
- **Audit & Lineage:** Every fact and quarantine table includes ETL lineage metadata (`batch_id`, `ingested_at`) ensuring auditability and idempotency.
- **Portability:** DDL is written in ANSI SQL standard, fully compatible with SQLite, Microsoft SQL Server, and PostgreSQL.

---

### 2. Star Schema Entity Relationship Overview

```
                      +-------------------+
                      |     dim_date      |
                      +-------------------+
                      | PK  date_key      |
                      |     full_date     |
                      |     day_of_week   |
                      |     is_weekend    |
                      +--------+----------+
                               |
                               | (1:N)
+-------------------+          |          +-------------------+
|    dim_store      |          |          |    dim_product    |
+-------------------+          |          +-------------------+
| PK  store_id      |          |          | PK  product_id    |
|     store_name    |----+     |     +----|     product_name  |
|     store_format  |    |     |     |    |     category      |
|     storage_cap   |    |     |     |    |     pack_size     |
+-------------------+    |     |     |    | FK  supplier_id   |
                         |     |     |    +---------+---------+
                         |     |     |              |
                         v     v     v              |
             +-------------------------------+      |
             |       fact_sales_daily        |      |
             +-------------------------------+      |
             | PK(FK) date_key               |      |
             | PK(FK) store_id               |      |
             | PK(FK) product_id             |      |
             |        quantity_sold          |      |
             |        gross_sales_amount     |      |
             |        net_sales_amount       |      |
             |        cogs_amount            |      |
             |        gross_profit_amount    |      |
             +-------------------------------+      |
                                                    |
             +-------------------------------+      |
             |   fact_inventory_snapshot     |      |
             +-------------------------------+      |
             | PK(FK) date_key               |      |
             | PK(FK) store_id               |      |
             | PK(FK) product_id             |      |
             |        beginning_on_hand_qty  |      |
             |        received_qty           |      |
             |        sold_qty               |      |
             |        ending_on_hand_qty     |      |
             |        ending_inventory_value |      |
             |        is_stockout            |      |
             +-------------------------------+      |
                                                    |
             +-------------------------------+      |
             |     fact_purchase_orders      |      |
             +-------------------------------+      |
             | PK     po_id                  |      |
             | FK     order_date_key         |      |
             | FK     expected_deliv_date_key|      |
             | FK     actual_deliv_date_key  |      |
             | FK     store_id               |      |
             | FK     product_id             |<-----+
             | FK     supplier_id            |<-----+ (1:N)
             |        order_qty              |      |
             |        received_qty           |      |
             |        total_cost_amount      |      |
             |        status                 |      |
             +-------------------------------+      |
                                                    |
                                          +---------+---------+
                                          |   dim_supplier    |
                                          +-------------------+
                                          | PK  supplier_id   |
                                          |     supplier_name |
                                          |     lead_time_mean|
                                          |     lead_time_std |
                                          |     min_order_qty |
                                          +-------------------+
```

---

### 3. Detailed Dimension Tables

#### `dim_date`
Provides chronological attributes for time-series aggregation, rolling window partitioning, and calendar slicing.
- **Grain:** One row per calendar day.

| Column Name | Data Type | Nullable | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `date_key` | `INTEGER` | NO | `PRIMARY KEY` | Integer surrogate key format `YYYYMMDD` (e.g., `20250101`). |
| `full_date` | `DATE` | NO | `UNIQUE` | Calendar date (`YYYY-MM-DD`). |
| `day_of_week` | `INTEGER` | NO | `CHECK (1 TO 7)` | 1 = Monday, 7 = Sunday (ISO 8601). |
| `day_name` | `VARCHAR(10)` | NO | | English day name (`Monday`, `Tuesday`, etc.). |
| `day_of_month` | `INTEGER` | NO | `CHECK (1 TO 31)` | Day of the month. |
| `month_num` | `INTEGER` | NO | `CHECK (1 TO 12)` | Month number (1 = January, 12 = December). |
| `month_name` | `VARCHAR(10)` | NO | | English month name (`January`, `February`, etc.). |
| `quarter` | `INTEGER` | NO | `CHECK (1 TO 4)` | Calendar quarter (1, 2, 3, 4). |
| `year` | `INTEGER` | NO | | Four-digit calendar year (e.g., `2025`). |
| `is_weekend` | `INTEGER` | NO | `CHECK (0 OR 1)` | Boolean flag: 1 if Saturday or Sunday, else 0. |
| `is_holiday` | `INTEGER` | NO | `CHECK (0 OR 1)` | Boolean flag: 1 if designated statutory retail holiday. |

---

#### `dim_store`
Captures retail outlet structural attributes, operating format, and physical warehouse limits.
- **Grain:** One row per retail store location.

| Column Name | Data Type | Nullable | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `store_id` | `VARCHAR(10)` | NO | `PRIMARY KEY` | Unique store code (e.g., `STR01`, `STR02`). |
| `store_name` | `VARCHAR(100)` | NO | | Human-readable store location name. |
| `store_format` | `VARCHAR(30)` | NO | | Retail format (`Flagship Urban`, `Suburban Superstore`, `Express`). |
| `city` | `VARCHAR(50)` | NO | | City location. |
| `state` | `VARCHAR(50)` | NO | | State/Province jurisdiction. |
| `square_footage` | `INTEGER` | NO | `CHECK (> 0)` | Total store floor area in sq. ft. |
| `storage_capacity_units` | `INTEGER` | NO | `CHECK (> 0)` | Maximum backroom physical holding capacity (units). |

---

#### `dim_supplier`
Encapsulates vendor contractual terms, lead time distributions, and procurement thresholds.
- **Grain:** One row per commercial supplier.

| Column Name | Data Type | Nullable | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `supplier_id` | `VARCHAR(10)` | NO | `PRIMARY KEY` | Unique supplier identifier (e.g., `SUP01`). |
| `supplier_name` | `VARCHAR(100)` | NO | | Legal commercial entity name. |
| `contact_email` | `VARCHAR(100)` | NO | | Procurement contact email. |
| `mean_lead_time_days` | `REAL` | NO | `CHECK (>= 1.0)` | Contractual average delivery transit time in days. |
| `lead_time_std_dev` | `REAL` | NO | `CHECK (>= 0.0)` | Historical standard deviation of lead time transit $\sigma_L$. |
| `min_order_qty` | `INTEGER` | NO | `CHECK (>= 1)` | Minimum acceptable purchase order quantity (MOQ). |
| `service_level_target_pct` | `REAL` | NO | `CHECK (>= 50.0 AND <= 99.9)` | Agreed contractual vendor fulfillment SLA percentage. |

---

#### `dim_product`
Contains SKU merchandising hierarchies, master pricing, packaging multiples, and vendor assignments.
- **Grain:** One row per unique retail stock keeping unit (SKU).

| Column Name | Data Type | Nullable | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `product_id` | `VARCHAR(10)` | NO | `PRIMARY KEY` | Unique SKU identifier (e.g., `PRD01`). |
| `product_name` | `VARCHAR(100)` | NO | | Commercial product label. |
| `category` | `VARCHAR(50)` | NO | | Department/Category (`Perishables`, `Ambient Grocery`, `Electronics`, etc.). |
| `sub_category` | `VARCHAR(50)` | NO | | Sub-classification. |
| `supplier_id` | `VARCHAR(10)` | NO | `FOREIGN KEY` | Primary vendor supplying this SKU (`REFERENCES dim_supplier(supplier_id)`). |
| `unit_cost_price` | `NUMERIC(10, 2)` | NO | `CHECK (> 0)` | Base wholesale procurement price per unit (\$ USD). |
| `unit_retail_price` | `NUMERIC(10, 2)` | NO | `CHECK (> unit_cost_price)` | Base retail selling price (\$ USD). Must exceed cost price. |
| `pack_size` | `INTEGER` | NO | `CHECK (>= 1)` | Case/Pack multiple for procurement (e.g., 6, 12, 24). |
| `shelf_life_days` | `INTEGER` | YES | `CHECK (> 0)` | Perishability threshold in days; NULL for non-perishables. |

---

### 4. Detailed Fact Tables

#### `fact_sales_daily`
Records daily realized customer transactions at the SKU-store level.
- **Grain:** One row per `(date_key, store_id, product_id)`.

| Column Name | Data Type | Nullable | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `date_key` | `INTEGER` | NO | `PK, FK -> dim_date` | Date of sales activity. |
| `store_id` | `VARCHAR(10)` | NO | `PK, FK -> dim_store` | Store where transaction occurred. |
| `product_id` | `VARCHAR(10)` | NO | `PK, FK -> dim_product` | Product sold. |
| `quantity_sold` | `INTEGER` | NO | `CHECK (>= 0)` | Total units sold to customers on that day. |
| `gross_sales_amount` | `NUMERIC(12, 2)` | NO | `CHECK (>= 0.00)` | Units Sold $\times$ Retail Price before promotions. |
| `discount_amount` | `NUMERIC(12, 2)` | NO | `CHECK (>= 0.00)` | Total promotional discount deducted. |
| `net_sales_amount` | `NUMERIC(12, 2)` | NO | `CHECK (>= 0.00)` | Gross Sales - Discount Amount. |
| `cogs_amount` | `NUMERIC(12, 2)` | NO | `CHECK (>= 0.00)` | Units Sold $\times$ Unit Cost Price. |
| `gross_profit_amount` | `NUMERIC(12, 2)` | NO | | Net Sales Amount - COGS Amount. |
| `is_promotional` | `INTEGER` | NO | `CHECK (0 OR 1)` | 1 if active promotional campaign was executed, else 0. |
| `batch_id` | `VARCHAR(50)` | NO | | ETL execution batch GUID / timestamp identifier. |
| `ingested_at` | `TIMESTAMP` | NO | | System UTC timestamp when record was committed. |

---

#### `fact_inventory_snapshot`
Maintains daily closing inventory state, movement audit, and stockout flags for demand uncensoring.
- **Grain:** One row per `(date_key, store_id, product_id)`.

| Column Name | Data Type | Nullable | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `date_key` | `INTEGER` | NO | `PK, FK -> dim_date` | Snapshot date. |
| `store_id` | `VARCHAR(10)` | NO | `PK, FK -> dim_store` | Store location. |
| `product_id` | `VARCHAR(10)` | NO | `PK, FK -> dim_product` | Product inventory tracked. |
| `beginning_on_hand_qty`| `INTEGER` | NO | `CHECK (>= 0)` | Physical units on shelf at store opening. |
| `received_qty` | `INTEGER` | NO | `CHECK (>= 0)` | Purchase order units physically received and stocked today. |
| `sold_qty` | `INTEGER` | NO | `CHECK (>= 0)` | Realized unit sales deducted today. |
| `ending_on_hand_qty` | `INTEGER` | NO | `CHECK (>= 0)` | Beginning + Received - Sold. Closing physical count. |
| `ending_inventory_value`| `NUMERIC(12, 2)`| NO | `CHECK (>= 0.00)`| Ending On Hand $\times$ Unit Cost Price (\$ USD). |
| `is_stockout` | `INTEGER` | NO | `CHECK (0 OR 1)` | 1 if `ending_on_hand_qty == 0` (censored demand flag). |
| `batch_id` | `VARCHAR(50)` | NO | | ETL batch lineage identifier. |
| `ingested_at` | `TIMESTAMP` | NO | | System UTC ingestion timestamp. |

---

#### `fact_purchase_orders`
Tracks the procurement lifecycle from order issuance to warehouse delivery receipt.
- **Grain:** One row per purchase order line item.

| Column Name | Data Type | Nullable | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `po_id` | `VARCHAR(30)` | NO | `PRIMARY KEY` | Unique purchase order tracking number (e.g., `PO-20250315-001`). |
| `order_date_key` | `INTEGER` | NO | `FK -> dim_date` | Date order was placed with supplier. |
| `expected_delivery_date_key` | `INTEGER` | NO | `FK -> dim_date` | Quoted delivery arrival date. |
| `actual_delivery_date_key` | `INTEGER` | YES | `FK -> dim_date` | Realized arrival date; NULL while in-transit. |
| `store_id` | `VARCHAR(10)` | NO | `FK -> dim_store` | Destination store warehouse. |
| `product_id` | `VARCHAR(10)` | NO | `FK -> dim_product` | Ordered SKU. |
| `supplier_id` | `VARCHAR(10)` | NO | `FK -> dim_supplier` | Vendor receiving the purchase order. |
| `order_qty` | `INTEGER` | NO | `CHECK (> 0)` | Ordered units (must be multiple of pack_size and $\ge$ MOQ). |
| `received_qty` | `INTEGER` | NO | `CHECK (>= 0)` | Units actually received upon arrival. 0 while in-transit. |
| `unit_cost_price` | `NUMERIC(10, 2)`| NO | `CHECK (> 0.00)` | Contractual unit purchase price locked at PO generation. |
| `total_cost_amount` | `NUMERIC(12, 2)`| NO | `CHECK (> 0.00)` | Order Qty $\times$ Unit Cost Price. |
| `status` | `VARCHAR(20)` | NO | | Order lifecycle state (`PLACED`, `IN_TRANSIT`, `DELIVERED`, `CANCELLED`). |
| `batch_id` | `VARCHAR(50)` | NO | | ETL batch lineage identifier. |
| `ingested_at` | `TIMESTAMP` | NO | | System UTC ingestion timestamp. |

---

### 5. Data Quality, Quarantine & Lineage Tables

#### `quarantine_invalid_records`
Dead-letter table isolating malformed, invalid, or corrupted source records. Prevents pipeline failure while preserving corrupted payloads for audit and reprocessing.
- **Grain:** One row per rejected raw record.

| Column Name | Data Type | Nullable | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `quarantine_id` | `INTEGER` | NO | `PRIMARY KEY AUTOINCREMENT` | Auto-incrementing audit surrogate key. |
| `source_feed` | `VARCHAR(50)` | NO | | Originating source data stream (e.g., `raw_sales`, `raw_pos`). |
| `raw_payload_json` | `TEXT` | NO | | Exact stringified JSON record payload rejected by validator. |
| `violation_category` | `VARCHAR(50)` | NO | | Category (`SCHEMA_ERROR`, `ORPHAN_KEY`, `DOMAIN_VIOLATION`). |
| `violation_details` | `TEXT` | NO | | Detailed error description or Pydantic validation trace. |
| `rejected_at` | `TIMESTAMP` | NO | | UTC timestamp of rejection. |
| `batch_id` | `VARCHAR(50)` | NO | | ETL batch identifier in which rejection occurred. |

---

#### `etl_batch_log`
Provides end-to-end ingestion observability, processing duration, and quality quarantine ratios.
- **Grain:** One row per ETL pipeline execution.

| Column Name | Data Type | Nullable | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `batch_id` | `VARCHAR(50)` | NO | `PRIMARY KEY` | Unique batch execution GUID. |
| `pipeline_name` | `VARCHAR(50)` | NO | | Name of pipeline module executed. |
| `status` | `VARCHAR(20)` | NO | | Execution state (`STARTED`, `COMPLETED`, `FAILED`). |
| `records_processed` | `INTEGER` | NO | | Total raw input records parsed. |
| `records_loaded` | `INTEGER` | NO | | Successfully validated records committed to fact tables. |
| `records_quarantined`| `INTEGER` | NO | | Corrupted records redirected to dead-letter quarantine. |
| `started_at` | `TIMESTAMP` | NO | | UTC start timestamp. |
| `completed_at` | `TIMESTAMP` | YES | | UTC termination timestamp. |

---
*Document Version: 1.0.0*  
*Author: RetailPulse Architecture Team*

