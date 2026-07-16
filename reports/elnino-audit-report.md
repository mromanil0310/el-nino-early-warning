# El Niño Early Warning — Audit & Backlog Report

_Last updated: 2026-07-16. Source of truth for bugs, fixes, and the prioritized backlog. Newest dated section is authoritative; older sections retained for history._

## 🌏 Dashboard mass-appeal pass — 2026-07-16

The dashboard was officer-facing and English-only in its chrome (only the advisories were bilingual), desktop-shaped, and offered no way to spread an advisory. This pass broadens it toward the farmers and barangay officials it ultimately serves. **All changes verified in-browser against the built static export and confirmed live on Vercel via content-hash match.**

**Defects fixed:**
- **`TrendIcon` was invisible to screen-reader / colorblind users** — the ↑↓→ arrows carried meaning only through glyph + color + an unreliable `<span title>`. Added `role="img"` + `aria-label` (glyph now `aria-hidden`).
- **Map tap did nothing on mobile** — tapping a province dot filtered the card list, but the list sits far below the map on a phone, so it looked like a no-op. Now scrolls the filtered result into view. (Subtle bug found en route: `behavior:'smooth'` is a silent no-op under reduced-motion / the render env; the scroll now runs from a post-commit effect with instant behavior so it lands reliably.)

**Mass-appeal features (ELN-020 partial — Filipino localization + reach):**
- **Share advisory** — each expanded advisory has a "Share this advisory" action: native share sheet on mobile → clipboard fallback on desktop, includes a link back so recipients can look up their own province. Turns each dashboard viewer into a distribution point for barangay group chats / SMS.
- **Full Filipino UI** (`dashboard/lib/i18n.tsx`) — a shared language context + EN/FIL header toggle now drives the **entire** interface and the advisory text, not just the advisory column. Persists to localStorage, sets `<html lang>`, migrates the legacy per-card `advisoryLang` key, starts from `en` to avoid hydration mismatch. Technical data values (PAGASA outlook labels, crop stages, region codes, `wet`/`dry` season) are deliberately left untranslated. The redundant per-card language toggle was removed — one global switch controls everything.
- **Mobile map redesign** — the tall dot-map is collapsed behind a "Show risk map" toggle on phones so the summary + actionable cards surface first; on desktop (`sm+`) the map always shows, unchanged.
- **Find my province** — geolocation button that jumps to the nearest monitored province, with localized graceful fallbacks (denied / unavailable / none-nearby).

Commits: `5950704` (share + a11y + mobile-tap), `db3a294` (Filipino UI + mobile map + locate-me). Dashboard `tsc` + `next build` + `next lint` green; 114 pipeline tests still passing (dashboard-only change).

**Not touched (deliberate):** every province still scores identically (`38 · Medium`) because the station→province rainfall weighting isn't wired into the risk model yet — that's the scoped-but-not-started PAGASA station-level bulletin rework, a real architecture change, not a quick fix.

## 🚀 Deployment progress — 2026-07-11

**Supabase project is now LIVE** (project ref `niqphdpmcuiaosamcvmf`, free tier, Southeast Asia region) — the first of the four remaining deployment steps from the Phase 1 checklist.

- All 6 migrations applied and verified (001–006).
- Reference tables seeded and row counts confirmed via REST API: `provinces` (82), `crop_calendars` (32), `pagasa_stations` (57), `province_station_mapping` (108).
- `dashboard/.env.local` updated with the real project URL + anon key (local dev only — not committed, per `.gitignore`).
- Verified end-to-end: dashboard correctly showed a schema-cache error before migrations, then the correct "no data yet" empty state after seeding — confirming both the live connection and the ELN-027 fail-loud error handling work against a real backend, not just stubbed data.

**Still empty (expected, not a bug):** `risk_scores`, `pagasa_forecasts`, `weekly_digests` — these are pipeline outputs, populated only once the pipeline actually runs (scraper → dbt → digest generator), not by manual seeding.

