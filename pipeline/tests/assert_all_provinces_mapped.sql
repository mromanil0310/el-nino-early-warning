-- Phase 2 Build 3: every province must map to at least one PAGASA synoptic station,
-- or it can never receive a station-based forecast (silent coverage gap).
-- Returns rows (= failures) for unmapped provinces.

SELECT p.id, p.name
FROM {{ ref('provinces') }} p
LEFT JOIN {{ ref('province_station_mapping') }} m
    ON m.province_id = p.id
WHERE m.province_id IS NULL
