# Methodology & Validation Roadmap

**Status: experimental heuristic — NOT scientifically validated.** This document states precisely how the risk score is computed today, what parts rest on established science versus author judgement, and a concrete plan to make each component defensible before the tool is presented as authoritative. It is the detailed companion to the README's *"⚠️ Scientific basis & limitations"* section.

> If you take one thing from this doc: today a score is a **relative priority** ("look at this province/crop-stage before that one"), **not** a measured or predicted crop-loss figure.

---

## 1. Current methodology (what the code actually does)

```
risk_score = rainfall_severity_weight × crop_stage_vulnerability_index × 100
   risk level:  High > 65 · Medium 35–65 · Low < 35
```

**Hazard — `rainfall_severity_weight` (0–1):** the probability of below-normal seasonal rainfall. PAGASA issues its outlook per synoptic station as a 3-way probability (P(Below)/P(Near)/P(Above) Normal). We take `severity = P(below-normal)` per station, then weight-average the stations mapped to each province (`province_station_mapping`, weights sum to 1). When only a legacy categorical province outlook is available, a step weight is used as a fallback (Below Normal → 0.75, Near Normal → 0.25, Above → 0).

**Vulnerability — `crop_stage_vulnerability_index` (0–1):** a lookup by the crop's current growth stage (from the planting/harvest calendar):

| Stage | Index | Basis |
|---|---|---|
| pre-planting | 0.4 | judgement (delayed-planting still possible) |
| early-vegetative | 0.5 | judgement |
| late-vegetative | 0.7 | judgement |
| **reproductive** (flowering/grain-filling) | **1.0** | ordering grounded in literature (most water-sensitive) |
| harvest | 0.3 | judgement |
| off-season | 0.0 | no standing crop |

---

## 2. Grounded vs. unvalidated

