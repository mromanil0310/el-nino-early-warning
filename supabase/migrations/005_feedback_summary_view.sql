-- 005_feedback_summary_view.sql
-- ELN-021: expose an anon-safe AGGREGATE of advisory_feedback for the dashboard impact
-- view. The base table is service-role-only (it links to contacts), so the dashboard
-- (anon key) cannot read it. This view exposes only week_of + response_code + counts —
-- no contact_id, no raw_text, no phone numbers — and is granted to anon/authenticated.
--
-- A regular (non-security_invoker) view runs with the owner's privileges, so it can
-- aggregate the RLS-protected base table while exposing only the safe columns below.
CREATE OR REPLACE VIEW feedback_summary AS
SELECT
    week_of,
    response_code,
    COUNT(*) AS responses
FROM advisory_feedback
GROUP BY week_of, response_code;

GRANT SELECT ON feedback_summary TO anon, authenticated;
