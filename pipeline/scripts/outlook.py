"""
outlook.py
Pure PAGASA seasonal-outlook classification — no I/O, no heavy dependencies, so it
can be imported and unit-tested without Supabase or pdfplumber.

Single source of truth for mapping PAGASA rainfall-outlook labels to a numeric
anomaly, plus the probability-based station rainfall-severity model (ELN-031).
Used by pagasa_scraper.py and preview_run.py.
"""

import re

# Rainfall anomaly classification → numeric mapping (PAGASA standard labels).
#   below normal       → drier than normal; elevated El Niño risk
#   much below normal  → severe drought outlook; highest El Niño risk
OUTLOOK_TO_ANOMALY: dict[str, float] = {
    "below normal": -25.0,
    "much below normal": -40.0,
    "near normal": 0.0,
    "above normal": 15.0,
    "much above normal": 30.0,
}

# Variant spellings / abbreviations PAGASA bulletins sometimes use.
OUTLOOK_NORMALIZATION: dict[str, str] = {
    "bn": "below normal",
    "mbn": "much below normal",
    "nn": "near normal",
    "an": "above normal",
    "man": "much above normal",
    "below-normal": "below normal",
    "much-below-normal": "much below normal",
    "near-normal": "near normal",
    "above-normal": "above normal",
}

# Outlook labels ordered MOST-SPECIFIC FIRST so that "much below normal" is matched
# before its substring "below normal" (and "much above normal" before "above normal").
#
# This ordering is safety-critical: "below normal" is a substring of "much below
# normal", so a naive in-order substring scan classifies the *most severe* drought
# outlook (weight 1.0) as the milder "Below Normal" (weight 0.75). That silently
# under-warns the hardest-hit provinces — e.g. a late-vegetative rice crop would drop
# from 70 (High) to 52.5 (Medium). Always match longest label first.
OUTLOOK_KEYS_BY_SPECIFICITY: list[str] = sorted(OUTLOOK_TO_ANOMALY, key=len, reverse=True)


def match_outlook(text: str) -> tuple[str, float] | None:
    """Find the PAGASA seasonal outlook inside free text (e.g. a PDF table row).

    Returns ``(Title-Case label, rainfall_anomaly_pct)`` or ``None`` if no known
    label is present. The most specific label wins, so "much below normal" is never
    read as "below normal".
    """
    haystack = text.lower()
    for key in OUTLOOK_KEYS_BY_SPECIFICITY:
        if key in haystack:
            return key.title(), OUTLOOK_TO_ANOMALY[key]
    return None


# ─── Probability-based rainfall severity (station-level model, ELN-031) ───────────
#
# PAGASA's real seasonal rainfall outlook is issued PER SYNOPTIC STATION as a 3-way
# probability distribution — P(Below Normal) / P(Near Normal) / P(Above Normal),
# summing to 100% — not as one categorical label per province. The pilot collapsed
# that to a single categorical label per province, so every "Below Normal" province
# got the SAME severity weight (0.75) and every province scored identically regardless
# of how strong its drought tilt actually was.
#
# This model restores the real signal. Rainfall severity is the EXPECTED drought
# severity over the forecast distribution:
#
#     severity = P_below · 1.0  +  P_near · 0.25  +  P_above · 0.0
#
# The per-outcome severities {below: 1.0, near: 0.25, above: 0.0} are exactly the
# legacy categorical step weights, so a canonical "Below Normal"-tilted distribution
# reproduces ≈0.75 and the change is a smooth generalization, not a recalibration.
# Because it is continuous in the probabilities, two provinces that PAGASA tilts
# differently now get different severities (and therefore different risk scores).
#
# These functions are the single source of truth, mirrored by:
#   - models/staging/stg_pagasa_station_forecasts.sql (per-station severity)
#   - models/marts/int_province_rainfall.sql          (weighted station→province)
#   - scripts/preview_run.py                          (offline preview / integration test)

# Per-outcome drought severity — identical to the legacy categorical step weights.
SEVERITY_BELOW = 1.0
SEVERITY_NEAR = 0.25
SEVERITY_ABOVE = 0.0

# Anomaly → probability slopes (per 1% anomaly). Drier (more negative anomaly) raises
# P_below and lowers P_above around the climatological 1/3 base. Calibrated so the
# legacy category anomalies reproduce the legacy severities: e.g. Below Normal (−25%)
# → severity ≈ 0.75, Much Below Normal (−40%) → ≈ 0.95.
_CLIMATOLOGICAL = 1.0 / 3.0
_BELOW_SLOPE = 0.015
_ABOVE_SLOPE = 0.010
_P_MIN = 0.02
_P_MAX = 0.95


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def severity_from_probabilities(p_below: float, p_near: float, p_above: float) -> float:
    """Expected drought severity over a PAGASA 3-way rainfall probability distribution.

    Accepts probabilities as fractions (0–1) or percentages (0–100) — the triple is
    normalized to sum to 1 first, so either scale works. Returns a severity in [0, 1].
    A degenerate all-zero triple returns 0.0 (no signal).
    """
    total = p_below + p_near + p_above
    if total <= 0:
        return 0.0
    pb, pn, pa = p_below / total, p_near / total, p_above / total
    severity = pb * SEVERITY_BELOW + pn * SEVERITY_NEAR + pa * SEVERITY_ABOVE
    return _clamp(severity, 0.0, 1.0)


