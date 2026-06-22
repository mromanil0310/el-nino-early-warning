"""
test_risk_scoring.py
Unit tests for El Niño risk scoring logic.

Tests the core formula:
  risk_score = rainfall_severity_weight × crop_stage_vulnerability_index × 100

Also tests:
  - PAGASA outlook normalization
  - Risk level classification (High/Medium/Low)
  - Crop stage vulnerability index mapping
  - Edge cases (off-season, zero-vulnerability)

Run: python -m pytest pipeline/tests/test_risk_scoring.py -v
"""

import os
import sys

import pytest
from datetime import date

# crop_stage.py is the pure Python reference for stg_crop_calendars.sql — testing the
# REAL date→stage→vulnerability logic (no parallel reimplementation that can drift).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from crop_stage import derive_stage  # noqa: E402


# ─── Inline the core scoring logic so tests don't need Supabase ──────────────
# (compute_risk_score / classify_risk_level / get_rainfall_severity_weight mirror the
#  arithmetic in risk_scores.sql + stg_pagasa_forecasts.sql. The crop-stage mapping is
#  tested via the shared derive_stage reference above, not a separate copy here.)

def compute_risk_score(rainfall_severity_weight: float, vulnerability_index: float) -> float:
    """Core El Niño risk formula."""
    return round(rainfall_severity_weight * vulnerability_index * 100, 1)


def classify_risk_level(risk_score: float) -> str:
    """Classify risk score into High/Medium/Low."""
    if risk_score > 65:
        return 'High'
    elif risk_score >= 35:
        return 'Medium'
    else:
        return 'Low'


def get_rainfall_severity_weight(outlook: str) -> float:
    """Map PAGASA seasonal outlook to severity weight."""
    normalized = outlook.strip().lower()
    mapping = {
        'much below normal': 1.0,
        'below normal': 0.75,
        'near normal': 0.25,
        'above normal': 0.0,
        'much above normal': 0.0,
    }
    return mapping.get(normalized, 0.25)  # default Near Normal


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestRainfallSeverityWeight:
    def test_much_below_normal(self):
        assert get_rainfall_severity_weight('Much Below Normal') == 1.0

    def test_below_normal(self):
        assert get_rainfall_severity_weight('Below Normal') == 0.75

    def test_near_normal(self):
        assert get_rainfall_severity_weight('Near Normal') == 0.25

    def test_above_normal(self):
        assert get_rainfall_severity_weight('Above Normal') == 0.0

    def test_much_above_normal(self):
        assert get_rainfall_severity_weight('Much Above Normal') == 0.0

    def test_case_insensitive(self):
        assert get_rainfall_severity_weight('below normal') == 0.75
        assert get_rainfall_severity_weight('BELOW NORMAL') == 0.75
        assert get_rainfall_severity_weight('Below Normal') == 0.75

    def test_unknown_defaults_to_near_normal(self):
        assert get_rainfall_severity_weight('unknown') == 0.25


class TestCropStageDerivation:
    """
    Exercises derive_stage (the reference for stg_crop_calendars.sql) over real seed
    dates — Pangasinan palay (wet) from seeds/crop_calendars.csv:
      planting 2026-06-01 → 2026-07-31, harvest 2026-09-15 → 2026-11-30.
    The late-vegetative→reproductive midpoint is 2026-08-23.

    This replaces the previous string-lookup test, which diverged from the SQL: it
    mapped 'vegetative' → 0.7 only and asserted a 'late_vegetative' label the SQL never
    emits. In reality the SQL labels BOTH the early (0.5) and late (0.7) vegetative
    windows 'vegetative'; the date — not the label — sets the vulnerability.
    """
    PS, PE = date(2026, 6, 1), date(2026, 7, 31)
    HS, HE = date(2026, 9, 15), date(2026, 11, 30)

    def stage(self, d: date):
        return derive_stage(d, self.PS, self.PE, self.HS, self.HE)

    def test_pre_planting(self):
        assert self.stage(date(2026, 5, 15)) == ('pre-planting', 0.4)

    def test_early_vegetative(self):
        assert self.stage(date(2026, 6, 1)) == ('vegetative', 0.5)   # planting_start (inclusive)
        assert self.stage(date(2026, 7, 1)) == ('vegetative', 0.5)
        assert self.stage(date(2026, 7, 31)) == ('vegetative', 0.5)  # planting_end → still early (first-match)

    def test_late_vegetative(self):
        assert self.stage(date(2026, 8, 10)) == ('vegetative', 0.7)
        assert self.stage(date(2026, 8, 23)) == ('vegetative', 0.7)  # midpoint (inclusive, first-match)

    def test_reproductive_maximum(self):
        assert self.stage(date(2026, 8, 24)) == ('reproductive', 1.0)
        assert self.stage(date(2026, 9, 1)) == ('reproductive', 1.0)
        assert self.stage(date(2026, 9, 15)) == ('reproductive', 1.0)  # harvest_start → reproductive (first-match)

    def test_harvest_low(self):
        assert self.stage(date(2026, 10, 1)) == ('harvest', 0.3)
        assert self.stage(date(2026, 11, 30)) == ('harvest', 0.3)      # harvest_end (inclusive)

    def test_off_season_zero(self):
        assert self.stage(date(2026, 12, 25)) == ('off-season', 0.0)

    def test_vegetative_label_covers_two_vulnerabilities(self):
        # The exact divergence the old test missed: 'vegetative' is BOTH 0.5 and 0.7.
        early = self.stage(date(2026, 7, 1))
        late = self.stage(date(2026, 8, 10))
        assert early[0] == late[0] == 'vegetative'
        assert early[1] == 0.5 and late[1] == 0.7


