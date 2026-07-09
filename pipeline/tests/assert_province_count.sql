-- Phase 2 Build 3: national coverage means exactly total_province_count (82) provinces
-- in the seed. A partial seed load or accidental row deletion fails this test.

SELECT COUNT(*) AS n
FROM {{ ref('provinces') }}
HAVING COUNT(*) != {{ var('total_province_count', 82) }}
