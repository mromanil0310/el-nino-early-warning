-- 006_province_station_mapping.sql
-- Phase 2 Build 3 (data model fix): PAGASA issues its seasonal rainfall outlook per
-- climate monitoring station, not per administrative province. The pilot approximated
-- one forecast per province — acceptable for 15 Luzon provinces, inaccurate at national
-- scale where one province may span 2–3 stations (and one station several provinces).
--
-- These two tables record the official synoptic station registry and a weighted
-- station→province assignment, enabling weighted risk averaging in the dbt layer.
-- Weights per province must sum to 1.0 (enforced by the dbt singular test
-- assert_station_weights_sum_to_one.sql).
--
-- NOTE: integer SERIAL ids (not UUIDs) to match the existing schema (provinces.id).
-- Station registry source: DOST-PAGASA Synoptic Station Profile publications (2024,
-- Southern Luzon + Mindanao PRSD) and the PAGASA PRSD station directory
-- (prsd.pagasa.dost.gov.ph), compiled 2026-07-08. 57 operational synoptic stations.

CREATE TABLE pagasa_stations (
    id           SERIAL PRIMARY KEY,
    station_code VARCHAR(20)  UNIQUE NOT NULL,   -- short slug, e.g. "DAGUPAN"
    name         VARCHAR(100) NOT NULL,           -- official station name
    lat          DECIMAL(9,6),
    lon          DECIMAL(9,6),
    region_code  VARCHAR(20),                     -- administrative region of the station
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE province_station_mapping (
    province_id  INTEGER NOT NULL REFERENCES provinces(id),
    station_id   INTEGER NOT NULL REFERENCES pagasa_stations(id),
    weight       DECIMAL(4,3) NOT NULL DEFAULT 1.0,  -- weighted averaging where a province spans stations
    PRIMARY KEY (province_id, station_id),
    CHECK (weight > 0 AND weight <= 1.0)
);

CREATE INDEX idx_psm_station ON province_station_mapping (station_id);

-- Same least-privilege posture as 002: reference data derived from public PAGASA
-- sources — safe for the anon dashboard role. No PII.
ALTER TABLE pagasa_stations          ENABLE ROW LEVEL SECURITY;
ALTER TABLE province_station_mapping ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anon read: stations" ON pagasa_stations          FOR SELECT TO anon USING (true);
CREATE POLICY "Anon read: psm"      ON province_station_mapping FOR SELECT TO anon USING (true);
