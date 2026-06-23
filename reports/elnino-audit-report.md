# El Niño Early Warning — Audit & Backlog Report

_Last updated: 2026-06-23. Source of truth for bugs, fixes, and the prioritized backlog. Newest dated section is authoritative; older sections retained for history._

> A weekly El Niño agricultural risk system for 15 Luzon provinces (PAGASA → risk score → Claude advisory → SMS). Because it warns farmers, **correctness and delivery reliability are the top priorities** — a silent failure or an under-stated risk has real-world cost.

---

## 🏁 Sprint — 2026-06-23 (reliability hardening)

**Goal:** put the project on a safe operational footing — version control, CI, fail-loud ops, and the highest-impact correctness fixes.

**Test status:** **76 unit tests passing** (pure logic). Pipeline modules also `py_compile` clean.

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
| ELN-010 | SMS opt-out / unsubscribe (consent / NTC compliance) | M | open |

### P2 — Medium (quality / UX)
| ID | Item | Effort | Status |
|----|------|--------|--------|
| ELN-011 | Distinct `early-vegetative`/`late-vegetative` `crop_stage` labels (SQL + `crop_stage.py` + schema.yml + tests) | S | ✅ resolved 2026-06-23 |
| ELN-012 | Dashboard province map (choropleth — lat/lon already seeded) | M | open |
| ELN-013 | Historical week-over-week trend chart per province | M | open |
| ELN-014 | dbt uniqueness test on `risk_scores` (`province_id,crop,week_of`) — singular test `assert_risk_scores_unique.sql` | S | ✅ resolved 2026-06-23 |
| ELN-015 | Dev setup — `Makefile` + `pipeline/requirements-dev.txt` | S | ✅ resolved 2026-06-23 |
| ELN-016 | Integration test of scrape→dbt→digest→SMS against a seeded test Postgres | M | open |

### P3 — Low (polish / product)
| ID | Item | Effort | Status |
|----|------|--------|--------|
| ELN-017 | Remove hardcoded test phone number literal in `send_sms.py --test` (now env-only, normalized) | XS | ✅ resolved 2026-06-23 |
| ELN-018 | Bump Anthropic SDK (0.34.2 → current); consider tool-based structured advisory | S | open |
| ELN-019 | Verify/test Supabase RLS policies (anon read-only, service-key server-only) | S | open |
| ELN-020 | Coverage expansion: more provinces (Visayas/Mindanao), crops, localization (Ilocano/Cebuano) | L | open |
| ELN-021 | Outcome feedback loop — did a warning lead to action / avoided loss? | L | open |
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
- **Batch (P1/P2/P3 close-out):** ELN-005 (trend-join first-run guard), ELN-007 (multi-line advisory parser), ELN-009 (E.164 phone normalization), ELN-011 (early/late vegetative labels), ELN-014 (dbt uniqueness test), ELN-015 (Makefile + requirements-dev), ELN-017 (env-only test phone). **76 unit tests passing.**

---

## 🧪 Run log
- `python -m pytest pipeline/tests -q` → **76 passed**.
- `py_compile` clean: `pagasa_scraper`, `digest_generator`, `send_sms`, `elnino_weekly` (DAG), `outlook`, `crop_stage`, `delivery`, `smstext`, `retry_util`, `preview_run`.
- `dbt test` (schema.yml) and the dashboard build are **CI/DB-only** — not run in this dev environment.
