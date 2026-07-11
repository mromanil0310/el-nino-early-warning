"""
phone.py
Philippine mobile number normalization — the one function the inbound webhook needs
from pipeline/sms/delivery.py.

VENDORED COPY (extracted, not the whole file): duplicated rather than imported via a
relative/sys.path trick, because the webhook deploys as an isolated service (Railway
"Root Directory" = pipeline/webhook only copies that subdirectory into the build —
sibling folders like pipeline/sms/ are never present in the container). Keep in sync
with normalize_ph_phone() in pipeline/sms/delivery.py if the normalization rules change;
that original is covered by pipeline/tests/test_sms_delivery.py, and this copy is
intentionally identical.
"""

import re


def normalize_ph_phone(raw: str) -> str | None:
    """Normalize a Philippine mobile number to E.164 (+639XXXXXXXXX), or None if invalid.

    Accepts the common shapes cooperative contacts are entered in — ``09171234567``,
    ``+639171234567``, ``639171234567``, ``9171234567`` — tolerant of spaces, dashes,
    and parentheses. PH mobile numbers are country code 63 + a 10-digit subscriber
    number that starts with 9; anything else returns None (so it's skipped, not sent to
    a malformed number that the carrier would silently reject).
    """
    if not raw:
        return None
    s = re.sub(r"[\s\-()]", "", str(raw))
    digits = s[1:] if s.startswith("+") else s
    if not digits.isdigit():
        return None
    if digits.startswith("63"):
        subscriber = digits[2:]
    elif digits.startswith("0"):
        subscriber = digits[1:]
    else:
        subscriber = digits
    # A valid PH mobile subscriber number is exactly 10 digits beginning with 9.
    if len(subscriber) == 10 and subscriber.startswith("9"):
        return "+63" + subscriber
    return None
