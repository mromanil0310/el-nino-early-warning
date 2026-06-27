"""
pagasa_scraper.py
Fetches PAGASA Seasonal Climate Outlook data and writes it to Supabase.

PAGASA publishes seasonal outlooks at:
  https://www.pagasa.dost.gov.ph/climate/climate-prediction/seasonal-forecast

The bulletin is a PDF. This scraper:
  1. Downloads the latest seasonal outlook PDF
  2. Parses province-level rainfall anomaly classifications
  3. Maps them to numeric anomaly values
  4. Writes to the pagasa_forecasts table via Supabase REST

Run manually or via Airflow (see dags/elnino_weekly.py).
"""

import io
import os
import re
import logging
import requests
import pdfplumber
from datetime import date, datetime
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── Supabase client ──────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ─── PAGASA outlook URL ───────────────────────────────────────────────────────
# Update this URL when PAGASA publishes a new bulletin.
# PAGASA typically publishes monthly or when alert status changes.
PAGASA_BULLETIN_URL = os.getenv(
    "PAGASA_BULLETIN_URL",
    "https://www.pagasa.dost.gov.ph/climate/climate-prediction/seasonal-forecast"
)

# ─── Rainfall anomaly classification → numeric mapping ───────────────────────
# Pure classification logic lives in outlook.py (no I/O) so it is unit-testable and
# there is a single, correctly-ordered source of truth. `match_outlook` matches the
# most specific label first so "Much Below Normal" is never downgraded to "Below
# Normal". Robust import: works both run-as-script and imported as `scripts.pagasa_scraper`.
try:
    from outlook import OUTLOOK_TO_ANOMALY, OUTLOOK_NORMALIZATION, match_outlook
    from retry_util import retry_call
except ImportError:  # pragma: no cover - import path differs under Airflow
    from scripts.outlook import OUTLOOK_TO_ANOMALY, OUTLOOK_NORMALIZATION, match_outlook
    from scripts.retry_util import retry_call

# Pilot province names → province_id mapping (must match provinces table)
PROVINCE_ID_MAP: dict[str, int] = {
    "pangasinan": 1,
    "ilocos norte": 2,
    "ilocos sur": 3,
    "la union": 4,
    "nueva ecija": 5,
    "tarlac": 6,
    "pampanga": 7,
    "bulacan": 8,
    "zambales": 9,
    "bataan": 10,
    "laguna": 11,
    "batangas": 12,
    "quezon": 13,
    "benguet": 14,
    "mountain province": 15,
}


def download_pagasa_pdf(url: str) -> bytes | None:
    """Download PAGASA bulletin PDF. Returns bytes or None on failure."""
    try:
        # Retry transient network errors / 5xx on the bulletin fetch.
        def _get():
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r
        resp = retry_call(_get, attempts=3, base_delay=2.0,
                          exceptions=(requests.RequestException,), label="pagasa download")
        content_type = resp.headers.get("content-type", "")
        if "pdf" in content_type or url.endswith(".pdf"):
            return resp.content
        # If the page is HTML (bulletin index), try to find the PDF link
        pdf_links = re.findall(r'href="([^"]+\.pdf)"', resp.text)
        if pdf_links:
            pdf_url = pdf_links[0]
            if not pdf_url.startswith("http"):
                pdf_url = "https://www.pagasa.dost.gov.ph" + pdf_url
            log.info(f"Found PDF link: {pdf_url}")
            pdf_resp = requests.get(pdf_url, timeout=30)
            pdf_resp.raise_for_status()
            return pdf_resp.content
        log.warning("No PDF found in PAGASA bulletin page")
        return None
    except Exception as e:
        log.error(f"Failed to download PAGASA bulletin: {e}")
        return None


