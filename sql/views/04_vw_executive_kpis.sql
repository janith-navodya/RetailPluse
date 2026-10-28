-- ===============================================================================
-- RetailPulse DI: Analytical SQL Views - Executive KPIs & Inventory Turnover
-- ===============================================================================
USE RetailPulseDB;
GO

-- 1. View: vw_store_inventory_turnover
-- Calculates annualized inventory turnover per store:
-- Inventory Turnover = (Total COGS / Average Daily Inventory Valuation) * (365 / Operating Days)
CREATE OR ALTER VIEW dbo.vw_store_inventory_turnover AS
WITH store_daily_valuation AS (
    SELECT 
        inv.date_key,
        inv.store_id,
        SUM(inv.ending_inventory_value) AS daily_inventory_value
    FROM dbo.fact_inventory_snapshot inv
    GROUP BY inv.date_key, inv.store_id
),
store_sales_cogs AS (
    SELECT 
        s.store_id,
        SUM(s.cogs_amount) AS total_cogs,
        SUM(s.net_sales_amount) AS total_net_sales,
        COUNT(DISTINCT s.date_key) AS operating_days
    FROM dbo.fact_sales_daily s
    GROUP BY s.store_id
)
SELECT 
    sc.store_id,
    st.store_name,
    st.store_format,
    sc.operating_days,
    sc.total_net_sales,
    sc.total_cogs,
    ROUND(AVG(sdv.daily_inventory_value), 2) AS avg_daily_inventory_value,
    ROUND(sc.total_cogs / NULLIF(AVG(sdv.daily_inventory_value), 0), 2) AS raw_inventory_turnover,
    ROUND(
        (sc.total_cogs / NULLIF(AVG(sdv.daily_inventory_value), 0)) * (365.0 / NULLIF(sc.operating_days, 0)),
        2
    ) AS annualized_inventory_turnover
FROM store_sales_cogs sc
INNER JOIN dbo.dim_store st ON sc.store_id = st.store_id
INNER JOIN store_daily_valuation sdv ON sc.store_id = sdv.store_id
GROUP BY 
    sc.store_id,
    st.store_name,
    st.store_format,
    sc.operating_days,
    sc.total_net_sales,
    sc.total_cogs;
GO

-- 2. View: vw_executive_kpis
-- Enterprise-wide executive overview summarizing all top-level operational KPIs
CREATE OR ALTER VIEW dbo.vw_executive_kpis AS
WITH daily_valuation AS (
    SELECT 
        date_key,
        SUM(ending_inventory_value) AS daily_inventory_value
    FROM dbo.fact_inventory_snapshot
    GROUP BY date_key
),
overall_sales AS (
    SELECT 
        SUM(net_sales_amount) AS total_net_sales,
        SUM(cogs_amount) AS total_cogs,
        SUM(gross_profit_amount) AS total_gross_profit,
        ROUND((SUM(gross_profit_amount) * 100.0) / NULLIF(SUM(net_sales_amount), 0), 2) AS gross_margin_pct,
        COUNT(DISTINCT date_key) AS total_operating_days
    FROM dbo.fact_sales_daily
),
overall_inv AS (
    SELECT 
        COUNT(*) AS total_inventory_records,
        SUM(CAST(is_stockout AS INT)) AS total_stockout_events,
        ROUND((SUM(CAST(is_stockout AS FLOAT)) * 100.0) / NULLIF(COUNT(*), 0), 2) AS overall_stockout_rate_pct,
        AVG(daily_inventory_value) AS avg_daily_total_inventory_value
    FROM dbo.fact_inventory_snapshot
    CROSS JOIN (SELECT AVG(daily_inventory_value) AS daily_inventory_value FROM daily_valuation) v
)
SELECT 
    s.total_net_sales,
    s.total_cogs,
    s.total_gross_profit,
    s.gross_margin_pct,
    s.total_operating_days,
    i.overall_stockout_rate_pct,
    ROUND(i.avg_daily_total_inventory_value, 2) AS avg_daily_total_inventory_value,
    ROUND(
        (s.total_cogs / NULLIF(i.avg_daily_total_inventory_value, 0)) * (365.0 / NULLIF(s.total_operating_days, 0)),
        2
    ) AS annualized_inventory_turnover
FROM overall_sales s
CROSS JOIN overall_inv i;
GO

