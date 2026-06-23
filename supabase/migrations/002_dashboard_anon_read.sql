-- 002_dashboard_anon_read.sql
-- ELN-019: the public dashboard authenticates with the ANON key (no user login), but
-- 001_initial_schema.sql granted SELECT only `TO authenticated`. Under RLS, anonymous
-- reads therefore matched no policy and returned ZERO rows — the deployed dashboard
-- would render empty.
--
-- Grant read-only access on the PUBLIC-SAFE tables to the `anon` role. Sensitive tables
-- stay locked down:
--   • cooperative_contacts, sms_log → PII (names, phone numbers): service_role only.
--   • pipeline_runs                 → ops audit log: authenticated only (unchanged).
--
-- This is least-privilege for a public early-warning dashboard: only model outputs and
-- reference data (all derived from public PAGASA/PhilRice sources) are exposed to anon.

CREATE POLICY "Anon read: provinces"       ON provinces        FOR SELECT TO anon USING (true);
CREATE POLICY "Anon read: forecasts"       ON pagasa_forecasts FOR SELECT TO anon USING (true);
CREATE POLICY "Anon read: crop_calendars"  ON crop_calendars   FOR SELECT TO anon USING (true);
CREATE POLICY "Anon read: risk_scores"     ON risk_scores      FOR SELECT TO anon USING (true);
CREATE POLICY "Anon read: digests"         ON weekly_digests   FOR SELECT TO anon USING (true);
