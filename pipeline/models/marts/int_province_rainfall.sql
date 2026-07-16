-- int_province_rainfall.sql
-- ELN-031: weighted station→province rainfall severity. Aggregates the per-station
-- PAGASA probability forecasts (stg_pagasa_station_forecasts) up to the province level
-- using the province_station_mapping weights (which sum to 1.0 per province, enforced by
-- assert_station_weights_sum_to_one.sql — so each SUM below is a weighted average).
--
-- This is the model that finally makes provinces differentiate: a province fed by drier
-- stations gets a higher severity than one fed by wetter stations, instead of every
-- "Below Normal" province collapsing to the same categorical step weight.
--
-- Provinces without a station forecast fall back to the legacy province-level
-- pagasa_forecasts (stg_pagasa_forecasts), so the change is non-breaking during rollout.
--
-- Emits exactly the columns risk_scores.sql consumes: province_id,
-- rainfall_severity_weight, seasonal_outlook, rainfall_anomaly_pct, forecast_date.

{{ config(materialized='view') }}

WITH station_fc AS (
    SELECT
        station_id,
        forecast_date,
        station_severity,
        below_normal_pct,
        near_normal_pct,
        above_normal_pct
    FROM {{ ref('stg_pagasa_station_forecasts') }}
),

-- Weighted aggregation across the stations mapped to each province.
station_based AS (
    SELECT
        m.province_id,
        SUM(m.weight * s.station_severity)          AS rainfall_severity_weight,
        SUM(m.weight * s.below_normal_pct) / 100.0  AS p_below,
        SUM(m.weight * s.above_normal_pct) / 100.0  AS p_above,
        MAX(s.forecast_date)                        AS forecast_date
    FROM {{ ref('province_station_mapping') }} m
    INNER JOIN station_fc s ON s.station_id = m.station_id
    GROUP BY m.province_id
),

-- Representative display fields from the weighted probability tilt. The anomaly is the
-- inverse of outlook.probabilities_from_anomaly's P_below branch (climatological 1/3,
-- slope 0.015); the label mirrors outlook.label_from_probabilities.
station_scored AS (
    SELECT
        province_id,
        GREATEST(0.0, LEAST(1.0, rainfall_severity_weight)) AS rainfall_severity_weight,
        forecast_date,
        ROUND((((1.0 / 3.0) - p_below) / 0.015)::numeric, 1) AS rainfall_anomaly_pct,
        CASE
            WHEN (p_below - p_above) >= 0.30 AND p_below >= 0.80 THEN 'Much Below Normal'
            WHEN (p_below - p_above) >= 0.30                     THEN 'Below Normal'
            WHEN (p_above - p_below) >= 0.30 AND p_above >= 0.80 THEN 'Much Above Normal'
            WHEN (p_above - p_below) >= 0.30                     THEN 'Above Normal'
            ELSE 'Near Normal'
        END AS seasonal_outlook
    FROM station_based
),

-- Fallback for provinces with only a legacy province-level forecast (no station data).
fallback AS (
    SELECT
        f.province_id,
        f.rainfall_severity_weight,
        f.seasonal_outlook,
        f.rainfall_anomaly_pct,
        f.forecast_date
    FROM {{ ref('stg_pagasa_forecasts') }} f
    WHERE f.province_id NOT IN (SELECT province_id FROM station_scored)
)

SELECT province_id, rainfall_severity_weight, seasonal_outlook, rainfall_anomaly_pct, forecast_date
FROM station_scored
UNION ALL
SELECT province_id, rainfall_severity_weight, seasonal_outlook, rainfall_anomaly_pct, forecast_date
FROM fallback
