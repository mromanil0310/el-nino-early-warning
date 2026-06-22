"""
send_sms.py
Sends weekly digest SMS to registered cooperative contacts via Semaphore.ph.

Semaphore.ph API:
  POST https://api.semaphore.co/api/v4/messages
  Body: { apikey, number, message, sendername }

Cost: ~₱0.65/SMS (Semaphore standard rate as of 2026)
100 cooperatives × weekly = ~₱260/month — well within MVP budget.
"""

import os
import sys
import logging
import requests
from datetime import date, timedelta
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SEMAPHORE_API_KEY = os.environ["SEMAPHORE_API_KEY"]
SEMAPHORE_SENDER_NAME = os.getenv("SEMAPHORE_SENDER_NAME", "ELNINO-PH")  # max 11 chars
SEMAPHORE_API_URL = "https://api.semaphore.co/api/v4/messages"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Set to True to dry-run (log SMS without sending)
DRY_RUN = os.getenv("SMS_DRY_RUN", "false").lower() == "true"

# Pure delivery-status logic lives in delivery.py (no I/O) so it can be unit-tested.
# Robust import: works both run-as-script and imported as `sms.send_sms` (Airflow).
try:
    from delivery import is_successful_send, attach_digests
except ImportError:  # pragma: no cover - import path differs under Airflow
    from sms.delivery import is_successful_send, attach_digests

# retry_util lives in ../scripts — make it importable whether run as a script or package.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
try:
    from retry_util import retry_call
except ImportError:  # pragma: no cover
    from scripts.retry_util import retry_call


def get_iso_week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def fetch_contacts_with_digests(week_of: date) -> list[dict]:
    """
    Fetches active cooperative contacts and attaches their province's weekly digest.

    Two queries total — all active contacts, plus all of this week's digests — joined
    in memory by attach_digests(). Previously this issued one weekly_digests query per
    contact (an N+1 that scaled with the contact list).
    """
    contacts = (
        supabase.table("cooperative_contacts")
        .select("*, provinces(id, name)")
        .eq("is_active", True)
        .execute()
        .data
        or []
    )
    digests = (
        supabase.table("weekly_digests")
        .select("id, province_id, sms_text")
        .eq("week_of", week_of.isoformat())
        .execute()
        .data
        or []
    )

    filtered = attach_digests(contacts, digests)
    log.info(f"Found {len(filtered)} active contacts with digests for week {week_of}")
    return filtered


def send_sms(phone_number: str, message: str) -> dict:
    """
    Sends a single SMS via Semaphore.ph API.
    Returns the API response dict.
    """
    if DRY_RUN:
        log.info(f"  [DRY RUN] Would send to {phone_number}: {message[:60]}...")
        return {"status": "dry_run", "message_id": "dry_run"}

    payload = {
        "apikey": SEMAPHORE_API_KEY,
        "number": phone_number,
        "message": message,
        "sendername": SEMAPHORE_SENDER_NAME,
    }
    try:
        # Retry transient network errors / 5xx; an immediate Semaphore "Failed" payload
        # is a 200 and is handled by is_successful_send (not retried here).
        def _post():
            r = requests.post(SEMAPHORE_API_URL, data=payload, timeout=15)
            r.raise_for_status()
            return r
        resp = retry_call(_post, attempts=3, base_delay=2.0,
                          exceptions=(requests.RequestException,), label=f"semaphore {phone_number}")
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0]
        return data
    except Exception as e:
        log.error(f"  Semaphore API error for {phone_number}: {e}")
        return {"status": "failed", "error": str(e)}


def log_sms_to_supabase(digest_id: int, contact_id: int, response: dict) -> None:
    """Write SMS send result to sms_log table."""
    try:
        supabase.table("sms_log").insert({
            "digest_id": digest_id,
            "contact_id": contact_id,
            "semaphore_message_id": str(response.get("message_id", "")),
            "status": "sent" if is_successful_send(response) else "failed",
        }).execute()
    except Exception as e:
        log.error(f"Failed to log SMS: {e}")


def run(week_of: date | None = None) -> int:
    """
    Main entry point. Sends SMS to all active cooperative contacts with a digest this week.
    Returns number of SMS sent successfully.
    Called by Airflow DAG after digest generation.
    """
    if week_of is None:
        week_of = get_iso_week_start(date.today())

    log.info(f"SMS sender run: week_of={week_of}, dry_run={DRY_RUN}")

    contacts = fetch_contacts_with_digests(week_of)
    if not contacts:
        log.info("No contacts to send to this week")
        return 0

    sent = 0
    for contact in contacts:
        digest = contact.get("digest", {})
        sms_text = digest.get("sms_text", "")
        if not sms_text:
            log.warning(f"No SMS text for contact {contact['id']} — skipping")
            continue

        phone = contact["phone_number"]
        province_name = (contact.get("provinces") or {}).get("name", "Unknown")
        log.info(f"  Sending to {contact['contact_name']} ({province_name}) → {phone}")

        response = send_sms(phone, sms_text)
        log_sms_to_supabase(digest["id"], contact["id"], response)

        if is_successful_send(response):
            sent += 1
            log.info(f"    ✓ Sent (message_id: {response.get('message_id', 'unknown')})")
        else:
            log.error(f"    ✗ Failed: {response.get('error') or response.get('status') or 'unknown error'}")

    log.info(f"SMS sender complete: {sent}/{len(contacts)} sent")
    return sent


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        # Test: send to Biboy's number only
        test_number = os.environ.get("TEST_PHONE_NUMBER", "+639495034475")
        log.info(f"TEST MODE: sending to {test_number} only")
        result = send_sms(test_number, f"El Niño Early Warning TEST — Nueva Ecija Palay: HIGH risk this week. Delay replanting. -ELNINO")
        log.info(f"Test result: {result}")
    else:
        run()
