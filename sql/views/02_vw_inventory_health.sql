-- ===============================================================================
-- RetailPulse DI: Analytical SQL Views - Inventory Health & Days of Supply
-- ===============================================================================
USE RetailPulseDB;
GO

-- 1. View: vw_inventory_health
-- Point-in-time inventory health: closing stock on hand, rolling 30-day average daily sales,
-- Days of Supply (DoS), and store-product stockout frequency percentage.
CREATE OR ALTER VIEW dbo.vw_inventory_health AS
WITH rolling_sales AS (
    SELECT 
        s.date_key,
        s.store_id,
        s.product_id,
        s.quantity_sold,
        AVG(CAST(s.quantity_sold AS FLOAT)) OVER (
            PARTITION BY s.store_id, s.product_id
            ORDER BY s.date_key
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS ads_30d
    FROM dbo.fact_sales_daily s
)
SELECT 
    inv.date_key,
    d.full_date,
    inv.store_id,
    st.store_name,
    inv.product_id,
    p.product_name,
    p.category,
    p.brand,
    inv.beginning_on_hand_qty,
    inv.received_qty,
    inv.sold_qty,
    inv.ending_on_hand_qty AS closing_stock_on_hand,
    inv.ending_inventory_value,
    inv.is_stockout,
    ROUND(ISNULL(rs.ads_30d, 0.0), 2) AS rolling_30d_avg_daily_sales,
    CASE 
        WHEN inv.ending_on_hand_qty = 0 THEN 0.0
        WHEN rs.ads_30d IS NULL OR rs.ads_30d = 0 THEN 999.0
        ELSE ROUND(CAST(inv.ending_on_hand_qty AS FLOAT) / NULLIF(rs.ads_30d, 0), 1)
    END AS days_of_supply,
    ROUND(
        AVG(CAST(inv.is_stockout AS FLOAT)) OVER (
            PARTITION BY inv.store_id, inv.product_id
        ) * 100.0,
        2
    ) AS stockout_frequency_pct
FROM dbo.fact_inventory_snapshot inv
INNER JOIN dbo.dim_store st ON inv.store_id = st.store_id
INNER JOIN dbo.dim_product p ON inv.product_id = p.product_id
INNER JOIN dbo.dim_date d ON inv.date_key = d.date_key
LEFT JOIN rolling_sales rs 
    ON inv.date_key = rs.date_key 
   AND inv.store_id = rs.store_id 
   AND inv.product_id = rs.product_id;
GO

-- 2. View: vw_inventory_health_summary
-- Aggregated SKU-Store operational inventory health and stockout metrics
CREATE OR ALTER VIEW dbo.vw_inventory_health_summary AS
SELECT 
    inv.store_id,
    st.store_name,
    inv.product_id,
    p.product_name,
    p.category,
    p.brand,
    COUNT(*) AS total_operating_days,
    SUM(CAST(inv.is_stockout AS INT)) AS total_stockout_days,
    ROUND(
        (SUM(CAST(inv.is_stockout AS FLOAT)) * 100.0) / NULLIF(COUNT(*), 0),
        2
    ) AS stockout_rate_pct,
    ROUND(AVG(CAST(inv.ending_on_hand_qty AS FLOAT)), 1) AS avg_on_hand_qty,
    ROUND(AVG(CAST(inv.ending_inventory_value AS FLOAT)), 2) AS avg_inventory_value
FROM dbo.fact_inventory_snapshot inv
INNER JOIN dbo.dim_store st ON inv.store_id = st.store_id
INNER JOIN dbo.dim_product p ON inv.product_id = p.product_id
GROUP BY 
    inv.store_id,
    st.store_name,
    inv.product_id,
    p.product_name,
    p.category,
    p.brand;
GO

