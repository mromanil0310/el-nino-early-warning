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
from outlook import (  # pure reference for the ELN-031 station rainfall model
    anomaly_from_probabilities,
    label_from_probabilities,
    severity_from_probabilities,
)
from station_baseline import station_baseline_probabilities

SEEDS = os.path.join(os.path.dirname(__file__), "..", "seeds")


def classify(score: float) -> str:
    return "High" if score > 65 else "Medium" if score >= 35 else "Low"


def load_csv(name: str) -> list[dict]:
    with open(os.path.join(SEEDS, name), newline="") as f:
        return list(csv.DictReader(f))


def province_rainfall() -> dict[int, dict]:
    """Reproduce int_province_rainfall.sql over the seeds + station baseline (no DB).

    Weight-averages the per-station probability forecasts up to each province via
    province_station_mapping, then derives severity + a display anomaly/label — exactly
    the ELN-031 dbt path. Returns {province_id: {weight, anomaly, outlook}}.
    """
    id_to_code = {int(s["id"]): s["station_code"] for s in load_csv("pagasa_stations.csv")}
    station_probs = station_baseline_probabilities()  # station_code → (pb, pn, pa) fractions

    acc: dict[int, dict] = {}
    for m in load_csv("province_station_mapping.csv"):
        code = id_to_code.get(int(m["station_id"]))
        if code not in station_probs:
            continue  # station has no forecast (non-pilot) — mirrors the INNER JOIN
        pb, pn, pa = station_probs[code]
        w = float(m["weight"])
        a = acc.setdefault(int(m["province_id"]), {"sev": 0.0, "pb": 0.0, "pa": 0.0})
        a["sev"] += w * severity_from_probabilities(pb, pn, pa)
        a["pb"] += w * pb
        a["pa"] += w * pa

    out: dict[int, dict] = {}
    for pid, a in acc.items():
        pb, pa = a["pb"], a["pa"]
        pn = max(0.0, 1.0 - pb - pa)
        out[pid] = {
            "weight": min(1.0, max(0.0, a["sev"])),
            "anomaly": anomaly_from_probabilities(pb, pn, pa),
            "outlook": label_from_probabilities(pb, pn, pa),
        }
    return out


def compute_scores(as_of: date, rainfall: dict[int, dict] | None = None) -> list[dict]:
    """Reproduce the risk_scores.sql output for `as_of` over the seed data (no DB).

    Applies the same staging filter (active crops only), off-season exclusion
    (vulnerability > 0), the ELN-031 weighted station→province rainfall severity, the
    formula, and thresholds the dbt models use. Returns rows sorted highest-risk first.
    Pure + importable, so it backs both the preview and the integration test.
    """
    provinces = {int(p["id"]): p["name"] for p in load_csv("provinces.csv")}
    rain = rainfall if rainfall is not None else province_rainfall()
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
        pr = rain.get(pid)
        if pr is None:  # province with no station forecast — skipped like the INNER JOIN
            continue
        weight = pr["weight"]
        score = round(weight * vuln * 100, 1)
        rows.append({
            "province": provinces[pid], "province_id": pid, "crop": c["crop"], "season": c["season"],
            "outlook": pr["outlook"], "anomaly": pr["anomaly"], "stage": stage, "vuln": vuln,
            "weight": weight, "score": score, "level": classify(score),
        })
    rows.sort(key=lambda r: (-r["score"], r["province"]))
    return rows


def run(as_of: date) -> None:
    rows = compute_scores(as_of)
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
