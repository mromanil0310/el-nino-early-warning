# El Niño Agricultural Early Warning Data Layer — Architecture Blueprint
**Blueprint Date:** 2026-06-21 | **Source:** Philippine Agriculture Opportunity Radar (June 21, 2026) — Rank #1 BUILD NOW
**Architect:** Biboy Labs Chief Technology & AI Architect
**Status:** AWAITING BIBOY'S APPROVAL — no build authorized until explicit trigger in attended Claude Code session

---

## STEP 1 — Product Understanding

### Why this product matters
PAGASA issued an El Niño Alert in April 2026 with 79% probability of a June–August 2026 event that could reduce national rice yields by 25–35%. That's 7–10 million metric tons of palay at risk. The data to issue crop-specific barangay-level risk advisories exists — PAGASA produces it, PhilRice has crop-climate correlation research, PSA publishes crop calendars — but no system joins these into a decision-support layer that reaches the people who need it: LGU agricultural officers, cooperative leaders, and the DA Regional Field Office staff who make planting advisory decisions. The synthesis step doesn't exist. This product builds it.

### Why users will adopt it
LGU agricultural officers are the immediate user. They currently receive PAGASA bulletins (regional aggregate, weeks late) and DA crop advisories (reactive, post-damage). They make planting schedule, farmer advisory, and input support decisions without localized risk data. A weekly dashboard showing which municipalities in their province face the highest yield-loss probability for the current planting stage — pulled from current data — is an immediate, unambiguous upgrade to their decision-making. They don't need to be sold on the concept; they need to be shown the interface and given access. The farmer is not the user; the LGU officer is.

### Why it can win
Three advantages: (1) **Data engineering moat** — PAGASA and PSA data is public but genuinely messy; the skill to build a reliable ingestion pipeline that normalizes province-level climate data against crop calendars is Biboy's core domain. (2) **Timing window** — the El Niño event is happening now; a prototype dashboard in 4–6 weeks could influence Q3 2026 planting advisories, which is a concrete and demonstrable impact. (3) **Palawan proximity** — a Palawan pilot with PAgO (Provincial Agriculture Office) gives Biboy a reachable first institutional customer within driving distance. Proximity to the problem is a genuine distribution advantage over a remote builder.

---

## STEP 2 — MVP Reduction

### Feature classification

| Feature | Classification | Reason |
|---|---|---|
| PAGASA seasonal forecast ingestion pipeline | MUST HAVE | The product is a data layer; this is the primary data source |
| PSA provincial crop calendar ingestion | MUST HAVE | Without crop stage data, the risk model has no context |
| Province-level El Niño yield-risk scoring | MUST HAVE | The core analytical output; the product's reason to exist |
| LGU dashboard (web, risk by province/municipality) | MUST HAVE | The interface institutional users actually consume |
| Weekly automated data refresh | MUST HAVE | Stale data is worse than no data for an early warning system |
| Cooperative weekly SMS digest (top-3 planting risks) | SHOULD HAVE | Extends reach to cooperatives without internet; adds distribution credibility |
| DA Regional Field Office API endpoint | LATER | Phase 2; requires formal DA integration agreement; valuable but not MVP |
| Barangay-level granularity | LATER | Province and municipality level is the MVP floor; barangay requires granular crop area data that PSA doesn't publish at that resolution |
| Farmer-facing mobile app | REMOVE | Wrong user in MVP; farmer-facing requires dialect localization, feature phone UX, and community trust-building that are Phase 3 concerns at earliest |
| Satellite imagery integration | REMOVE | Adds cost and complexity (Planet/Sentinel API licensing/processing); PhilRice Ricelytics can supply processed data in Phase 3 |
| Crop insurance pre-screening | REMOVE | Separate product (EXPLORE in PH Ag Radar); don't conflate |
| Real-time weather feeds | LATER | PAGASA seasonal forecasts are the appropriate data frequency for planting advisories; real-time weather is a different product |
| Revenue gate / subscription paywall | LATER | Phase 2; first demonstrate institutional value, then charge |
| Multi-crop coverage (beyond rice/corn) | LATER | Start with palay (rice) — highest social impact, best data availability |

