-- 008_pagasa_station_forecasts.sql
-- ELN-031: PAGASA issues its seasonal rainfall outlook PER SYNOPTIC STATION as a
-- 3-way probability distribution — P(Below Normal) / P(Near Normal) / P(Above Normal),
-- summing to ~100% — not as one categorical label per province. Migration 006 added the
-- station registry and the weighted station→province mapping; this table finally stores
-- the per-station forecast those weights aggregate.
--
-- The dbt layer (stg_pagasa_station_forecasts → int_province_rainfall) turns these
-- per-station probabilities into a continuous, weight-averaged province rainfall
-- severity, so provinces with different drought tilts get different risk scores instead
-- of every "Below Normal" province collapsing to the same categorical weight.
--
-- The older province-level pagasa_forecasts table is retained as a fallback source for
-- provinces that have no station forecast yet (int_province_rainfall COALESCEs to it).
--
-- Integer SERIAL ids to match the existing schema. Probabilities stored 0–100 to match
-- how PAGASA prints them; a CHECK keeps the triple summing to ~100.

CREATE TABLE pagasa_station_forecasts (
    id                SERIAL PRIMARY KEY,
    station_id        INTEGER NOT NULL REFERENCES pagasa_stations(id),
    forecast_date     DATE NOT NULL,
    below_normal_pct  DECIMAL(5,2) NOT NULL,
    near_normal_pct   DECIMAL(5,2) NOT NULL,
    above_normal_pct  DECIMAL(5,2) NOT NULL,
    source_bulletin   VARCHAR(200),
    raw_text          TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (station_id, forecast_date),
    CHECK (below_normal_pct >= 0 AND near_normal_pct >= 0 AND above_normal_pct >= 0),
    CHECK (ABS(below_normal_pct + near_normal_pct + above_normal_pct - 100) <= 1.0)
);

CREATE INDEX idx_psf_station_date ON pagasa_station_forecasts (station_id, forecast_date DESC);

-- Same least-privilege posture as 002/006: derived from public PAGASA bulletins, no PII —
-- safe for the anon dashboard role.
ALTER TABLE pagasa_station_forecasts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anon read: station forecasts" ON pagasa_station_forecasts FOR SELECT TO anon USING (true);
