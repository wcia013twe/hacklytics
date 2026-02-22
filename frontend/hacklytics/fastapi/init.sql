-- Actian Vector DB Schema Initialization
-- Based on RAG.MD Section 3.2.3
-- Creates safety_protocols (static knowledge base) and incident_log (dynamic temporal memory)

-- NOTE: Actian Vector has NATIVE vector support - no extension needed
-- Unlike PostgreSQL + pgvector, Actian Vector type is built-in
-- Reference: https://docs.actian.com/vector/6.0/index.html#page/User/Vector_Data_Types.htm

-- ============================================================
-- Table 1: safety_protocols (Static Knowledge Base)
-- ============================================================
-- Pre-loaded with fire safety standards, NFPA protocols, and operational SOPs
-- Each protocol is embedded as a 384-dimensional vector representing its scenario description
-- This table is READ-ONLY during missions

CREATE TABLE IF NOT EXISTS safety_protocols (
    id              SERIAL PRIMARY KEY,
    scenario_vector VECTOR(384),
    protocol_text   TEXT NOT NULL,
    severity        VARCHAR(10) CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    category        VARCHAR(50),
    tags            VARCHAR(200),
    source          VARCHAR(100),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for vector similarity search using IVFFlat
-- lists=50 is optimized for ~100-500 protocols in the knowledge base
CREATE INDEX IF NOT EXISTS idx_protocol_vector
ON safety_protocols
USING ivfflat (scenario_vector vector_cosine_ops)
WITH (lists = 50);

-- Index for severity filtering (used in retrieval queries)
CREATE INDEX IF NOT EXISTS idx_protocol_severity
ON safety_protocols (severity);

-- ============================================================
-- Table 2: incident_log (Dynamic Temporal Memory)
-- ============================================================
-- Written in real-time during each session. Every processed packet generates one row.
-- This table enables temporal reasoning - RAG queries "find similar past incidents" from its own previous writes.
-- This is the short-term memory of the system.

CREATE TABLE IF NOT EXISTS incident_log (
    id                SERIAL PRIMARY KEY,
    -- Unix epoch timestamp (UTC) from the original telemetry packet
    -- This is EVENT TIME - when the sensor reading occurred on the Jetson device
    -- Used for temporal analysis, trend detection, and session history queries
    timestamp         DOUBLE PRECISION NOT NULL,
    session_id        VARCHAR(50) NOT NULL,
    device_id         VARCHAR(50) NOT NULL,
    narrative_vector  VECTOR(384),
    raw_narrative     TEXT,
    trend_tag         VARCHAR(20) CHECK (trend_tag IN ('RAPID_GROWTH', 'GROWING', 'STABLE', 'DIMINISHING', 'UNKNOWN')),
    hazard_level      VARCHAR(10) CHECK (hazard_level IN ('CLEAR', 'LOW', 'MODERATE', 'HIGH', 'CRITICAL')),
    fire_dominance    REAL,
    smoke_opacity     REAL,
    proximity_alert   BOOLEAN,
    -- SQL TIMESTAMP for audit trail - WRITE TIME (when row was inserted to database)
    -- This differs from 'timestamp' during network delays or batch uploads
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for vector similarity search on incident history
-- lists=100 is optimized for ~1000-10000 incidents (30min session at 1 pkt/sec = ~1800 rows)
CREATE INDEX IF NOT EXISTS idx_incident_vector
ON incident_log
USING ivfflat (narrative_vector vector_cosine_ops)
WITH (lists = 100);

-- Composite index for session history queries (filters by session_id, orders by timestamp)
CREATE INDEX IF NOT EXISTS idx_incident_session
ON incident_log (session_id, timestamp);

-- Index for device-specific queries
CREATE INDEX IF NOT EXISTS idx_incident_device
ON incident_log (device_id, timestamp);

-- ============================================================
-- Seed Data: Common Safety Protocols
-- ============================================================
-- NOTE: scenario_vector will be populated by a separate Python seeding script
-- that uses sentence-transformers to embed each scenario description
-- This is just placeholder data structure

-- Example protocol (vector would be populated by seeding script):
-- INSERT INTO safety_protocols (scenario_vector, protocol_text, severity, category, tags, source)
-- VALUES (
--     '[0.1, 0.2, ... 384 dimensions]',  -- Embedding of "Person trapped, fire blocking exit"
--     'NFPA 1001: Immediate evacuation required when fire occupies >40% of visual field and victims are present. Establish defensive perimeter.',
--     'CRITICAL',
--     'fire',
--     'trapped,exit_blocked,evacuation',
--     'NFPA_1001'
-- );

-- Placeholder comment for seeding script location
-- To seed protocols, run: python scripts/seed_protocols.py

-- ============================================================
-- Utility Views
-- ============================================================

-- View to check recent incidents per session
CREATE OR REPLACE VIEW recent_incidents AS
SELECT
    session_id,
    device_id,
    hazard_level,
    trend_tag,
    raw_narrative,
    timestamp,
    EXTRACT(EPOCH FROM (NOW() - created_at)) AS seconds_ago
FROM incident_log
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;

-- View to check protocol coverage by severity
CREATE OR REPLACE VIEW protocol_coverage AS
SELECT
    severity,
    category,
    COUNT(*) as count
FROM safety_protocols
GROUP BY severity, category
ORDER BY severity, category;

-- ============================================================
-- Verification Queries (for manual testing after deployment)
-- ============================================================

-- Verify tables were created
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Verify indexes were created
-- SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public';

-- Check protocol count (should be 0 until seeded)
-- SELECT COUNT(*) FROM safety_protocols;

-- Check incident count (should be 0 until first packet arrives)
-- SELECT COUNT(*) FROM incident_log;