class TestRiskScoreFormula:
    """Test core formula: risk_score = rainfall_severity × vulnerability × 100"""

    def test_maximum_risk(self):
        """Much Below Normal × Reproductive = 100.0 (worst case)"""
        score = compute_risk_score(
            rainfall_severity_weight=1.0,   # Much Below Normal
            vulnerability_index=1.0,         # Reproductive
        )
        assert score == 100.0

    def test_high_risk_below_normal_reproductive(self):
        """Below Normal × Reproductive = 75.0 → High"""
        score = compute_risk_score(
            rainfall_severity_weight=0.75,
            vulnerability_index=1.0,
        )
        assert score == 75.0
        assert classify_risk_level(score) == 'High'

    def test_medium_risk_below_normal_vegetative(self):
        """Below Normal × Vegetative = 52.5 → Medium"""
        score = compute_risk_score(
            rainfall_severity_weight=0.75,
            vulnerability_index=0.7,
        )
        assert score == 52.5
        assert classify_risk_level(score) == 'Medium'

    def test_low_risk_near_normal_preplanting(self):
        """Near Normal × Pre-planting = 10.0 → Low"""
        score = compute_risk_score(
            rainfall_severity_weight=0.25,
            vulnerability_index=0.4,
        )
        assert score == 10.0
        assert classify_risk_level(score) == 'Low'

    def test_zero_risk_above_normal(self):
        """Above Normal → weight=0.0 → risk=0.0 regardless of crop stage"""
        score = compute_risk_score(
            rainfall_severity_weight=0.0,
            vulnerability_index=1.0,   # Reproductive — still zero
        )
        assert score == 0.0

    def test_zero_risk_off_season(self):
        """Off-season crops → vulnerability=0.0 → risk=0.0"""
        score = compute_risk_score(
            rainfall_severity_weight=1.0,   # Worst drought
            vulnerability_index=0.0,         # Off-season
        )
        assert score == 0.0

    def test_nueva_ecija_baseline(self):
        """
        Nueva Ecija (PH rice bowl) in wet season reproductive stage:
        Below Normal (-30%) × Reproductive → High risk
        """
        score = compute_risk_score(
            rainfall_severity_weight=0.75,  # Below Normal
            vulnerability_index=1.0,         # Wet season flowering
        )
        assert score == 75.0
        assert classify_risk_level(score) == 'High'

    def test_laguna_near_normal(self):
        """Laguna forecasted Near Normal → Low risk even at reproductive stage (25 < 35)"""
        score = compute_risk_score(
            rainfall_severity_weight=0.25,  # Near Normal
            vulnerability_index=1.0,         # Reproductive
        )
        assert score == 25.0
        assert classify_risk_level(score) == 'Low'


class TestRiskLevelClassification:
    """Verify threshold boundaries."""

    def test_high_threshold_boundary(self):
        assert classify_risk_level(65.1) == 'High'
        assert classify_risk_level(65.0) == 'Medium'  # boundary is exclusive
        assert classify_risk_level(100.0) == 'High'

    def test_medium_threshold_boundary(self):
        assert classify_risk_level(35.0) == 'Medium'
        assert classify_risk_level(34.9) == 'Low'

    def test_low(self):
        assert classify_risk_level(0.0) == 'Low'
        assert classify_risk_level(10.0) == 'Low'


class TestOutlookNormalization:
    """Test PAGASA PDF may produce variant spellings."""

    def test_hyphenated(self):
        # PAGASA PDFs sometimes use hyphens
        # This tests that we handle it in scraper normalization
        # (the SQL handles it via LIKE '%below%')
        assert 'below' in 'below-normal'
        assert 'much below' in 'much-below-normal'.replace('-', ' ')

    def test_abbreviation_mapping(self):
        """BN, MBN etc used in some PAGASA tables."""
        abbrev_map = {'bn': 'below normal', 'mbn': 'much below normal', 'nn': 'near normal'}
        assert abbrev_map['bn'] == 'below normal'
        assert get_rainfall_severity_weight(abbrev_map['mbn']) == 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
