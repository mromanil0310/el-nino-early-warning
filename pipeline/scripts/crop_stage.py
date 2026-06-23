"""
crop_stage.py
Pure crop-stage + El Niño vulnerability derivation — the Python reference for the dbt
model stg_crop_calendars.sql. No I/O or heavy dependencies, so it is unit-testable.

IMPORTANT: this mirrors the CASE logic in
    pipeline/models/staging/stg_crop_calendars.sql
exactly. The SQL is the production source of truth; this module is the executable spec
the tests assert against. If you change the stage windows or vulnerability indices,
change BOTH and keep test_risk_scoring.py in sync. The dbt schema tests in
models/schema.yml additionally constrain the SQL output to the value set below.

PhilRice El Niño vulnerability (most sensitive at reproductive/flowering):
    pre-planting        0.4   manageable via delayed-planting decision
    early-vegetative    0.5   planting window
    late-vegetative     0.7   planting_end → midpoint to harvest
    reproductive        1.0   flowering/grain-filling — spikelet sterility
    harvest             0.3   delayed harvest / threshing losses
    off-season          0.0   no growing crop at risk
"""

from datetime import date, timedelta

# Every (crop_stage, vulnerability_index) pair the logic can emit. early-vegetative
# (0.5) and late-vegetative (0.7) are distinct labels (ELN-011) so advisories and the
# dashboard convey which window a crop is in. Kept in sync with models/schema.yml.
VALID_STAGES = ("pre-planting", "early-vegetative", "late-vegetative", "reproductive", "harvest", "off-season")
VALID_VULNERABILITIES = (0.0, 0.3, 0.4, 0.5, 0.7, 1.0)


def derive_stage(
    current: date,
    planting_start: date,
    planting_end: date,
    harvest_start: date,
    harvest_end: date,
) -> tuple[str, float]:
    """Return ``(crop_stage, vulnerability_index)`` for ``current`` vs the crop calendar.

    Mirrors stg_crop_calendars.sql: boundaries are inclusive and resolved
    first-match-wins, exactly like the SQL CASE expression.
    """
    if current < planting_start:
        return ("pre-planting", 0.4)
    if planting_start <= current <= planting_end:
        return ("early-vegetative", 0.5)
    # Integer day-count // 2, matching Postgres `(harvest_start - planting_end) / 2`.
    midpoint = planting_end + timedelta(days=(harvest_start - planting_end).days // 2)
    if planting_end <= current <= midpoint:
        return ("late-vegetative", 0.7)
    if midpoint <= current <= harvest_start:
        return ("reproductive", 1.0)
    if harvest_start <= current <= harvest_end:
        return ("harvest", 0.3)
    return ("off-season", 0.0)
