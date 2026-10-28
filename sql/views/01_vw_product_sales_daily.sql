-- ===============================================================================
-- RetailPulse DI: Analytical SQL Views - Product & Store Daily Sales
-- ===============================================================================
USE RetailPulseDB;
GO

-- 1. View: vw_product_sales_daily
-- Aggregated net sales, units sold, COGS, gross profit, and gross margin percentage
-- per product per day across all stores.
CREATE OR ALTER VIEW dbo.vw_product_sales_daily AS
SELECT 
    s.date_key,
    d.full_date,
    s.product_id,
    p.product_name,
    p.category,
    p.sub_category,
    p.brand,
    p.supplier_id,
    COUNT(DISTINCT s.store_id) AS active_store_count,
    SUM(s.quantity_sold) AS total_units_sold,
    SUM(s.gross_sales_amount) AS total_gross_sales,
    SUM(s.discount_amount) AS total_discount_amount,
    SUM(s.net_sales_amount) AS total_net_sales,
    SUM(s.cogs_amount) AS total_cogs,
    SUM(s.gross_profit_amount) AS total_gross_profit,
    ROUND(
        (SUM(s.gross_profit_amount) * 100.0) / NULLIF(SUM(s.net_sales_amount), 0),
        2
    ) AS gross_margin_pct
FROM dbo.fact_sales_daily s
INNER JOIN dbo.dim_product p ON s.product_id = p.product_id
INNER JOIN dbo.dim_date d ON s.date_key = d.date_key
GROUP BY 
    s.date_key,
    d.full_date,
    s.product_id,
    p.product_name,
    p.category,
    p.sub_category,
    p.brand,
    p.supplier_id;
GO

-- 2. View: vw_store_product_sales_daily
-- Granular sales, profit, and margin per store, per product, per day.
CREATE OR ALTER VIEW dbo.vw_store_product_sales_daily AS
SELECT 
    s.date_key,
    d.full_date,
    s.store_id,
    st.store_name,
    st.store_format,
    s.product_id,
    p.product_name,
    p.category,
    p.brand,
    s.quantity_sold,
    s.gross_sales_amount,
    s.discount_amount,
    s.net_sales_amount,
    s.cogs_amount,
    s.gross_profit_amount,
    ROUND(
        (s.gross_profit_amount * 100.0) / NULLIF(s.net_sales_amount, 0),
        2
    ) AS gross_margin_pct,
    s.is_promotional
FROM dbo.fact_sales_daily s
INNER JOIN dbo.dim_store st ON s.store_id = st.store_id
INNER JOIN dbo.dim_product p ON s.product_id = p.product_id
INNER JOIN dbo.dim_date d ON s.date_key = d.date_key;
GO