**Correction: Railway is not needed.** `.github/workflows/pipeline.yml` is already a complete, self-contained weekly pipeline runner (scrape → dbt run/test → AI advisories → SMS → Vercel rebuild hook), scheduled every Monday 06:00 PHT and manually triggerable via `workflow_dispatch` (with a `dry_run` input that skips SMS). The 7 required secrets already existed in the repo (set 2026-06-27) but held placeholder values — that's why every scheduled run had been failing with DNS errors. No separate Railway deployment is required; updating these secrets is enough.

**ELN-028 — pipeline deployment fixes (2026-07-11):**
- All Supabase secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_DB_HOST`, `SUPABASE_DB_USER`, `SUPABASE_DB_PASSWORD`) and `ANTHROPIC_API_KEY` updated to real values; `SEMAPHORE_API_KEY` intentionally left as a placeholder for now (SMS not needed to verify core risk-scoring; `dry_run=true` skips that step).
- **Fixed:** `pipeline/requirements-pipeline.txt` still pinned `anthropic==0.34.2` — the ELN-018 SDK bump only touched `pipeline/requirements.txt`, missing the leaner file GitHub Actions actually installs from. Now `0.116.0` in both.
- **Fixed:** `SUPABASE_DB_HOST` was initially set to the Direct Connection host, which resolved to an IPv6-only address — GitHub Actions runners can't reach IPv6, causing `Network is unreachable`. Corrected to the Session Pooler host (`aws-1-ap-northeast-2.pooler.supabase.com`, IPv4-proxied) and matching pooler-format user (`postgres.<project-ref>`).
- **Fixed (real bug, not a config typo):** `dbt_project.yml` had `+schema: public` set explicitly on both the `seeds` and `marts` blocks. dbt's default `generate_schema_name` macro *concatenates* a configured schema onto the profile's target schema rather than replacing it — since the profile's target schema is also `public`, this produced `public_public`, a schema that doesn't exist. All seed and mart tables live in plain `public` (created by the migrations, populated via manual CSV import), so every `ref()` to them failed with `relation does not exist`. Removed the redundant overrides; `staging: +schema: staging` was left alone (internal-only, not queried externally).
- **Confirmed working end-to-end after the schema fix:** `dbt run` + `dbt test` went green on the first real run against live PAGASA data — `risk_scores` populated with 21 real rows.
- **Fixed (pre-existing bug, surfaced by the first-ever real run):** `risk_scores` was materialized by dbt as a `table`, which drops and recreates it every run — this does not carry over the hand-written FK to `provinces` from migration 001. Without it, PostgREST can't resolve the embedded `provinces(...)` join that both the dashboard and `digest_generator.py` rely on (`PGRST200`). Added the FK back via a dbt `post_hook` on `risk_scores.sql` (safe to re-run every build, since the table is fresh every time).
- **Fixed (separate pre-existing bug, also surfaced by the first real run):** `digest_generator.py` additionally requested an embedded `pagasa_forecasts(seasonal_outlook, rainfall_anomaly_pct)` join — but `risk_scores` was *never* linked to `pagasa_forecasts` by any FK, even in the original migration, and didn't need to be: both columns are already copied onto every `risk_scores` row directly by the dbt model's own forecast join. Removed the redundant embed; the script now reads `row["seasonal_outlook"]` / `row["rainfall_anomaly_pct"]` directly. This bug pre-dates this session and would have failed the first time the script ever ran against real seeded data — which is what just happened.
- **First fully green pipeline run:** scrape → dbt run/test → AI advisories → dashboard rebuild hook, all passed (`dry_run=true` skipped SMS). Confirmed live in the dashboard against the actual deployed backend: real risk scores, real map, real filters, real AI-generated Filipino/English advisory text, real SMS-format text — all rendering correctly.
- **Found and fixed a real accuracy bug (ELN-029), not cosmetic:** `weekly_digests` had no `crop` column — only `UNIQUE (province_id, week_of)`. Since `risk_scores` computes one row per province **×** crop, any province growing more than one crop in the same week (e.g. Pangasinan: corn + palay) caused `digest_generator.py`'s per-row upsert to silently overwrite the same row — whichever crop was processed last in the loop is the only one that survived, and every other crop's dashboard card for that province showed the wrong crop's advisory. Caught by manually expanding a corn card and noticing the advisory text was about palay irrigation. Fixed with migration `007_weekly_digests_crop.sql` (adds `crop`, re-keys the unique constraint to `(province_id, crop, week_of)`, clears the 15 pre-fix rows since they can't be reliably re-attributed to a crop after being overwritten) plus matching changes to `digest_generator.py` (`write_digest` now takes/stores `crop`) and the dashboard (`getDigestForProvince` now filters by crop too). Migration 007 applied; verified with a second pipeline run — `weekly_digests` now has 21 rows (matching `risk_scores`), and Pangasinan's corn/palay cards show genuinely distinct advisories.

**Dashboard deployed to Vercel** (`el-nino-early-warning.vercel.app`, project already existed under Biboy Labs, built from commit `7f01db8`). Found the same class of bug as the GitHub Actions secrets: `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` in Vercel's env vars were dated **Jun 27** — two weeks before this Supabase project existed, i.e. stale/placeholder values from whenever the Vercel project was first scaffolded. Because this is a static export (`output: 'export'` in `next.config.js`), Next.js bakes `NEXT_PUBLIC_` vars into the JS bundle at **build time**, not runtime — so the live site was silently serving a build pointed at a different (probably empty) Supabase project, no error, just the "no data yet" empty state masking the real cause. Updated both vars to the real project's values and triggered a fresh **Redeploy** (not "Instant Rollback," which would have reused the stale build). Verified live and correct afterward: 21 real crop assessments, correct risk breakdown, and the ELN-029 per-crop advisory fix confirmed working in production too (Pangasinan corn/palay show distinct advisories).

**Semaphore.ph account set up.** `SEMAPHORE_API_KEY` GitHub secret updated to the real key. Account still at 0 credits (real SMS sending needs a top-up first) and `cooperative_contacts` is empty (0 rows — no PII seeded, by design), so a real `dry_run=false` run right now would send zero actual messages either way. Neither is blocking; both can happen later.

**ELN-030 — inbound webhook Railway deployment (in progress).** The webhook (`pipeline/webhook/inbound.py`) needs an always-on host, unlike the pipeline (GitHub Actions, ELN-028 correction) or dashboard (Vercel static export) — Railway is the right fit for this piece specifically. Hit a real, repeated deployment bug: `inbound.py` originally imported its pure-logic dependencies (`feedback.classify_inbound`, `delivery.normalize_ph_phone`) from sibling directories (`pipeline/scripts/`, `pipeline/sms/`) via `sys.path` manipulation. Railway's "Root Directory" setting for a monorepo subdirectory deploy only copies *that* subdirectory into the build container — sibling folders are never present, so every attempt (Root=`pipeline/webhook` with sibling imports, Root=`pipeline` with a `webhook/` command prefix, split across Build vs. Deploy phases) hit variations of `ModuleNotFoundError` or `No such file or directory` for the sibling-dependent files. Root cause confirmed by testing the *same* fix in both the Build phase and the Deploy phase and getting the identical failure both times — ruled out "which phase" as the variable.

**Fix:** vendored the two needed pieces of pure logic directly into `pipeline/webhook/` as local files — `feedback.py` (full copy of the classifier) and `phone.py` (just `normalize_ph_phone`, extracted from the larger `delivery.py`) — removing the sys.path cross-directory dependency entirely. `inbound.py` now imports both as plain local modules. Added `pipeline/tests/test_webhook_vendored_sync.py` — loads both the original and vendored copies by explicit file path (they share filenames, so a normal import-by-name would just resolve to whichever loads first) and asserts identical behavior across representative cases, so future edits to one side without the other fail CI instead of silently drifting. 114 tests passing (110 + 4 new).

**Also discovered: Railway was replaying a stale cached `railpack-plan.json` build plan**, independent of the current dashboard settings and even the deployed commit — confirmed when a rebuild against the *new* `ELN-030` commit still showed the old (already-cleared) custom Build Command in its build plan. No cache-clear option existed in the dashboard (deployment "..." menu only offered View logs / Redeploy / Remove). **Fix:** deleted the stuck service entirely and created a fresh one from the same GitHub repo — guaranteed clean slate, no inherited cache.

**ELN-030 webhook is now LIVE**, deployed at `el-nino-early-warning-production-742b.up.railway.app`, Root Directory `pipeline/webhook`, no custom Build/Start command overrides (Railway's auto-detected `Procfile` + `requirements.txt` works correctly now that the directory is fully self-contained). Verified with real HTTP requests against the live service, not just a status page:
- `GET /health` → `{"ok":true}`, 200 — confirms the service booted successfully (a missing `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` would crash it at import time).
- `POST /sms/inbound` with no signature → `403 Forbidden` — HMAC validation actively rejects unsigned requests.
- `POST /sms/inbound` with a valid HMAC signature (STOP reply) → `200 {"kind":"opt_out","code":null,"ok":true}` — signature check passed, reply correctly classified, and the Supabase write succeeded (the code only returns this payload shape after a successful write; a failed write returns `ok:false` instead).

Note: that last test used a synthetic phone number (`+639171234567`), which is now sitting in `sms_opt_outs` marked opted-out. Harmless unless that exact number is ever assigned to a real cooperative contact — can be deleted from Supabase's Table Editor whenever convenient (not reachable with the anon key, by design — that table is service-role-only).

**Remaining before public launch:** confirm the Railway webhook deploys cleanly with the vendored fix + simplified settings, point Semaphore's inbound webhook URL at it with the `SEMAPHORE_WEBHOOK_SECRET` from ELN-025, buy Semaphore credits and add real cooperative contacts when ready for actual SMS delivery, then let the pipeline run for real (`dry_run=false`) or on its Monday 6am schedule.

> ## ✅ Pilot complete (`v1.0.0-pilot`) — Phase 2 started 2026-07-08
> Every defect and cleanly-completable feature is closed and CI-verified — pipeline,
> dashboard, security/RLS, compliance (opt-out + feedback loop), tests, docs.
> **Remaining = roadmap only:** ELN-020 (geographic/crop/language expansion),
> ELN-024 (dev-only eslint v16), Phase 2 Builds 3–5 (province-station model,
> FastAPI DA endpoint, monthly PDF report — see the Phase 2 blueprint).
> See the deployment checklist below to go live.

---

## 🏁 Sprint — 2026-07-08 (Phase 2 Builds 1–2)

Per the 2026-07-05 Phase 2 architecture blueprint (Builder Handoff):

| ID | Item | Status | Verification |
|----|------|--------|-------------|
| **ELN-025** | Inbound webhook HMAC signature validation (Phase 2 Build 1) — new pure `pipeline/webhook/signature.py` (`verify_semaphore_signature`, timing-safe `hmac.compare_digest`) wired into `inbound.py`; 403 on missing/invalid signature when `SEMAPHORE_WEBHOOK_SECRET` is set, loud warning + skip when unset (dev). Deploy step: set `SEMAPHORE_WEBHOOK_SECRET` in the Railway webhook service **and** Semaphore account → Inbound Webhook → Signature Secret. | ✅ | 9 new unit tests (`test_webhook_signature.py`); `py_compile` clean. |
| **ELN-018** | Anthropic SDK bump 0.34.2 → **0.116.0** (Phase 2 Build 2) | ✅ (review) | Call site uses stable `messages.create` + `APIConnectionError`/`RateLimitError`/`InternalServerError` — all unchanged in current SDK. SDK not installed locally, so reviewed + compiled, not executed; verify with one live `digest_generator.py` run on deploy. |
| **ELN-026** | Phase 2 Build 3 data groundwork — province-station model + national province seed | ✅ (partial — see remaining) | (a) `provinces.csv` expanded 15 → **82 provinces** (pilot rows 1–15 byte-identical; PSGC names, approx. centroids). (b) New `pagasa_stations.csv` — **57 operational synoptic stations**, compiled 2026-07-08 from DOST-PAGASA Synoptic Station Profile 2024 (Southern Luzon + Mindanao PRSD) and the PRSD station directory. (c) New `province_station_mapping.csv` — 108 weighted mappings, full coverage, weights sum to 1.0/province (validated offline). (d) Migration `006_province_station_mapping.sql` (integer FKs to match live schema — blueprint sketch used UUIDs; anon-read RLS per 002 pattern). (e) dbt seed tests + singular tests `assert_station_weights_sum_to_one` / `assert_all_provinces_mapped` / `assert_province_count` (82). (f) **Scraper correctness fix:** `PROVINCE_ID_MAP` now generated from the seed CSV (no drift) via new pure `provinces_map.py`, with containment-aware matching — "South Cotabato" / "Quezon City" / "Northern Samar" text can no longer mis-populate Cotabato / Quezon / Samar; PAGASA aliases (Western Samar, North Cotabato, Compostela Valley, Mt. Province) resolve. 10 new unit tests. |

**Test status:** **110 unit tests passing (+3 skipped DB smoke).**

### Dashboard product pass — 2026-07-11 (ELN-027)

Full product/UX/a11y/engineering audit + improvement pass on the Next.js dashboard (improve, not rewrite). Verified live in-browser (error path against the unconfigured backend; happy path with stubbed REST responses; mobile 375px).

| Area | What shipped |
|------|--------------|
| **Reliability (critical fix)** | Query errors were swallowed into `[]`, so an outage rendered as "No risk scores available yet" — a silent failure on a warning tool. Queries now throw; the page shows the cause + a Try again button. Also fixed: white-screen crash on missing env vars (visible config message instead), null crash on `rainfall_anomaly_pct.toFixed()`. |
| **UX** | Skeleton loaders; distinct empty/error/no-match states with recovery actions; human dates (`<time>`); map dots + ranked rows are clickable/focusable and filter the card list; **CSV export** of filtered rows (bridge until the Phase 2 API); EN/TL advisory choice persists via localStorage; search clear button; dynamic "N provinces monitored" (82-ready, no hardcoded "15"). |
| **Accessibility** | `<html lang>` via new `_document`; aria-pressed/expanded/controls/live/alert/status; focus-visible rings; `lang="fil"` on Filipino text; contrast fixes (gray-400 → 500+). |
| **Engineering** | `.eslintrc.json` (lint now configured + clean); `vercel.json` security headers (static export can't use next.config headers); SVG favicon (was 404); `lib/format.ts` (date/CSV utils); typed feedback rows, no `any`; preconnect to Supabase; removed empty `pages/api/` scaffold. Gates: tsc + ESLint + `next build` green (148 kB first load). |
| **Environment fix** | `dashboard/node_modules` had 1,015 file-sync-corrupted duplicate entries (`react 4`, `node 4`, …) that silently broke React hydration on `/` (no console errors). Clean `npm ci` fixed it. Same corruption pattern as `out/404 2.html` — watch for it elsewhere in synced folders. |

**Known gap:** `dashboard/.env.local` points at a placeholder Supabase URL — the dashboard has never run against real data locally. Set real values when deploying Phase 1.

**Build 3 remaining (deliberately NOT fabricated):** `crop_calendars.csv` still covers the 15 pilot provinces. Planting windows for the 67 new provinces must come from PSA Open Stat / DA regional calendars — wrong windows would produce wrong farmer advisories, so this needs source data, not invention. Until then the pipeline safely scores only calendared provinces (staging inner-join excludes the rest), and the "all 82 provinces have risk scores per run" dbt test is deferred with it. The weighted station→province dbt join (risk model) also lands with that work.

> A weekly El Niño agricultural risk system for 15 Luzon provinces (PAGASA → risk score → Claude advisory → SMS). Because it warns farmers, **correctness and delivery reliability are the top priorities** — a silent failure or an under-stated risk has real-world cost.

---

## 🏁 Sprint — 2026-06-23 (reliability hardening)

**Goal:** put the project on a safe operational footing — version control, CI, fail-loud ops, and the highest-impact correctness fixes.

**Test status:** **83 unit tests passing (+3 skipped DB smoke)** (pure logic). Pipeline modules also `py_compile` clean.

**Verification caveat (reported honestly):** `pdfplumber`, `supabase`, `anthropic`, and the Airflow runtime are **not installed in this dev environment**, so changes inside the DAG and the Supabase/Claude/PDF call sites are **reviewed + compiled, not executed locally**. All *pure* logic (scoring, SMS encoding, retry, outlook) is fully unit-tested. dbt schema tests and the dashboard build run in CI / against the live DB.

### Shipped this sprint

| ID | Item | Status | Verification |
|----|------|--------|-------------|
| **ELN-001** | Version control + CI | ✅ | `git init` + `.gitignore` + `.github/workflows/ci.yml` (pytest + dbt-YAML lint gating; dashboard build non-blocking). |
| **ELN-002** | Pipeline-failure alerting | ✅ (review) | DAG `on_failure_callback` logs loudly + posts to `OPS_ALERT_WEBHOOK_URL` when set. Fires after retries are exhausted. |
| **ELN-003** | `pipeline_runs` real status + schema fix | ✅ (review) | `task_log_pipeline_run` now derives `success`/`partial`/`failed` from upstream task states. Also fixed a **schema-mismatch** that would have failed the insert outright (it referenced non-existent `digests_generated`/`sms_sent` columns and omitted the `NOT NULL` `dag_id`). |
| **ELN-004** | PAGASA scraper freshness guard | ✅ (review) | On PDF-parse fallback, distinguishes operator override vs the built-in baseline; logs `STALE FORECAST` (ERROR) when the baseline exceeds `MANUAL_OVERRIDE_MAX_AGE_DAYS` (45), and hard-fails when `PAGASA_FAIL_ON_STALE=true`. |
| **ELN-006** | Retry/backoff on external calls | ✅ (helper tested) | New pure `retry_util.retry_call` (6 tests) wired into the Claude advisory, PAGASA download, and Semaphore POST. |
| **ELN-008** | Encoding-aware SMS fitting | ✅ (tested) | New pure `smstext.py` (12 tests): GSM-7 vs UCS-2 detection, segment counting, one-segment word-boundary truncation preserving ` -ELNINO`. Wired into `digest_generator` (replaces naive `[:130]`). Corrected a misconception — ñ/Ñ are GSM-7; the real UCS-2 triggers are á/í/ó/ú, ₱, em-dashes, curly quotes. |

---

## 📋 Open backlog

### P0 — Blockers (all addressed this sprint; remaining is deploy/verify)
| ID | Item | Status |
|----|------|--------|
| ELN-001..004 | git/CI, alerting, run-status, scraper freshness | ✅ shipped — verify in CI + a real Railway run |

### P1 — High (correctness / robustness)
| ID | Item | Effort | Status |
|----|------|--------|--------|
| ELN-005 | Self-referencing `{{ this }}` trend join crashed on first run / `--full-refresh` (table doesn't exist yet) — guarded with `adapter.get_relation` existence check + empty `prior_scores` CTE | S | ✅ resolved 2026-06-23 |
| ELN-006 | Retry/backoff | M | ✅ shipped |
| ELN-007 | Harden the Claude advisory parser (was truncating multi-line `ADVISORY_*` to first line) — pure `advisory.parse_advisory` captures values to the next label | M | ✅ resolved 2026-06-23 |
| ELN-008 | Encoding-aware SMS | S | ✅ shipped |
| ELN-009 | Phone E.164 normalization (`normalize_ph_phone`) before Semaphore; invalid numbers skipped | S | ✅ resolved 2026-06-23 |
| ELN-010 | SMS opt-out — `sms_opt_outs` (migration 003) + `normalize_phone_set` + send_sms suppression, **plus the inbound webhook** (`pipeline/webhook/inbound.py`) that records STOP replies. | M | ✅ resolved 2026-06-23 |

### P2 — Medium (quality / UX)
| ID | Item | Effort | Status |
|----|------|--------|--------|
| ELN-011 | Distinct `early-vegetative`/`late-vegetative` `crop_stage` labels (SQL + `crop_stage.py` + schema.yml + tests) | S | ✅ resolved 2026-06-23 |
| ELN-012 | Dashboard risk map — `ProvinceMap.tsx` plots each pilot province by lat/lon, colored by its worst crop's risk level, with a ranked list + legend (dependency-free, no GeoJSON) | M | ✅ resolved 2026-06-23 |
| ELN-013 | Historical trend sparkline per province — `Sparkline.tsx` (last 8 weeks) in the expanded card, using the existing `getHistoricalScores` query | M | ✅ resolved 2026-06-23 |
| ELN-014 | dbt uniqueness test on `risk_scores` (`province_id,crop,week_of`) — singular test `assert_risk_scores_unique.sql` | S | ✅ resolved 2026-06-23 |
| ELN-015 | Dev setup — `Makefile` + `pipeline/requirements-dev.txt` | S | ✅ resolved 2026-06-23 |
| ELN-016 | Integration tests: `test_pipeline_integration.py` runs the full scoring path over the real seed CSVs across a year of weekly dates (runnable, CI-gated); `test_db_smoke.py` is a live-DB schema smoke test that skips unless `INTEGRATION_DATABASE_URL` is set | M | ✅ resolved 2026-06-23 |

### P3 — Low (polish / product)
| ID | Item | Effort | Status |
|----|------|--------|--------|
| ELN-017 | Remove hardcoded test phone number literal in `send_sms.py --test` (now env-only, normalized) | XS | ✅ resolved 2026-06-23 |
| ELN-018 | Bump Anthropic SDK (0.34.2 → 0.116.0) — tool-based structured advisory deferred to a later pass | S | ✅ resolved 2026-07-08 |
| ELN-019 | Supabase RLS — found read policies were `TO authenticated`, but the dashboard uses the **anon** key (no login) → anon reads returned zero rows. Migration 002 grants anon SELECT on the public-safe tables only; PII tables (`cooperative_contacts`, `sms_log`) stay service-role-only. | S | ✅ resolved 2026-06-23 |
| ELN-020 | Coverage expansion: more provinces (Visayas/Mindanao), crops, localization (Ilocano/Cebuano) | L | open |
| ELN-021 | Outcome feedback loop — end to end: `advisory_feedback` (mig 004) + `feedback.parse_feedback`/`classify_inbound` + inbound webhook + anon-safe `feedback_summary` view (mig 005) + dashboard `FeedbackSummary.tsx` impact panel | L | ✅ resolved 2026-06-23 |
| ELN-022 | Dashboard `npm ci` failed with `Invalid Version:` — 21 corrupt optional-native-binding entries (`@unrs/resolver-binding-*`, no `version`) in `package-lock.json` (npm optional-dep bug). | S | ✅ resolved 2026-06-23 |
| ELN-023 | `next@14.2.5` runtime security advisory — bumped to `14.2.35` (latest 14.2.x) + `eslint-config-next` to match; npm ci / tsc / build re-verified | S | ✅ resolved 2026-06-23 |
| ELN-024 | Residual **dev-only** audit item: `@next/eslint-plugin-next` advisory (via `eslint-config-next`); fix is a breaking bump to v16. Lint tooling only — does not ship to users. Defer to a tooling upgrade. | XS | open (found during ELN-023) |

---

## ✅ Closed log

**Prior session (2026-06-22):**
- Scraper "Much Below Normal" → "Below Normal" downgrade (substring-order bug) — `outlook.py` + tests.
- SMS Semaphore "Failed" logged as "sent" (case-sensitive check) — `delivery.py` + tests.
- Test/SQL scoring divergence (`vegetative` mapped to 0.7 only) — `crop_stage.py` + `models/schema.yml` + tests.
- N+1 query in `fetch_contacts_with_digests` — `delivery.py` `attach_digests` + tests.
- Added `preview_run.py` offline no-DB pipeline preview.

**This session (2026-06-23):** ELN-001, 002, 003, 004, 006, 008 (see sprint table above).
- **ELN-022** (post-push): regenerated `dashboard/package-lock.json` (clean reinstall) to remove 21 corrupt `@unrs/resolver-binding-*` entries that crashed `npm ci`. Dashboard now passes `npm ci` + `tsc --noEmit` + `next build` locally; the CI dashboard job is now **gating** (no longer `continue-on-error`).
- **ELN-023**: bumped `next` 14.2.5 → 14.2.35 (security advisory).
- **Batch (P1/P2/P3 close-out):** ELN-005 (trend-join first-run guard), ELN-007 (multi-line advisory parser), ELN-009 (E.164 phone normalization), ELN-011 (early/late vegetative labels), ELN-014 (dbt uniqueness test), ELN-015 (Makefile + requirements-dev), ELN-017 (env-only test phone).
- **Compliance/security/UX batch:** ELN-010 (SMS opt-out suppression + migration 003), ELN-019 (anon-read RLS migration 002 — fixed the empty-dashboard bug), ELN-013 (dashboard trend sparkline). **83 unit tests passing (+3 skipped DB smoke); dashboard `tsc` + build green.**

---

## 🧪 Run log
- `python -m pytest pipeline/tests -q` → **83 passed** (+3 skipped DB smoke).
- `py_compile` clean: `pagasa_scraper`, `digest_generator`, `send_sms`, `elnino_weekly` (DAG), `outlook`, `crop_stage`, `delivery`, `smstext`, `retry_util`, `advisory`, `preview_run`.
- Dashboard: `npm ci` + `tsc --noEmit` + `next build` green (CI-gated on every push).
- `dbt test` (schema.yml + `assert_risk_scores_unique.sql`) runs against the live DB.

---

## 🚦 Production-readiness — pilot

**Code: ready.** Every known defect is fixed; the system is robust (retries, fail-loud
alerting, freshness guards), compliant (disclaimer + SMS opt-out), secure (RLS least-
privilege), tested (79 unit + dbt schema tests), CI-gated, and documented. The remaining
backlog is product roadmap or live-infra wiring, not code gaps.

### Owner deployment checklist (one-time)
1. **Apply migrations** in Supabase SQL editor, in order: `001_initial_schema.sql`,
   `002_dashboard_anon_read.sql` (**required** — without it the anon dashboard is empty),
   `003_sms_opt_outs.sql`. Seed `provinces.csv` + `crop_calendars.csv`.
2. **Pipeline env** (Railway): `SUPABASE_*`, `ANTHROPIC_API_KEY`, `SEMAPHORE_API_KEY`,
   plus optional `OPS_ALERT_WEBHOOK_URL` (failure alerts), `PAGASA_FAIL_ON_STALE`,
   `TEST_PHONE_NUMBER` (for `send_sms.py --test`).
3. **Dashboard env** (Vercel): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
4. **Deploy the inbound webhook** (`pipeline/webhook/inbound.py`, Flask) as a small
   always-on service (e.g. a second Railway service, `python pipeline/webhook/inbound.py`)
   and point the Semaphore inbound webhook at `POST /sms/inbound`. It records STOP →
   `sms_opt_outs` and other replies → `advisory_feedback` (ELN-010 + ELN-021).
5. Run once: `make preview` (offline sanity) → `dbt seed && dbt run && dbt test` → 
   `python scripts/digest_generator.py` → `python sms/send_sms.py --test`.

### Remaining backlog = roadmap (not blocking the pilot)
- **ELN-018**
  Anthropic SDK refresh · **ELN-020** coverage expansion (Visayas/Mindanao, more crops,
  Ilocano/Cebuano) · **ELN-021** outcome feedback loop · **ELN-024** eslint v16 (dev-only,
  breaking). (**ELN-012** map ✅ shipped.)
