"""
delivery.py
Pure SMS delivery-status helpers for Semaphore.ph — no I/O, no heavy dependencies,
so the acceptance logic can be unit-tested without the Supabase or requests clients.
"""

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
