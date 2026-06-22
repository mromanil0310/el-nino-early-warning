"""
elnino_weekly.py
Airflow DAG — El Niño Early Warning weekly pipeline

Schedule: Every Monday at 06:00 PHT (22:00 UTC Sunday)
PAGASA seasonal outlooks are updated weekly/monthly.
Pipeline runs Monday morning so advisories arrive before the farming week.

Task order:
  pagasa_scrape → dbt_run → digest_generate → sms_send → vercel_webhook

Deployed on: Railway.app
Environment variables required (set in Railway dashboard):
  SUPABASE_URL, SUPABASE_SERVICE_KEY, SUPABASE_DB_HOST, SUPABASE_DB_USER,
  SUPABASE_DB_PASSWORD, ANTHROPIC_API_KEY, SEMAPHORE_API_KEY,
  VERCEL_DEPLOY_HOOK_URL (optional), OPS_ALERT_WEBHOOK_URL (optional — failure alerts)
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, date

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago

# ─── Pipeline script paths ─────────────────────────────────────────────────────
# In Railway, the repo is cloned to /app — update this if deploy path differs.
PIPELINE_DIR = os.getenv("PIPELINE_DIR", "/app/pipeline")
sys.path.insert(0, PIPELINE_DIR)

# ─── Failure alerting (ELN-002) ───────────────────────────────────────────────
# A silently-failed weekly run means NO advisories reach farmers. Alert loudly on any
# task failure: always to the logs, and to OPS_ALERT_WEBHOOK_URL (Slack/Discord/etc.)
# when configured. Retries still apply first — this fires only after they're exhausted.
def alert_on_failure(context) -> None:
    ti = context.get("task_instance")
    task_id = getattr(ti, "task_id", "unknown")
    run_id = getattr(context.get("dag_run"), "run_id", "?")
    exc = context.get("exception")
    msg = (f"ALERT: El Niño weekly pipeline task '{task_id}' FAILED (run {run_id}). "
           f"Advisories may not have been sent this week. Error: {exc}")
    print(msg)
    webhook = os.getenv("OPS_ALERT_WEBHOOK_URL")
    if webhook:
        try:
            import requests as _rq
            _rq.post(webhook, json={"text": msg}, timeout=10)
        except Exception as e:  # never let alerting raise inside a failure callback
            print(f"ops alert webhook failed: {e}")


# ─── Default DAG args ─────────────────────────────────────────────────────────
DEFAULT_ARGS = {
    "owner": "biboy-labs",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "on_failure_callback": alert_on_failure,
    "retries": 2,
    "retry_delay": timedelta(minutes=15),
}


# ─── Task functions ───────────────────────────────────────────────────────────

def task_pagasa_scrape(**context) -> int:
    """Scrape PAGASA bulletin and write forecasts to Supabase."""
    from scripts.pagasa_scraper import run as scrape_run
    today = date.today()
    rows = scrape_run(forecast_date=today)
    context["task_instance"].xcom_push(key="provinces_updated", value=rows)
    return rows


def task_digest_generate(**context) -> int:
    """Generate Claude haiku advisories for all provinces with risk scores."""
    from scripts.digest_generator import run as digest_run, get_iso_week_start
    week_of = get_iso_week_start(date.today())
    count = digest_run(week_of=week_of)
    context["task_instance"].xcom_push(key="digests_generated", value=count)
    return count


def task_sms_send(**context) -> int:
    """Send weekly SMS to cooperative contacts."""
    from sms.send_sms import run as sms_run, get_iso_week_start
    week_of = get_iso_week_start(date.today())
    sent = sms_run(week_of=week_of)
    context["task_instance"].xcom_push(key="sms_sent", value=sent)
    return sent


def task_vercel_webhook(**context) -> None:
    """Trigger Vercel static rebuild so the dashboard reflects new scores."""
    import requests as req
    hook_url = os.getenv("VERCEL_DEPLOY_HOOK_URL")
    if not hook_url:
        print("VERCEL_DEPLOY_HOOK_URL not set — skipping dashboard rebuild")
        return
    resp = req.post(hook_url, timeout=10)
    print(f"Vercel webhook: {resp.status_code} {resp.text[:100]}")


def task_log_pipeline_run(**context) -> None:
    """Write pipeline run summary to Supabase pipeline_runs table.

    Runs under trigger_rule='all_done', so it must report the REAL outcome derived from
    upstream task states — never a hardcoded 'success'. Also writes the schema-required
    dag_id and only the columns that exist (previous insert referenced non-existent
    digests_generated/sms_sent columns and omitted the NOT NULL dag_id, so it failed).
    """
    from supabase import create_client
    ti = context["task_instance"]
    dag_run = context["dag_run"]

    states = {t.task_id: t.state for t in dag_run.get_task_instances() if t.task_id != ti.task_id}
    failed = [tid for tid, st in states.items() if st == "failed"]
    succeeded = [tid for tid, st in states.items() if st == "success"]
    status = "success" if not failed else ("partial" if succeeded else "failed")

    provinces = ti.xcom_pull(task_ids="pagasa_scrape", key="provinces_updated") or 0
    digests = ti.xcom_pull(task_ids="digest_generate", key="digests_generated") or 0
    sms = ti.xcom_pull(task_ids="sms_send", key="sms_sent") or 0
    # error_message carries the run detail (counts always; failed-task list when failing).
    detail = f"provinces={provinces}, digests={digests}, sms_sent={sms}"
    error_message = detail if not failed else f"{detail}; failed tasks: {', '.join(failed)}"

    supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    supabase.table("pipeline_runs").insert({
        "dag_id": dag_run.dag_id,
        "run_date": date.today().isoformat(),
        "status": status,
        "provinces_updated": provinces,
        "error_message": error_message,
    }).execute()
    print(f"pipeline_runs logged: status={status} ({error_message})")


# ─── DAG definition ───────────────────────────────────────────────────────────

with DAG(
    dag_id="elnino_weekly",
    default_args=DEFAULT_ARGS,
    description="El Niño Early Warning — weekly PAGASA scrape → risk score → advisory → SMS",
    schedule_interval="0 22 * * 0",  # Every Sunday 22:00 UTC = Monday 06:00 PHT
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    tags=["elnino", "agriculture", "philippines"],
) as dag:

    # Task 1: Scrape PAGASA seasonal outlook
    pagasa_scrape = PythonOperator(
        task_id="pagasa_scrape",
        python_callable=task_pagasa_scrape,
        doc_md="Download and parse PAGASA seasonal rainfall outlook PDF. Falls back to manual overrides if PDF parse fails.",
    )

    # Task 2: Run dbt models (staging → marts/risk_scores)
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {PIPELINE_DIR} && "
            f"dbt run --profiles-dir {PIPELINE_DIR} --target prod "
            f"--select staging.stg_pagasa_forecasts staging.stg_crop_calendars marts.risk_scores"
        ),
        doc_md="Run dbt staging + risk_scores mart. Computes province × crop risk scores for this week.",
    )

    # Task 3: Generate AI advisories
    digest_generate = PythonOperator(
        task_id="digest_generate",
        python_callable=task_digest_generate,
        doc_md="Call Claude haiku to generate English + Tagalog advisory per province. ~₱0.02–0.05/province.",
    )

    # Task 4: Send SMS
    sms_send = PythonOperator(
        task_id="sms_send",
        python_callable=task_sms_send,
        doc_md="Send weekly SMS to active cooperative contacts via Semaphore.ph. ~₱0.65/SMS.",
    )

    # Task 5: Trigger Vercel static rebuild
    vercel_webhook = PythonOperator(
        task_id="vercel_webhook",
        python_callable=task_vercel_webhook,
        doc_md="Trigger Vercel deploy hook so the Next.js static dashboard reflects new risk scores.",
    )

    # Task 6: Log run summary
    log_run = PythonOperator(
        task_id="log_pipeline_run",
        python_callable=task_log_pipeline_run,
        trigger_rule="all_done",  # log even if some tasks failed
        doc_md="Write pipeline run summary to Supabase pipeline_runs table.",
    )

    # ─── Task dependencies ────────────────────────────────────────────────────
    pagasa_scrape >> dbt_run >> digest_generate >> sms_send >> vercel_webhook >> log_run
