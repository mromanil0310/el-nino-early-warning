-- Phase 2 Build 3: station weights per province must sum to 1.0, or the weighted
-- risk average silently over/under-states risk for that province.
-- Returns rows (= failures) for any province whose mapping weights don't sum to 1.0.

SELECT
    province_id,
    SUM(weight) AS total_weight
FROM {{ ref('province_station_mapping') }}
GROUP BY province_id
HAVING ABS(SUM(weight) - 1.0) > 0.001
