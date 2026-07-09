"""
test_provinces_map.py
Unit tests for the seed-derived province map + containment-aware bulletin matching
(pipeline/scripts/provinces_map.py) — Phase 2 Build 3.

Run: python -m pytest pipeline/tests/test_provinces_map.py -v
"""

import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from provinces_map import (  # noqa: E402
    PROVINCE_ID_MAP,
    find_all_province_in_text,
    find_province_in_text,
)

SEED = os.path.join(os.path.dirname(__file__), "..", "seeds", "provinces.csv")


class TestSeedConsistency:
    def test_map_covers_every_seed_province(self):
        with open(SEED, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 82
        for r in rows:
            assert PROVINCE_ID_MAP[r["name"].strip().lower()] == int(r["id"])

    def test_seed_ids_are_unique_and_contiguous(self):
        with open(SEED, newline="", encoding="utf-8") as f:
            ids = sorted(int(r["id"]) for r in csv.DictReader(f))
        assert ids == list(range(1, 83))

    def test_pilot_ids_unchanged(self):
        # The live DB + scraper baseline already use these ids — they must never move.
        assert PROVINCE_ID_MAP["pangasinan"] == 1
        assert PROVINCE_ID_MAP["nueva ecija"] == 5
        assert PROVINCE_ID_MAP["quezon"] == 13
        assert PROVINCE_ID_MAP["mountain province"] == 15

    def test_aliases_resolve_to_canonical_ids(self):
        assert PROVINCE_ID_MAP["western samar"] == PROVINCE_ID_MAP["samar"]
        assert PROVINCE_ID_MAP["north cotabato"] == PROVINCE_ID_MAP["cotabato"]
        assert PROVINCE_ID_MAP["compostela valley"] == PROVINCE_ID_MAP["davao de oro"]
        assert PROVINCE_ID_MAP["mt. province"] == PROVINCE_ID_MAP["mountain province"]


class TestContainmentMatching:
    def test_short_name_inside_longer_province_rejected(self):
        assert find_province_in_text("cotabato", "south cotabato: below normal") is None
        assert find_province_in_text("samar", "northern samar below normal") is None
        assert find_province_in_text("samar", "eastern samar: near normal") is None
        assert find_province_in_text("leyte", "southern leyte above normal") is None

    def test_short_name_inside_non_province_place_rejected(self):
        assert find_province_in_text("quezon", "quezon city: near normal") is None
        assert find_province_in_text("cotabato", "cotabato city below normal") is None
        assert find_province_in_text("isabela", "isabela city near normal") is None

    def test_standalone_name_matches(self):
        assert find_province_in_text("cotabato", "cotabato: below normal") == 0
        assert find_province_in_text("samar", "samar below normal") == 0
        assert find_province_in_text("quezon", "the province of quezon, below normal") is not None
        assert find_province_in_text("leyte", "leyte: much below normal") == 0

    def test_mixed_text_finds_only_standalone_occurrence(self):
        text = "south cotabato: below normal. cotabato: near normal."
        positions = find_all_province_in_text("cotabato", text)
        assert positions == [text.index("cotabato: near")]

    def test_longer_name_still_matches_itself(self):
        assert find_province_in_text("south cotabato", "south cotabato: below normal") == 0
        assert find_province_in_text("northern samar", "northern samar below normal") == 0

    def test_word_boundary_required(self):
        # "abra" must not match inside e.g. "alabrastro"-like tokens
        assert find_province_in_text("abra", "the alabrador region") is None
        assert find_province_in_text("abra", "abra: below normal") == 0
