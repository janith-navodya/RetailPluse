-- ============================================================================
-- RETAILPULSE DECISION INTELLIGENCE (DI)
-- DDL SCRIPT 02: DEAD-LETTER QUARANTINE & ETL LINEAGE SCHEMA (T-SQL)
-- Database Target: RetailPulseDI
-- Authentication: Windows Integrated (-E) | Driver: ODBC Driver 18
-- ============================================================================

USE RetailPulseDI;
GO

-- ----------------------------------------------------------------------------
-- 1. ETL BATCH AUDIT LOG TABLE
-- ----------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.etl_batch_log', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.etl_batch_log (
        batch_id                VARCHAR(50) NOT NULL CONSTRAINT PK_etl_batch_log PRIMARY KEY,
        pipeline_name           VARCHAR(50) NOT NULL,
        status                  VARCHAR(20) NOT NULL CONSTRAINT CK_etl_batch_status CHECK (status IN ('STARTED', 'COMPLETED', 'FAILED')),
        records_processed       INT NOT NULL CONSTRAINT DF_etl_batch_proc DEFAULT 0,
        records_loaded          INT NOT NULL CONSTRAINT DF_etl_batch_load DEFAULT 0,
        records_quarantined     INT NOT NULL CONSTRAINT DF_etl_batch_quar DEFAULT 0,
        started_at              DATETIME2(0) NOT NULL,
        completed_at            DATETIME2(0) NULL
    );
END
GO

-- ----------------------------------------------------------------------------
-- 2. DEAD-LETTER QUARANTINE TABLE
-- ----------------------------------------------------------------------------
IF OBJECT_ID(N'dbo.quarantine_invalid_records', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.quarantine_invalid_records (
        quarantine_id           BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_quarantine PRIMARY KEY CLUSTERED,
        source_feed             VARCHAR(50) NOT NULL,
        raw_payload_json        NVARCHAR(MAX) NOT NULL,
        violation_category      VARCHAR(50) NOT NULL, -- 'SCHEMA_ERROR', 'ORPHAN_KEY', 'DOMAIN_VIOLATION'
        violation_details       NVARCHAR(MAX) NOT NULL,
        rejected_at             DATETIME2(0) NOT NULL CONSTRAINT DF_quarantine_rejected DEFAULT SYSUTCDATETIME(),
        batch_id                VARCHAR(50) NOT NULL CONSTRAINT FK_quarantine_batch REFERENCES dbo.etl_batch_log(batch_id)
    );
END
GO

-- ----------------------------------------------------------------------------
-- 3. AUDIT INDEXES
-- ----------------------------------------------------------------------------
IF NOT EXISTS (SELECT name FROM sys.indexes WHERE name = N'IX_quarantine_batch')
    CREATE NONCLUSTERED INDEX IX_quarantine_batch ON dbo.quarantine_invalid_records (batch_id, source_feed);
GO

IF NOT EXISTS (SELECT name FROM sys.indexes WHERE name = N'IX_quarantine_category')
    CREATE NONCLUSTERED INDEX IX_quarantine_category ON dbo.quarantine_invalid_records (violation_category);
GO

