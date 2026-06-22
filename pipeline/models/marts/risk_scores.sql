-- risk_scores.sql
-- CORE MODEL: El Niño agricultural risk scoring
-- Implements: risk_score = rainfall_severity_weight × crop_stage_vulnerability_index × 100
--
-- Formula source: PhilRice El Niño Impact Assessment Framework
-- Thresholds: High > 65, Medium 35–65, Low < 35
--
-- Materializes as a TABLE for fast dashboard queries.
-- Runs weekly after PAGASA data is scraped.

{{ config(
    materialized='table',
    post_hook=[
        "CREATE INDEX IF NOT EXISTS idx_risk_scores_province_week ON {{ this }} (province_id, week_of DESC)",
        "CREATE INDEX IF NOT EXISTS idx_risk_scores_risk_level ON {{ this }} (risk_level)"
    ]
) }}

WITH forecasts AS (
    SELECT
        province_id,
        rainfall_severity_weight,
        seasonal_outlook,
        rainfall_anomaly_pct,
        forecast_date
    FROM {{ ref('stg_pagasa_forecasts') }}
),

crop_stages AS (
    SELECT
        province_id,
        crop,
        season,
        crop_stage,
        vulnerability_index,
        planting_start,
        harvest_end,
        score_date
    FROM {{ ref('stg_crop_calendars') }}
),

-- Cross forecasts with active crop stages (one row per province × crop)
combined AS (
    SELECT
        f.province_id,
        c.crop,
        c.season,
        c.crop_stage,
        c.vulnerability_index,
        f.rainfall_severity_weight,
        f.seasonal_outlook,
        f.rainfall_anomaly_pct,
        f.forecast_date,
        c.planting_start,
        c.harvest_end,
        c.score_date,

        -- THE CORE FORMULA
        -- risk_score = rainfall_severity_weight × crop_stage_vulnerability_index × 100
        ROUND(
            (f.rainfall_severity_weight * c.vulnerability_index * 100)::numeric,
            1
        ) AS risk_score

    FROM forecasts f
    INNER JOIN crop_stages c ON c.province_id = f.province_id
),

-- Apply risk level classification
scored AS (
    SELECT
        province_id,
        crop,
        season,
        crop_stage,
        vulnerability_index,
        rainfall_severity_weight,
        seasonal_outlook,
        rainfall_anomaly_pct,
        risk_score,
        forecast_date,
        planting_start,
        harvest_end,
        score_date,

        -- Risk level thresholds
        CASE
            WHEN risk_score > 65 THEN 'High'
            WHEN risk_score >= 35 THEN 'Medium'
            ELSE 'Low'
        END AS risk_level,

        -- ISO week of score (Monday)
        DATE_TRUNC('week', score_date)::date AS week_of

    FROM combined
    WHERE vulnerability_index > 0  -- exclude off-season crops
),

-- Add week-over-week trend by comparing to prior week's score
-- Uses a self-referencing LAG on the materialized table from last week
-- On first run, prior_score is NULL → trend = 'new'
with_trend AS (
    SELECT
        s.*,
        prior.risk_score AS prior_week_score,
        CASE
            WHEN prior.risk_score IS NULL              THEN 'new'
            WHEN s.risk_score > prior.risk_score + 5   THEN 'increasing'
            WHEN s.risk_score < prior.risk_score - 5   THEN 'decreasing'
            ELSE                                            'stable'
        END AS trend

    FROM scored s
    LEFT JOIN {{ this }} prior
        ON  prior.province_id = s.province_id
        AND prior.crop        = s.crop
        AND prior.week_of     = (s.week_of - INTERVAL '7 days')::date
)

SELECT
    -- Identifiers
    province_id,
    crop,
    season,
    week_of,

    -- Inputs
    crop_stage,
    vulnerability_index,
    rainfall_severity_weight,
    seasonal_outlook,
    rainfall_anomaly_pct,
    forecast_date,

    -- Output
    risk_score,
    risk_level,
    trend,
    prior_week_score,

    -- Metadata
    score_date,
    planting_start,
    harvest_end,
    NOW() AS scored_at

FROM with_trend
ORDER BY risk_score DESC, province_id, crop
