# El Niño Early Warning System — Philippine Agriculture

Weekly El Niño agricultural risk scores for 15 Luzon pilot provinces. Scrapes PAGASA seasonal forecasts, computes province × crop risk scores with an **experimental heuristic** (rainfall-outlook probability × crop growth-stage sensitivity — see [Risk Scoring](#risk-scoring-formula), including its limitations), generates AI advisories via Claude haiku, and sends SMS alerts to cooperative contacts via Semaphore.ph.

> ⚠️ **Experimental / not scientifically validated.** The risk score is a decision-support heuristic, not an official or peer-reviewed methodology, and its indices/thresholds are not calibrated to measured crop losses. See [Risk Scoring → Limitations](#risk-scoring-formula). Not a substitute for official PAGASA/DA advisories.

**Status:** Pilot — 15 Luzon provinces  
**Built by:** Biboy Labs

---

## 🌐 Live System

| | |
|---|---|
| 🌾 **Dashboard (web app)** | **[el-nino-early-warning.vercel.app](https://el-nino-early-warning.vercel.app)** |
| 📖 **User guide** — how to read & use the dashboard | **[/USER_GUIDE](https://el-nino-early-warning.vercel.app/USER_GUIDE/)** |

The dashboard is public and mobile-friendly, with a full English / Filipino toggle. Source for the guide: [`dashboard/public/USER_GUIDE.html`](dashboard/public/USER_GUIDE.html).

---

## Architecture

```
PAGASA outlook → pagasa_scraper.py → Supabase
                     ├─ pagasa_forecasts          (province-level, fallback)
                     └─ pagasa_station_forecasts  (per-station Below/Near/Above %)
                                       ↓
        dbt: stg_pagasa_station_forecasts → int_province_rainfall → risk_scores
             (weighted station→province rainfall severity × crop-stage vulnerability)
                                       ↓
                    digest_generator.py → Claude haiku → weekly_digests
                                       ↓
                    send_sms.py → Semaphore.ph → cooperative contacts
                                       ↓
                    Next.js dashboard (English / Filipino) → Vercel
```

**Pipeline schedule:** Every Monday 06:00 PHT (Sunday 22:00 UTC)  
**Deployed on:** GitHub Actions (weekly pipeline) + Vercel (dashboard) + Supabase (data)

---

## Risk Scoring Formula

```
risk_score = rainfall_severity_weight × crop_stage_vulnerability_index × 100
```

**Rainfall severity (0–1)** is the probability of *below-normal* seasonal rainfall, aggregated to each province from its nearest PAGASA synoptic stations. PAGASA issues the outlook per station as a 3-way probability — P(Below) / P(Near) / P(Above) Normal — and `int_province_rainfall` weight-averages the stations mapped to each province (`province_station_mapping`, weights sum to 1.0):

```
station_severity  = P(below-normal rainfall)          # per station
province_severity = Σ (weight × station_severity)     # weighted up to the province
```

Because it's continuous, two provinces with different outlooks get different scores — they no longer collapse to one categorical weight. A province with only a legacy province-level forecast (no station data) falls back to a categorical step weight (Below Normal → 0.75, Near Normal → 0.25, Above Normal → 0.0). The pure logic lives in [`pipeline/scripts/outlook.py`](pipeline/scripts/outlook.py) and is mirrored by the dbt models and `preview_run.py`.

| Crop Stage | Vulnerability Index |
|------------|-------------------|
| Reproductive (flowering/grain-filling) | 1.0 |
| Late vegetative | 0.7 |
| Early vegetative | 0.5 |
| Pre-planting | 0.4 |
| Harvest | 0.3 |
| Off-season | 0.0 |

| Score | Risk Level |
|-------|-----------|
| > 65 | High |
| 35–65 | Medium |
| < 35 | Low |

### ⚠️ Scientific basis & limitations

This scoring is an **experimental heuristic**, not a standardized, official, or peer-reviewed methodology.

**What is grounded:**
- The *conceptual* form (risk = hazard × vulnerability) mirrors standard disaster-risk framing and PAGASA's own [crop-impact assessment](https://www.pagasa.dost.gov.ph/agri-weather/impact-assessment-for-agriculture) approach (crop stage + rainfall).
- The vulnerability *ordering* — rice most water-sensitive at the reproductive/flowering stage — is well established in the peer-reviewed literature.
- Inputs are real: PAGASA seasonal rainfall-outlook categories and crop planting/harvest calendars.

**What is NOT validated (do not present as proven):**
- The specific vulnerability index *magnitudes* (0.4/0.5/0.7/1.0/0.3), the `× 100` scaling, and the 35/65 thresholds are heuristic — **not calibrated** to a published yield-response study or to measured crop losses.
- `severity = P(below-normal rainfall)` is a reasonable proxy, not a recognized drought index (cf. SPI/SPEI, or PAGASA's SVTR/CCI).
- The model has **no empirical validation** against historical El Niño yield data, so a score of "57" does not correspond to any measured loss level. Scores are **relative priorities, not absolute risk.**
- Earlier versions cited a "PhilRice El Niño Impact Assessment Framework" — that specific document could not be verified and the claim has been removed.

**To make it authoritative:** calibrate indices to a published source (e.g. FAO Ky factors / IRRI / PhilRice), adopt an established drought index, validate thresholds against historical loss data, and have a PAGASA/PhilRice/DA agronomist review it. The concrete plan — workstreams, data to acquire, acceptance criteria, and references — is in **[`docs/methodology-and-validation.md`](docs/methodology-and-validation.md)**.

**🤝 Open to scientific scrutiny.** This is deliberately public and unfinished. Review, corrections, data, or collaboration from the climate/agronomy research community and from PAGASA / PhilRice / IRRI / DA are genuinely welcome — please [open an issue or PR](https://github.com/mromanil0310/el-nino-early-warning/issues).

---

## Pilot Provinces (15 Luzon)

Pangasinan, Ilocos Norte, Ilocos Sur, La Union, Nueva Ecija (PH rice bowl), Tarlac, Pampanga, Bulacan, Zambales, Bataan, Laguna, Batangas, Quezon, Benguet, Mountain Province

---

## Repository Structure

```
El-Nino-Early-Warning/
├── .github/workflows/pipeline.yml    # weekly pipeline (GitHub Actions cron)
├── supabase/migrations/              # 001…008 — apply in order in Supabase
│   ├── 001_initial_schema.sql
│   ├── 006_province_station_mapping.sql   # station registry + weighted mapping
│   ├── 007_weekly_digests_crop.sql
│   └── 008_pagasa_station_forecasts.sql   # per-station 3-way probabilities
├── pipeline/
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_pagasa_forecasts.sql          # province-level (fallback)
│   │   │   ├── stg_pagasa_station_forecasts.sql  # per-station severity
│   │   │   └── stg_crop_calendars.sql
│   │   ├── marts/
│   │   │   ├── int_province_rainfall.sql   # weighted station→province severity
│   │   │   └── risk_scores.sql             # CORE: severity × vulnerability
│   │   ├── sources.yml
│   │   └── schema.yml
│   ├── scripts/
│   │   ├── pagasa_scraper.py        # download/parse + write forecasts
│   │   ├── outlook.py               # pure severity/probability model
│   │   ├── station_baseline.py      # grounded per-station baseline
│   │   ├── crop_stage.py            # crop-stage vulnerability (reference)
│   │   ├── digest_generator.py      # Claude haiku advisory generation
│   │   └── preview_run.py           # offline scoring preview (no DB)
│   ├── sms/send_sms.py              # Semaphore.ph SMS delivery
│   ├── webhook/inbound.py           # inbound-SMS webhook (opt-out + feedback)
│   ├── seeds/
│   │   ├── provinces.csv                    # 82 provinces (15 pilot)
│   │   ├── crop_calendars.csv               # crop planting/harvest windows
│   │   ├── pagasa_stations.csv              # PAGASA synoptic stations
│   │   └── province_station_mapping.csv     # weighted station↔province
│   ├── tests/                       # pytest (147) + dbt singular tests
│   ├── dbt_project.yml · profiles.yml · requirements*.txt
├── dashboard/                       # Next.js (static export → Vercel)
│   ├── pages/ (index, _app, _document)
│   ├── components/ (ProvinceCard, ProvinceMap, RiskBadge, RiskSummaryBar,
│   │               TrendIcon, Sparkline, FeedbackSummary, LanguageToggle)
│   ├── lib/ (supabase.ts, format.ts, i18n.tsx)   # i18n = English/Filipino
│   └── public/USER_GUIDE.html
├── reports/elnino-audit-report.md   # source-of-truth backlog + run log
├── docker-compose.yml · .env.example · README.md
```

---

## Deployment

### 1. Supabase Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Run the migrations **in order** (`001` → `008`): **SQL Editor → paste each `supabase/migrations/00N_*.sql` → Run**
3. Seed the reference tables (`dbt seed`, step 4 below, loads `provinces`, `crop_calendars`, `pagasa_stations`, `province_station_mapping`) — or import each `seeds/*.csv` via **Table Editor → Insert from CSV**
4. Copy your `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, and DB connection details

### 2. GitHub Actions (Pipeline)

The weekly pipeline runs as a scheduled GitHub Actions workflow — no separate server needed. See [`.github/workflows/pipeline.yml`](.github/workflows/pipeline.yml): it scrapes PAGASA → runs the dbt risk-score models → generates AI advisories → sends SMS → triggers a Vercel rebuild, every Monday 06:00 PHT, and is also runnable on demand via **workflow_dispatch** (with a `dry_run` input that skips SMS).

Set the required secrets in **Settings → Secrets and variables → Actions**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_HOST`, `SUPABASE_DB_USER`, `SUPABASE_DB_PASSWORD`, `ANTHROPIC_API_KEY`, `SEMAPHORE_API_KEY`, and `VERCEL_DEPLOY_HOOK_URL` (see `.env.example`).

### 3. Vercel (Dashboard)

1. Import the repo → Vercel will detect Next.js (static export)
2. Set environment variables: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   (baked in at build time — a redeploy is required after changing them)
3. Create a Deploy Hook and save it as the `VERCEL_DEPLOY_HOOK_URL` **GitHub Actions secret** (the pipeline calls it after each run)

### 4. dbt seed + first run

```bash
cd pipeline
pip install -r requirements.txt
dbt seed --profiles-dir . --target prod       # Load provinces, crop_calendars, stations, mapping
python scripts/pagasa_scraper.py               # Write forecasts (station baseline by default)
dbt run --profiles-dir . --target prod        # Compute weighted risk scores
python scripts/digest_generator.py            # Generate advisories
python sms/send_sms.py --test                 # Test SMS to $TEST_PHONE_NUMBER
```

---

## Local Development

```bash
# Start local stack
docker-compose up -d

# Run tests
cd pipeline
pip install -r requirements.txt pytest
python -m pytest tests/test_risk_scoring.py -v

# dbt against local postgres
dbt run --profiles-dir . --target dev
```

---

## Security

- `SUPABASE_SERVICE_KEY` is **only** used in the Python pipeline — never in the browser
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` is the read-only key for the dashboard
- Row Level Security (RLS) is enabled on all Supabase tables (anon = read-only)
- Claude and Semaphore API keys are GitHub Actions secrets — never bundled in frontend code
- The inbound-SMS webhook verifies an HMAC signature (`SEMAPHORE_WEBHOOK_SECRET`)
- Every advisory and SMS includes a mandatory disclaimer

---

## Cost Estimate (Monthly, 15 provinces)

| Service | Cost |
|---------|------|
| Supabase (free tier) | ₱0 |
| GitHub Actions (weekly pipeline, public repo) | ₱0 |
| Vercel (free tier) | ₱0 |
| Claude haiku advisories (15 provinces/week × 4 weeks) | ~₱24 |
| Semaphore.ph SMS (100 contacts × 4 weeks × ₱0.65) | ~₱260 |
| **Total** | **~₱284/month** |

---

## Disclaimer

This system is an **experimental** decision-support tool based on public PAGASA seasonal forecasts and crop planting/harvest calendars. Risk scores are **indicative estimates from an unvalidated heuristic** (see [Scientific basis & limitations](#️-scientific-basis--limitations)) — not an official or scientifically-proven risk methodology, and not calibrated to measured crop losses. Always verify with your local Department of Agriculture or PAGASA office before taking agricultural action. Not a substitute for official PAGASA or DA advisories.
