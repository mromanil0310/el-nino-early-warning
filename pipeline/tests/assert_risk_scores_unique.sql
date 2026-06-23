-- Singular dbt test (ELN-014): risk_scores must hold exactly one row per
-- province × crop × week. Returns the offending groups (test FAILS) if a duplicate
-- ever appears — e.g. from overlapping crop-calendar rows or a bad forecast join.
SELECT
    province_id,
    crop,
    week_of,
    COUNT(*) AS n_rows
FROM {{ ref('risk_scores') }}
GROUP BY province_id, crop, week_of
HAVING COUNT(*) > 1
