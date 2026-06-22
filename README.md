# El Niño Early Warning System — Philippine Agriculture

Weekly El Niño agricultural risk scores for 15 Luzon pilot provinces. Scrapes PAGASA seasonal forecasts, computes province × crop risk scores using PhilRice methodology, generates AI advisories via Claude haiku, and sends SMS alerts to cooperative contacts via Semaphore.ph.

**Status:** Pilot — 15 Luzon provinces  
**Built by:** Biboy Labs

---

## Architecture

```
PAGASA PDF → pagasa_scraper.py → Supabase (pagasa_forecasts)
                                       ↓
                               dbt risk_scores model
                                (rainfall × vulnerability)
                                       ↓
                         digest_generator.py → Claude haiku
                                       ↓
                           weekly_digests table
                                       ↓
                    send_sms.py → Semaphore.ph → cooperative contacts
                                       ↓
                         Next.js dashboard → Vercel
```

**Pipeline schedule:** Every Monday 06:00 PHT (Sunday 22:00 UTC)  
**Deployed on:** Railway.app (pipeline) + Vercel (dashboard) + Supabase (data)

---

## Risk Scoring Formula

```
risk_score = rainfall_severity_weight × crop_stage_vulnerability_index × 100
```

| PAGASA Outlook | Severity Weight |
|----------------|----------------|
| Much Below Normal | 1.0 |
| Below Normal | 0.75 |
| Near Normal | 0.25 |
| Above / Much Above Normal | 0.0 |

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

*Source: PhilRice El Niño Impact Assessment Framework*

---

## Pilot Provinces (15 Luzon)

Pangasinan, Ilocos Norte, Ilocos Sur, La Union, Nueva Ecija (PH rice bowl), Tarlac, Pampanga, Bulacan, Zambales, Bataan, Laguna, Batangas, Quezon, Benguet, Mountain Province

---

## Repository Structure

```
El-Nino-Early-Warning/
├── pipeline/
│   ├── dags/
│   │   └── elnino_weekly.py        # Airflow DAG
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_pagasa_forecasts.sql
│   │   │   └── stg_crop_calendars.sql
│   │   ├── marts/
│   │   │   └── risk_scores.sql     # CORE: scoring formula
│   │   └── sources.yml
│   ├── scripts/
│   │   ├── pagasa_scraper.py       # PDF download + parse + Supabase write
│   │   └── digest_generator.py     # Claude haiku advisory generation
│   ├── sms/
│   │   └── send_sms.py             # Semaphore.ph SMS delivery
│   ├── seeds/
│   │   ├── provinces.csv           # 15 pilot provinces
│   │   └── crop_calendars.csv      # PhilRice crop calendar (35 rows)
│   ├── supabase/
│   │   └── migrations/
│   │       └── 001_initial_schema.sql
│   ├── tests/
│   │   └── test_risk_scoring.py
│   ├── dbt_project.yml
│   ├── profiles.yml
│   └── requirements.txt
├── dashboard/
│   ├── pages/
│   │   ├── index.tsx               # Main risk score dashboard
│   │   └── _app.tsx
│   ├── components/
│   │   ├── ProvinceCard.tsx
│   │   ├── RiskBadge.tsx
│   │   ├── RiskSummaryBar.tsx
│   │   └── TrendIcon.tsx
│   ├── lib/
│   │   └── supabase.ts
│   ├── styles/
│   │   └── globals.css
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   └── tsconfig.json
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Deployment

### 1. Supabase Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Run the migration: **SQL Editor → paste `001_initial_schema.sql` → Run**
3. Seed provinces: **Table Editor → provinces → Insert from CSV → `seeds/provinces.csv`**
4. Seed crop calendars: **Table Editor → crop_calendars → Insert from CSV → `seeds/crop_calendars.csv`**
5. Copy your `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, and DB connection details

### 2. Railway.app (Pipeline)

1. New project → Deploy from GitHub
2. Set all environment variables from `.env.example` (excluding NEXT_PUBLIC_ ones)
3. Add a PostgreSQL service or let Airflow use Supabase directly
4. Set start command: `airflow webserver` (for webserver) / `airflow scheduler` (for scheduler)

Or for a minimal Railway deploy without Airflow, use Railway's **Cron** service:

```
# Weekly Monday 06:00 PHT cron (Railway cron syntax)
0 22 * * 0  cd /app && python pipeline/scripts/pagasa_scraper.py && dbt run --profiles-dir pipeline && python pipeline/scripts/digest_generator.py && python pipeline/sms/send_sms.py
```

### 3. Vercel (Dashboard)

1. Import the repo → Vercel will detect Next.js
2. Set environment variables: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
3. Create a Deploy Hook and save it as `VERCEL_DEPLOY_HOOK_URL` in Railway

### 4. dbt seed + first run

```bash
cd pipeline
pip install -r requirements.txt
dbt seed --profiles-dir . --target prod       # Load provinces + crop_calendars
python scripts/pagasa_scraper.py               # Scrape PAGASA (uses manual override fallback)
dbt run --profiles-dir . --target prod        # Compute risk scores
python scripts/digest_generator.py            # Generate advisories
python sms/send_sms.py --test                 # Test SMS to +639495034475
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
- Row Level Security (RLS) is enabled on all Supabase tables
- Claude API key is a Railway env var — never bundled in frontend code
- Semaphore API key is a Railway env var
- Every advisory and SMS includes a mandatory disclaimer

---

## Cost Estimate (Monthly, 15 provinces)

| Service | Cost |
|---------|------|
| Supabase (free tier) | ₱0 |
| Railway.app (Hobby) | ~₱200 |
| Vercel (free tier) | ₱0 |
| Claude haiku advisories (15 provinces/week × 4 weeks) | ~₱24 |
| Semaphore.ph SMS (100 contacts × 4 weeks × ₱0.65) | ~₱260 |
| **Total** | **~₱484/month** |

---

## Disclaimer

This system is a decision-support tool based on public PAGASA seasonal forecasts and PhilRice published crop calendars. Risk scores are model estimates. Always verify with your local Department of Agriculture or PAGASA office before taking agricultural action. Not a substitute for official PAGASA or DA advisories.
