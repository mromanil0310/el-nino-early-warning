"""
digest_generator.py
Generates weekly AI advisories per province using Claude haiku.

For each province with a risk score this week:
  1. Fetches the risk score + PAGASA forecast from Supabase
  2. Calls Claude haiku with a bounded, structured prompt
  3. Writes the advisory (English + Tagalog + SMS-compressed) to weekly_digests table

The prompt is strictly bounded — no free-text user input is ever routed to Claude.
All inputs are structured data pulled from the database.

Cost estimate: ~₱0.02–0.05 per province per week (claude-haiku-4-5)
"""

import os
import logging
import anthropic
from datetime import date, timedelta
from supabase import create_client, Client

# Pure helpers (encoding-aware SMS + retry). Robust import: run-as-script or DAG package.
try:
    from smstext import fit_sms
    from retry_util import retry_call
except ImportError:  # pragma: no cover - import path differs under Airflow
    from scripts.smstext import fit_sms
    from scripts.retry_util import retry_call

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

DISCLAIMER_EN = "NOTE: This is a decision-support tool based on public PAGASA and PSA data. Verify with your local DA/PAGASA office before acting."
DISCLAIMER_TL = "PAALALA: Ang impormasyong ito ay batay sa pampublikong datos ng PAGASA at PSA. Kumpirmahin sa inyong lokal na DA/PAGASA bago kumilos."


def get_iso_week_start(d: date) -> date:
    """Returns the Monday of the ISO week containing date d."""
    return d - timedelta(days=d.weekday())


def fetch_risk_scores_for_week(week_of: date) -> list[dict]:
    """Fetch all risk scores for the given week with province and forecast data."""
    result = supabase.table("risk_scores").select(
        "*, provinces(name, region_code, pagasa_zone), "
        "pagasa_forecasts(seasonal_outlook, rainfall_anomaly_pct)"
    ).eq("week_of", week_of.isoformat()).execute()
    return result.data or []


def generate_advisory(
    province_name: str,
    region_code: str,
    crop: str,
    risk_score: float,
    risk_level: str,
    crop_stage: str,
    trend: str,
    seasonal_outlook: str,
    rainfall_anomaly_pct: float,
    week_of: date,
) -> dict[str, str]:
    """
    Calls Claude haiku to generate a 3-sentence advisory in English and Tagalog,
    plus an SMS-compressed version.

    Returns {"advisory_en": ..., "advisory_tl": ..., "sms_text": ...}
    """
    # Bounded structured prompt — no user input reaches Claude
    prompt = f"""You are a technical agricultural advisory writer for Philippine LGU agricultural officers.

Generate a weekly El Niño agricultural risk advisory based on the following data:

Province: {province_name} (Region {region_code})
Crop: {crop.title()}
Week of: {week_of.strftime("%B %d, %Y")}
El Niño Risk Score: {risk_score:.0f}/100 ({risk_level})
Crop Stage: {crop_stage}
Risk Trend vs Last Week: {trend}
PAGASA Seasonal Outlook: {seasonal_outlook}
Rainfall Anomaly: {rainfall_anomaly_pct:+.0f}% vs normal

Write exactly:
1. ADVISORY_EN: A 3-sentence advisory in plain English for LGU agricultural officers. Sentence 1: state the risk level and why. Sentence 2: specific action recommendation for farmers at this crop stage. Sentence 3: what to watch for next week.
2. ADVISORY_TL: Translate the same 3 sentences into Filipino (Tagalog). Use plain language a cooperative officer can read aloud to farmers.
3. SMS_TEXT: A single sentence under 140 characters combining province, risk level, and the single most important action. Include "{week_of.strftime('%b %d')}" as the date.

Format your response EXACTLY as:
ADVISORY_EN: [text]
ADVISORY_TL: [text]
SMS_TEXT: [text]

Do not add headers, bullets, or any other text."""

    # Retry transient Anthropic errors (connection blips, rate limits, 5xx) so one bad
    # call doesn't drop this province's advisory for the week.
    message = retry_call(
        lambda: claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        ),
        attempts=3,
        base_delay=2.0,
        exceptions=(
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        ),
        label=f"claude advisory {province_name}",
    )

    raw = message.content[0].text.strip()
    lines = {
        line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
        for line in raw.splitlines()
        if ":" in line and line.split(":", 1)[0].strip() in ("ADVISORY_EN", "ADVISORY_TL", "SMS_TEXT")
    }

    advisory_en = lines.get("ADVISORY_EN", f"{province_name} El Niño Risk: {risk_level}. Consult your DA field office for specific guidance.")
    advisory_tl = lines.get("ADVISORY_TL", f"Panganib ng El Niño sa {province_name}: {risk_level}. Makipag-ugnayan sa inyong DA.")
    sms_text = lines.get("SMS_TEXT", f"{week_of.strftime('%b %d')} {province_name} {crop}: {risk_level} El Niño risk. Check DA advisory.")

    # Append disclaimer
    full_en = advisory_en + " " + DISCLAIMER_EN
    full_tl = advisory_tl + " " + DISCLAIMER_TL
    # Encoding-aware fit: keep the whole SMS within ONE segment (160 GSM-7 / 70 UCS-2)
    # incl. the " -ELNINO" tag, trimming on a word boundary. Tagalog ñ stays GSM-7;
    # ₱/accents/em-dashes from the model correctly downshift to the 70-char UCS-2 limit.
    sms_with_disclaimer = fit_sms(sms_text, " -ELNINO")

    return {
        "advisory_en": full_en,
        "advisory_tl": full_tl,
        "sms_text": sms_with_disclaimer,
    }


