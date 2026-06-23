"""
test_advisory.py
Unit tests for the Claude advisory parser (pipeline/scripts/advisory.py).

Run: python -m pytest pipeline/tests/test_advisory.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from advisory import parse_advisory  # noqa: E402


def test_single_line_values():
    raw = "ADVISORY_EN: High risk.\nADVISORY_TL: Mataas na panganib.\nSMS_TEXT: Aug 31 High risk."
    out = parse_advisory(raw)
    assert out["ADVISORY_EN"] == "High risk."
    assert out["ADVISORY_TL"] == "Mataas na panganib."
    assert out["SMS_TEXT"] == "Aug 31 High risk."


def test_multiline_values_are_captured_in_full():
    # The regression: a multi-sentence ADVISORY_EN spanning lines must not truncate.
    raw = (
        "ADVISORY_EN: Sentence one about the risk.\n"
        "Sentence two with the action.\n"
        "Sentence three on what to watch.\n"
        "ADVISORY_TL: Unang pangungusap.\nPangalawang pangungusap.\n"
        "SMS_TEXT: Aug 31 Nueva Ecija: High risk. Irrigate. -ELNINO"
    )
    out = parse_advisory(raw)
    assert out["ADVISORY_EN"] == "Sentence one about the risk. Sentence two with the action. Sentence three on what to watch."
    assert out["ADVISORY_TL"] == "Unang pangungusap. Pangalawang pangungusap."
    assert out["SMS_TEXT"].startswith("Aug 31 Nueva Ecija: High risk.")


def test_tolerates_bullets_numbering_and_case():
    raw = "1. advisory_en: foo\n2) ADVISORY_TL - bar\n- SMS_TEXT : baz"
    out = parse_advisory(raw)
    assert out == {"ADVISORY_EN": "foo", "ADVISORY_TL": "bar", "SMS_TEXT": "baz"}


def test_missing_keys_simply_absent():
    out = parse_advisory("ADVISORY_EN: only english here")
    assert out == {"ADVISORY_EN": "only english here"}


def test_empty_input():
    assert parse_advisory("") == {}
    assert parse_advisory("no labels at all, just prose") == {}


def test_colon_inside_value_is_preserved():
    out = parse_advisory("ADVISORY_EN: Note: irrigate flowering fields now.")
    assert out["ADVISORY_EN"] == "Note: irrigate flowering fields now."
