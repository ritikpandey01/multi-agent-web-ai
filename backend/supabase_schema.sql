-- Supabase Schema for WebIntel v2.0 (with Auth)
-- Run this in the Supabase SQL Editor

-- Drop old tables if they exist
DROP TABLE IF EXISTS diffs;
DROP TABLE IF EXISTS monitors;
DROP TABLE IF EXISTS reports;
DROP TABLE IF EXISTS users;

-- 0. Users Table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Disable RLS for users (we handle auth in our backend)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to users" ON users FOR ALL USING (true) WITH CHECK (true);

-- 1. Reports Table (with user_id foreign key)
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    user_id UUID REFERENCES users(id),
    query TEXT NOT NULL,
    mode TEXT NOT NULL,
    query_type TEXT NOT NULL,
    overall_confidence FLOAT NOT NULL,
    report JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to reports" ON reports FOR ALL USING (true) WITH CHECK (true);

-- 2. Monitors Table
CREATE TABLE monitors (
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

ALTER TABLE monitors ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to monitors" ON monitors FOR ALL USING (true) WITH CHECK (true);

-- 3. Diffs Table
CREATE TABLE diffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    old_session_id TEXT NOT NULL,
    new_session_id TEXT NOT NULL,
    diff JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE diffs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all access to diffs" ON diffs FOR ALL USING (true) WITH CHECK (true);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_session_id ON reports(session_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
