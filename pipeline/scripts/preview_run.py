"""
preview_run.py
Offline preview of the weekly pipeline output — NO database, NO network, NO API keys.

Runs the real scoring logic (crop_stage.derive_stage + the risk formula + the dbt
staging filters) over the committed seed data and the PAGASA June-2026 baseline
forecast, and prints the province × crop risk table exactly as risk_scores.sql would
produce it, plus a sample farmer SMS.

Usage:
    python scripts/preview_run.py [YYYY-MM-DD]   # defaults to 2026-06-22
"""

import csv
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from crop_stage import derive_stage  # pure reference for stg_crop_calendars.sql

SEEDS = os.path.join(os.path.dirname(__file__), "..", "seeds")

# PAGASA El Niño Watch (April 2026) baseline — 79% probability Jun–Aug 2026.
# Mirrors pagasa_scraper.get_manual_overrides(): (outlook, rainfall_anomaly_pct).
FORECAST: dict[int, tuple[str, float]] = {
    1: ("Below Normal", -28.0), 2: ("Below Normal", -25.0), 3: ("Below Normal", -25.0),
    4: ("Below Normal", -22.0), 5: ("Below Normal", -30.0), 6: ("Below Normal", -27.0),
    7: ("Below Normal", -25.0), 8: ("Below Normal", -22.0), 9: ("Below Normal", -24.0),
    10: ("Below Normal", -22.0), 11: ("Near Normal", -10.0), 12: ("Near Normal", -8.0),
    13: ("Near Normal", -5.0), 14: ("Below Normal", -20.0), 15: ("Below Normal", -18.0),
}


def severity_weight(outlook: str) -> float:
    """Mirror of stg_pagasa_forecasts.sql (most-specific label first)."""
    o = outlook.lower()
    if "much below" in o:
        return 1.0
    if "below" in o:
        return 0.75
    if "much above" in o or "above" in o:
        return 0.0
    if "near" in o:
        return 0.25
    return 0.25


def classify(score: float) -> str:
    return "High" if score > 65 else "Medium" if score >= 35 else "Low"


def load_csv(name: str) -> list[dict]:
    with open(os.path.join(SEEDS, name), newline="") as f:
        return list(csv.DictReader(f))


def run(as_of: date) -> None:
    provinces = {int(p["id"]): p["name"] for p in load_csv("provinces.csv")}
    rows = []
    for c in load_csv("crop_calendars.csv"):
        ps, pe = date.fromisoformat(c["planting_start"]), date.fromisoformat(c["planting_end"])
        hs, he = date.fromisoformat(c["harvest_start"]), date.fromisoformat(c["harvest_end"])
        # stg_crop_calendars.sql WHERE: active crops only (within harvest, planted within 60d)
        if not (as_of <= he and as_of >= ps - timedelta(days=60)):
            continue
        stage, vuln = derive_stage(as_of, ps, pe, hs, he)
        if vuln <= 0:  # risk_scores.sql excludes off-season (WHERE vulnerability_index > 0)
            continue
        pid = int(c["province_id"])
        outlook, anomaly = FORECAST[pid]
        weight = severity_weight(outlook)
        score = round(weight * vuln * 100, 1)
        rows.append({
            "province": provinces[pid], "crop": c["crop"], "season": c["season"],
            "outlook": outlook, "anomaly": anomaly, "stage": stage, "vuln": vuln,
            "weight": weight, "score": score, "level": classify(score),
        })

    rows.sort(key=lambda r: (-r["score"], r["province"]))
    week = as_of - timedelta(days=as_of.weekday())

    print(f"\n  EL NIÑO AGRICULTURAL RISK — week of {week:%b %d, %Y}  (as-of {as_of})")
    print(f"  PAGASA outlook: El Niño Watch, 79% probability Jun–Aug 2026")
    print("  " + "─" * 84)
    print(f"  {'PROVINCE':<18}{'CROP':<7}{'OUTLOOK':<14}{'STAGE':<13}{'WEIGHT':>7}{'VULN':>6}{'SCORE':>7}  RISK")
    print("  " + "─" * 84)
    icon = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}
    for r in rows:
        print(f"  {r['province']:<18}{r['crop']:<7}{r['outlook']:<14}{r['stage']:<13}"
              f"{r['weight']:>7.2f}{r['vuln']:>6.2f}{r['score']:>7.1f}  {icon[r['level']]} {r['level']}")
    print("  " + "─" * 84)
    counts = {lvl: sum(1 for r in rows if r["level"] == lvl) for lvl in ("High", "Medium", "Low")}
    print(f"  {len(rows)} province×crop scores   "
          f"🔴 {counts['High']} High   🟠 {counts['Medium']} Medium   🟢 {counts['Low']} Low")

    # Sample farmer SMS (digest_generator fallback format — Claude unavailable offline)
    top = rows[0]
    sms = (f"{week:%b %d} {top['province']} {top['crop']}: {top['level']} El Niño risk. "
           f"Check DA advisory.")[:130] + " -ELNINO"
    print(f"\n  SAMPLE SMS → {top['province']} cooperative ({len(sms)} chars):")
    print(f"    \"{sms}\"\n")


if __name__ == "__main__":
    run(date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 6, 22))
