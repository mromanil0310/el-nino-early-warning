"""
outlook.py
Pure PAGASA seasonal-outlook classification — no I/O, no heavy dependencies, so it
can be imported and unit-tested without Supabase or pdfplumber.

Single source of truth for mapping PAGASA rainfall-outlook labels to a numeric
anomaly. Used by pagasa_scraper.py.
"""

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
