-- stg_pagasa_station_forecasts.sql
-- Staging: latest PAGASA per-station 3-way rainfall probability forecast, with the
-- station's continuous drought severity.
--
-- severity = P_below  (near- and above-normal outcomes carry no drought risk;
--            probabilities normalized to 1)
--
-- This mirrors outlook.severity_from_probabilities (the Python source of truth): only
-- below-normal rainfall drives El Niño drought risk, so severity is the probability of
-- below-normal rainfall. A "Below Normal"-tilted station reproduces ≈0.75. One row per
-- station (most recent forecast_date wins).

WITH source AS (
    SELECT
        id,
        station_id,
        forecast_date,
        below_normal_pct,
        near_normal_pct,
        above_normal_pct,
        source_bulletin,
        created_at,
        ROW_NUMBER() OVER (
            PARTITION BY station_id
            ORDER BY forecast_date DESC, created_at DESC
        ) AS row_num
    FROM {{ source('elnino', 'pagasa_station_forecasts') }}
)

SELECT
    id,
    station_id,
    forecast_date,
    below_normal_pct,
    near_normal_pct,
    above_normal_pct,

    -- Continuous drought severity in [0, 1] = P(below-normal rainfall).
    GREATEST(0.0, LEAST(1.0,
        below_normal_pct
        / NULLIF(below_normal_pct + near_normal_pct + above_normal_pct, 0)
    )) AS station_severity,

    source_bulletin,
    created_at
FROM source
WHERE row_num = 1
