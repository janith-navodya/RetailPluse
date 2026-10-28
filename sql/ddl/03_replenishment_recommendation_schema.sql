-- ===============================================================================
-- RetailPulse DI: DDL Schema for Replenishment Decision Recommendations
-- ===============================================================================
USE RetailPulseDB;
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'fact_replenishment_recommendation')
BEGIN
    CREATE TABLE dbo.fact_replenishment_recommendation (
        recommendation_id VARCHAR(64) NOT NULL PRIMARY KEY,
        run_date_key INT NOT NULL,
        store_id VARCHAR(10) NOT NULL,
        product_id VARCHAR(10) NOT NULL,
        supplier_id VARCHAR(10) NOT NULL,
        current_on_hand_qty INT NOT NULL,
        current_on_order_qty INT NOT NULL,
        inventory_position INT NOT NULL,
        lead_time_demand_qty FLOAT NOT NULL,
        safety_stock_qty FLOAT NOT NULL,
        reorder_point_qty FLOAT NOT NULL,
        inventory_status VARCHAR(30) NOT NULL,
        recommended_units INT NOT NULL,
        recommended_packs INT NOT NULL,
        unit_cost_price DECIMAL(10, 2) NOT NULL,
        estimated_cost DECIMAL(12, 2) NOT NULL,
        priority_rank INT NOT NULL,
        approval_status VARCHAR(20) NOT NULL DEFAULT 'PROPOSED',
        batch_id VARCHAR(64) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_repl_store FOREIGN KEY (store_id) REFERENCES dbo.dim_store(store_id),
        CONSTRAINT FK_repl_product FOREIGN KEY (product_id) REFERENCES dbo.dim_product(product_id),
        CONSTRAINT FK_repl_supplier FOREIGN KEY (supplier_id) REFERENCES dbo.dim_supplier(supplier_id),
        CONSTRAINT FK_repl_date FOREIGN KEY (run_date_key) REFERENCES dbo.dim_date(date_key)
    );

    CREATE NONCLUSTERED INDEX IX_repl_status ON dbo.fact_replenishment_recommendation (run_date_key, store_id, approval_status);
    CREATE NONCLUSTERED INDEX IX_repl_inventory_status ON dbo.fact_replenishment_recommendation (inventory_status);
END;
GO
