-- Enable vector extension (pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

-- ===========================================
-- Table 1: safety_protocols (Static KB)
-- ===========================================

CREATE TABLE IF NOT EXISTS safety_protocols (
    id              SERIAL PRIMARY KEY,
    scenario_vector vector(384) NOT NULL,          -- MiniLM-L6 embeddings
    protocol_text   TEXT NOT NULL,                 -- Actual safety instruction
    severity        VARCHAR(10) NOT NULL,          -- CLEAR | LOW | MODERATE | HIGH | CRITICAL
    category        VARCHAR(50) NOT NULL,          -- fire | structural | hazmat | medical
    tags            VARCHAR(200),                  -- Comma-separated: trapped, exit_blocked, etc.
    source          VARCHAR(100),                  -- Reference: NFPA_1001, OSHA_29CFR
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector similarity index (IVFFlat)
CREATE INDEX idx_protocol_vector ON safety_protocols
    USING ivfflat (scenario_vector vector_cosine_ops)
    WITH (lists = 50);

-- Severity filter index
CREATE INDEX idx_protocol_severity ON safety_protocols (severity);

-- Category index
CREATE INDEX idx_protocol_category ON safety_protocols (category);


-- ===========================================
-- Table 2: incident_log (Dynamic Memory)
-- ===========================================

CREATE TABLE IF NOT EXISTS incident_log (
    id                SERIAL PRIMARY KEY,
    timestamp         DOUBLE PRECISION NOT NULL,   -- Unix epoch from Jetson
    session_id        VARCHAR(50) NOT NULL,        -- mission_YYYY_MM_DD
    device_id         VARCHAR(50) NOT NULL,        -- jetson_alpha_01
    narrative_vector  vector(384) NOT NULL,        -- Enriched narrative embedding
    raw_narrative     TEXT NOT NULL,               -- Human-readable narrative
    trend_tag         VARCHAR(20),                 -- RAPID_GROWTH | GROWING | STABLE | DIMINISHING
    hazard_level      VARCHAR(10),                 -- CLEAR | LOW | MODERATE | HIGH | CRITICAL
    fire_dominance    DOUBLE PRECISION,            -- Denormalized from scores
    smoke_opacity     DOUBLE PRECISION,
    proximity_alert   BOOLEAN,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vector similarity index
CREATE INDEX idx_incident_vector ON incident_log
    USING ivfflat (narrative_vector vector_cosine_ops)
    WITH (lists = 100);

-- Session + timestamp index (critical for history queries)
CREATE INDEX idx_incident_session ON incident_log (session_id, timestamp DESC);

-- Device + timestamp index
CREATE INDEX idx_incident_device ON incident_log (device_id, timestamp DESC);

-- Hazard level index (for filtering)
CREATE INDEX idx_incident_hazard ON incident_log (hazard_level);


-- ===========================================
-- Helper Functions
-- ===========================================

-- Function to compute cosine similarity (for debugging)
CREATE OR REPLACE FUNCTION cosine_similarity(a vector, b vector)
RETURNS DOUBLE PRECISION AS $$
    SELECT 1 - (a <-> b);  -- IMPORTANT: Use <-> for L2 distance
$$ LANGUAGE SQL IMMUTABLE STRICT;
