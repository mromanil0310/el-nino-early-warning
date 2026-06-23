"""
delivery.py
Pure SMS delivery-status helpers for Semaphore.ph — no I/O, no heavy dependencies,
so the acceptance logic can be unit-tested without the Supabase or requests clients.
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


def normalize_phone_set(rows: list[dict], field: str = "phone_number") -> set[str]:
    """Build a set of E.164 numbers from rows (e.g. sms_opt_outs), skipping invalid ones.

    Used to suppress opted-out recipients (ELN-010): both the opt-out list and each
    contact's number are normalized the same way, so suppression is format-agnostic.
    """
    out: set[str] = set()
    for r in rows:
        normalized = normalize_ph_phone(r.get(field, ""))
        if normalized:
            out.add(normalized)
    return out

# Semaphore returns CAPITALIZED message statuses: Pending, Queued, Sent, Failed,
# Refunded. The ones below (matched case-insensitively) mean the SMS will NOT be
# delivered. "error" also covers the {"status": "error"} shape some failures use.
#
# This matters: a previous case-sensitive check (`status not in ("failed", "error")`)
# treated Semaphore's "Failed" as a success, so genuinely failed farmer alerts were
# logged as "sent" — under-reporting delivery failures for a safety system.
SEMAPHORE_FAILURE_STATUSES = {"failed", "refunded", "error"}


def is_successful_send(response: dict) -> bool:
    """True only if Semaphore accepted the SMS for delivery.

    Handles two failure shapes, case-insensitively: (1) our own
    ``{"status": "failed"/"error"}`` set on a network exception, and (2) Semaphore's
    capitalized ``"Failed"``/``"Refunded"``. A genuine acceptance always returns a
    ``message_id``, so a missing id is treated as a failure too.
    """
    status = str(response.get("status", "")).strip().lower()
    if status in SEMAPHORE_FAILURE_STATUSES:
        return False
    return bool(response.get("message_id"))


def attach_digests(contacts: list[dict], digests: list[dict]) -> list[dict]:
    """Attach each active contact's province digest in memory.

    Replaces an N+1 query (one weekly_digests lookup per contact) with a single
    province→digest index. ``digests`` is this week's weekly_digests rows (one query).
    Returns only contacts whose province has a digest, each with the digest set on
    ``contact["digest"]``. Input dicts are not mutated.
    """
    by_province = {d["province_id"]: d for d in digests}
    out: list[dict] = []
    for contact in contacts:
        province_id = contact.get("province_id")
        if province_id is None:
            continue
        digest = by_province.get(province_id)
        if digest:
            out.append({**contact, "digest": digest})
    return out
