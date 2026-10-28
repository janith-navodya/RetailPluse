-- ============================================================================
-- RETAILPULSE DECISION INTELLIGENCE (DI)
-- DDL SCRIPT 01: DIMENSIONAL STAR SCHEMA
-- Compatible with ANSI SQL, SQLite 3, PostgreSQL 14+, Microsoft SQL Server 2019+
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. DIMENSION TABLES
-- ----------------------------------------------------------------------------

-- Dimension: Date
CREATE TABLE IF NOT EXISTS dim_date (
    date_key                INTEGER NOT NULL PRIMARY KEY, -- Format: YYYYMMDD
    full_date               DATE NOT NULL UNIQUE,
    day_of_week             INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7), -- 1=Mon, 7=Sun
    day_name                VARCHAR(10) NOT NULL,
    day_of_month            INTEGER NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    month_num               INTEGER NOT NULL CHECK (month_num BETWEEN 1 AND 12),
    month_name              VARCHAR(10) NOT NULL,
    quarter                 INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    year                    INTEGER NOT NULL,
    is_weekend              INTEGER NOT NULL CHECK (is_weekend IN (0, 1)),
    is_holiday              INTEGER NOT NULL CHECK (is_holiday IN (0, 1))
);

-- Dimension: Store
CREATE TABLE IF NOT EXISTS dim_store (
    store_id                VARCHAR(10) NOT NULL PRIMARY KEY,
    store_name              VARCHAR(100) NOT NULL,
    store_format            VARCHAR(30) NOT NULL, -- 'Flagship Urban', 'Suburban Superstore', 'Express'
    city                    VARCHAR(50) NOT NULL,
    state                   VARCHAR(50) NOT NULL,
    square_footage          INTEGER NOT NULL CHECK (square_footage > 0),
    storage_capacity_units  INTEGER NOT NULL CHECK (storage_capacity_units > 0)
);

-- Dimension: Supplier
CREATE TABLE IF NOT EXISTS dim_supplier (
    supplier_id             VARCHAR(10) NOT NULL PRIMARY KEY,
    supplier_name           VARCHAR(100) NOT NULL,
    contact_email           VARCHAR(100) NOT NULL,
    mean_lead_time_days     REAL NOT NULL CHECK (mean_lead_time_days >= 1.0),
    lead_time_std_dev       REAL NOT NULL CHECK (lead_time_std_dev >= 0.0),
    min_order_qty           INTEGER NOT NULL CHECK (min_order_qty >= 1),
    service_level_target_pct REAL NOT NULL CHECK (service_level_target_pct BETWEEN 50.0 AND 99.9)
);

-- Dimension: Product
CREATE TABLE IF NOT EXISTS dim_product (
    product_id              VARCHAR(10) NOT NULL PRIMARY KEY,
    product_name            VARCHAR(100) NOT NULL,
    category                VARCHAR(50) NOT NULL,
    sub_category            VARCHAR(50) NOT NULL,
    brand                   VARCHAR(50) NOT NULL,
    supplier_id             VARCHAR(10) NOT NULL,
    unit_cost_price         NUMERIC(10, 2) NOT NULL CHECK (unit_cost_price > 0),
    unit_retail_price       NUMERIC(10, 2) NOT NULL CHECK (unit_retail_price > unit_cost_price),
    pack_size               INTEGER NOT NULL CHECK (pack_size >= 1),
    shelf_life_days         INTEGER NULL CHECK (shelf_life_days IS NULL OR shelf_life_days > 0),
    FOREIGN KEY (supplier_id) REFERENCES dim_supplier(supplier_id)
);

-- ----------------------------------------------------------------------------
-- 2. FACT TABLES
-- ----------------------------------------------------------------------------

-- Fact: Daily Sales Transactions
CREATE TABLE IF NOT EXISTS fact_sales_daily (
    date_key                INTEGER NOT NULL,
    store_id                VARCHAR(10) NOT NULL,
    product_id              VARCHAR(10) NOT NULL,
    quantity_sold           INTEGER NOT NULL CHECK (quantity_sold >= 0),
    gross_sales_amount      NUMERIC(12, 2) NOT NULL CHECK (gross_sales_amount >= 0.00),
    discount_amount         NUMERIC(12, 2) NOT NULL CHECK (discount_amount >= 0.00),
    net_sales_amount        NUMERIC(12, 2) NOT NULL CHECK (net_sales_amount >= 0.00),
    cogs_amount             NUMERIC(12, 2) NOT NULL CHECK (cogs_amount >= 0.00),
    gross_profit_amount     NUMERIC(12, 2) NOT NULL,
    is_promotional          INTEGER NOT NULL CHECK (is_promotional IN (0, 1)),
    batch_id                VARCHAR(50) NOT NULL,
    ingested_at             TIMESTAMP NOT NULL,
    PRIMARY KEY (date_key, store_id, product_id),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id)
);

