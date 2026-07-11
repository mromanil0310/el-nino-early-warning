-- 007_weekly_digests_crop.sql
-- ELN-029: weekly_digests was missing a `crop` column and was only unique on
-- (province_id, week_of). risk_scores computes one row per province x crop, so any
-- province growing more than one crop in a given week (e.g. Pangasinan: corn + palay)
-- caused digest_generator.py's per-row write_digest() upsert to silently overwrite
-- the same (province_id, week_of) row multiple times — whichever crop was processed
-- LAST in the loop is the only one that survives. Every OTHER crop's dashboard card
-- for that province then displays the wrong crop's advisory (e.g. a corn farmer
-- reading irrigation guidance written for palay). Surfaced by the first-ever real
-- pipeline run against live PAGASA/crop-calendar data.
--
-- Existing rows predate this fix and cannot be reliably re-attributed to a specific
-- crop (the overwrite already happened, so we don't know which crop's advisory a row
-- "actually" holds for multi-crop provinces). This is the pilot's first-ever
-- generated batch with no external consumers yet, so the safe fix is to clear it and
-- let the next pipeline run regenerate every row correctly under the new constraint.

DELETE FROM weekly_digests;

ALTER TABLE weekly_digests
    ADD COLUMN crop VARCHAR(50) NOT NULL DEFAULT 'unknown';

ALTER TABLE weekly_digests
    DROP CONSTRAINT weekly_digests_province_id_week_of_key,
    ADD CONSTRAINT weekly_digests_province_id_crop_week_of_key UNIQUE (province_id, crop, week_of);

ALTER TABLE weekly_digests ALTER COLUMN crop DROP DEFAULT;
