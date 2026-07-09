"""
test_webhook_signature.py
Unit tests for the Semaphore inbound-webhook HMAC validation
(pipeline/webhook/signature.py).

Run: python -m pytest pipeline/tests/test_webhook_signature.py -v
"""

import hashlib
import hmac
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webhook"))
from signature import verify_semaphore_signature  # noqa: E402

SECRET = "test-webhook-secret"
PAYLOAD = b"sender=%2B639171234567&message=STOP"


def sign(payload: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestValidSignature:
    def test_correct_signature_accepted(self):
        assert verify_semaphore_signature(PAYLOAD, sign(PAYLOAD), SECRET)

    def test_empty_payload_signed_correctly(self):
        assert verify_semaphore_signature(b"", sign(b""), SECRET)


class TestInvalidSignature:
    def test_wrong_secret_rejected(self):
        assert not verify_semaphore_signature(PAYLOAD, sign(PAYLOAD, "other-secret"), SECRET)

    def test_tampered_payload_rejected(self):
        assert not verify_semaphore_signature(b"sender=attacker&message=STOP", sign(PAYLOAD), SECRET)

    def test_missing_header_rejected(self):
        assert not verify_semaphore_signature(PAYLOAD, "", SECRET)
        assert not verify_semaphore_signature(PAYLOAD, None, SECRET)

    def test_garbage_header_rejected(self):
        assert not verify_semaphore_signature(PAYLOAD, "sha256=deadbeef", SECRET)
        assert not verify_semaphore_signature(PAYLOAD, "not-even-a-signature", SECRET)

    def test_digest_without_prefix_rejected(self):
        bare = hmac.new(SECRET.encode(), PAYLOAD, hashlib.sha256).hexdigest()
        assert not verify_semaphore_signature(PAYLOAD, bare, SECRET)


class TestNoSecretConfigured:
    def test_empty_secret_skips_validation(self):
        assert verify_semaphore_signature(PAYLOAD, "", "")
        assert verify_semaphore_signature(PAYLOAD, "anything", "")