def write_digest(province_id: int, week_of: date, advisory: dict[str, str]) -> None:
    """Upsert weekly digest to Supabase."""
    supabase.table("weekly_digests").upsert({
        "province_id": province_id,
        "week_of": week_of.isoformat(),
        "advisory_en": advisory["advisory_en"],
        "advisory_tl": advisory["advisory_tl"],
        "sms_text": advisory["sms_text"],
    }, on_conflict="province_id,week_of").execute()


def run(week_of: date | None = None) -> int:
    """
    Main entry point. Generates digests for all provinces with risk scores this week.
    Returns number of digests generated.
    Called by Airflow DAG after risk scoring dbt run.
    """
    if week_of is None:
        week_of = get_iso_week_start(date.today())

    log.info(f"Digest generator run: week_of={week_of}")

    risk_scores = fetch_risk_scores_for_week(week_of)
    if not risk_scores:
        log.warning(f"No risk scores found for week {week_of} — skipping digest generation")
        return 0

    generated = 0
    for row in risk_scores:
        province = row.get("provinces", {})
        forecast = row.get("pagasa_forecasts", {}) or {}
        province_name = province.get("name", "Unknown")
        province_id = row["province_id"]

        log.info(f"  Generating digest: {province_name} {row['crop']} — {row['risk_level']}")
        try:
            advisory = generate_advisory(
                province_name=province_name,
                region_code=province.get("region_code", ""),
                crop=row["crop"],
                risk_score=float(row["risk_score"]),
                risk_level=row["risk_level"],
                crop_stage=row.get("crop_stage", "unknown"),
                trend=row.get("trend", "stable"),
                seasonal_outlook=forecast.get("seasonal_outlook", "Below Normal"),
                rainfall_anomaly_pct=float(forecast.get("rainfall_anomaly_pct", -25.0)),
                week_of=week_of,
            )
            write_digest(province_id, week_of, advisory)
            generated += 1
            log.info(f"    ✓ {province_name}: {advisory['sms_text'][:60]}...")
        except Exception as e:
            log.error(f"    ✗ Failed for {province_name}: {e}")

    log.info(f"Digest generation complete: {generated}/{len(risk_scores)} provinces")
    return generated


if __name__ == "__main__":
    run()
