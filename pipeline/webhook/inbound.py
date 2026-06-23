"""
inbound.py
Minimal inbound-SMS webhook for Semaphore.ph — the collection channel for ELN-010
(opt-out) and ELN-021 (feedback). Receives reply SMS and writes to Supabase:

  • "STOP" / "UNSUBSCRIBE" / "TIGIL" …  → sms_opt_outs       (send_sms then suppresses it)
  • any other reply                     → advisory_feedback  (acted/not_acted/need_help/unknown)

Deploy as a small always-on web service (e.g. a second Railway service) and point the
Semaphore inbound webhook at `POST /sms/inbound`. It reuses the SAME pure logic as the
weekly pipeline — feedback.classify_inbound + delivery.normalize_ph_phone — so there is
no parallel re-implementation to drift.

Env: SUPABASE_URL, SUPABASE_SERVICE_KEY, PORT (optional).
"""

import logging
import os
import sys
from datetime import date

from flask import Flask, jsonify, request
from supabase import create_client

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sms"))
from feedback import classify_inbound  # noqa: E402
from delivery import normalize_ph_phone  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def _field(data: dict, *names: str) -> str:
    """Read the first present field — Semaphore inbound payloads vary in key names."""
    for n in names:
        if data.get(n):
            return str(data[n])
    return ""


@app.post("/sms/inbound")
def inbound():
    data = request.form.to_dict() or request.get_json(silent=True) or {}
    raw_phone = _field(data, "sender", "number", "from")
    message = _field(data, "message", "text", "body")

    phone = normalize_ph_phone(raw_phone)
    if not phone:
        log.warning("inbound: unparseable sender %r", raw_phone)
        # 200 so Semaphore doesn't retry an unprocessable payload.
        return jsonify(ok=False, reason="invalid sender"), 200

    kind, code = classify_inbound(message)
    try:
        if kind == "opt_out":
            supabase.table("sms_opt_outs").upsert(
                {"phone_number": phone, "reason": "STOP reply"}, on_conflict="phone_number"
            ).execute()
            log.info("inbound: opted out %s", phone)
        else:
            contact = (
                supabase.table("cooperative_contacts")
                .select("id, province_id").eq("phone_number", raw_phone).limit(1).execute().data
                or [{}]
            )[0]
            supabase.table("advisory_feedback").insert({
                "contact_id": contact.get("id"),
                "province_id": contact.get("province_id"),
                "week_of": date.today().isoformat(),
                "response_code": code,
                "raw_text": message[:500],
            }).execute()
            log.info("inbound: feedback %s from %s", code, phone)
    except Exception as e:  # never 500 to Semaphore — log and ack
        log.error("inbound: write failed: %s", e)
        return jsonify(ok=False), 200

    return jsonify(ok=True, kind=kind, code=code), 200


@app.get("/health")
def health():
    return jsonify(ok=True), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
