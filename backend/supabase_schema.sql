-- Supabase Schema for WebIntel (UPDATED)

-- If you created the previous tables, please drop them first:
DROP TABLE IF EXISTS diffs;
DROP TABLE IF EXISTS monitors;
DROP TABLE IF EXISTS reports;

-- 1. Reports Table
-- Stores the final executed AI research reports
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    query TEXT NOT NULL,
    mode TEXT NOT NULL,
    query_type TEXT NOT NULL,
    overall_confidence FLOAT NOT NULL,
    report JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Monitors Table
-- Stores background tracking jobs (chron jobs)
CREATE TABLE IF NOT EXISTS monitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    mode TEXT NOT NULL,
    query_type TEXT NOT NULL,
    interval_hours INTEGER NOT NULL,
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Diffs Table
-- Stores differences over time for tracked queries
CREATE TABLE IF NOT EXISTS diffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    old_session_id TEXT NOT NULL,
    new_session_id TEXT NOT NULL,
    diff JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);
