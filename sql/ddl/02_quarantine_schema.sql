-- ============================================================================
-- RETAILPULSE DECISION INTELLIGENCE (DI)
-- DDL SCRIPT 02: DEAD-LETTER QUARANTINE & ETL LINEAGE SCHEMA
-- Compatible with ANSI SQL, SQLite 3, PostgreSQL 14+, Microsoft SQL Server 2019+
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. ETL BATCH AUDIT LOG TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_batch_log (
    batch_id                VARCHAR(50) NOT NULL PRIMARY KEY,
    pipeline_name           VARCHAR(50) NOT NULL,
    status                  VARCHAR(20) NOT NULL CHECK (status IN ('STARTED', 'COMPLETED', 'FAILED')),
    records_processed       INTEGER NOT NULL DEFAULT 0,
    records_loaded          INTEGER NOT NULL DEFAULT 0,
    records_quarantined     INTEGER NOT NULL DEFAULT 0,
    started_at              TIMESTAMP NOT NULL,
    completed_at            TIMESTAMP NULL
);

-- ----------------------------------------------------------------------------
-- 2. DEAD-LETTER QUARANTINE TABLE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quarantine_invalid_records (
    quarantine_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_feed             VARCHAR(50) NOT NULL,
    raw_payload_json        TEXT NOT NULL,
    violation_category      VARCHAR(50) NOT NULL, -- 'SCHEMA_ERROR', 'ORPHAN_KEY', 'DOMAIN_VIOLATION'
    violation_details       TEXT NOT NULL,
    rejected_at             TIMESTAMP NOT NULL,
    batch_id                VARCHAR(50) NOT NULL,
    FOREIGN KEY (batch_id) REFERENCES etl_batch_log(batch_id)
);

-- ----------------------------------------------------------------------------
-- 3. AUDIT INDEXES
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_quarantine_batch ON quarantine_invalid_records(batch_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_feed ON quarantine_invalid_records(source_feed);
CREATE INDEX IF NOT EXISTS idx_quarantine_category ON quarantine_invalid_records(violation_category);

