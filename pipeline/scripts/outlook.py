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
# This model restores the real signal. Rainfall severity is the DROUGHT-relevant part
# of the forecast distribution — the probability of BELOW-normal rainfall:
#
#     severity = P_below · 1.0  +  P_near · 0.0  +  P_above · 0.0  =  P_below
#
# Only below-normal rainfall drives El Niño drought risk, so near- and above-normal
# outcomes contribute nothing. A canonical "Below Normal"-tilted distribution still
# reproduces ≈0.75 (P_below ≈ 0.75), so the legacy calibration is preserved at the
# below-normal end, while near-normal provinces now score low (P_below near the 1/3
# climatological floor) instead of being propped up by a near-normal severity term.
# Continuous in the probabilities ⇒ provinces with different tilts get different scores.
#
# The anomaly→probability mapping has a DEAD ZONE around 0: mild anomalies (|a| ≤ 8%)
# stay at the climatological P_below, and the drought signal only ramps in past it — so
# a −5%…−9% ("near normal") province stays Low at every crop stage, while the drought
# belt (−18%…−40%) differentiates across the Medium/High range.
#
# These functions are the single source of truth, mirrored by:
#   - models/staging/stg_pagasa_station_forecasts.sql (per-station severity)
#   - models/marts/int_province_rainfall.sql          (weighted station→province)
#   - scripts/preview_run.py                          (offline preview / integration test)

# Per-outcome drought severity. Only below-normal rainfall carries drought risk.
SEVERITY_BELOW = 1.0
SEVERITY_NEAR = 0.0
SEVERITY_ABOVE = 0.0

# Anomaly → probability calibration. P_below sits at the climatological base inside a
# dead zone of ±DEADZONE %, then ramps up with dryness (DRY_SLOPE) / down with wetness
# (WET_SLOPE). Tuned so Below Normal (−25%) → P_below ≈ 0.74, Much Below (−40%) → ≈0.95,
# and mild −5…−9% provinces stay ≤ 0.35 (Low even at peak crop vulnerability).
_CLIMATOLOGICAL = 1.0 / 3.0
_PB_BASE = 0.30
_PB_DEADZONE = 8.0
_PB_DRY_SLOPE = 0.026
_PB_WET_SLOPE = 0.030
_PA_SLOPE = 0.010
_P_MIN = 0.02
_P_MAX = 0.95


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def severity_from_probabilities(p_below: float, p_near: float, p_above: float) -> float:
    """Drought severity over a PAGASA 3-way rainfall probability distribution.

    severity = P_below (near/above-normal outcomes carry no drought risk). Accepts
    probabilities as fractions (0–1) or percentages (0–100) — the triple is normalized
    to sum to 1 first, so either scale works. Returns a severity in [0, 1]. A degenerate
    all-zero triple returns 0.0 (no signal).
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
    aren't available. A dead zone of ±8% keeps mild anomalies at the climatological
    P_below; beyond it, drier raises P_below and wetter lowers it. Returns (P_below,
    P_near, P_above) as fractions summing to 1.
    """
    dry = max(0.0, -anomaly_pct - _PB_DEADZONE)
    wet = max(0.0, anomaly_pct - _PB_DEADZONE)
    p_below = _clamp(_PB_BASE + dry * _PB_DRY_SLOPE - wet * _PB_WET_SLOPE, _P_MIN, _P_MAX)
    p_above = _clamp(_CLIMATOLOGICAL + anomaly_pct * _PA_SLOPE, _P_MIN, _P_MAX)
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

    The inverse of ``probabilities_from_anomaly``'s P_below branch (dead zone included),
    so a distribution built from an anomaly round-trips back to it (within clamping).
    Used to show a single anomaly figure for a weighted-aggregated province.
    """
    total = p_below + p_near + p_above
    pb = (p_below / total) if total > 0 else _PB_BASE
    if pb > _PB_BASE:
        return round(-(_PB_DEADZONE + (pb - _PB_BASE) / _PB_DRY_SLOPE), 1)
    if pb < _PB_BASE:
        return round(_PB_DEADZONE + (_PB_BASE - pb) / _PB_WET_SLOPE, 1)
    return 0.0


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
    # "Much Below/Above Normal" is a strong PAGASA signal (~−40% anomaly) — reserve it
    # for a dominant tail (P_below ≥ 0.88), so the ordinary El Niño drought belt
    # (P_below ≈ 0.56–0.87, i.e. −18…−30%) stays labelled "Below Normal" on the dashboard.
    if tilt >= 0.30:
        return "Much Below Normal" if pb >= 0.88 else "Below Normal"
    if tilt <= -0.30:
        return "Much Above Normal" if pa >= 0.88 else "Above Normal"
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
