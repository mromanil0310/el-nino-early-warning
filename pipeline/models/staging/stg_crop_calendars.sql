-- stg_crop_calendars.sql
-- Staging model: determine current crop growth stage for each province+crop
-- Based on today's date vs planting/harvest windows
-- Used by the risk scoring model to apply vulnerability weights

WITH source AS (
    SELECT
        id,
        province_id,
        crop,
        season,
        planting_start,
        planting_end,
        harvest_start,
        harvest_end
    FROM {{ source('elnino', 'crop_calendars') }}
),

with_stage AS (
    SELECT
        id,
        province_id,
        crop,
        season,
        planting_start,
        planting_end,
        harvest_start,
        harvest_end,
        CURRENT_DATE AS score_date,

        -- Determine crop growth stage based on current date vs crop calendar
        -- Stages follow PhilRice vulnerability classification:
        --   pre-planting (before planting window)
        --   vegetative   (planting_start → ~halfway to harvest)
        --   reproductive (flowering window — highest El Niño sensitivity)
        --   harvest      (approaching harvest)
        --   off-season   (after harvest, before next season)
        CASE
            WHEN CURRENT_DATE < planting_start
                THEN 'pre-planting'
            WHEN CURRENT_DATE BETWEEN planting_start AND planting_end
                THEN 'early-vegetative'
            WHEN CURRENT_DATE BETWEEN planting_end AND (planting_end + (harvest_start - planting_end) / 2)
                THEN 'late-vegetative'
            WHEN CURRENT_DATE BETWEEN (planting_end + (harvest_start - planting_end) / 2) AND harvest_start
                THEN 'reproductive'
            WHEN CURRENT_DATE BETWEEN harvest_start AND harvest_end
                THEN 'harvest'
            ELSE 'off-season'
        END AS crop_stage,

        -- PhilRice El Niño crop stage vulnerability index
        -- Source: PhilRice "Effects of El Niño on Rice Production in the Philippines"
        -- Reproductive (flowering/grain-filling) is most sensitive
        CASE
            WHEN CURRENT_DATE < planting_start
                THEN 0.4   -- pre-planting: manageable via delayed planting decision
            WHEN CURRENT_DATE BETWEEN planting_start AND planting_end
                THEN 0.5   -- early vegetative: moderate risk
            WHEN CURRENT_DATE BETWEEN planting_end AND (planting_end + (harvest_start - planting_end) / 2)
                THEN 0.7   -- late vegetative: higher sensitivity
            WHEN CURRENT_DATE BETWEEN (planting_end + (harvest_start - planting_end) / 2) AND harvest_start
                THEN 1.0   -- reproductive: maximum sensitivity (spikelet sterility)
            WHEN CURRENT_DATE BETWEEN harvest_start AND harvest_end
                THEN 0.3   -- harvest: risk is delayed harvest / threshing losses
            ELSE 0.0        -- off-season: no growing crop at risk
        END AS vulnerability_index

    FROM source
)

SELECT
    id,
    province_id,
    crop,
    season,
    planting_start,
    planting_end,
    harvest_start,
    harvest_end,
    score_date,
    crop_stage,
    vulnerability_index
FROM with_stage
-- Only include active seasons (crops that have been planted or are pre-planting within 60 days)
WHERE CURRENT_DATE <= harvest_end
  AND CURRENT_DATE >= (planting_start - INTERVAL '60 days')
