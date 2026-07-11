"""
test_webhook_vendored_sync.py
The webhook vendors pipeline/scripts/feedback.py and normalize_ph_phone() from
pipeline/sms/delivery.py as local copies (pipeline/webhook/feedback.py,
pipeline/webhook/phone.py) because Railway's subdirectory deploy for the webhook
service never includes those sibling folders. This test guards against the two
copies silently drifting apart — if someone fixes a bug in the original but forgets
the vendored copy (or vice versa), this fails instead of the divergence going unnoticed.

Loads each module by explicit file path (not sys.path + import-by-name) since the
original and vendored copies share the same filename (feedback.py) — importing both
by name from different sys.path entries would just resolve to whichever loads first.

Run: python -m pytest pipeline/tests/test_webhook_vendored_sync.py -v
"""

import importlib.util
import os

_HERE = os.path.dirname(__file__)


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


original_feedback = _load("original_feedback", os.path.join(_HERE, "..", "scripts", "feedback.py"))
vendored_feedback = _load("vendored_feedback", os.path.join(_HERE, "..", "webhook", "feedback.py"))
original_delivery = _load("original_delivery", os.path.join(_HERE, "..", "sms", "delivery.py"))
vendored_phone = _load("vendored_phone", os.path.join(_HERE, "..", "webhook", "phone.py"))

FEEDBACK_CASES = [
    "1", "2", "3", "yes", "no", "help", "oo", "hindi", "tulong",
    "STOP", "stop all", "TIGIL po", "unsubscribe", "", "   ", "maybe later",
]

PHONE_CASES = [
    "09171234567", "+639171234567", "639171234567", "9171234567",
    "0917-123-4567", "(0917) 123 4567", "", None, "12345", "+1234567890",
]


class TestFeedbackStaysInSync:
    def test_classify_inbound_matches(self):
        for text in FEEDBACK_CASES:
            assert vendored_feedback.classify_inbound(text) == original_feedback.classify_inbound(text), text

    def test_parse_feedback_matches(self):
        for text in FEEDBACK_CASES:
            assert vendored_feedback.parse_feedback(text) == original_feedback.parse_feedback(text), text

    def test_constants_match(self):
        assert vendored_feedback.ACTED == original_feedback.ACTED
        assert vendored_feedback.NOT_ACTED == original_feedback.NOT_ACTED
        assert vendored_feedback.NEED_HELP == original_feedback.NEED_HELP
        assert vendored_feedback.UNKNOWN == original_feedback.UNKNOWN
        assert vendored_feedback.OPT_OUT_KEYWORDS == original_feedback.OPT_OUT_KEYWORDS


class TestPhoneStaysInSync:
    def test_normalize_ph_phone_matches(self):
        for raw in PHONE_CASES:
            assert vendored_phone.normalize_ph_phone(raw) == original_delivery.normalize_ph_phone(raw), raw