-- Fact: Daily Closing Inventory Snapshot
CREATE TABLE IF NOT EXISTS fact_inventory_snapshot (
    date_key                INTEGER NOT NULL,
    store_id                VARCHAR(10) NOT NULL,
    product_id              VARCHAR(10) NOT NULL,
    beginning_on_hand_qty   INTEGER NOT NULL CHECK (beginning_on_hand_qty >= 0),
    received_qty            INTEGER NOT NULL CHECK (received_qty >= 0),
    sold_qty                INTEGER NOT NULL CHECK (sold_qty >= 0),
    ending_on_hand_qty      INTEGER NOT NULL CHECK (ending_on_hand_qty >= 0),
    ending_inventory_value  NUMERIC(12, 2) NOT NULL CHECK (ending_inventory_value >= 0.00),
    is_stockout             INTEGER NOT NULL CHECK (is_stockout IN (0, 1)),
    batch_id                VARCHAR(50) NOT NULL,
    ingested_at             TIMESTAMP NOT NULL,
    PRIMARY KEY (date_key, store_id, product_id),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id)
);

-- Fact: Purchase Orders (Procurement Lifecycle)
CREATE TABLE IF NOT EXISTS fact_purchase_orders (
    po_id                   VARCHAR(30) NOT NULL PRIMARY KEY,
    order_date_key          INTEGER NOT NULL,
    expected_delivery_date_key INTEGER NOT NULL,
    actual_delivery_date_key INTEGER NULL,
    store_id                VARCHAR(10) NOT NULL,
    product_id              VARCHAR(10) NOT NULL,
    supplier_id             VARCHAR(10) NOT NULL,
    order_qty               INTEGER NOT NULL CHECK (order_qty > 0),
    received_qty            INTEGER NOT NULL CHECK (received_qty >= 0),
    unit_cost_price         NUMERIC(10, 2) NOT NULL CHECK (unit_cost_price > 0.00),
    total_cost_amount       NUMERIC(12, 2) NOT NULL CHECK (total_cost_amount > 0.00),
    status                  VARCHAR(20) NOT NULL CHECK (status IN ('PLACED', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED')),
    batch_id                VARCHAR(50) NOT NULL,
    ingested_at             TIMESTAMP NOT NULL,
    FOREIGN KEY (order_date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (expected_delivery_date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (actual_delivery_date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
    FOREIGN KEY (product_id) REFERENCES dim_product(product_id),
    FOREIGN KEY (supplier_id) REFERENCES dim_supplier(supplier_id)
);

-- ----------------------------------------------------------------------------
-- 3. PERFORMANCE INDEXES
-- ----------------------------------------------------------------------------

-- Indexes on Fact Sales
CREATE INDEX IF NOT EXISTS idx_sales_date ON fact_sales_daily(date_key);
CREATE INDEX IF NOT EXISTS idx_sales_store_prod ON fact_sales_daily(store_id, product_id);

-- Indexes on Fact Inventory Snapshot
CREATE INDEX IF NOT EXISTS idx_inv_date ON fact_inventory_snapshot(date_key);
CREATE INDEX IF NOT EXISTS idx_inv_store_prod ON fact_inventory_snapshot(store_id, product_id);
CREATE INDEX IF NOT EXISTS idx_inv_stockout ON fact_inventory_snapshot(is_stockout);

-- Indexes on Fact Purchase Orders
CREATE INDEX IF NOT EXISTS idx_po_dates ON fact_purchase_orders(order_date_key, expected_delivery_date_key);
CREATE INDEX IF NOT EXISTS idx_po_supplier ON fact_purchase_orders(supplier_id);
CREATE INDEX IF NOT EXISTS idx_po_status ON fact_purchase_orders(status);
