-- 004_advisory_feedback.sql
-- ELN-021 (foundation): capture cooperative replies to the weekly advisory SMS so the
-- pilot can measure whether warnings led to action. Inbound replies are classified by
-- feedback.parse_feedback() (acted / not_acted / need_help / unknown) and inserted here
-- by the same inbound webhook that records STOP into sms_opt_outs. Aggregate reads will
-- power an "impact" view on the dashboard.
CREATE TABLE IF NOT EXISTS advisory_feedback (
    id            SERIAL PRIMARY KEY,
    contact_id    INTEGER REFERENCES cooperative_contacts(id),
    province_id   INTEGER REFERENCES provinces(id),
    week_of       DATE,
    response_code VARCHAR(20) NOT NULL,   -- 'acted' | 'not_acted' | 'need_help' | 'unknown'
    raw_text      TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Linked to contacts → service_role only (no anon/authenticated read policy).
ALTER TABLE advisory_feedback ENABLE ROW LEVEL SECURITY;
