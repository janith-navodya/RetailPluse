-- ============================================================================
-- RETAILPULSE DECISION INTELLIGENCE (DI)
-- DDL SCRIPT 01: MICROSOFT SQL SERVER STAR SCHEMA (T-SQL)
-- Database Target: RetailPulseDI
-- Authentication: Windows Integrated (-E) | Driver: ODBC Driver 18
-- ============================================================================

USE RetailPulseDI;
GO

-- ----------------------------------------------------------------------------
-- 1. DIMENSION TABLES
-- ----------------------------------------------------------------------------

-- Dimension: dim_date
IF OBJECT_ID(N'dbo.dim_date', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.dim_date (
        date_key                INT NOT NULL CONSTRAINT PK_dim_date PRIMARY KEY, -- Format: YYYYMMDD
        full_date               DATE NOT NULL CONSTRAINT UQ_dim_date_full UNIQUE,
        day_of_week             TINYINT NOT NULL CONSTRAINT CK_dim_date_dow CHECK (day_of_week BETWEEN 1 AND 7), -- 1=Mon, 7=Sun
        day_name                VARCHAR(10) NOT NULL,
        day_of_month            TINYINT NOT NULL CONSTRAINT CK_dim_date_dom CHECK (day_of_month BETWEEN 1 AND 31),
        month_num               TINYINT NOT NULL CONSTRAINT CK_dim_date_month CHECK (month_num BETWEEN 1 AND 12),
        month_name              VARCHAR(10) NOT NULL,
        quarter                 TINYINT NOT NULL CONSTRAINT CK_dim_date_quarter CHECK (quarter BETWEEN 1 AND 4),
        year                    SMALLINT NOT NULL,
        is_weekend              TINYINT NOT NULL CONSTRAINT CK_dim_date_weekend CHECK (is_weekend IN (0, 1)),
        is_holiday              TINYINT NOT NULL CONSTRAINT CK_dim_date_holiday CHECK (is_holiday IN (0, 1))
    );
END
GO

-- Dimension: dim_supplier
IF OBJECT_ID(N'dbo.dim_supplier', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.dim_supplier (
        supplier_id             VARCHAR(10) NOT NULL CONSTRAINT PK_dim_supplier PRIMARY KEY,
        supplier_name           VARCHAR(100) NOT NULL,
        contact_email           VARCHAR(100) NOT NULL,
        mean_lead_time_days     FLOAT NOT NULL CONSTRAINT CK_dim_supplier_mean_lt CHECK (mean_lead_time_days >= 1.0),
        lead_time_std_dev       FLOAT NOT NULL CONSTRAINT CK_dim_supplier_lt_std CHECK (lead_time_std_dev >= 0.0),
        min_order_qty           INT NOT NULL CONSTRAINT CK_dim_supplier_moq CHECK (min_order_qty >= 1),
        service_level_target_pct FLOAT NOT NULL CONSTRAINT CK_dim_supplier_sla CHECK (service_level_target_pct BETWEEN 50.0 AND 99.9)
    );
END
GO

-- Dimension: dim_store (Multi-echelon dimension)
IF OBJECT_ID(N'dbo.dim_store', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.dim_store (
        store_id                VARCHAR(10) NOT NULL CONSTRAINT PK_dim_store PRIMARY KEY,
        store_name              VARCHAR(100) NOT NULL,
        store_format            VARCHAR(30) NOT NULL, -- 'Flagship Urban', 'Suburban Superstore', 'Express'
        city                    VARCHAR(50) NOT NULL,
        state                   VARCHAR(50) NOT NULL,
        square_footage          INT NOT NULL CONSTRAINT CK_dim_store_sqft CHECK (square_footage > 0),
        storage_capacity_units  INT NOT NULL CONSTRAINT CK_dim_store_storage CHECK (storage_capacity_units > 0)
    );
END
GO

-- Dimension: dim_product
IF OBJECT_ID(N'dbo.dim_product', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.dim_product (
        product_id              VARCHAR(10) NOT NULL CONSTRAINT PK_dim_product PRIMARY KEY,
        product_name            VARCHAR(100) NOT NULL,
        category                VARCHAR(50) NOT NULL,
        sub_category            VARCHAR(50) NOT NULL,
        brand                   VARCHAR(50) NOT NULL,
        supplier_id             VARCHAR(10) NOT NULL CONSTRAINT FK_dim_product_supplier REFERENCES dbo.dim_supplier(supplier_id),
        unit_cost_price         DECIMAL(10, 2) NOT NULL CONSTRAINT CK_dim_product_cost CHECK (unit_cost_price > 0),
        unit_retail_price       DECIMAL(10, 2) NOT NULL,
        pack_size               INT NOT NULL CONSTRAINT CK_dim_product_pack CHECK (pack_size >= 1),
        shelf_life_days         INT NULL CONSTRAINT CK_dim_product_shelf CHECK (shelf_life_days IS NULL OR shelf_life_days > 0),
        CONSTRAINT CK_dim_product_retail_exceeds_cost CHECK (unit_retail_price > unit_cost_price)
    );
END
GO

-- ----------------------------------------------------------------------------
-- 2. FACT TABLES
-- ----------------------------------------------------------------------------

-- Fact: fact_sales_daily
IF OBJECT_ID(N'dbo.fact_sales_daily', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.fact_sales_daily (
        date_key                INT NOT NULL CONSTRAINT FK_fact_sales_date REFERENCES dbo.dim_date(date_key),
        store_id                VARCHAR(10) NOT NULL CONSTRAINT FK_fact_sales_store REFERENCES dbo.dim_store(store_id),
        product_id              VARCHAR(10) NOT NULL CONSTRAINT FK_fact_sales_product REFERENCES dbo.dim_product(product_id),
        quantity_sold           INT NOT NULL CONSTRAINT CK_fact_sales_qty CHECK (quantity_sold >= 0),
        gross_sales_amount      DECIMAL(12, 2) NOT NULL CONSTRAINT CK_fact_sales_gross CHECK (gross_sales_amount >= 0.00),
        discount_amount         DECIMAL(12, 2) NOT NULL CONSTRAINT CK_fact_sales_discount CHECK (discount_amount >= 0.00),
        net_sales_amount        DECIMAL(12, 2) NOT NULL CONSTRAINT CK_fact_sales_net CHECK (net_sales_amount >= 0.00),
        cogs_amount             DECIMAL(12, 2) NOT NULL CONSTRAINT CK_fact_sales_cogs CHECK (cogs_amount >= 0.00),
        gross_profit_amount     DECIMAL(12, 2) NOT NULL,
        is_promotional          TINYINT NOT NULL CONSTRAINT CK_fact_sales_promo CHECK (is_promotional IN (0, 1)),
        batch_id                VARCHAR(50) NOT NULL,
        ingested_at             DATETIME2(0) NOT NULL CONSTRAINT DF_fact_sales_ingested DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_fact_sales_daily PRIMARY KEY CLUSTERED (date_key, store_id, product_id)
    );
END
GO

-- Fact: fact_inventory_snapshot (Captures physical stock & stockout censoring flags)
IF OBJECT_ID(N'dbo.fact_inventory_snapshot', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.fact_inventory_snapshot (
        date_key                INT NOT NULL CONSTRAINT FK_fact_inv_date REFERENCES dbo.dim_date(date_key),
        store_id                VARCHAR(10) NOT NULL CONSTRAINT FK_fact_inv_store REFERENCES dbo.dim_store(store_id),
        product_id              VARCHAR(10) NOT NULL CONSTRAINT FK_fact_inv_product REFERENCES dbo.dim_product(product_id),
        beginning_on_hand_qty   INT NOT NULL CONSTRAINT CK_fact_inv_beg CHECK (beginning_on_hand_qty >= 0),
        received_qty            INT NOT NULL CONSTRAINT CK_fact_inv_rec CHECK (received_qty >= 0),
        sold_qty                INT NOT NULL CONSTRAINT CK_fact_inv_sold CHECK (sold_qty >= 0),
        ending_on_hand_qty      INT NOT NULL CONSTRAINT CK_fact_inv_end CHECK (ending_on_hand_qty >= 0),
        ending_inventory_value  DECIMAL(12, 2) NOT NULL CONSTRAINT CK_fact_inv_val CHECK (ending_inventory_value >= 0.00),
        is_stockout             TINYINT NOT NULL CONSTRAINT CK_fact_inv_stockout CHECK (is_stockout IN (0, 1)),
        batch_id                VARCHAR(50) NOT NULL,
        ingested_at             DATETIME2(0) NOT NULL CONSTRAINT DF_fact_inv_ingested DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_fact_inventory_snapshot PRIMARY KEY CLUSTERED (date_key, store_id, product_id)
    );
END
GO

-- Fact: fact_purchase_orders (Procurement, Lead Times & MOQ Enforcement)
IF OBJECT_ID(N'dbo.fact_purchase_orders', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.fact_purchase_orders (
        po_id                   VARCHAR(30) NOT NULL CONSTRAINT PK_fact_purchase_orders PRIMARY KEY,
        order_date_key          INT NOT NULL CONSTRAINT FK_fact_po_ord_date REFERENCES dbo.dim_date(date_key),
        expected_delivery_date_key INT NOT NULL CONSTRAINT FK_fact_po_exp_date REFERENCES dbo.dim_date(date_key),
        actual_delivery_date_key INT NULL CONSTRAINT FK_fact_po_act_date REFERENCES dbo.dim_date(date_key),
        store_id                VARCHAR(10) NOT NULL CONSTRAINT FK_fact_po_store REFERENCES dbo.dim_store(store_id),
        product_id              VARCHAR(10) NOT NULL CONSTRAINT FK_fact_po_product REFERENCES dbo.dim_product(product_id),
        supplier_id             VARCHAR(10) NOT NULL CONSTRAINT FK_fact_po_supplier REFERENCES dbo.dim_supplier(supplier_id),
        order_qty               INT NOT NULL CONSTRAINT CK_fact_po_qty CHECK (order_qty > 0),
        received_qty            INT NOT NULL CONSTRAINT CK_fact_po_rec CHECK (received_qty >= 0),
        unit_cost_price         DECIMAL(10, 2) NOT NULL CONSTRAINT CK_fact_po_cost CHECK (unit_cost_price > 0.00),
        total_cost_amount       DECIMAL(12, 2) NOT NULL CONSTRAINT CK_fact_po_total CHECK (total_cost_amount > 0.00),
        status                  VARCHAR(20) NOT NULL CONSTRAINT CK_fact_po_status CHECK (status IN ('PLACED', 'IN_TRANSIT', 'DELIVERED', 'CANCELLED')),
        batch_id                VARCHAR(50) NOT NULL,
        ingested_at             DATETIME2(0) NOT NULL CONSTRAINT DF_fact_po_ingested DEFAULT SYSUTCDATETIME()
    );
END
GO

-- ----------------------------------------------------------------------------
-- 3. PERFORMANCE INDEXES
-- ----------------------------------------------------------------------------

-- Indexes on fact_sales_daily
IF NOT EXISTS (SELECT name FROM sys.indexes WHERE name = N'IX_fact_sales_store_prod')
    CREATE NONCLUSTERED INDEX IX_fact_sales_store_prod ON dbo.fact_sales_daily (store_id, product_id) INCLUDE (quantity_sold, net_sales_amount, cogs_amount);
GO

-- Indexes on fact_inventory_snapshot
IF NOT EXISTS (SELECT name FROM sys.indexes WHERE name = N'IX_fact_inv_stockout')
    CREATE NONCLUSTERED INDEX IX_fact_inv_stockout ON dbo.fact_inventory_snapshot (is_stockout, date_key) INCLUDE (store_id, product_id, ending_on_hand_qty);
GO

IF NOT EXISTS (SELECT name FROM sys.indexes WHERE name = N'IX_fact_inv_store_prod')
    CREATE NONCLUSTERED INDEX IX_fact_inv_store_prod ON dbo.fact_inventory_snapshot (store_id, product_id, date_key) INCLUDE (ending_on_hand_qty, ending_inventory_value);
GO

-- Indexes on fact_purchase_orders
IF NOT EXISTS (SELECT name FROM sys.indexes WHERE name = N'IX_fact_po_status')
    CREATE NONCLUSTERED INDEX IX_fact_po_status ON dbo.fact_purchase_orders (status, supplier_id) INCLUDE (order_qty, received_qty);
GO

