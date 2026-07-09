# El Niño Agricultural Early Warning Data Layer — Architecture Blueprint

> ## Latest: Phase 2 Architecture Planning — 2026-07-05
> Phase 1 (deployment checklist) is documented in the Enhancement Run — 2026-06-27 section below. The system remains undeployed as of July 5. This run blueprints Phase 2: the architectural decisions that must be made as soon as Phase 1 deployment is complete.

---

## Enhancement Run — 2026-07-05
**Source:** Weekly Architecture Blueprint fallback (no new ACCELERATE/BUILD NOW items without prior blueprints in the pool; all qualifying items have < 4-week blueprints)
**Run type:** Phase 2 Architecture Planning — triggered by zero-qualifying-pool fallback; El Niño EWS is highest-priority existing product (Portfolio Review June 27 score 18.67, ACCELERATE)
**Architect:** Biboy Labs Chief Technology & AI Architect

### What's changed since June 27

The codebase is unchanged — 83 tests still passing, all P0–P3 defects closed. What has changed:

- **12 more days of the agricultural window have elapsed.** Today is July 5. Wet-season planting decisions in Luzon (Region I, III, IV-A) are being made now, not in August. The June 27 blueprint said "deploy this week." That week has passed. The July 5 Executive Weekly Review names deployment as the single most important unfinished action in the entire portfolio.
- **Both Opportunity Radar variants are overdue.** The July radar cycle has not filed (System Health Check, July 5: ⚠️ WARNING). No new BUILD NOW opportunities exist from either source. The architecture queue has no new candidates to blueprint.
- **Phase 2 planning is now timely.** Once deployment happens, the next architectural questions arrive immediately: How do we expand from 15 to 82 provinces? What does the DA integration API look like? How do we secure the inbound webhook before it's exposed to DA systems? These decisions can and should be made before they become urgent blockers.

The June 27 DEPLOY NOW recommendation is architecturally unchanged. This run does not revisit deployment — it blueprints what comes next.

---

### Phase 2 Step 1 — Context

**Why Phase 2 matters right now:** The June 27 blueprint specified a 45–60 minute deployment. Once that's done, the pipeline runs automatically every Monday at 06:00 PHT. The next constraint shifts from technical to institutional: getting an LGU agricultural officer or DA Regional Field Office on the dashboard, and positioning the product for TASAT grant funding. Both require architectural decisions that are better made now than under pressure.

**Why Phase 2 can win:** The data engineering is proven (83 tests, CI-gated). The advisory output is working (Haiku-generated, SMS-delivered). The TASAT grant's $8M climate-smart rice component is the clearest funding pathway in Philippine agriculture right now — and the technical proposal that competes for it requires an API endpoint, national province coverage, and a methodology document. Phase 2 produces all three.

**Why Phase 2 is achievable:** Every component below is an incremental extension of the Phase 1 stack. No new technology is introduced. The largest new component (FastAPI endpoint) is 3 routes and approximately 200 lines of Python. Province expansion is a seed file update. Webhook hardening is a 20-line function.

---

### Phase 2 Step 2 — Scope

**MUST HAVE for Phase 2 MVP (smallest version that enables institutional adoption):**

| Feature | Reason |
|---|---|
| Inbound webhook signature validation | Security baseline before any DA/institutional exposure; currently the webhook URL accepts any POST |
| Anthropic SDK upgrade (0.34.2 → current) | ELN-018; deferred from deployment; small effort, growing technical debt |
| Province seed expansion (15 → 82 provinces) | TASAT grant and DA partnership both require national coverage; 15 provinces is a pilot, 82 is a product |
| Province-station mapping data model fix | Current model approximates PAGASA's station-based forecast structure; at 82 provinces the approximation introduces material scoring errors for multi-station provinces |
| FastAPI DA integration endpoint | DA Regional Field Office and TASAT applications both require a documented, authenticated API; Supabase REST alone is not institutionally acceptable |

**SHOULD HAVE (before first institutional demo, not required at Phase 2 start):**

| Feature | Reason |
|---|---|
| Monthly PDF summary per region | LGU and DA reporting cycles are monthly; a one-page PDF summary is expected output |
| OpenAPI/Swagger documentation | DA IT departments will ask for this; FastAPI generates it for free |
| API key rotation mechanism | Issue, rotate, and revoke keys without manual DB surgery |

**LATER (explicitly deferred):**

| Feature | Trigger condition |
|---|---|
| Crop expansion (vegetables, cassava) | First DA/LGU partner confirmed and using the dashboard |
| Localization (Ilocano, Cebuano) | Request from a specific LGU in a dialect-dominant region |
| Farmer-facing WhatsApp digest | Formal cooperative network partnership; not solo-buildable |
| Historical yield ML calibration | 2 full El Niño seasons of actual vs. predicted data |

**REMOVE (do not build in Phase 2):**

