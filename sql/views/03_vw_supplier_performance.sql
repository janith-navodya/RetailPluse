-- ===============================================================================
-- RetailPulse DI: Analytical SQL Views - Supplier Performance & Service Level
-- ===============================================================================
USE RetailPulseDB;
GO

-- 1. View: vw_supplier_performance
-- Executive vendor scorecard tracking actual vs nominal lead times, variance,
-- fill rates, on-time delivery rates, and MOQ adherence percentages.
CREATE OR ALTER VIEW dbo.vw_supplier_performance AS
SELECT 
    po.supplier_id,
    sup.supplier_name,
    sup.contact_email,
    ROUND(sup.mean_lead_time_days, 1) AS nominal_lead_time_days,
    ROUND(sup.lead_time_std_dev, 2) AS nominal_lead_time_std_dev,
    sup.min_order_qty,
    sup.service_level_target_pct,
    COUNT(*) AS total_orders_placed,
    SUM(CASE WHEN po.status = 'DELIVERED' THEN 1 ELSE 0 END) AS total_orders_delivered,
    ROUND(
        AVG(CAST(CASE WHEN po.status = 'DELIVERED' THEN DATEDIFF(day, d_ord.full_date, d_act.full_date) END AS FLOAT)),
        2
    ) AS avg_actual_lead_time_days,
    ROUND(
        AVG(CAST(CASE WHEN po.status = 'DELIVERED' THEN DATEDIFF(day, d_ord.full_date, d_act.full_date) - sup.mean_lead_time_days END AS FLOAT)),
        2
    ) AS lead_time_variance_days,
    ROUND(
        AVG(CAST(CASE WHEN po.status = 'DELIVERED' THEN po.received_qty END AS FLOAT) / NULLIF(CASE WHEN po.status = 'DELIVERED' THEN po.order_qty END, 0)) * 100.0,
        2
    ) AS order_fill_rate_pct,
    ROUND(
        AVG(CAST(CASE WHEN po.order_qty >= sup.min_order_qty THEN 1.0 ELSE 0.0 END AS FLOAT)) * 100.0,
        2
    ) AS moq_adherence_pct,
    ROUND(
        AVG(CAST(CASE WHEN po.status = 'DELIVERED' AND po.actual_delivery_date_key <= po.expected_delivery_date_key THEN 1.0 ELSE 0.0 END AS FLOAT)) * 100.0,
        2
    ) AS on_time_delivery_rate_pct,
    SUM(po.total_cost_amount) AS total_procurement_spend
FROM dbo.fact_purchase_orders po
INNER JOIN dbo.dim_supplier sup ON po.supplier_id = sup.supplier_id
INNER JOIN dbo.dim_date d_ord ON po.order_date_key = d_ord.date_key
LEFT JOIN dbo.dim_date d_act ON po.actual_delivery_date_key = d_act.date_key
GROUP BY 
    po.supplier_id,
    sup.supplier_name,
    sup.contact_email,
    sup.mean_lead_time_days,
    sup.lead_time_std_dev,
    sup.min_order_qty,
    sup.service_level_target_pct;
GO

-- 2. View: vw_purchase_order_details
-- Granular purchase order line-level performance view
CREATE OR ALTER VIEW dbo.vw_purchase_order_details AS
SELECT 
    po.po_id,
    po.order_date_key,
    d_ord.full_date AS order_date,
    po.expected_delivery_date_key,
    d_exp.full_date AS expected_delivery_date,
    po.actual_delivery_date_key,
    d_act.full_date AS actual_delivery_date,
    po.store_id,
    st.store_name,
    po.product_id,
    p.product_name,
    p.category,
    po.supplier_id,
    sup.supplier_name,
    sup.min_order_qty,
    po.order_qty,
    po.received_qty,
    po.unit_cost_price,
    po.total_cost_amount,
    po.status,
    sup.mean_lead_time_days AS nominal_lead_time_days,
    CASE 
        WHEN po.status = 'DELIVERED' THEN DATEDIFF(day, d_ord.full_date, d_act.full_date)
        ELSE NULL 
    END AS actual_lead_time_days,
    CASE 
        WHEN po.status = 'DELIVERED' THEN DATEDIFF(day, d_ord.full_date, d_act.full_date) - sup.mean_lead_time_days
        ELSE NULL 
    END AS lead_time_variance_days,
    ROUND((CAST(po.received_qty AS FLOAT) / NULLIF(po.order_qty, 0)) * 100.0, 2) AS order_fill_rate_pct,
    CASE WHEN po.order_qty >= sup.min_order_qty THEN 1 ELSE 0 END AS moq_adherence_flag,
    CASE 
        WHEN po.status = 'DELIVERED' AND po.actual_delivery_date_key <= po.expected_delivery_date_key THEN 1 
        ELSE 0 
    END AS on_time_delivery_flag
FROM dbo.fact_purchase_orders po
INNER JOIN dbo.dim_supplier sup ON po.supplier_id = sup.supplier_id
INNER JOIN dbo.dim_store st ON po.store_id = st.store_id
INNER JOIN dbo.dim_product p ON po.product_id = p.product_id
INNER JOIN dbo.dim_date d_ord ON po.order_date_key = d_ord.date_key
INNER JOIN dbo.dim_date d_exp ON po.expected_delivery_date_key = d_exp.date_key
LEFT JOIN dbo.dim_date d_act ON po.actual_delivery_date_key = d_act.date_key;
GO
