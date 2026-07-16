-- ELN-031: the continuous rainfall severity weight must stay within [0, 1] everywhere
-- it is produced. accepted_values can't express a continuous range, so this singular
-- test guards the invariant instead. Returns rows (= failures) for any out-of-range value
-- in the per-station severity, the weighted province aggregate, or the final mart.

SELECT 'stg_pagasa_station_forecasts' AS model, station_id::text AS key, station_severity AS value
FROM {{ ref('stg_pagasa_station_forecasts') }}
WHERE station_severity < 0 OR station_severity > 1

UNION ALL
SELECT 'int_province_rainfall', province_id::text, rainfall_severity_weight
FROM {{ ref('int_province_rainfall') }}
WHERE rainfall_severity_weight < 0 OR rainfall_severity_weight > 1

UNION ALL
SELECT 'risk_scores', province_id::text, rainfall_severity_weight
FROM {{ ref('risk_scores') }}
WHERE rainfall_severity_weight < 0 OR rainfall_severity_weight > 1