def parse_outlook_from_pdf(pdf_bytes: bytes) -> dict[str, dict]:
    """
    Parse province-level seasonal outlook from PAGASA PDF.
    Returns {province_name: {seasonal_outlook, rainfall_anomaly_pct, raw_text}}

    PAGASA PDFs vary in format. This parser:
    1. Extracts all text from all pages
    2. Looks for province names followed by outlook keywords
    3. Falls back to a table-based extraction if text extraction fails

    NOTE: If PAGASA changes their PDF format, update the regex patterns below.
    """
    results = {}
    full_text = ""

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text += text.lower() + "\n"

                # Try table extraction
                for table in page.extract_tables():
                    if not table:
                        continue
                    for row in table:
                        if not row:
                            continue
                        row_text = " ".join(str(c) for c in row if c).lower()
                        for prov_name in PROVINCE_ID_MAP:
                            if prov_name in row_text:
                                # match_outlook checks the most specific label first, so
                                # "much below normal" is never mis-read as "below normal".
                                matched = match_outlook(row_text)
                                if matched:
                                    label, anomaly = matched
                                    results[prov_name] = {
                                        "seasonal_outlook": label,
                                        "rainfall_anomaly_pct": anomaly,
                                        "raw_text": row_text[:500],
                                    }
    except Exception as e:
        log.error(f"PDF parse error: {e}")

    # Text-based fallback: search for province name + outlook keyword pairs
    for prov_name in PROVINCE_ID_MAP:
        if prov_name in results:
            continue  # already found in table
        # Look for province name within 200 chars of an outlook keyword. Alternation is
        # ordered most-specific first so "much below normal" is captured whole, never as
        # the shorter "below normal".
        pattern = rf"{re.escape(prov_name)}.{{0,200}}?(much below normal|much above normal|below normal|above normal|near normal)"
        match = re.search(pattern, full_text, re.DOTALL)
        if match:
            outlook = match.group(1)
            results[prov_name] = {
                "seasonal_outlook": outlook.title(),
                "rainfall_anomaly_pct": OUTLOOK_TO_ANOMALY[outlook],
                "raw_text": match.group(0)[:500],
            }

    log.info(f"Parsed outlook for {len(results)} provinces from PDF")
    return results


# ELN-004: the built-in fallback below is a fixed baseline — it does NOT track new
# PAGASA bulletins. Flag it as stale so the pipeline never silently scores on old data.
MANUAL_OVERRIDE_AS_OF = date(2026, 6, 1)   # PAGASA baseline, June 2026
MANUAL_OVERRIDE_MAX_AGE_DAYS = 45          # PAGASA refreshes seasonal outlooks ~monthly


def get_manual_overrides() -> tuple[dict[str, dict], str]:
    """
    Manual override for when PDF parsing fails or PAGASA issues a separate alert.
    Set PAGASA_MANUAL_OVERRIDE env var to a JSON string:
    {"pangasinan": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -25.0}}

    Returns (overrides, source) where source is "env" (operator-provided, assumed fresh)
    or "default" (the fixed built-in baseline, subject to the staleness check above).
    """
    import json
    override_json = os.getenv("PAGASA_MANUAL_OVERRIDE")
    if override_json:
        try:
            return json.loads(override_json), "env"
        except Exception as e:
            log.error(f"Failed to parse PAGASA_MANUAL_OVERRIDE: {e}")

    # Default: June 2026 El Niño baseline (79% probability, Below Normal for most of Luzon)
    # Source: PAGASA El Niño Watch April 2026
    default_overrides = {
        "pangasinan": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -28.0, "raw_text": "PAGASA El Niño Watch April 2026 — 79% probability June-August 2026"},
        "ilocos norte": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -25.0, "raw_text": "PAGASA baseline June 2026"},
        "ilocos sur": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -25.0, "raw_text": "PAGASA baseline June 2026"},
        "la union": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -22.0, "raw_text": "PAGASA baseline June 2026"},
        "nueva ecija": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -30.0, "raw_text": "PAGASA baseline June 2026 — rice bowl province, highest risk"},
        "tarlac": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -27.0, "raw_text": "PAGASA baseline June 2026"},
        "pampanga": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -25.0, "raw_text": "PAGASA baseline June 2026"},
        "bulacan": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -22.0, "raw_text": "PAGASA baseline June 2026"},
        "zambales": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -24.0, "raw_text": "PAGASA baseline June 2026"},
        "bataan": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -22.0, "raw_text": "PAGASA baseline June 2026"},
        "laguna": {"seasonal_outlook": "Near Normal", "rainfall_anomaly_pct": -10.0, "raw_text": "PAGASA baseline June 2026"},
        "batangas": {"seasonal_outlook": "Near Normal", "rainfall_anomaly_pct": -8.0, "raw_text": "PAGASA baseline June 2026"},
        "quezon": {"seasonal_outlook": "Near Normal", "rainfall_anomaly_pct": -5.0, "raw_text": "PAGASA baseline June 2026"},
        "benguet": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -20.0, "raw_text": "PAGASA baseline June 2026 — highland areas"},
        "mountain province": {"seasonal_outlook": "Below Normal", "rainfall_anomaly_pct": -18.0, "raw_text": "PAGASA baseline June 2026 — highland areas"},
    }
    return default_overrides, "default"


