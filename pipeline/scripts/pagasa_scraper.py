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
    from outlook import (
        OUTLOOK_TO_ANOMALY,
        OUTLOOK_NORMALIZATION,
        match_outlook,
        parse_station_probabilities_from_text,
    )
    from retry_util import retry_call
    from station_baseline import STATION_BASELINE_AS_OF, station_baseline_probabilities
except ImportError:  # pragma: no cover - import path differs under Airflow
    from scripts.outlook import (
        OUTLOOK_TO_ANOMALY,
        OUTLOOK_NORMALIZATION,
        match_outlook,
        parse_station_probabilities_from_text,
    )
    from scripts.retry_util import retry_call
    from scripts.station_baseline import STATION_BASELINE_AS_OF, station_baseline_probabilities

# Province names → province_id, generated from the canonical seed CSV (all 82
# provinces + PAGASA aliases). Containment-aware matching prevents "south cotabato"
# text from populating (North) Cotabato, etc. (Phase 2 Build 3.)
try:
    from provinces_map import PROVINCE_ID_MAP, find_all_province_in_text, find_province_in_text
except ImportError:  # pragma: no cover - import path differs under Airflow
    from scripts.provinces_map import PROVINCE_ID_MAP, find_all_province_in_text, find_province_in_text


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
                            if find_province_in_text(prov_name, row_text) is not None:
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

    # Text-based fallback: search for province name + outlook keyword pairs.
    # find_province_in_text is containment-aware (a "south cotabato" mention never
    # anchors plain "cotabato"); the outlook keyword must appear within 200 chars
    # after the standalone province mention. Alternation is ordered most-specific
    # first so "much below normal" is captured whole, never as "below normal".
    for prov_name in PROVINCE_ID_MAP:
        if prov_name in results:
            continue  # already found in table
        for pos in find_all_province_in_text(prov_name, full_text):
            window = full_text[pos : pos + len(prov_name) + 200]
            match = re.search(
                r"(much below normal|much above normal|below normal|above normal|near normal)",
                window,
                re.DOTALL,
            )
            if match:
                outlook = match.group(1)
                results[prov_name] = {
                    "seasonal_outlook": outlook.title(),
                    "rainfall_anomaly_pct": OUTLOOK_TO_ANOMALY[outlook],
                    "raw_text": window[: match.end()][:500],
                }
                break

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


# ─── ELN-031: per-station probability forecasts ──────────────────────────────
# PAGASA issues rainfall outlooks per synoptic station as Below/Near/Above probabilities.
# We write them to pagasa_station_forecasts; the dbt layer (int_province_rainfall) weight-
# averages them to the province level so provinces differentiate. Parsing the real station
# bulletin is best-effort (unverified format) — when it yields too few stations we fall
# back to the station baseline, exactly like the province-level path.
STATION_BASELINE_MAX_AGE_DAYS = 45


def _extract_full_text(pdf_bytes: bytes) -> str:
    """Concatenate the text of every PDF page (lowercased). '' on failure."""
    try:
        parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                parts.append((page.extract_text() or "").lower())
        return "\n".join(parts)
    except Exception as e:
        log.error(f"Station PDF text extraction failed: {e}")
        return ""


def fetch_station_registry() -> list[dict]:
    """PAGASA synoptic station registry (id, station_code, name) from Supabase."""
    try:
        res = supabase.table("pagasa_stations").select("id, station_code, name").execute()
        return res.data or []
    except Exception as e:
        log.error(f"Failed to fetch station registry: {e}")
        return []


def build_station_probabilities(
    full_text: str, registry: list[dict]
) -> tuple[dict[str, tuple[float, float, float]], str]:
    """Return ({station_code: (below%, near%, above%)}, provenance).

    Tries to parse the bulletin; if fewer than 5 stations parse, fills the rest from the
    station baseline. Provenance is "pdf" when parsing carried it, else "baseline".
    """
    stations = [(r["station_code"], r["name"]) for r in registry]
    parsed = parse_station_probabilities_from_text(full_text, stations) if full_text else {}
    provenance = "pdf"
    if len(parsed) < 5:
        provenance = "baseline"
        for code, (pb, pn, pa) in station_baseline_probabilities().items():
            if code not in parsed:
                parsed[code] = (round(pb * 100, 1), round(pn * 100, 1), round(pa * 100, 1))
    return parsed, provenance


def write_station_forecasts_to_supabase(
    station_probs: dict[str, tuple[float, float, float]],
    registry: list[dict],
    forecast_date: date,
    source_bulletin: str = "",
) -> int:
    """Upsert per-station probability forecasts. Returns rows written."""
    code_to_id = {r["station_code"]: r["id"] for r in registry}
    rows_written = 0
    for code, (pb, pn, pa) in station_probs.items():
        station_id = code_to_id.get(code)
        if not station_id:
            log.warning(f"Station code not in registry: {code}")
            continue
        try:
            supabase.table("pagasa_station_forecasts").upsert({
                "station_id": station_id,
                "forecast_date": forecast_date.isoformat(),
                "below_normal_pct": pb,
                "near_normal_pct": pn,
                "above_normal_pct": pa,
                "source_bulletin": source_bulletin or PAGASA_BULLETIN_URL,
            }, on_conflict="station_id,forecast_date").execute()
            rows_written += 1
        except Exception as e:
            log.error(f"  Failed to write station forecast for {code}: {e}")
    return rows_written


def run_station_forecasts(pdf_bytes: bytes | None, forecast_date: date) -> int:
    """Write per-station probability forecasts (parsed or baseline). Returns rows written."""
    registry = fetch_station_registry()
    if not registry:
        log.warning("No station registry — skipping station forecasts (apply migration 006/008?)")
        return 0
    full_text = _extract_full_text(pdf_bytes) if pdf_bytes else ""
    station_probs, provenance = build_station_probabilities(full_text, registry)

    if provenance == "baseline":
        age = (date.today() - date.fromisoformat(STATION_BASELINE_AS_OF)).days
        if age > STATION_BASELINE_MAX_AGE_DAYS:
            log.error(
                "STALE STATION BASELINE: bulletin parse yielded too few stations and the "
                "baseline is %d days old (as-of %s, max %d). Refresh station_baseline.py.",
                age, STATION_BASELINE_AS_OF, STATION_BASELINE_MAX_AGE_DAYS,
            )
        else:
            log.warning("Using station baseline (%d days old) for %d stations.", age, len(station_probs))
    else:
        log.info("Parsed %d stations from bulletin.", len(station_probs))

    rows = write_station_forecasts_to_supabase(station_probs, registry, forecast_date)
    log.info("Station forecast provenance: %s (%d stations written)", provenance, rows)
    return rows


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

    # ELN-031: per-station probability forecasts (weighted to provinces in dbt). The
    # province-level write above remains the fallback for provinces without station data.
    station_rows = run_station_forecasts(pdf_bytes, forecast_date)
    log.info(f"PAGASA station forecasts: {station_rows} stations updated")

    return rows


if __name__ == "__main__":
    run()