def probabilities_from_anomaly(anomaly_pct: float) -> tuple[float, float, float]:
    """Approximate a PAGASA 3-way probability distribution from a % rainfall anomaly.

    Used to express the manual-override baseline (and to fold legacy categorical
    province forecasts into the probability model) when true per-station probabilities
    aren't available. Negative anomaly = drier = higher P_below. Returns (P_below,
    P_near, P_above) as fractions summing to 1.
    """
    p_below = _clamp(_CLIMATOLOGICAL - anomaly_pct * _BELOW_SLOPE, _P_MIN, _P_MAX)
    p_above = _clamp(_CLIMATOLOGICAL + anomaly_pct * _ABOVE_SLOPE, _P_MIN, _P_MAX)
    p_near = max(0.0, 1.0 - p_below - p_above)
    total = p_below + p_near + p_above
    return (p_below / total, p_near / total, p_above / total)


def probabilities_from_category(label: str) -> tuple[float, float, float]:
    """Canonical 3-way probability distribution for a legacy categorical outlook label.

    Routes through the shared anomaly→probability mapping using the same canonical
    anomaly per label as ``OUTLOOK_TO_ANOMALY``, so categorical fallbacks stay
    calibrated with the legacy step weights. Unknown labels → Near Normal.
    """
    anomaly = OUTLOOK_TO_ANOMALY.get(label.strip().lower(), OUTLOOK_TO_ANOMALY["near normal"])
    return probabilities_from_anomaly(anomaly)


def anomaly_from_probabilities(p_below: float, p_near: float, p_above: float) -> float:
    """Representative % rainfall anomaly for display, inverted from P_below.

    The inverse of ``probabilities_from_anomaly``'s P_below branch, so a distribution
    built from an anomaly round-trips back to it (within clamping). Used to show a
    single anomaly figure on the dashboard for a weighted-aggregated province.
    """
    total = p_below + p_near + p_above
    pb = (p_below / total) if total > 0 else _CLIMATOLOGICAL
    return round((_CLIMATOLOGICAL - pb) / _BELOW_SLOPE, 1)


def label_from_probabilities(p_below: float, p_near: float, p_above: float) -> str:
    """Representative PAGASA outlook label for a distribution (display only).

    Uses the below-vs-above tilt: a strong below tilt with high P_below reads as
    "Much Below Normal", a moderate below tilt as "Below Normal", the mirror for wet,
    else "Near Normal".
    """
    total = p_below + p_near + p_above
    if total <= 0:
        return "Near Normal"
    pb, pa = p_below / total, p_above / total
    tilt = pb - pa
    # "Much Below/Above Normal" is a strong PAGASA signal — reserve it for a dominant
    # tail (≥0.80), so an ordinary El Niño "Below Normal" baseline (P_below ≈ 0.7–0.78)
    # stays labelled "Below Normal" rather than being escalated on the dashboard.
    if tilt >= 0.30:
        return "Much Below Normal" if pb >= 0.80 else "Below Normal"
    if tilt <= -0.30:
        return "Much Above Normal" if pa >= 0.80 else "Above Normal"
    return "Near Normal"


def parse_station_probabilities_from_text(
    text: str,
    stations,
    window: int = 160,
) -> dict[str, tuple[float, float, float]]:
    """Best-effort extraction of per-station 3-way rainfall probabilities from bulletin text.

    ``stations`` is an iterable of ``(station_code, station_name)``. For each station,
    finds its name (or code) in the text and reads the first three consecutive numbers in
    the following window that look like a probability distribution (each 0–100, summing to
    ~100). Returns ``{station_code: (P_below, P_near, P_above)}`` as PERCENTAGES (0–100),
    only for stations where such a triple was found.

    ASSUMES PAGASA prints the columns in Below / Near / Above order. This is UNVERIFIED
    against a live PAGASA station bulletin — pagasa_scraper falls back to the station
    baseline (station_baseline.py) whenever this yields too few stations, so the pipeline
    never scores on a mis-parsed table.
    """
    haystack = text.lower()
    out: dict[str, tuple[float, float, float]] = {}
    for code, name in stations:
        # "Dagupan City" from "Dagupan City Synoptic Station"; fall back to the code.
        key = name.lower().split(" synoptic")[0].strip()
        idx = haystack.find(key)
        if idx == -1:
            idx = haystack.find(code.lower())
            if idx == -1:
                continue
            key = code.lower()
        window_text = haystack[idx : idx + len(key) + window]
        nums = [float(n) for n in re.findall(r"\d{1,3}(?:\.\d+)?", window_text)]
        for i in range(len(nums) - 2):
            a, b, c = nums[i], nums[i + 1], nums[i + 2]
            if all(0 <= v <= 100 for v in (a, b, c)) and abs(a + b + c - 100) <= 2:
                out[code] = (a, b, c)
                break
    return out
