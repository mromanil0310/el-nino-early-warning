"""
test_smstext.py
Unit tests for encoding-aware SMS formatting (pipeline/scripts/smstext.py).

Run: python -m pytest pipeline/tests/test_smstext.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from smstext import is_gsm7, sms_encoding, sms_length, sms_segments, fit_sms  # noqa: E402


class TestEncodingDetection:
    def test_el_nino_with_tilde_stays_gsm7(self):
        # ñ/Ñ are in GSM-7 — the common misconception this guards against.
        assert is_gsm7("El Niño risk this week")
        assert sms_encoding("El Niño") == "GSM-7"

    def test_peso_sign_forces_ucs2(self):
        assert not is_gsm7("Cost ₱260")
        assert sms_encoding("Cost ₱260") == "UCS-2"

    def test_acute_accents_force_ucs2(self):
        assert sms_encoding("kalapít") == "UCS-2"   # acute í is not in GSM-7

    def test_em_dash_and_curly_quotes_force_ucs2(self):
        assert sms_encoding("High risk — act now") == "UCS-2"
        assert sms_encoding("“irrigate”") == "UCS-2"

    def test_plain_ascii_is_gsm7(self):
        assert is_gsm7("Aug 31 Nueva Ecija palay: High risk. -ELNINO")


class TestSegments:
    def test_gsm7_single_segment_boundary(self):
        assert sms_segments("a" * 160) == 1
        assert sms_segments("a" * 161) == 2

    def test_ucs2_single_segment_boundary(self):
        assert sms_segments("₱" + "a" * 69) == 1   # 70 chars, UCS-2
        assert sms_segments("₱" + "a" * 70) == 2    # 71 chars

    def test_extension_char_counts_double(self):
        assert sms_length("€") == 2  # GSM-7 extension


class TestFitSms:
    def test_short_message_unchanged(self):
        assert fit_sms("Hello", " -ELNINO") == "Hello -ELNINO"

    def test_long_gsm7_trimmed_to_one_segment_keeps_suffix(self):
        body = "word " * 60  # 300 chars
        out = fit_sms(body, " -ELNINO")
        assert sms_segments(out) == 1
        assert out.endswith(" -ELNINO")
        assert "..." in out

    def test_long_ucs2_trimmed_to_70(self):
        body = "₱ " + "alerta " * 30  # UCS-2 due to ₱
        out = fit_sms(body, " -ELNINO")
        assert sms_segments(out) == 1
        assert sms_length(out) <= 70
        assert out.endswith(" -ELNINO")

    def test_suffix_always_preserved(self):
        out = fit_sms("x" * 500, " -ELNINO")
        assert out.endswith(" -ELNINO")
        assert sms_segments(out) == 1
