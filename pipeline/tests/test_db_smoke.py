"""
test_db_smoke.py
Live end-to-end DB smoke test (ELN-016) — SKIPPED unless a test Postgres is configured.

Set INTEGRATION_DATABASE_URL to a Postgres connection string that has the migrations
applied (e.g. a throwaway Supabase project or the docker-compose Postgres), then:

    INTEGRATION_DATABASE_URL=postgresql://user:pass@host:5432/db \
        python -m pytest pipeline/tests/test_db_smoke.py -v

It verifies the deployed schema is reachable and shaped as the pipeline expects — it
does NOT reimplement scoring (that's covered by test_pipeline_integration.py). In CI
and on dev machines without the env var, it's collected and skipped cleanly.
"""

import os

import pytest

DB_URL = os.getenv("INTEGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="set INTEGRATION_DATABASE_URL to run the live DB smoke test")

EXPECTED_TABLES = {
    "provinces", "pagasa_forecasts", "crop_calendars", "risk_scores",
    "weekly_digests", "cooperative_contacts", "sms_log", "pipeline_runs",
    "sms_opt_outs",
}
EXPECTED_RISK_SCORE_COLUMNS = {
    "province_id", "crop", "week_of", "crop_stage", "vulnerability_index",
    "rainfall_severity_weight", "risk_score", "risk_level", "trend",
}


@pytest.fixture(scope="module")
def conn():
    psycopg2 = pytest.importorskip("psycopg2")
    c = psycopg2.connect(DB_URL)
    yield c
    c.close()


def test_database_is_reachable(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
        assert cur.fetchone()[0] == 1


def test_core_tables_exist(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        present = {r[0] for r in cur.fetchall()}
    missing = EXPECTED_TABLES - present
    assert not missing, f"missing tables (apply migrations 001-003): {missing}"


def test_risk_scores_has_expected_columns(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'risk_scores'"
        )
        cols = {r[0] for r in cur.fetchall()}
    missing = EXPECTED_RISK_SCORE_COLUMNS - cols
    assert not missing, f"risk_scores missing columns: {missing}"
