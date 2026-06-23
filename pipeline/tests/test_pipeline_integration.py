"""
test_pipeline_integration.py
Integration test (ELN-016) of the scoring path over the REAL seed data — provinces.csv
+ crop_calendars.csv run through crop_stage.derive_stage + the severity/formula/threshold
logic exactly as risk_scores.sql does. No database required (the dbt SQL is mirrored by
preview_run.compute_scores), so this runs in CI; a live end-to-end DB smoke test is
scaffolded separately in test_db_smoke.py.

Run: python -m pytest pipeline/tests/test_pipeline_integration.py -v
"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from preview_run import compute_scores, severity_weight  # noqa: E402
from crop_stage import VALID_STAGES, VALID_VULNERABILITIES  # noqa: E402

# off-season (0.0) rows are excluded by the mart, so the valid set here drops it.
SCORED_VULNERABILITIES = tuple(v for v in VALID_VULNERABILITIES if v > 0)
SCORED_STAGES = tuple(s for s in VALID_STAGES if s != "off-season")


def _assert_row_invariants(rows):
    seen = set()
    for r in rows:
        assert 0.0 <= r["score"] <= 100.0, r
        assert r["level"] == ("High" if r["score"] > 65 else "Medium" if r["score"] >= 35 else "Low"), r
        assert r["stage"] in SCORED_STAGES, r
        assert r["vuln"] in SCORED_VULNERABILITIES, r
        assert r["weight"] in (0.0, 0.25, 0.75, 1.0), r
        assert round(r["weight"] * r["vuln"] * 100, 1) == r["score"], r
        key = (r["province_id"], r["crop"], r["season"])
        assert key not in seen, f"duplicate province×crop×season: {key}"
        seen.add(key)


def test_invariants_hold_every_week_for_a_year():
    """Walk a full year of weekly runs — nothing crashes and every row is well-formed."""
    d = date(2026, 6, 1)
    for _ in range(52):
        _assert_row_invariants(compute_scores(d))
        d += timedelta(days=7)


def test_june_planting_window_is_medium_or_low():
    # Planting season → crops early-vegetative (0.5) at most → no province reaches High.
    rows = compute_scores(date(2026, 6, 22))
    assert len(rows) == 21
    assert all(r["level"] in ("Medium", "Low") for r in rows)
    assert {r["stage"] for r in rows} <= {"pre-planting", "early-vegetative"}


def test_september_reproductive_flags_the_rice_bowl_high():
    rows = compute_scores(date(2026, 9, 1))
    by = {(r["province"], r["crop"]): r for r in rows}
    # Nueva Ecija (Below Normal) at reproductive → 75 / High.
    assert by[("Nueva Ecija", "palay")]["level"] == "High"
    assert by[("Nueva Ecija", "palay")]["score"] == 75.0
    # Laguna (Near Normal) → Low even at reproductive.
    assert by[("Laguna", "palay")]["level"] == "Low"
    high = [r for r in rows if r["level"] == "High"]
    assert len(high) >= 12  # most pilot provinces are Below Normal this season


def test_severity_weight_mirrors_sql_labels():
    assert severity_weight("Much Below Normal") == 1.0
    assert severity_weight("Below Normal") == 0.75
    assert severity_weight("Near Normal") == 0.25
    assert severity_weight("Above Normal") == 0.0
    assert severity_weight("Much Above Normal") == 0.0
