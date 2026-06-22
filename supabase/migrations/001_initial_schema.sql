-- El Niño Early Warning Data Layer — Initial Schema
-- Run via: supabase db push OR psql $DATABASE_URL < 001_initial_schema.sql

-- Enable PostGIS for geographic queries
CREATE EXTENSION IF NOT EXISTS postgis;

-- ─────────────────────────────────────────────
-- PROVINCES
-- Pilot: 15 high-risk Luzon provinces (Regions I, III, IV-A, CAR)
-- ─────────────────────────────────────────────
CREATE TABLE provinces (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    region_code     VARCHAR(20)  NOT NULL,   -- e.g. "III", "I", "IV-A", "CAR"
    pagasa_zone     VARCHAR(50),             -- PAGASA climate zone label
    lat             DECIMAL(9,6),
    lon             DECIMAL(9,6),
    is_pilot        BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- PAGASA FORECASTS
-- One row per province per forecast run
-- ─────────────────────────────────────────────
CREATE TABLE pagasa_forecasts (
    id                      SERIAL PRIMARY KEY,
    province_id             INTEGER NOT NULL REFERENCES provinces(id),
    forecast_date           DATE    NOT NULL,
    seasonal_outlook        VARCHAR(50) NOT NULL,   -- "Below Normal" | "Near Normal" | "Above Normal"
    rainfall_anomaly_pct    DECIMAL(6,2),           -- % deviation from normal; negative = drier
    temperature_anomaly_c   DECIMAL(4,2),           -- °C above/below normal
    source_bulletin         VARCHAR(200),            -- URL or bulletin reference
    raw_text                TEXT,                    -- original bulletin excerpt for audit
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (province_id, forecast_date)
);

-- ─────────────────────────────────────────────
-- CROP CALENDARS
-- Planting and harvest windows by province and crop
-- Seeded manually from PSA Open Stat tables
-- ─────────────────────────────────────────────
CREATE TABLE crop_calendars (
    id              SERIAL PRIMARY KEY,
    province_id     INTEGER     NOT NULL REFERENCES provinces(id),
    crop            VARCHAR(50) NOT NULL,   -- "palay" | "corn"
    season          VARCHAR(20) NOT NULL,   -- "wet" | "dry"
    planting_start  DATE        NOT NULL,   -- approximate start of planting window
    planting_end    DATE        NOT NULL,
    harvest_start   DATE        NOT NULL,
    harvest_end     DATE        NOT NULL,
    notes           TEXT,
    UNIQUE (province_id, crop, season)
);

-- ─────────────────────────────────────────────
-- RISK SCORES
-- Computed weekly by the dbt pipeline
-- ─────────────────────────────────────────────
CREATE TABLE risk_scores (
    id              SERIAL PRIMARY KEY,
    province_id     INTEGER     NOT NULL REFERENCES provinces(id),
    crop            VARCHAR(50) NOT NULL,
    week_of         DATE        NOT NULL,   -- Monday of the scored week (ISO week start)
    risk_score      DECIMAL(5,2) NOT NULL,  -- 0–100
    risk_level      VARCHAR(10)  NOT NULL,  -- "High" | "Medium" | "Low"
    crop_stage      VARCHAR(30),            -- "pre-planting" | "vegetative" | "reproductive" | "harvest"
    trend           VARCHAR(10),            -- "rising" | "stable" | "falling" vs prior week
    model_version   VARCHAR(20) DEFAULT '1.0',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (province_id, crop, week_of)
);

-- ─────────────────────────────────────────────
-- WEEKLY DIGESTS
-- AI-generated advisories per province per week
-- ─────────────────────────────────────────────
CREATE TABLE weekly_digests (
    id              SERIAL PRIMARY KEY,
    province_id     INTEGER NOT NULL REFERENCES provinces(id),
    week_of         DATE    NOT NULL,
    advisory_en     TEXT    NOT NULL,   -- plain English advisory (3 sentences)
    advisory_tl     TEXT    NOT NULL,   -- Tagalog advisory (3 sentences)
    sms_text        TEXT    NOT NULL,   -- compressed for SMS (160 chars)
    generated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (province_id, week_of)
);

-- ─────────────────────────────────────────────
-- COOPERATIVE CONTACTS
-- Pre-registered cooperative officers for SMS delivery
-- ─────────────────────────────────────────────
CREATE TABLE cooperative_contacts (
    id              SERIAL PRIMARY KEY,
    province_id     INTEGER     NOT NULL REFERENCES provinces(id),
    cooperative_name VARCHAR(200) NOT NULL,
    contact_name    VARCHAR(100),
    phone_number    VARCHAR(20)  NOT NULL,   -- E.164 format: +639XXXXXXXXX
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- SMS LOG
-- Audit trail for every message sent
-- ─────────────────────────────────────────────
CREATE TABLE sms_log (
    id                  SERIAL PRIMARY KEY,
    digest_id           INTEGER NOT NULL REFERENCES weekly_digests(id),
    contact_id          INTEGER NOT NULL REFERENCES cooperative_contacts(id),
    semaphore_message_id VARCHAR(100),
    status              VARCHAR(20) DEFAULT 'sent',  -- "sent" | "failed" | "delivered"
    sent_at             TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- PIPELINE RUNS
-- Audit log for every Airflow DAG run
-- ─────────────────────────────────────────────
CREATE TABLE pipeline_runs (
    id                  SERIAL PRIMARY KEY,
    run_date            DATE        NOT NULL,
    dag_id              VARCHAR(100) NOT NULL,
    status              VARCHAR(20) NOT NULL,   -- "success" | "failed" | "partial"
    provinces_updated   INTEGER DEFAULT 0,
    duration_seconds    INTEGER,
    error_message       TEXT,
    started_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────
CREATE INDEX idx_risk_scores_province_week  ON risk_scores (province_id, week_of DESC);
CREATE INDEX idx_risk_scores_week_of        ON risk_scores (week_of DESC);
CREATE INDEX idx_pagasa_forecasts_province  ON pagasa_forecasts (province_id, forecast_date DESC);
CREATE INDEX idx_weekly_digests_province    ON weekly_digests (province_id, week_of DESC);

-- ─────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ─────────────────────────────────────────────
ALTER TABLE provinces              ENABLE ROW LEVEL SECURITY;
ALTER TABLE pagasa_forecasts       ENABLE ROW LEVEL SECURITY;
ALTER TABLE crop_calendars         ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_scores            ENABLE ROW LEVEL SECURITY;
ALTER TABLE weekly_digests         ENABLE ROW LEVEL SECURITY;
ALTER TABLE cooperative_contacts   ENABLE ROW LEVEL SECURITY;
ALTER TABLE sms_log                ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_runs          ENABLE ROW LEVEL SECURITY;

-- Authenticated users can read all public data tables
CREATE POLICY "Authenticated read: provinces"        ON provinces            FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated read: forecasts"        ON pagasa_forecasts     FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated read: crop_calendars"   ON crop_calendars       FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated read: risk_scores"      ON risk_scores          FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated read: digests"          ON weekly_digests       FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated read: pipeline_runs"    ON pipeline_runs        FOR SELECT TO authenticated USING (true);

-- Service role (pipeline) can write to all tables — enforced by using service_role key in pipeline only
-- No explicit policy needed: service_role bypasses RLS by default in Supabase
