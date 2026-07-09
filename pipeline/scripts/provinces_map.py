"""
provinces_map.py
Province name → id map generated from the canonical seed (pipeline/seeds/provinces.csv),
plus containment-aware text matching for the PAGASA bulletin parser.

Why this exists (Phase 2 Build 3, 15 → 82 provinces):
  • A hardcoded name→id dict drifts from the seed. Loading the seed at import time
    makes the scraper and the database share one source of truth.
  • Plain substring matching mis-assigns forecasts at national scale: "cotabato" is a
    substring of "south cotabato" and "cotabato city", "samar" of "northern samar",
    "quezon" of "quezon city". A bulletin row about South Cotabato must NOT populate
    (North) Cotabato. `find_province_in_text` only accepts an occurrence of a name
    that is not inside a longer known place name.

Pure module: stdlib only (csv, pathlib, re) — unit-tested without pipeline deps.
"""

import csv
import re
from pathlib import Path

_SEED_PATH = Path(__file__).resolve().parent.parent / "seeds" / "provinces.csv"

# Alternate names PAGASA bulletins use for provinces in the seed.
_ALIASES: dict[str, str] = {
    "western samar": "samar",
    "north cotabato": "cotabato",
    "compostela valley": "davao de oro",   # renamed 2019
    "mt. province": "mountain province",
}

# Longer place names that CONTAIN a province name but are not that province.
# An occurrence of the short name inside one of these is rejected.
_NON_PROVINCE_CONTAINERS = (
    "quezon city",      # ⊅ Quezon province
    "cotabato city",    # ⊅ (North) Cotabato — independent city in BARMM
    "isabela city",     # ⊅ Isabela province — city in Basilan
)


def _load_seed() -> dict[str, int]:
    with open(_SEED_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    name_to_id = {r["name"].strip().lower(): int(r["id"]) for r in rows}
    for alias, canonical in _ALIASES.items():
        if canonical in name_to_id:
            name_to_id[alias] = name_to_id[canonical]
    return name_to_id


#: Province (and alias) name → province_id. Keys are lowercase.
PROVINCE_ID_MAP: dict[str, int] = _load_seed()

# For each name, every longer known name (province, alias, or non-province place)
# that contains it as a substring — occurrences inside those are rejected.
_ALL_KNOWN = list(PROVINCE_ID_MAP) + list(_NON_PROVINCE_CONTAINERS)
_CONTAINERS: dict[str, list[str]] = {
    name: [other for other in _ALL_KNOWN if other != name and name in other]
    for name in PROVINCE_ID_MAP
}


def find_all_province_in_text(prov_name: str, text: str) -> list[int]:
    """
    Positions of every standalone occurrence of `prov_name` in `text`
    (lowercase). "Standalone" = word-bounded and not inside a longer known
    place name ("cotabato" inside "south cotabato" doesn't count).
    """
    container_spans: list[tuple[int, int]] = []
    for container in _CONTAINERS.get(prov_name, ()):
        for m in re.finditer(re.escape(container), text):
            container_spans.append(m.span())

    return [
        m.start()
        for m in re.finditer(rf"\b{re.escape(prov_name)}\b", text)
        if not any(cs <= m.start() and m.end() <= ce for cs, ce in container_spans)
    ]


def find_province_in_text(prov_name: str, text: str) -> int | None:
    """First standalone occurrence of `prov_name` in `text`, or None."""
    positions = find_all_province_in_text(prov_name, text)
    return positions[0] if positions else None
