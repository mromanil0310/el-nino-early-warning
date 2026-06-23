-- 003_sms_opt_outs.sql
-- ELN-010: SMS opt-out / unsubscribe suppression list (consent compliance).
--
-- A recipient who replies STOP — or is manually unsubscribed — is recorded here, and
-- send_sms.py skips any contact whose (normalized) number is present. Inbound "STOP"
-- capture is wired via a Semaphore inbound webhook (ops task) that inserts a row here;
-- manual inserts also work in the interim.
--
-- Numbers are stored E.164 (+639XXXXXXXXX), matching normalize_ph_phone() output.
CREATE TABLE IF NOT EXISTS sms_opt_outs (
    id            SERIAL PRIMARY KEY,
    phone_number  VARCHAR(20) NOT NULL UNIQUE,
    reason        VARCHAR(100),                 -- e.g. 'STOP reply', 'manual', 'bounce'
    opted_out_at  TIMESTAMPTZ DEFAULT NOW()
);

-- PII (phone numbers): service_role only — no anon/authenticated read policy.
ALTER TABLE sms_opt_outs ENABLE ROW LEVEL SECURITY;
