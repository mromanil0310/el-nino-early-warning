"""
signature.py
Pure HMAC-SHA256 signature verification for the Semaphore inbound webhook.

Semaphore signs each inbound POST with the shared secret configured in
account settings → Inbound Webhook → Signature Secret; the signature arrives
in the `X-Semaphore-Signature` header as `sha256=<hexdigest>`.

Kept free of Flask/Supabase imports so it is unit-testable without the
webhook service's runtime dependencies (same pattern as feedback/smstext).
"""

import hashlib
import hmac


def verify_semaphore_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """
    True when `sig_header` is a valid HMAC-SHA256 of `payload` under `secret`.

    An empty `secret` means validation is not configured (dev environment) —
    the request is accepted and the caller is expected to log that fact.
    """
    if not secret:
        return True
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header or "")
