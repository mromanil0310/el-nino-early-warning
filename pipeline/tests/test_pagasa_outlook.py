"""
test_pagasa_outlook.py
Unit tests for PAGASA seasonal-outlook classification (pipeline/scripts/outlook.py).

Guards the safety-critical ordering bug: "much below normal" (the most severe drought
outlook, weight 1.0) must never be downgraded to "below normal" (weight 0.75), which
would under-warn the hardest-hit provinces.

Run: python -m pytest pipeline/tests/test_pagasa_outlook.py -v
"""

import os
import sys

import pytest

# outlook.py is a pure module (no Supabase/pdfplumber), importable on its own.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from outlook import match_outlook, OUTLOOK_TO_ANOMALY  # noqa: E402


class TestMatchOutlookSpecificity:
    """The regression: most-specific label must win over its substring."""

    def test_much_below_normal_not_downgraded(self):
        label, anomaly = match_outlook("nueva ecija much below normal")
        assert label == "Much Below Normal"
        assert anomaly == -40.0

    def test_much_above_normal_not_downgraded(self):
        label, anomaly = match_outlook("benguet much above normal")
        assert label == "Much Above Normal"
        assert anomaly == 30.0

    def test_realistic_pdf_table_row(self):
        # A PAGASA table row joined into one string, as the scraper builds it.
        row = "pangasinan | jun-aug 2026 | much below normal | -40%"
        label, anomaly = match_outlook(row)
        assert (label, anomaly) == ("Much Below Normal", -40.0)


class TestMatchOutlookLabels:
    def test_below_normal(self):
        assert match_outlook("ilocos norte below normal") == ("Below Normal", -25.0)

    def test_above_normal(self):
        assert match_outlook("laguna above normal") == ("Above Normal", 15.0)

    def test_near_normal(self):
        assert match_outlook("quezon near normal") == ("Near Normal", 0.0)

    def test_case_insensitive(self):
        assert match_outlook("TARLAC: MUCH BELOW NORMAL") == ("Much Below Normal", -40.0)

    def test_no_outlook_returns_none(self):
        assert match_outlook("pampanga forecast pending") is None
        assert match_outlook("") is None


def test_every_label_is_recoverable():
    """Every label in the mapping round-trips through match_outlook unchanged."""
    for key, anomaly in OUTLOOK_TO_ANOMALY.items():
        label, got = match_outlook(f"some province {key} text")
        assert label == key.title()
        assert got == anomaly