| Feature | Reason |
|---|---|
| Real-time weather feed integration | Wrong data frequency for planting advisories; adds cost and complexity with no user value at this stage |
| Satellite imagery (beyond what's implied by PAGASA data) | Remote sensing domain expertise and data licensing not justified until Phase 3 |

**Phase 2 MVP Definition:** The smallest Phase 2 that enables institutional adoption is a secured, nationally-scoped advisory system with a documented API: webhook auth hardened, SDK upgraded, all 82 provinces seeded with correct PAGASA station mapping, and a 3-route FastAPI endpoint with API key auth and auto-generated docs. This is what a DA Regional Field Office or TASAT grant evaluator needs to see.

---

### Phase 2 Step 3 — Architecture

Phase 1 stack (Python + dbt + Airflow on Railway + Supabase PostgreSQL + Vercel Next.js + Semaphore.ph) is correct and unchanged. Phase 2 adds three components:

#### Component A: Province-Station Data Model

**Problem:** PAGASA uses climate monitoring stations (not administrative provinces) as their forecast unit. One province may overlap 2–3 PAGASA stations; one station may cover parts of multiple provinces. The current model assigns a single PAGASA forecast to each province — correct enough for 15 Luzon provinces but inaccurate at national scale.

**Fix:** Add two tables via migration `006_province_station_mapping.sql`:

```sql
CREATE TABLE pagasa_stations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    station_code VARCHAR(20) UNIQUE NOT NULL,
    name         VARCHAR(100) NOT NULL,
    lat          DECIMAL(9,6),
    lon          DECIMAL(9,6),
    region_code  VARCHAR(10)
);

CREATE TABLE province_station_mapping (
    province_id UUID REFERENCES provinces(id),
    station_id  UUID REFERENCES pagasa_stations(id),
    weight      DECIMAL(4,3) DEFAULT 1.0, -- for weighted risk averaging where provinces span stations
    PRIMARY KEY (province_id, station_id)
);
```

**Why chosen:** Corrects the fundamental mismatch between PAGASA's station-based forecast structure and the province-level risk score output. Weight allows weighted averaging when a province spans multiple PAGASA stations.

**Tradeoffs:** Adds a join step to the risk-score dbt model; increases seed data complexity (need to map all 82 provinces to their PAGASA stations from public PAGASA station registry).

**Scalability trigger:** No change needed until PAGASA restructures their station network (rare; last major restructure was 2010s).

#### Component B: FastAPI DA Integration Endpoint

**Choice:** FastAPI service deployed as a 5th Railway service; `slowapi` for rate limiting; API keys stored as SHA-256 hashes in `api_keys` table.

**Why chosen:** Supabase REST is not institutionally acceptable for DA integration (exposes anon key structure, no versioning, no business-logic layer). FastAPI gives versioned routes, auto-generated OpenAPI docs, and a clean authentication layer in minimal code.

**Routes (MVP — 3 required, 2 optional):**

```
GET  /api/v1/provinces              — all provinces, latest risk score per province
GET  /api/v1/provinces/{id}         — single province, risk history (last 12 weeks)
GET  /api/v1/advisories/latest      — all latest advisories (English + Tagalog)
GET  /api/v1/advisories/export.csv  — CSV bulk export (for DA Excel workflows)
GET  /api/v1/methodology            — scoring methodology JSON (required for TASAT proposal)
```

**Auth:** `X-API-Key` header. Key storage:

```sql
CREATE TABLE api_keys (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash    VARCHAR(64) NOT NULL UNIQUE, -- SHA-256 of the issued key
    da_office   VARCHAR(100),
    region_scope VARCHAR(20), -- 'national' or specific region code
    rate_limit  INTEGER DEFAULT 100, -- requests/minute
    created_at  TIMESTAMPTZ DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);
```

Issue a key: generate 32 random bytes, base64url-encode → issue to DA office; store `SHA256(key)` in `api_keys`. Revoke: set `revoked_at = now()`.

**Rate limit:** 100 req/min per key via `slowapi`. Sufficient for dashboard polling; not at API abuse scale.

**Deployment:** New Railway service. Start command: `uvicorn pipeline.api.main:app --host 0.0.0.0 --port 8000`. Environment vars: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (shared with pipeline; no new secrets needed).

**Tradeoffs:** Adds a 5th Railway service (minor cost increase on starter tier). FastAPI cold starts on Railway are ~500ms — acceptable for institutional batch queries, not for real-time dashboards (but the dashboard still uses Supabase REST directly, so this is irrelevant).

**Scalability trigger:** Move to Railway's reserved tier or add a caching layer (Redis, already on Railway) when API queries exceed 1,000 req/hour.

#### Component C: Inbound Webhook Signature Validation

**Current state:** `pipeline/webhook/inbound.py` accepts any POST to the webhook URL. Risk: anyone who knows the URL can send fake opt-out or feedback events.

**Fix (add to `inbound.py`):**

```python
import hmac, hashlib, os
from flask import request, abort

def verify_semaphore_signature(payload: bytes, sig_header: str) -> bool:
    secret = os.environ.get("SEMAPHORE_WEBHOOK_SECRET", "")
    if not secret:
        return True  # skip validation in dev (no secret set)
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)

# In the route handler:
@app.route("/sms/inbound", methods=["POST"])
def inbound():
    sig = request.headers.get("X-Semaphore-Signature", "")
    if not verify_semaphore_signature(request.get_data(), sig):
        abort(403)
    # ... existing handler logic
```

**New Railway env var:** `SEMAPHORE_WEBHOOK_SECRET` — configure in Semaphore.ph account settings → Inbound Webhook → Signature Secret. Set the same value in Railway.

**Why chosen:** Semaphore supports HMAC-SHA256 signature verification on inbound webhooks. `hmac.compare_digest` prevents timing attacks.

**Tradeoffs:** If `SEMAPHORE_WEBHOOK_SECRET` is not set (e.g., dev environment), validation is skipped — acceptable, explicit, and documented.

**Scalability trigger:** No change needed unless Semaphore changes their signature scheme (versioned in header format; monitor Semaphore changelog).

#### Data Residency Decision Framework

If DA contract or TASAT grant requires PH data residency:

| Option | Path | Cost | When |
|---|---|---|---|
| A: Negotiate exemption | All stored data is public domain (PAGASA + PSA); no PII; Data Privacy Act risk is negligible | ₱0 | First option — include in any MOU: "All data processed is public domain; no personal data stored; jurisdiction acknowledged" |
| B: PH-domiciled backup | Daily `pg_dump` to AWS Manila (ap-southeast-1) S3; primary Supabase stays as-is | ~₱500/month | If option A fails but primary residency not required |
| C: Full migration | Migrate Supabase → AWS Manila RDS PostgreSQL; Airflow → AWS MWAA | ₱30,000–₱60,000/month | Only if contract value justifies (multi-province DA subscription > ₱5M/year) |

**Recommended path:** Option A first. Options B and C are contingency — do not pre-build.

---

### Phase 2 Step 4 — AI Strategy

| Application | Status | Reasoning |
|---|---|---|
| Claude Haiku advisory generation (82 provinces) | BUILD NOW | Same code, more provinces; cost scales linearly (~₱0.02–0.05/call × 82 provinces × 52 weeks ≈ ₱85–200/year — negligible) |
| Anthropic SDK upgrade (0.34.2 → current) | BUILD NOW at Phase 2 start | ELN-018; low risk, S effort; do this in the first Phase 2 session before adding more Haiku calls at scale |
| Advisory explanation sentence (why High risk) | PHASE 2 optional | Not AI — generate from structured data: "Rainfall anomaly: -45% vs. normal; crop stage: reproductive (peak vulnerability)." One deterministic sentence added to advisory; high user value, zero AI cost |
| Historical yield ML calibration | PHASE 3 | Need 2 full El Niño seasons of actual vs. predicted yield data before a model is more useful than the current rule-based scoring |
| Dialect localization via Claude | PHASE 3 | Ilocano/Cebuano advisory requires prompt engineering and field validation; not justified until a specific LGU partner requests it |
| Risk score anomaly detection (self-check) | PHASE 2 optional | Automated check: compare generated advisory sentiment (positive/negative/neutral) vs. PAGASA forecast direction (above/below/near normal); flag mismatches for human review. Deterministic, not ML. |

No AI in Phase 2 that isn't already in Phase 1, except the SDK upgrade and optional explanation sentence.

---

### Phase 2 Step 5 — Data

**New core entities (Phase 2):**

```
pagasa_stations(id, code, name, lat, lon, region_code)
province_station_mapping(province_id, station_id, weight)
api_keys(id, key_hash, da_office, region_scope, rate_limit, created_at, revoked_at)
```

**Updated North Star Metric:** LGU advisory decisions informed by the dashboard per quarter. Tracked via quarterly check-in with pilot users. Phase 2 proxy: API calls from DA systems per week (tracked in a new `api_access_log` table — append-only, stores key_hash + endpoint + timestamp, no request body).

**Updated success metrics (Phase 2):**
1. Province coverage (target: all 82 provinces with risk scores by end of Phase 2)
2. API integrations (DA offices with active API keys)
3. Weekly pipeline reliability (unchanged target: 100%)
4. Dashboard WAU (LGU officers)
5. Advisory feedback rate (rate of `acted` / `need_help` responses to SMS advisories)

**Minimum additional event tracking:**
```
api_request: {key_hash (not key), endpoint, response_code, timestamp}
province_expanded: {province_count, run_date}
```

---

### Phase 2 Step 6 — Security

| Risk | Phase 2 Mitigation |
|---|---|
| Inbound webhook spoofing | Implement HMAC-SHA256 validation (Component C above) — MUST HAVE at Phase 2 start |
| API key leakage | Store only SHA-256 hash; plain key sent once at issuance and never stored; rotation via CLI: generate new key, send to DA contact, revoke old |
| Province risk score accuracy at scale | Add dbt tests: every province has ≥ 1 `risk_score` record per pipeline run; no province has a null `risk_level`; PAGASA station weights sum to 1.0 per province |
| TASAT grant compliance | Include methodology JSON at `/api/v1/methodology`; data lineage in pipeline git history; no PII in any table |
| DA MOU data residency clause | Option A: negotiate exemption; document all-public-domain nature of stored data |
| Advisory sentiment mismatch at scale | Optional: automated sentiment-vs-PAGASA cross-check after digest generation; flag to `OPS_ALERT_WEBHOOK_URL` if mismatch rate > 10% in a run |

**Elevated risk (Phase 2-specific):** Province-station mapping accuracy. Incorrect station-to-province mapping produces wrong risk scores for affected provinces. Mitigation: seed `province_station_mapping` from PAGASA's published station-area tables; add a dbt test that validates province risk scores against the PAGASA forecast direction for the corresponding station (score should be High when PAGASA is "Below Normal" for a reproductive-stage crop).

---

### Phase 2 Step 7 — Roadmap

**Phase 2 — Institutional Adoption (6–8 weeks post Phase 1 deployment)**

*Week 1 (immediately after Phase 1 deployment):*
- Deploy inbound webhook auth (`SEMAPHORE_WEBHOOK_SECRET` + `verify_semaphore_signature`)
- Upgrade Anthropic SDK (`pip install anthropic --upgrade`, test `digest_generator.py`)
- Send one email to CDA MIMAROPA Puerto Princesa regional office — one paragraph, introduce the system, attach the Vercel dashboard URL, ask for a 30-minute call about cooperative data infrastructure

*Weeks 2–4:*
- Build `pagasa_stations` and `province_station_mapping` tables (migration 006); seed from PAGASA public station registry
- Expand `provinces.csv` to all 82 provinces; update `crop_calendars.csv`; validate with dbt tests
- Build FastAPI endpoint (MVP routes + auth + rate limiting + OpenAPI docs); deploy as 5th Railway service

*Month 2:*
- Issue first API key to DA Regional Field Office or CDA MIMAROPA for dashboard/API testing
- Build monthly PDF report DAG (`elnino_monthly_report`) using reportlab; upload to Supabase Storage
- Draft TASAT grant technical proposal (uses the FastAPI methodology endpoint as a reference)

*Month 3:*
- TASAT proposal submitted to World Bank/DA point of contact
- Formal LGU/DA partnership MOU or letter of intent
- Debrief first 60 days of advisory feedback (ELN-021 feedback loop data)

**Phase 3 — Revenue + Scale (Months 4–9):** Unchanged from June 27 blueprint.
**Phase 4 — Platform (Month 10+):** Unchanged from June 27 blueprint.

---

### Phase 2 Step 8 — Builder Handoff

Five discrete builds in Phase 2 order of priority:

**Build 1: Inbound webhook auth (30 minutes, do this first)**
- File: `pipeline/webhook/inbound.py`
- Add `verify_semaphore_signature()` function (20 lines; code in Step 3 above)
- Call it at the top of the `/sms/inbound` route handler; `abort(403)` on failure
- Add to Railway webhook service env vars: `SEMAPHORE_WEBHOOK_SECRET`
- Set the same secret in Semaphore.ph account → Inbound Webhook settings
- Test: send a POST to the webhook URL without the signature header; confirm 403 response

**Build 2: Anthropic SDK upgrade (15 minutes)**
- Update `pipeline/requirements.txt`: `anthropic>=0.40.0` (or latest)
- Test: run `digest_generator.py` against 3 test provinces in dev; confirm advisory output unchanged
- Commit and redeploy Railway pipeline service

**Build 3: Province-station mapping + expansion (4–6 hours)**
- Create `supabase/migrations/006_province_station_mapping.sql` (schema in Step 3 above)
- Apply migration via Supabase SQL editor
- Compile `pagasa_stations` seed data from PAGASA Climate Station Registry (publicly available PDF/website); create `pipeline/seeds/pagasa_stations.csv`
- Map all 82 provinces to their PAGASA station(s); create `pipeline/seeds/province_station_mapping.csv`
- Expand `pipeline/seeds/provinces.csv` to all 82 provinces
- Expand `pipeline/seeds/crop_calendars.csv` using PSA Open Stat provincial crop area data
- Update dbt models: `risk_scores` model to use weighted station-province join; add null-safe handling for provinces without crop calendar data
- Add dbt tests: province count = 82, all provinces have risk scores per run, station weights sum to 1.0
- Run `dbt seed` + `dbt run` + `dbt test` against Supabase; confirm all 82 provinces produce valid risk scores

**Build 4: FastAPI endpoint (1–2 days)**
- Create `pipeline/api/main.py` with 5 routes (Step 3 above)
- Create `supabase/migrations/007_api_keys.sql` (schema in Step 5 above); apply
- Create `pipeline/api/auth.py`: API key validation, rate limiting via slowapi
- Deploy as 5th Railway service; env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- Test: issue a key (`generate_key.py` CLI); call `/api/v1/provinces` with header; confirm rate limit enforced
- Verify OpenAPI docs at `/api/v1/docs`

**Build 5: Monthly PDF report DAG (half day)**
- Create `pipeline/dags/elnino_monthly_report.py` — triggers on 1st of each month at 08:00 PHT
- Uses reportlab to generate a 1-page per-region PDF: risk summary table + top-5 high-risk provinces + advisory excerpt
- Upload to Supabase Storage (`reports/` bucket); store URL in a new `reports` table
- Link from dashboard (Reports section — simple list of monthly PDF links)

---

### Phase 2 Step 9 — Executive Recommendation

| Dimension | Score | Notes |
|---|---|---|
| Architecture Confidence | 9/10 | All Phase 2 components are incremental extensions of the proven Phase 1 stack |
| Build Complexity | 7/10 | 5 components; province expansion is data-intensive but technically straightforward |
| Scalability | 9/10 | 82 provinces × 52 weeks fits Supabase free tier; API key model scales to 100+ DA offices |
| Technical Risk | 8/10 | Primary risk: PAGASA station mapping accuracy; mitigated by dbt validation tests |
| AI Leverage | 6/10 | SDK upgrade + expanding Haiku advisory to 82 provinces; no new AI applications in Phase 2 |

**Estimated Phase 2 timeline:** 6–8 weeks post Phase 1 deployment

**Final Recommendation: BUILD NOW** (Phase 2 begins immediately after Phase 1 deployment, which itself requires Biboy's action on the June 27 DEPLOY NOW checklist)

The architectural decisions above are not speculative — they are the predictable next questions once the system is live: How do we expand province coverage? How does DA integrate? How do we secure the webhook before it's institutionally exposed? Answering these now means Phase 2 starts with zero architectural ambiguity. The TASAT grant's $8M climate-smart component represents the most clearly-aligned funding pathway in Philippine agriculture; this Phase 2 blueprint produces the technical foundation a competitive TASAT proposal requires.

Phase 1 is not done. Every day Phase 1 is not deployed is a day Phase 2 can't start — and a day the agricultural window narrows.

*"If Biboy Labs builds only one product this month, this is how I would build it."* — it is already built. Phase 1 deployment unlocks Phase 2, and Phase 2 is what converts a working pilot into an institutionally-adopted, grant-funded national advisory system.

---
*Enhancement run by: Weekly Architecture Blueprint task (automated) | 2026-07-05 | AWAITING BIBOY'S APPROVAL*

---

> ## ⚠️ SUPERSEDED — Enhancement Run: 2026-06-27
> The June 21 blueprint was written pre-build. As of June 23, 2026, the product is **fully built and pilot-ready** (`v1.0.0-pilot`, 83 unit tests passing, CI-gated, audit complete). The pre-build spec below is retained for reference. The authoritative guidance for this product is the **Enhancement Run sections at the top of this file**.

---

## Enhancement Run — 2026-06-27
**Source:** Portfolio Review June 27, 2026 — Rank #1 ACCELERATE (score 18.67)
**Run type:** Re-blueprint triggered by material scope change (pre-build spec → post-build deployment)
**Architect:** Biboy Labs Chief Technology & AI Architect

### What changed since June 21

The product was built. In the 6 days between the June 21 blueprint and now, the El Niño Early Warning System went from a spec to a working, tested, pilot-ready system:

- **15 commits** to a live codebase
- **83 unit tests passing** (+3 skipped DB smoke tests), CI-gated on every push
- **All P0–P3 defects resolved** (ELN-001 through ELN-023; 3 roadmap items open: ELN-018 SDK bump, ELN-020 coverage expansion, ELN-024 dev-only lint)
- **Audit verdict (June 23):** "Code: ready. Every known defect is fixed."
- **Deployed architecture confirmed:** Railway (Airflow pipeline) + Supabase (PostgreSQL + RLS) + Vercel (Next.js dashboard) + Semaphore.ph (SMS delivery) — exactly as the June 21 blueprint specified
- **v1.0.0-pilot scope:** 15 Luzon provinces, palay + corn risk scoring, Claude Haiku weekly advisories, SMS to cooperative contacts, opt-out compliance, advisory feedback loop

The constraint is no longer architecture — it is **4 precise deployment steps** that require Supabase dashboard access, Railway env var configuration, and Vercel project setup.

---

### Enhancement Step 2 — What's Left (Production Deployment as the New MVP)

The June 21 MVP is done. The next milestone is a **production deployment** — taking the pilot-ready codebase live so the weekly pipeline runs automatically, the dashboard serves real data, and cooperative contacts receive their first SMS advisories.

**MUST HAVE for production launch:**

| Action | Where | Detail |
|--------|--------|--------|
| Apply migrations 001–003 in order | Supabase SQL editor | `001_initial_schema.sql` → `002_dashboard_anon_read.sql` (**critical**: without this the anon dashboard shows empty — RLS blocks anon reads) → `003_sms_opt_outs.sql` |
| Apply migrations 004–005 | Supabase SQL editor | `004_advisory_feedback.sql` → `005_feedback_summary_view.sql` (completes the feedback loop for ELN-021) |
| Seed data | Supabase / dbt seed | `pipeline/seeds/provinces.csv` + `pipeline/seeds/crop_calendars.csv` (15 pilot provinces, planting calendars) |
| Set Railway env vars | Railway dashboard | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_HOST`, `SUPABASE_DB_USER`, `SUPABASE_DB_PASSWORD`, `ANTHROPIC_API_KEY`, `SEMAPHORE_API_KEY`; optional: `OPS_ALERT_WEBHOOK_URL` (Slack/Discord for failure alerts — set this), `PAGASA_FAIL_ON_STALE`, `TEST_PHONE_NUMBER` |
| Set Vercel env vars | Vercel dashboard | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| Deploy inbound webhook | Railway (second service) | `python pipeline/webhook/inbound.py` (Flask); configure Semaphore inbound webhook URL → `POST https://<railway-url>/sms/inbound`; env: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` |
| Trigger first pipeline run | Railway / Airflow | Trigger `elnino_weekly` DAG manually; verify advisory generation, SMS send to test number, dashboard data updates |

**SHOULD HAVE before first institutional demo (same session or next day):**
- Set `OPS_ALERT_WEBHOOK_URL` to a Slack/Discord channel so pipeline failures alert in real time
- Confirm dashboard is accessible at the Vercel URL (share with first LGU contact)
- Send test SMS to Biboy's own number (`send_sms.py --test`) before activating cooperative contacts

**LATER (Phase 2):**
- DA/CDA MIMAROPA outreach (relational, not technical)
- Visayas/Mindanao province expansion (ELN-020)
- Crop expansion (vegetables, cassava)
- Localization (Ilocano, Cebuano)
- Anthropic SDK bump to current (ELN-018 — low risk, S effort, do it in Phase 2)
- DA API endpoint (requires formal partnership; Phase 3 from original blueprint)

**NOT NEEDED (do not touch):**
- ELN-024 (dev-only eslint upgrade) — does not ship to users; defer indefinitely

---

### Enhancement Step 3 — Confirmed Production Architecture

The June 21 blueprint's architecture was correct and is exactly what was built. This section records what's confirmed live vs. what still needs wiring at deploy time.

| Component | Blueprint Spec | Actual State |
|-----------|---------------|-------------|
| Pipeline | Python + dbt + Airflow on Railway | ✅ Built — `pipeline/dags/elnino_weekly.py`, dbt models in `pipeline/models/` |
| Database | Supabase PostgreSQL + PostGIS | ✅ Schema designed; 5 migration files ready; **not yet applied to production** |
| Frontend | Next.js static + Recharts + Vercel | ✅ Built — dashboard in `dashboard/`, CI-gated, `next build` green |
| Auth | Supabase Auth (invite-only pilot) | ✅ Architecture in place; anon-read RLS corrected (ELN-019, migration 002) |
| AI | Claude Haiku advisory generation | ✅ Built — `pipeline/scripts/digest_generator.py`, structured advisory parse, retry with backoff |
| SMS | Semaphore.ph | ✅ Built — `pipeline/sms/send_sms.py`, E.164 normalization, opt-out suppression, encoding-aware fitting |
| Inbound webhook | Flask service on Railway | ✅ Built — `pipeline/webhook/inbound.py`; **not yet deployed as Railway service** |
| Monitoring | Airflow failure callbacks + optional OPS_ALERT_WEBHOOK_URL | ✅ Built; **OPS_ALERT_WEBHOOK_URL needs to be set at deploy time** |

**One architectural addition vs. June 21 blueprint:** The inbound webhook is a **4th Railway service** (in addition to Airflow scheduler, Airflow webserver, Redis). This is a small always-on Flask process; Railway's free/starter tier handles it without additional cost. It's the collection channel for both SMS opt-outs (compliance) and advisory feedback (ELN-021). Deploy it at the same time as the pipeline — these are not separable if opt-out compliance is required from day 1 (it is).

---

### Enhancement Step 4 — AI Status

| Application | Status | Notes |
|---|---|---|
| Claude Haiku weekly advisory generation | ✅ BUILT AND WORKING | 3-sentence English + Tagalog advisory per province, stored in `weekly_digests`, served via dashboard + SMS; structured output parsing with multi-line support (ELN-007 fix) |
| Anthropic SDK upgrade (0.34.2 → current) | PHASE 2 | ELN-018; S effort; not a production blocker; do it when starting Phase 2 expansion work |
| Risk score ML calibration (vs. historical yield) | PHASE 2 | Rule-based scoring is correct for MVP; 2–3 seasons of data needed before ML adds value |
| Farmer-facing dialect chatbot | PHASE 3 | Unchanged from June 21 blueprint |

---

### Enhancement Step 5 — Data Status

All 5 schema objects are ready; none are applied to production yet.

**Migration sequencing (apply in this order — order matters):**
1. `001_initial_schema.sql` — core tables (provinces, pagasa_forecasts, crop_calendars, risk_scores, weekly_digests, cooperative_contacts, sms_log, pipeline_runs)
2. `002_dashboard_anon_read.sql` — anon SELECT grants on public-safe tables; **CRITICAL to apply before any dashboard access**
3. `003_sms_opt_outs.sql` — sms_opt_outs table for STOP reply suppression
4. `004_advisory_feedback.sql` — advisory_feedback table for farmer reply classification
5. `005_feedback_summary_view.sql` — feedback_summary view + dashboard access grant

**North Star Metric (unchanged):** LGU agricultural advisory decisions informed by the dashboard per season. Proxy at MVP: dashboard weekly active users during El Niño season.

**Success metrics (updated for live system):**
1. Weekly pipeline reliability — % of scheduled runs completing without failure (target: 100%; alert on any failure)
2. Dashboard WAU — pilot LGU officers actively viewing advisories
3. SMS delivery rate — Semaphore confirmed-delivered / attempted (target: > 95%)
4. Advisory feedback rate — replies classified as `acted` or `need_help` (any non-zero is a signal in pilot)
5. Time-to-dashboard from PAGASA forecast publication (target: < 24 hours)

---

### Enhancement Step 6 — Security Status

| Risk | Status | Notes |
|---|---|---|
| Anon dashboard read RLS | ✅ Fixed | ELN-019 / migration 002 — anon SELECT on public-safe tables only; PII tables (cooperative_contacts, sms_log) remain service-role-only |
| SMS opt-out compliance | ✅ Implemented | ELN-010 / migration 003 — STOP/TIGIL replies write to sms_opt_outs; send_sms suppresses opted-out numbers |
| Advisory accuracy disclaimer | ✅ In code | Rendered on every dashboard page and in every SMS footer |
| Pipeline failure alerting | ✅ Implemented | ELN-002 — DAG failure callback; set OPS_ALERT_WEBHOOK_URL at deploy time to activate Slack/Discord alerting |
| Inbound webhook auth (Semaphore signature) | ⚠️ OPEN | `inbound.py` doesn't validate the Semaphore inbound signature. Anyone who knows the URL can POST fake opt-outs or feedback. Mitigation: webhook URL is not public; but add `X-Semaphore-Secret` header validation in Phase 2 |
| Government data residency (if DA formalizes) | ⚠️ Phase 2 risk | Supabase + Railway are not PH-domiciled; if DA contract requires PH data residency, migration to AWS Manila (ap-southeast-1) required. Flag this in any DA partnership conversation before signing |
| Next.js security bump | ✅ Resolved | ELN-023 — next 14.2.5 → 14.2.35 |

**Elevated risk requiring Phase 2 action:** Inbound webhook signature validation (for production at scale). Low risk at pilot stage (URL is unpublished) but must be added before any public launch.

---

### Enhancement Step 7 — Revised Roadmap

**Phase 1 — Production Deployment (this week, 1 session)**

Objectives: Get the weekly pipeline running live; first SMS advisories to cooperative contacts; dashboard accessible to pilot LGU officers.

Deliverables: Apply 5 Supabase migrations + seed data → set Railway env vars → deploy pipeline + inbound webhook → set Vercel env vars → deploy dashboard → trigger first manual pipeline run → confirm advisory generation + SMS delivery + dashboard data.

Acceptance criteria:
- `elnino_weekly` DAG completes without error on first manual trigger
- Dashboard at Vercel URL shows risk scores for all 15 pilot provinces
- SMS sent to test number successfully (confirmed delivery in Semaphore dashboard)
- OPS_ALERT_WEBHOOK_URL configured and tested (send a test failure notification)

**Phase 2 — Expansion + DA Outreach (Months 1–3)**

Objectives: Expand to Visayas/Mindanao provinces; initiate one formal DA/CDA MIMAROPA relationship; apply for TASAT grant climate-smart component; upgrade Anthropic SDK; add webhook signature validation.

Key deliverables: 10+ additional provinces seeded (ELN-020), TASAT proposal submitted (data pipeline as climate-smart advisory infrastructure), first formal LGU officer user confirmed, inbound webhook auth hardened.

**Phase 3 — Government Partnership + Revenue (Months 4–9)**

Objectives: Formal DA Regional Field Office partnership; SaaS subscription model; crop expansion; possibly farmer-facing WhatsApp digest.

Key deliverables: DA integration API endpoint (authenticated, rate-limited FastAPI layer), government SaaS contract (₱50–100K/year/province), multi-crop coverage, FAO/UNDP/ADB grant application package.

**Phase 4 — Platform (Month 10+):** Multi-hazard (typhoon + flood), multi-country (Vietnam, Indonesia, Bangladesh), multi-agency data feeds.

---

### Enhancement Step 8 — Deployment Handoff

**This is the single-source-of-truth for what Biboy does at his machine to go live.**

#### Step 1 — Supabase (15–20 minutes)
1. Open Supabase project dashboard → SQL Editor
2. Execute in order: `001_initial_schema.sql`, `002_dashboard_anon_read.sql`, `003_sms_opt_outs.sql`, `004_advisory_feedback.sql`, `005_feedback_summary_view.sql` (all in `supabase/migrations/`)
3. Seed data: either `dbt seed` from the pipeline environment (after Step 2 env vars are set), or manually import `pipeline/seeds/provinces.csv` and `pipeline/seeds/crop_calendars.csv` via Supabase Table Editor
4. Confirm: run `SELECT COUNT(*) FROM provinces;` → should return 15; `SELECT COUNT(*) FROM crop_calendars;` → should return > 0

#### Step 2 — Railway Pipeline (10–15 minutes)
Set these env vars in the Railway pipeline service:
```
SUPABASE_URL=<from Supabase project settings>
SUPABASE_SERVICE_KEY=<service_role key from Supabase settings>
SUPABASE_DB_HOST=<DB host from Supabase settings>
SUPABASE_DB_USER=postgres
SUPABASE_DB_PASSWORD=<DB password from Supabase settings>
ANTHROPIC_API_KEY=<from Anthropic console>
SEMAPHORE_API_KEY=<from Semaphore.ph account>
OPS_ALERT_WEBHOOK_URL=<Slack/Discord incoming webhook URL — create one>
PAGASA_FAIL_ON_STALE=true
TEST_PHONE_NUMBER=<Biboy's number in E.164 format, e.g. +639XXXXXXXXX>
```
Deploy the Railway service (connect GitHub repo; Railway auto-detects Airflow from `requirements.txt`).

#### Step 3 — Railway Inbound Webhook (5 minutes)
Create a **second Railway service** in the same project:
- Start command: `python pipeline/webhook/inbound.py`
- Env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (same values as above)
- Once deployed, copy the Railway-assigned URL
- In Semaphore.ph account settings → Inbound Webhook URL: `POST https://<railway-inbound-url>/sms/inbound`

#### Step 4 — Vercel Dashboard (5 minutes)
1. Connect `El-Nino-Early-Warning/dashboard/` to a Vercel project
2. Set env vars: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (anon key from Supabase settings)
3. Deploy; confirm dashboard loads and shows province risk scores

#### Step 5 — First Run + Verification (10–15 minutes)
1. In Airflow (Railway URL): trigger `elnino_weekly` DAG manually
2. Watch logs: pagasa_scrape → dbt_run → digest_generate → sms_send → vercel_webhook
3. Run `send_sms.py --test` to send a test SMS to `TEST_PHONE_NUMBER`; confirm delivery in Semaphore dashboard
4. Open Vercel dashboard URL; confirm province risk scores appear; check advisory text renders correctly
5. Verify OPS_ALERT_WEBHOOK_URL fires: temporarily kill the Airflow DAG mid-run or check the failure callback path

**Total estimated time to production:** 45–60 minutes in a single focused session.

---

### Enhancement Step 9 — Executive Recommendation

| Dimension | Score | Notes |
|---|---|---|
| Architecture Confidence | 10/10 | Product is built, audited, all P0s closed; 83 tests; CI-gated |
| Deployment Complexity | 10/10 | 5 SQL scripts + env vars + 2 Railway services + Vercel; estimated 45–60 min |
| Scalability | 8/10 | Railway/Supabase/Vercel scales cleanly to Phase 2 scope; government data residency is the next scaling concern if DA formalizes |
| Technical Risk | 9/10 | All known defects resolved; inbound webhook auth is the only open security item (low-risk at pilot scale) |
| AI Leverage | 6/10 | One focused, working AI application; appropriately scoped |

**Estimated time to production:** 45–60 minutes (single session).

**Final Recommendation: DEPLOY NOW**

The code is done. The architecture is sound. The deployment is a documented checklist, not an engineering decision. The El Niño agricultural damage window (July–October) is open now and closes. A system deployed this week informs planting advisories for the current wet season. A system deployed in September does not. There are no architectural unknowns remaining — only operational steps that can be completed in one focused hour.

After deployment: the pipeline runs automatically every Monday at 06:00 PHT. The only required action after the first week is outreach — one CDA MIMAROPA or DA Regional Field Office conversation to get an institutional user on the dashboard. That conversation is more valuable with a live, working URL to share than with a screenshot of a working demo.

*"If Biboy Labs builds only one product this month, this is how I would build it."* — note: it is already built. The question is whether to deploy it this week or let the agricultural damage window close while the code sits in a repository.

---
*Enhancement run by: Weekly Architecture Blueprint task (automated) | 2026-06-27 | AWAITING BIBOY'S APPROVAL*

---

## ━━━ ORIGINAL BLUEPRINT (2026-06-21) — RETAINED FOR REFERENCE ━━━

*The following is the pre-build blueprint produced June 21, 2026, before any code existed. It is preserved for architectural decision tracing. The Enhancement Run above supersedes it for operational guidance.*

---

# El Niño Agricultural Early Warning Data Layer — Architecture Blueprint
**Blueprint Date:** 2026-06-21 | **Source:** Philippine Agriculture Opportunity Radar (June 21, 2026) — Rank #1 BUILD NOW
**Architect:** Biboy Labs Chief Technology & AI Architect
**Status:** SUPERSEDED — see Enhancement Run (June 27, 2026) above

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
