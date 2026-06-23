"""
test_feedback.py
Unit tests for the SMS-reply feedback classifier (pipeline/scripts/feedback.py).

Run: python -m pytest pipeline/tests/test_feedback.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from feedback import parse_feedback, ACTED, NOT_ACTED, NEED_HELP, UNKNOWN  # noqa: E402


class TestNumericReplies:
    def test_numbers(self):
        assert parse_feedback("1") == ACTED
        assert parse_feedback("2") == NOT_ACTED
        assert parse_feedback("3") == NEED_HELP


class TestEnglish:
    def test_yes_no_help(self):
        assert parse_feedback("Yes") == ACTED
        assert parse_feedback("done") == ACTED
        assert parse_feedback("No") == NOT_ACTED
        assert parse_feedback("HELP") == NEED_HELP


class TestTagalog:
    def test_acted(self):
        assert parse_feedback("oo") == ACTED
        assert parse_feedback("ginawa na") == ACTED
        assert parse_feedback("tapos na po") == ACTED

    def test_not_acted(self):
        assert parse_feedback("hindi") == NOT_ACTED
        assert parse_feedback("hindi pa") == NOT_ACTED
        assert parse_feedback("wala") == NOT_ACTED

    def test_need_help(self):
        assert parse_feedback("tulong") == NEED_HELP
        assert parse_feedback("tulong po") == NEED_HELP
        assert parse_feedback("paano") == NEED_HELP
        assert parse_feedback("?") == NEED_HELP


class TestPrecedenceAndUnknown:
    def test_need_help_wins_over_yes_no(self):
        # A reply asking for help should never be counted as a plain yes/no.
        assert parse_feedback("help oo") == NEED_HELP

    def test_unknown(self):
        assert parse_feedback("") == UNKNOWN
        assert parse_feedback("   ") == UNKNOWN
        assert parse_feedback("salamat sa update") == UNKNOWN