### MVP Definition
The minimum viable El Niño Early Warning Data Layer is a **data pipeline + web dashboard** that ingests PAGASA seasonal climate forecasts and PSA provincial crop calendars weekly, computes a province-level El Niño yield-risk score for palay and corn, and presents it as a clean web dashboard for LGU agricultural officers showing which provinces face the highest risk for the current and next planting window. A secondary output is a plain-text weekly summary (formatted for copy-paste into SMS or email) for cooperative liaisons. Pilot scope: 10–15 high-risk provinces in Luzon (Regions I, III, IV-A, CAR) where the El Niño impact is projected to be highest.

**MUST HAVE list:** PAGASA forecast scraper/parser → PSA crop calendar loader → risk-scoring engine (province × crop stage × seasonal anomaly) → PostgreSQL data store → weekly automated pipeline run → web dashboard (province list + risk scores + trend) → plain-text weekly summary output.

---

## STEP 3 — Architecture Design

### Data Pipeline
**Choice:** Python (pandas/requests for ingestion) + dbt (transformation) + Airflow (orchestration, self-hosted via Docker on a ₱500/month VPS or Railway.app)
**Why:** This is exactly Biboy's Snowflake/dbt/Airflow domain expertise applied to a public-data problem. The stack is proven and directly leverages the existing skill set. No new technology to learn.
**Tradeoffs:** Self-hosted Airflow adds operational overhead vs. a managed workflow service; Railway.app or Render.com can reduce this. Managed Airflow (AWS MWAA) is over-engineered for a 3-table pipeline.
**Scalability trigger:** Move to Astronomer or AWS MWAA when pipeline exceeds 20+ DAGs or when a DA integration requires SLA guarantees.

### Database
**Choice:** PostgreSQL (Supabase free tier, escalate to Pro as needed)
**Why:** Supabase gives Postgres + REST API + PostGIS (for geographic queries) in one package, free for this data volume. PostGIS is valuable for the province-level geographic data model.
**Tradeoffs:** Supabase free tier has a 500MB DB limit and pauses after 1 week of inactivity — configure a keep-alive ping job. Pro tier (₱1,250/month) eliminates both constraints.
**Scalability trigger:** Supabase Pro at 50+ daily dashboard users or when DA API endpoint requires guaranteed uptime.

### Frontend Dashboard
**Choice:** Next.js (static export mode) deployed on Vercel + Recharts for risk score visualization
**Why:** Server-side data fetch on weekly pipeline run means the dashboard can be a static export (no SSR runtime cost). Recharts handles the risk trend charts with minimal overhead.
**Tradeoffs:** Static export means dashboard is only as fresh as the last build trigger. Use a Vercel deployment webhook from the Airflow pipeline to rebuild after each weekly data update.
**Scalability trigger:** Move to full Next.js SSR when real-time data updates are needed (not in MVP scope).

### Backend / API
**Choice:** Supabase REST API (auto-generated from schema) for dashboard data fetching; no custom API server in MVP
**Why:** Eliminates backend maintenance for MVP; Supabase REST is sufficient for the read-only dashboard queries.
**Tradeoffs:** No rate limiting or custom business logic layer; acceptable for MVP with a known institutional user base (not public internet scale).
**Scalability trigger:** Add FastAPI service layer when DA endpoint integration requires authenticated, rate-limited access.

### Authentication
**Choice:** Supabase Auth with email invite — dashboard access by invite only in pilot phase
**Why:** Limits MVP access to the pilot LGU officers and keeps the dashboard off the public internet during validation.
**Tradeoffs:** Manual invite management; acceptable for a 5–20 user pilot.
**Scalability trigger:** Self-service signup when the product is opened beyond pilot institutions.

