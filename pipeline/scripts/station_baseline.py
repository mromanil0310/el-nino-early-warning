"""
station_baseline.py
The PAGASA station-level seasonal-rainfall baseline for June–August 2026 (El Niño Watch,
79% probability). Pure data + conversion — no I/O — so both the live scraper
(pagasa_scraper.py) and the offline preview (preview_run.py) build the SAME per-station
probability forecasts from one source of truth.

Each entry is the station's expected % rainfall anomaly for the season; the drought
gradient follows the June-2026 outlook — driest across the northern/central Luzon rice
belt (Cabanatuan, Dagupan, Laoag/Clark), easing toward the wetter Pacific-facing
southern Tagalog coast (Infanta, Tayabas). Anomalies are converted to a 3-way
Below/Near/Above probability distribution via outlook.probabilities_from_anomaly so the
whole pipeline speaks one probability model.

This is a FALLBACK baseline: when pagasa_scraper parses a real per-station bulletin it
uses that instead. Refresh these when PAGASA issues a materially new seasonal outlook
(same cadence as the province-level get_manual_overrides baseline).
"""

try:
    from outlook import probabilities_from_anomaly
except ImportError:  # pragma: no cover - import path differs under Airflow
    from scripts.outlook import probabilities_from_anomaly

# Baseline as-of date + max age mirror pagasa_scraper's province-level staleness guard.
# Re-verified 2026-07-17 against PAGASA (El Niño present + intensifying; below-normal
# rainfall the expected impact) — bump this each time the outlook is re-confirmed.
STATION_BASELINE_AS_OF = "2026-07-17"

# station_code → expected seasonal % rainfall anomaly (negative = drier than normal).
# Covers the 13 synoptic stations that serve the 15 Luzon pilot provinces
# (province_station_mapping, migration 006).
STATION_BASELINE_ANOMALY: dict[str, float] = {
    "CABANATUAN": -30.0,    # Nueva Ecija — rice bowl, driest
    "DAGUPAN": -28.0,       # Pangasinan
    "CLARK": -25.0,         # Pampanga / Tarlac
    "LAOAG": -25.0,         # Ilocos Norte
    "SINAIT": -25.0,        # Ilocos Sur / La Union
    "IBA": -24.0,           # Zambales
    "SANILDEFONSO": -22.0,  # Bulacan
    "CUBI": -22.0,          # Bataan
    "BAGUIO": -19.0,        # Benguet / Mountain Province — highland
    "AMBULONG": -9.0,       # Laguna / Batangas — southern Tagalog, milder
    "TAYABAS": -6.0,        # Quezon (inland)
    "ALABAT": -5.0,         # Quezon (island)
    "INFANTA": -3.0,        # Quezon (Pacific coast, wettest)
}


def station_baseline_probabilities() -> dict[str, tuple[float, float, float]]:
    """station_code → (P_below, P_near, P_above) fractions, from the baseline anomalies."""
    return {code: probabilities_from_anomaly(a) for code, a in STATION_BASELINE_ANOMALY.items()}
