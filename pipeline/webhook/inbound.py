"""
inbound.py
Minimal inbound-SMS webhook for Semaphore.ph — the collection channel for ELN-010
(opt-out) and ELN-021 (feedback). Receives reply SMS and writes to Supabase:

  • "STOP" / "UNSUBSCRIBE" / "TIGIL" …  → sms_opt_outs       (send_sms then suppresses it)
  • any other reply                     → advisory_feedback  (acted/not_acted/need_help/unknown)

Deploy as a small always-on web service (Railway, Root Directory = pipeline/webhook)
and point the Semaphore inbound webhook at `POST /sms/inbound`. Its pure-logic
dependencies (feedback.py, phone.py) are VENDORED copies of the weekly pipeline's
pipeline/scripts/feedback.py and the normalize_ph_phone() function from
pipeline/sms/delivery.py, not sys.path imports of those sibling directories — Railway's
subdirectory deploy only copies pipeline/webhook/ into the build, so anything outside
it (including sibling folders) is never present in the container. See the vendored
files' own docstrings for what to keep in sync if the original logic changes.

Env: SUPABASE_URL, SUPABASE_SERVICE_KEY, PORT (optional),
SEMAPHORE_WEBHOOK_SECRET (optional — enables HMAC signature validation; set the
same value in Semaphore account settings → Inbound Webhook → Signature Secret).
"""

import logging
import os
from datetime import date

from flask import Flask, abort, jsonify, request
from supabase import create_client

from feedback import classify_inbound
from phone import normalize_ph_phone
from signature import verify_semaphore_signature

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
    secret = os.environ.get("SEMAPHORE_WEBHOOK_SECRET", "")
    if not secret:
        log.warning("inbound: SEMAPHORE_WEBHOOK_SECRET not set — signature validation skipped")
    elif not verify_semaphore_signature(
        request.get_data(), request.headers.get("X-Semaphore-Signature", ""), secret
    ):
        log.warning("inbound: rejected POST with missing/invalid signature")
        abort(403)

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