### Infrastructure
**Choice:** Supabase (database + auth) + Railway.app (Airflow + Redis) + Vercel (frontend) — all managed, low operational overhead
**Why:** Solo operator cannot run infrastructure; all three are managed, have free/low-cost tiers adequate for MVP, and remove the need for a dedicated DevOps role.
**Tradeoffs:** Three vendors adds some vendor-lock risk; mitigated by standard SQL schema and standard Python pipeline code that can move.
**Scalability trigger:** AWS or GCP migration only when government contract requires data residency in PH — this is a real concern for DA contracts; flag for Phase 2 due diligence.

### SMS Digest
**Choice:** Semaphore.ph API (Philippine SMS gateway, ₱0.65/SMS, no monthly fee)
**Why:** Globe/Smart API access requires business registration and approval windows; Semaphore is the fastest path to SMS delivery in PH for a solo operator and is widely used by PH developers.
**Tradeoffs:** Cost-per-SMS adds up at scale (100 cooperatives × weekly = 400 SMS/month ≈ ₱260/month — acceptable at MVP).
**Scalability trigger:** Direct Globe/Smart enterprise API when volume exceeds 10,000 SMS/month.

### Monitoring
**Choice:** Airflow built-in alerting (email on DAG failure) + Sentry free tier for frontend errors + Uptime Robot for dashboard availability
**Why:** Three free tools cover the critical failure modes: pipeline failure, frontend JS errors, and dashboard downtime.
**Tradeoffs:** No APM (application performance monitoring); acceptable for MVP data volumes.

---

## STEP 4 — AI Strategy

| AI Application | Classification | Reasoning |
|---|---|---|
| AI-generated plain-text advisory summaries (weekly digest) | BUILD NOW | Claude generates the plain-text weekly advisory summary from structured risk score data; a 3-sentence Tagalog/English advisory per province that cooperative officers can copy-paste into SMS; bounded input, bounded output, high value |
| Risk score calibration via historical yield data | PHASE 2 | Requires 2–3 seasons of historical correlation data; not yet available; start with rule-based scoring from PhilRice published correlations |
| Anomaly detection on price data (correlation with El Niño events) | PHASE 2 | Valuable when price monitoring data is being collected; not in MVP scope |
| Farmer-facing dialect chatbot | PHASE 3 | Wrong user for MVP; not buildable responsibly without dialect training data and field testing |
| Satellite yield forecasting model | DO NOT BUILD | Requires remote sensing expertise and model validation; use PhilRice/IRRI's existing outputs as data inputs instead |

**AI in MVP:** 1 BUILD NOW — Claude generates a weekly plain-text advisory summary per province from structured risk scores. Input is fully structured (province, crop, risk score, trend direction, PAGASA outlook summary). Output is a 3-sentence advisory in plain English + Tagalog. Single API call per province per week; estimated cost ₱0.02–0.05/call.

---

## STEP 5 — Data Strategy

### Core entities
- **Province** (id, name, region, PAGASA zone, PSA crop area ha by crop)
- **PAGASAForecast** (id, provinceId, forecastDate, seasonOutlook, rainfallAnomalyPct, temperatureAnomalyC)
- **CropCalendar** (id, provinceId, crop, plantingWindowStart, plantingWindowEnd, harvestWindowStart)
- **RiskScore** (id, provinceId, crop, weekOf, elNinoRiskScore, trendDirection, scoringRun)
- **WeeklyDigest** (id, provinceId, weekOf, plainTextAdvisory, smsText, generatedAt)

Relationships: Province → many PAGASAForecast, many CropCalendar, many RiskScore → one WeeklyDigest per week.

