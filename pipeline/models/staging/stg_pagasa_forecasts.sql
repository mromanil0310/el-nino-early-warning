-- stg_pagasa_forecasts.sql
-- Staging model: clean and standardize PAGASA forecast data
-- One row per province per forecast date (most recent wins)

WITH source AS (
    SELECT
        id,
        province_id,
        forecast_date,
        TRIM(LOWER(seasonal_outlook))   AS seasonal_outlook_raw,
        rainfall_anomaly_pct,
        temperature_anomaly_c,
        source_bulletin,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY province_id
            ORDER BY forecast_date DESC, created_at DESC
        ) AS row_num  -- keep most recent forecast per province
    FROM {{ source('elnino', 'pagasa_forecasts') }}
),

classified AS (
    SELECT
        id,
        province_id,
        forecast_date,
        seasonal_outlook_raw,
        rainfall_anomaly_pct,
        temperature_anomaly_c,
        source_bulletin,
        created_at,

        -- Normalize outlook to standard labels
        CASE
            WHEN seasonal_outlook_raw LIKE '%much below%'  THEN 'Much Below Normal'
            WHEN seasonal_outlook_raw LIKE '%below%'       THEN 'Below Normal'
            WHEN seasonal_outlook_raw LIKE '%much above%'  THEN 'Much Above Normal'
            WHEN seasonal_outlook_raw LIKE '%above%'       THEN 'Above Normal'
            ELSE 'Near Normal'
        END AS seasonal_outlook,

        -- Severity weight: 0.0 (wet) → 1.0 (very dry)
        -- Used in the risk scoring model
        CASE
            WHEN seasonal_outlook_raw LIKE '%much below%' THEN 1.0
            WHEN seasonal_outlook_raw LIKE '%below%'      THEN 0.75
            WHEN seasonal_outlook_raw LIKE '%near%'       THEN 0.25
            WHEN seasonal_outlook_raw LIKE '%above%'      THEN 0.0
            WHEN seasonal_outlook_raw LIKE '%much above%' THEN 0.0
            ELSE 0.25
        END AS rainfall_severity_weight,

        row_num
    FROM source
)

SELECT
    id,
    province_id,
    forecast_date,
    seasonal_outlook,
    rainfall_anomaly_pct,
    temperature_anomaly_c,
    rainfall_severity_weight,
    source_bulletin,
    created_at
FROM classified
WHERE row_num = 1  -- most recent forecast only