def write_forecasts_to_supabase(
    outlook_data: dict[str, dict],
    forecast_date: date,
    source_bulletin: str = "",
) -> int:
    """
    Upsert province forecasts to pagasa_forecasts table.
    Returns number of rows written.
    """
    rows_written = 0
    for prov_name, data in outlook_data.items():
        province_id = PROVINCE_ID_MAP.get(prov_name)
        if not province_id:
            log.warning(f"Province not in pilot map: {prov_name}")
            continue
        try:
            supabase.table("pagasa_forecasts").upsert({
                "province_id": province_id,
                "forecast_date": forecast_date.isoformat(),
                "seasonal_outlook": data.get("seasonal_outlook", "Unknown"),
                "rainfall_anomaly_pct": data.get("rainfall_anomaly_pct", 0.0),
                "temperature_anomaly_c": data.get("temperature_anomaly_c", 0.0),
                "source_bulletin": source_bulletin or PAGASA_BULLETIN_URL,
                "raw_text": data.get("raw_text", ""),
            }, on_conflict="province_id,forecast_date").execute()
            rows_written += 1
            log.info(f"  Wrote forecast: {prov_name} → {data.get('seasonal_outlook')}")
        except Exception as e:
            log.error(f"  Failed to write forecast for {prov_name}: {e}")
    return rows_written


def run(forecast_date: date | None = None) -> int:
    """
    Main entry point. Returns number of provinces updated.
    Called by Airflow DAG.
    """
    if forecast_date is None:
        forecast_date = date.today()

    log.info(f"PAGASA scraper run: forecast_date={forecast_date}")

    # Try to download and parse the PDF
    pdf_bytes = download_pagasa_pdf(PAGASA_BULLETIN_URL)
    outlook_data = {}

    if pdf_bytes:
        outlook_data = parse_outlook_from_pdf(pdf_bytes)
        log.info(f"Parsed {len(outlook_data)} provinces from PDF")

    # Fall back to manual overrides if PDF parsing yielded < 10 provinces
    provenance = "pdf"
    if len(outlook_data) < 10:
        log.warning(f"PDF parse yielded only {len(outlook_data)} provinces — using manual overrides")
        manual, source = get_manual_overrides()
        provenance = source
        # Manual overrides fill any gaps; PDF-parsed data takes precedence
        for prov, data in manual.items():
            if prov not in outlook_data:
                outlook_data[prov] = data

        # ELN-004 freshness guard: the built-in baseline does not track new bulletins.
        if source == "default":
            age = (date.today() - MANUAL_OVERRIDE_AS_OF).days
            if age > MANUAL_OVERRIDE_MAX_AGE_DAYS:
                log.error(
                    "STALE FORECAST: PAGASA PDF parse failed and the built-in baseline is "
                    "%d days old (as-of %s, max %d). Risk scores may be outdated — set "
                    "PAGASA_MANUAL_OVERRIDE with the latest outlook or fix the scraper.",
                    age, MANUAL_OVERRIDE_AS_OF.isoformat(), MANUAL_OVERRIDE_MAX_AGE_DAYS,
                )
                if os.getenv("PAGASA_FAIL_ON_STALE", "false").lower() == "true":
                    raise RuntimeError(
                        f"Refusing to score on a {age}-day-old baseline forecast "
                        "(PAGASA_FAIL_ON_STALE=true). Update PAGASA_MANUAL_OVERRIDE or fix the scraper."
                    )
            else:
                log.warning("Using built-in baseline override (%d days old).", age)
        else:
            log.warning("Using operator-provided PAGASA_MANUAL_OVERRIDE for fallback.")

    log.info("Forecast provenance: %s (%d provinces)", provenance, len(outlook_data))

    rows = write_forecasts_to_supabase(
        outlook_data,
        forecast_date,
        source_bulletin=PAGASA_BULLETIN_URL,
    )
    log.info(f"PAGASA scraper complete: {rows} provinces updated")
    return rows


if __name__ == "__main__":
    run()