### North Star Metric
**LGU advisory decisions informed by the dashboard per quarter** — tracked via post-pilot survey (not automated; automated tracking isn't possible without embedding in LGU workflows). Proxy: dashboard weekly active users (WAU) during El Niño season.

### Success metrics (MVP stage)
1. Dashboard WAU (pilot LGU officers)
2. Weekly digest views / SMS opens (proxy: cooperative officer engagement)
3. Pipeline reliability (% of weekly runs completing without error)
4. Province coverage accuracy (risk scores align with PAGASA actual advisories — validated by comparing with official DA field reports)
5. Time from PAGASA forecast publication to dashboard update (target: < 24 hours)

### Event tracking (minimum — server-side only)
| Event | Properties |
|---|---|
| `dashboard_view` | userId (hashed), provinceFilters, sessionDate |
| `digest_viewed` | userId (hashed), weekOf |
| `pipeline_run_completed` | runDate, provincesUpdated, durationSecs, status |
| `pipeline_run_failed` | runDate, dagId, errorMessage |

No PII beyond hashed user IDs. Institutional users only (no public access in pilot).

---

## STEP 6 — Security Review

| Risk | Type | Mitigation |
|---|---|---|
| Data is all public (PAGASA, PSA, PhilRice) | Privacy | Low privacy surface; no farmer PII collected |
| Dashboard access by institutional users only | Access control | Supabase Auth invite-only gate; no public access during pilot |
| Advisory accuracy liability | Product integrity | Add explicit disclaimer on every dashboard page and digest: "This is a decision-support tool based on publicly available data; verify with local PAGASA/DA advisory before acting." Label confidence level per score. |
| PAGASA data parsing errors (format changes) | Data integrity | Add schema validation step in Airflow before transformation; alert on schema drift |
| Government data hosting requirements (DA contract) | Regulatory | If DA formalizes partnership, data residency in PH may be required; AWS Manila (ap-southeast-1) or Azure PH are the escalation paths; Supabase + Railway are not PH-domiciled |
| SMS spoofing / impersonation | Security | Include product identifier in every SMS; Semaphore sends from registered sender ID |
| Pipeline downtime during El Niño peak | Availability | Airflow retry config: 3 retries with 30-min delay on forecast DAGs; email alert to Biboy on DAG failure |
| Incorrect risk scores amplifying farmer harm | Integrity | Version all scoring logic in dbt with git; require code review (self-review at minimum) before any model change; include model version in every RiskScore record |

**Elevated:** Advisory accuracy liability. This product informs agricultural decisions that affect livelihoods. The disclaimer is not optional. The scoring methodology should be documented publicly (even in a simple README on the dashboard) so that LGU officers can understand how the score is derived.

---

## STEP 7 — Development Roadmap

### Phase 1 — MVP (Weeks 1–6)

**Objectives:** Prove that the pipeline produces accurate province-level El Niño risk scores for 10–15 Luzon provinces, and that 3–5 LGU agricultural officers find the dashboard useful.

**Deliverables:**
- PAGASA seasonal forecast scraper (target: PAGASA Climate Outlook PDF + Climate of Cities bulletins)
- PSA crop calendar data load (manual for MVP; PSA Open Stat API for Phase 2)
- dbt models: risk score calculation (palay and corn), weekly trend
- Airflow DAG: weekly trigger, forecast → transform → score → notify
- Supabase schema and REST API
- Next.js dashboard: province list, risk score table, trend chart, weekly advisory text
- Plain-text weekly digest (AI-generated via Claude API, formatted for SMS/email)
- Semaphore SMS integration (pilot: 5–10 cooperatives in Luzon)
- Supabase Auth: invite-only access for pilot LGU officers
- Documentation: scoring methodology published on dashboard About page

**Dependencies:** PAGASA data format confirmation (parse PDF vs. structured bulletin), Supabase account, Railway.app account, Semaphore.ph account, Claude API key

**Acceptance criteria:**
- Pipeline runs weekly without manual intervention
- Risk scores for all 15 pilot provinces updated within 24 hours of PAGASA forecast publication
- Dashboard loads in < 3 seconds on a Philippine mobile connection (3G baseline)
- 3 LGU pilot users confirm the dashboard is usable after one demo session

### Phase 2 — Growth (Months 2–4)

**Objectives:** DA Regional Field Office partnership; expand to all 18 regions; Corn + vegetable crop coverage

**Deliverables:**
- DA integration API endpoint (authenticated, rate-limited)
- Formal partnership with 1–2 DA Regional Field Offices
- PSA Open Stat API integration (replace manual crop calendar load)
- Expand province coverage to all 18 regions
- Self-service signup for LGU officers (not invite-only)
- Government-facing reporting: monthly summary PDF per region

**Dependencies:** Phase 1 pilot validation data; DA relationship; decision on PH data residency

### Phase 3 — Scale (Months 5–9)

**Objectives:** Commercialization via government SaaS contract; farmer-facing digest via cooperative networks; satellite data integration

**Deliverables:**
- Formal DA/LGU SaaS subscription contract (₱50–100K/year per province)
- Cooperative-facing WhatsApp digest (via Semaphore or 360dialog)
- PhilRice or IRRI satellite data API integration for enhanced yield correlation
- Palawan PAgO dedicated instance (regional customization for fishing communities)
- FAO/UNDP grant application package

### Phase 4 — Platform (Month 10+)

**Objectives:** Multi-crop, multi-hazard (typhoon + flood + drought), multi-country (SEA)

---

## STEP 8 — Builder Handoff

### Product summary
El Niño Early Warning Data Layer is a data pipeline + web dashboard that ingests PAGASA seasonal forecasts and PSA crop calendars weekly, computes province-level yield-risk scores for palay/corn, and presents a dashboard for LGU agricultural officers + a plain-text weekly advisory (AI-generated, SMS-ready) for cooperative liaisons. Pilot scope: 10–15 Luzon provinces. No farmer-facing component in MVP.

### MVP scope (single source of truth)
- Airflow DAG running weekly (Sunday night Philippine time), triggered manually for initial runs
- PAGASA data source: PAGASA Seasonal Climate Outlook (PDF parse via pdfplumber or structured bulletin if available at pagasa.dost.gov.ph)
- PSA crop calendar: manually loaded from PSA Open Stat crop area tables for pilot provinces
- Risk scoring: rule-based model in dbt (seasonal rainfall anomaly × crop growth stage vulnerability index, based on PhilRice published El Niño impact coefficients)
- Output: province-level risk scores (High/Medium/Low + numeric 0–100) + trend vs. prior week
- Dashboard: Next.js static, deployed on Vercel; data fetched from Supabase REST at build time; Vercel webhook triggers rebuild after pipeline completion
- Weekly digest: Claude API call (claude-haiku-4-5) generates 3-sentence advisory per province; plain English + Tagalog; stored in Supabase, served via dashboard and SMS
- SMS: Semaphore.ph webhook triggered by Airflow after digest generation; sends to pre-registered cooperative numbers

### Architecture
- **Pipeline:** Python (requests, pdfplumber, pandas) + dbt + Airflow on Railway.app
- **Database:** Supabase (PostgreSQL + PostGIS)
- **Frontend:** Next.js static export + Recharts + Vercel
- **Auth:** Supabase Auth (email invite)
- **AI:** Claude API haiku (weekly digest generation)
- **SMS:** Semaphore.ph
- **Monitoring:** Airflow email alerts + Sentry frontend + Uptime Robot

### Data model (key tables)
```sql
provinces(id, name, region_code, pagasa_zone, lat, lon)
pagasa_forecasts(id, province_id, forecast_date, seasonal_outlook, rainfall_anomaly_pct)
crop_calendars(id, province_id, crop, planting_start, planting_end, harvest_start)
risk_scores(id, province_id, crop, week_of, risk_score, risk_level, trend, model_version)
weekly_digests(id, province_id, week_of, advisory_en, advisory_tl, sms_text, generated_at)
```

### Risk scoring model (MVP — rule-based, dbt)
```
risk_score = rainfall_anomaly_severity_weight × crop_stage_vulnerability_index
- rainfall_anomaly_severity: 0–1 (derived from PAGASA forecast: Below Normal, Below Normal, Dry)
- crop_stage_vulnerability: 1.0 (flowering/reproductive), 0.7 (vegetative), 0.4 (pre-planting/fallow)
  — based on PhilRice published El Niño vulnerability windows
- risk_score: 0–100; High > 65, Medium 35–65, Low < 35
```

### API requirements
- Supabase REST: auto-generated; key is service_role key for pipeline writes, anon key for dashboard reads
- Claude API: `POST /v1/messages` with model `claude-haiku-4-5-20251001`; prompt bounded to structured risk data; no user input routed to API
- Semaphore.ph: `POST https://api.semaphore.co/api/v4/messages`; message content from WeeklyDigest.sms_text

### Security requirements
- Supabase Row Level Security (RLS): authenticated users can read all risk scores; only service_role key (pipeline) can write
- Dashboard: invite-only; Supabase Auth middleware on Next.js API routes
- PAGASA/PSA data: public domain; no licensing concern
- Claude API key: Railway.app environment variable; never in client bundle
- Data disclaimer: rendered on every dashboard page and in every SMS footer

### Testing requirements
- Unit tests: risk score calculation (verify against known PhilRice El Niño impact case studies)
- Integration: full pipeline run against 3 test provinces using historical PAGASA data
- Dashboard: smoke test on mobile (iPhone Safari + Android Chrome) — 3G throttle test
- SMS: test send to Biboy's number before pilot launch

### Deployment requirements
- Railway.app: Airflow + Redis + Python environment; deploy via GitHub Actions
- Supabase: manual schema migration via Supabase CLI; migration files in /migrations
- Vercel: Next.js deployment; Vercel webhook URL registered in Airflow DAG as post-run trigger

---

## STEP 9 — Executive Recommendation

| Dimension | Score | Notes |
|---|---|---|
| Architecture Confidence | 9/10 | This is Biboy's exact skill set; no novel technology; pure data engineering |
| Build Complexity | 8/10 | Data ingestion complexity depends on PAGASA PDF format; risk scoring model is straightforward |
| Scalability | 7/10 | Supabase + Vercel scale cleanly; Airflow on Railway is the weak point at high DAG count |
| Technical Risk | 8/10 | Primary risk is PAGASA data format (PDF parsing is fragile); mitigated by structured bulletin if available |
| AI Leverage | 5/10 | One targeted AI application (digest generation); AI is not core to the product's value |

**Estimated MVP Timeline:** 4–6 weeks (2 weeks pipeline + scoring model, 2 weeks dashboard, 1 week SMS + digest, 1 week pilot setup)

### Final Recommendation: BUILD NOW

This is the highest-confidence blueprint of the three produced this week. It is pure data engineering. The data is public. The user (LGU agricultural officer) is reachable. The timing is not artificial — the El Niño event is active and the planting decisions that will determine Q3/Q4 2026 rice harvests are being made right now. A 4-week prototype could influence decisions this season, which is a concrete and demonstrable impact for a first government client conversation. The Palawan PAgO is a realistic first pilot partner given Biboy's location.

Revenue is slow (government SaaS cycles), but impact is immediate and the product generates grant-fundable credentials (FAO, UNDP, ADB are actively funding climate-smart agriculture in PH right now). The combination of immediate impact + grant fundability + solo-buildable stack makes this the most risk-adjusted product in this week's cohort.

*"If Biboy Labs builds only one product this month, this is how I would build it."*

---
*Blueprint generated by Weekly Architecture Blueprint task | 2026-06-21 | AWAITING BIBOY'S APPROVAL*