**Grounded (keep):**
- The **hazard × vulnerability** form mirrors standard disaster-risk framing (UNDRR/IPCC) and PAGASA's own [crop-impact assessment](https://www.pagasa.dost.gov.ph/agri-weather/impact-assessment-for-agriculture) (crop stage + rainfall + water requirement).
- The vulnerability **ordering** — rice most sensitive to water stress at reproductive/flowering, less so vegetative — is robust, peer-reviewed agronomy ([Nature Sci. Reports 2019](https://www.nature.com/articles/s41598-019-40161-0)).
- Real inputs: PAGASA seasonal rainfall-outlook categories; published crop planting/harvest calendars.

**Unvalidated (must fix before any authoritative claim):**
1. Vulnerability index **magnitudes** (0.4/0.5/0.7/1.0/0.3) — ordering is grounded, numbers are not calibrated to a published yield-response source.
2. `severity = P(below-normal)` is a reasonable proxy, **not** a recognized drought index (cf. SPI/SPEI; PAGASA's SVTR/CCI).
3. `× 100` scaling and the **35 / 65 thresholds** are arbitrary — not tied to observed loss levels.
4. **No empirical validation** against historical El Niño yield/damage — a "57" corresponds to no measured outcome.

---

## 3. Validation roadmap

Five workstreams, roughly in order of effort/impact. Each lists the goal, the concrete steps, and the data/reference needed.

### WS1 — Calibrate the crop-stage vulnerability index (low effort, high credibility)
- **Goal:** replace judgement magnitudes with values traceable to a published source.
- **Steps:** map each growth stage to the FAO **yield response factor (Ky)** for rice by growth period (FAO Irrigation & Drainage Paper 33 / 66), or to a PhilRice/IRRI water-stress study; document the mapping and cite it inline.
- **Data/refs:** FAO I&D Papers 33 & 66 (Ky by stage); IRRI drought-response literature; PhilRice water-management guides.
- **Acceptance:** every index value has a citation; a reviewer can reproduce it.

### WS2 — Replace the homegrown hazard with an established drought index (medium)
- **Goal:** use a recognized index instead of raw `P(below-normal)`.
- **Steps:** compute **SPI/SPEI** from station rainfall (WMO-recognized — [ref](https://philsa.gov.ph/wp-content/uploads/2022/10/ACRS2022Valete_etal_full_paper_Sept10_v2.pdf)) or adopt PAGASA's **Crop Condition Index / SVTR**; keep `P(below-normal)` only as a forward-looking prior blended with the observed index.
- **Data/refs:** historical + current station rainfall (PAGASA); SPI/SPEI reference implementation; PAGASA CCI methodology.
- **Acceptance:** hazard term is a documented, standard index; behaviour checked against a known drought year.

### WS3 — Anchor the thresholds to observed impact (medium)
- **Goal:** make High/Medium/Low mean something measurable.
- **Steps:** collect historical El Niño **crop-damage / yield-loss** data by province, fit the score→loss relationship, and set thresholds at loss levels that matter operationally (e.g. High ≈ ≥X% expected yield reduction).
- **Data/refs:** PSA **OpenSTAT** palay/corn yield series; DA/NDRRMC El Niño damage reports (2015–16, 2018–19, 2023–24).
- **Acceptance:** thresholds derived from data, with the score↔loss relationship documented.

### WS4 — End-to-end back-test (medium–high)
- **Goal:** show the model would have flagged real losses.
- **Steps:** re-run the pipeline over past El Niño seasons using the outlooks issued at the time; compare predicted province×crop risk vs actual yield anomaly / recorded damage; report skill metrics (hit rate, false-alarm rate, correlation, Brier/ROC).
- **Data/refs:** archived PAGASA outlooks; PSA yields; DA damage reports.
- **Acceptance:** documented skill scores beating a climatology baseline; failure modes described.

### WS5 — Independent expert review (essential before public/official use)
- **Goal:** domain sign-off.
- **Steps:** have a PAGASA climatologist, a PhilRice/IRRI agronomist, and a DA field officer review the methodology, indices, and outputs; incorporate feedback; ideally seek a data-sharing/endorsement path.
- **Acceptance:** written review notes addressed; scope of any endorsement stated honestly.

---

## 4. Data to acquire

| Data | Source | Used by |
|---|---|---|
| Historical station rainfall | PAGASA | WS2, WS4 |
| Archived seasonal outlooks (past El Niño years) | PAGASA | WS4 |
| Palay/corn yield by province & season | PSA OpenSTAT | WS3, WS4 |
| El Niño crop-damage reports | DA / NDRRMC | WS3, WS4 |
| Rice Ky / water-stress response | FAO I&D 33/66, IRRI, PhilRice | WS1 |

---

## 5. Until validation is done

Keep the current, honest framing everywhere it is surfaced:
- Label it **experimental**; scores are **indicative / relative**, not measured risk.
- Do not attribute the *methodology* to PAGASA or PhilRice (their **data** is an input; the scoring is ours).
- Keep the disclaimer prominent (dashboard banner, advisories, this repo).
- In any public communication (incl. LinkedIn), describe it as a **prototype / proof-of-concept**.

## References
- PAGASA — [Climate Impact Assessment for Philippine Agriculture](https://www.pagasa.dost.gov.ph/agri-weather/impact-assessment-for-agriculture)
- Rice reproductive-stage water-stress sensitivity — [Nature Scientific Reports, 2019](https://www.nature.com/articles/s41598-019-40161-0)
- ENSO impacts on Luzon rice — [J. Applied Meteorology & Climatology, 2009](https://journals.ametsoc.org/view/journals/apme/48/8/2008jamc1628.1.xml)
- El Niño agricultural risk (global) — [FAO](https://www.fao.org/newsroom/detail/el-nino-is-coming-here-is-where-the-risks-to-agriculture-are-highest/en)
- SPI as a WMO-recognized drought index — [PhilSA / ACRS 2022](https://philsa.gov.ph/wp-content/uploads/2022/10/ACRS2022Valete_etal_full_paper_Sept10_v2.pdf)
