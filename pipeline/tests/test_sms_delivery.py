"""
test_sms_delivery.py
Unit tests for Semaphore.ph SMS acceptance logic (pipeline/sms/delivery.py).

Guards the under-reporting bug: Semaphore returns a CAPITALIZED "Failed" status, so a
case-sensitive `status not in ("failed", "error")` check counted failed farmer alerts
as "sent". is_successful_send must treat any known failure status as a failure.

Run: python -m pytest pipeline/tests/test_sms_delivery.py -v
"""

import os
import sys

# delivery.py is a pure module (no Supabase/requests), importable on its own.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sms"))
from delivery import is_successful_send, attach_digests  # noqa: E402


class TestFailures:
    def test_semaphore_capitalized_failed_is_failure(self):
        # The regression: Semaphore returns "Failed" (capital F) even with a message_id.
        assert is_successful_send({"status": "Failed", "message_id": 12345}) is False

    def test_failed_is_case_insensitive(self):
        for s in ("failed", "Failed", "FAILED"):
            assert is_successful_send({"status": s, "message_id": 1}) is False

    def test_refunded_is_failure(self):
        assert is_successful_send({"status": "Refunded", "message_id": 1}) is False

    def test_network_error_shape_is_failure(self):
        # What send_sms() returns on a requests exception — no message_id.
        assert is_successful_send({"status": "failed", "error": "timeout"}) is False

    def test_error_payload_without_message_id_is_failure(self):
        assert is_successful_send({"message": "Invalid number"}) is False
        assert is_successful_send({}) is False


class TestSuccesses:
    def test_pending_with_message_id_is_success(self):
        # Semaphore's normal immediate response is "Pending" (queued for delivery).
        assert is_successful_send({"status": "Pending", "message_id": 98765}) is True

    def test_queued_and_sent_are_success(self):
        assert is_successful_send({"status": "Queued", "message_id": 1}) is True
        assert is_successful_send({"status": "Sent", "message_id": 1}) is True

    def test_message_id_present_no_status_is_success(self):
        assert is_successful_send({"message_id": 555}) is True

    def test_dry_run_is_success(self):
        assert is_successful_send({"status": "dry_run", "message_id": "dry_run"}) is True


class TestAttachDigests:
    """The N+1 fix: join contacts to this week's digests in memory."""

    CONTACTS = [
        {"id": 1, "contact_name": "Ana", "province_id": 5, "phone_number": "+639170000001"},
        {"id": 2, "contact_name": "Ben", "province_id": 5, "phone_number": "+639170000002"},  # same province
        {"id": 3, "contact_name": "Cy", "province_id": 11, "phone_number": "+639170000003"},  # no digest
        {"id": 4, "contact_name": "Dom", "province_id": None, "phone_number": "+639170000004"},  # no province
    ]
    DIGESTS = [
        {"id": 90, "province_id": 5, "sms_text": "Nueva Ecija: High risk"},
        {"id": 91, "province_id": 9, "sms_text": "Zambales: High risk"},  # province with no contact
    ]

    def test_only_contacts_with_a_digest_are_returned(self):
        out = attach_digests(self.CONTACTS, self.DIGESTS)
        assert [c["id"] for c in out] == [1, 2]  # province 5 only; 11 has no digest, 4 has no province

    def test_digest_is_attached_to_each_matching_contact(self):
        out = attach_digests(self.CONTACTS, self.DIGESTS)
        for c in out:
            assert c["digest"]["id"] == 90
            assert c["digest"]["sms_text"] == "Nueva Ecija: High risk"

    def test_inputs_are_not_mutated(self):
        attach_digests(self.CONTACTS, self.DIGESTS)
        assert all("digest" not in c for c in self.CONTACTS)

    def test_empty_inputs(self):
        assert attach_digests([], self.DIGESTS) == []
        assert attach_digests(self.CONTACTS, []) == []
