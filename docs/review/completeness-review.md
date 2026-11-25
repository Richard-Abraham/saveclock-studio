# SaveClock Studio — Pre-implementation Completeness Review

Reviewer: independent (read-only on docs) · Date: 2026-11-08 · Scope: DECISIONS, PRD, ROADMAP, CHECKLIST, ARCHITECTURE, STANDARDS, adr/, SECURITY, QUALITY, DESIGN, UX-SPEC, mockups/index.html.
Method: ID extraction by grep, then manual task-to-requirement mapping using each ROADMAP task's "Links" and "Done criteria". "Covered" = a task's done criteria would verify the item. "Partial" = a task touches the topic but the criterion does not verify the item. "Orphan" = no task. SEC/QM counts are my judgement calls and should be read as +/- 5.

Key structural finding: ROADMAP never cites a single SEC-xxx or QM-xxx ID. Security coverage is delegated to two catch-all tasks (T-4.8, T-5.5) that point at SECURITY.md section 10 / CHECKLIST D. Those lists exist, but most controls have no owner task, no phase and no task-level done criterion.

---

## 1. Coverage summary

| Category | Total | Covered | Partial | Orphan | Coverage (covered) | Coverage (covered+partial) |
|---|---|---|---|---|---|---|
| PRD user stories US-001..026 | 26 | 22 | 4 (US-007 UI, US-018 UI, US-023 operator tooling, US-024 spread thin) | 0 | 85% | 100% |
| PRD functional FR-001..040 | 40 | 39 | 1 (FR-039 analytics/consent) | 0 | 97.5% | 100% |
| PRD non-functional NFR-001..025 | 25 | 18 | 3 (NFR-009, NFR-016 live-region only, NFR-020 no pen test) | 4 (NFR-008, 011, 013, 018) | 72% | 84% |
| SECURITY controls, pre-launch (P0/P1, 113 of 115; SEC-022 and SEC-104 are P2) | 113 | 29 | 40 | 44 | 26% | 61% |
| QUALITY metrics that are CI/Release gates (51 of 106 QM) | 51 | 12 | 9 | 30 | 24% | 41% |
| ROADMAP tasks with no PRD/SEC/QM link | 69 | n/a | n/a | 19 are process or enabler tasks (see 2.3); 0 are gold-plating | n/a | n/a |

Reading: functional requirements are well covered. Security, quality gates and non-functional operations are not covered by tasks. This is the main weakness of the to-do list.

## 2. Traceability

### 2.1 Orphans (requirements with no task)

**NFR (4):** NFR-008 time-to-first-video p50 (no telemetry or measurement task), NFR-011 uptime 99.5% (no uptime monitor or SLO task), NFR-013 web LCP <= 2.5 s (only a Lighthouse accessibility score in T-1.7; the UX-SPEC 3.5 budgets are in no task or gate), NFR-018 audio never sent to third parties except fingerprint vendor (no data-flow review task).

**SECURITY, orphan IDs (44):**
- Upload and worker (5.1 to 5.3, 10 IDs): SEC-004 (filename normalisation), 007 (separate cookieless download domain; conflicts with ARCH 9 "no custom-domain serving"), 009 (metadata strip), 018 (decode-once canonical copy), 019 (stock download SSRF guard and host allowlist), 020 (job payloads IDs only), 023 (scratch dir hygiene), 030 (build-time model weights), 031 (SHA-256 pinned weights), 033 (offline inference).
- LLM (5.4, 3): SEC-040 (features-only prompt), 041, 043.
- Auth and abuse (5.5, 8): SEC-058 (CORS), 061 (Turnstile), 063 (abuse signals), 064 (queue fairness), 066 (compute budget and kill-switch), 073 (Referrer-Policy and no-store), 077 (admin on separate listener), plus SEC-076 centralised error handling only covered by STANDARDS.
- Secrets and infra (5.7, 5.12, 8 IDs): SEC-082 (rotation), 083 (Stripe restricted keys), 084 (DB roles), 130 (host hardening), 131, 132, 133 (Postgres and Redis not exposed), 136 (Redis persistence).
- Web, logging (5.9 and 5.10, 6): SEC-112, 113, 114 (Cloudflare WAF), 115, 121 (audit log), 123 (NTP).
- Supply chain (5.11, 6): SEC-091 (digest pinning), 093 (SBOM), 094 (Dependabot), 095 (GitHub hardening), 098, 099 (MFA).
- Privacy and legal (5.13 and 5.14, 4): SEC-145 (age gate), 147 (DSAR export), 149 (RoPA and DPIA), 155 (security.txt and abuse mailbox).

**SECURITY, partial (40)** include: SEC-001/002/003 (T-2.1 and T-1.6 name different paths and TTLs), 005, 006, 008, 011, 013, 014 (T-2.14 says "no network" only), 015, 016, 017, 021, 032, 044, 045, 055, 056, 059 (no PKCE or state criteria), 062 (atomic-race test missing), 065, 070, 074 to 076, 081, 085, 090, 092, 103, 110, 111 (only via CHECKLIST D), 120, 122, 134, 143, 144, 146, 148, 152.

**QUALITY gate metrics (51 gating QMs):**
- Covered 12: QM-001, 032, 036, 038, 051, 062, 063, 064, 068, 080, 081, 084.
- Partial 9: QM-002, 016, 033, 050, 052, 060, 061, 075, 077.
- Orphan 30: QM-003, 004, 009, 010, 011, 012, 015, 017, 018, 020, 021, 022, 023, 024, 025 (tempo, downbeat, section, confidence suite), QM-030, 031, 034, 035, 041, QM-067, 069 (sync canary), 070, 072 (VMAF), QM-082, 083, QM-090 to 093 (human rating app). No task builds the `ci-lite`, `nightly` and `release` modes, baselines, paired-bootstrap or the determinism check in QUALITY 5.
- Production monitoring QM-100 to 106 is non-gating but depends on analytics events and a "Report issue" feature that nothing builds (see G-12 and G-13).

**UX screens with no implementing task (ROADMAP covers S3 to S8 and S2 via T-4.1):** S1 Landing, S9 Projects list, S10 Pricing, S11 Account, S12 error/empty/offline/session-expiry catalogue, `/legal/*` static pages, the DMCA public form page, the S4 fingerprint notice UI (T-4.3 says "UI notice" only).

**QUALITY section 12 and 14 spike items not in Phase 0 tasks:** P0-4 (hard-set F1 >= 0.60 and confidence flagging), P0-8/9 (A/V sync on iOS Safari, Android Chrome, desktop Chrome with 3 testers), P0-12 (SigLIP P@1 >= 0.75 with kappa >= 0.6; T-0.8 uses a different "80% of top-3" rule), P0-14 (human "feels on beat" >= 3.8), P0-15, plus section 14 items 1 to 7 (pin mir_eval behaviour, dataset licences, tau for SigLIP, confidence distribution, early-bias decision record).

### 2.2 PRD US to ROADMAP map (summary)

US-001..003: T-4.1. US-004: T-2.1, T-3.2. US-005: T-2.2, T-3.2. US-006: T-2.3, T-3.5. US-007: T-2.5 (no UI task for vibe chips). US-008: T-2.4 to T-2.9. US-009: T-3.4. US-010, 011: T-3.5. US-012: T-2.10, T-3.3. US-013, 014: T-2.9, T-3.6. US-015: T-4.3. US-016: T-2.6, T-3.6. US-017: T-2.11, T-3.6, T-4.6. US-018: T-4.2 (no usage meter or limit-dialog UI). US-019, 021: T-5.1 (no pricing UI). US-020: T-5.2. US-022: T-2.10. US-023: T-4.4 (no operator tool). US-024: T-3.7. US-025: T-4.6. US-026: T-6.1.

### 2.3 Tasks with no requirement link (process or enabler only; all legitimate)

T-0.0, T-0.6, T-0.7, T-0.10, T-1.0, T-1.1, T-1.2, T-1.3, T-1.9, T-2.0, T-2.14 (links R-07 and SECURITY.md only), T-2.15, T-3.0, T-3.8, T-4.0, T-4.9, T-5.0, T-5.5, T-5.6. None should be removed. T-1.2 and T-1.3 should gain SEC links (see section 3).

---

## 3. To-do quality review

### 3.1 Task issues

| Task | Problem | Fix |
|---|---|---|
| Phase order (T-2.1, T-2.10, T-2.13, T-2.14, all of Phase 3) | Phases 2 and 3 need a user: warranty is stored per user (FR-002), ownership 403/404 is asserted in T-2.14, quota is decremented in T-2.10, UX-SPEC 1 requires sign-in before upload. Auth and ownership (T-4.1, T-4.2) arrive in Phase 4. This is a forward dependency, so the Phase 2 and 3 acceptance tests cannot be written as stated. | Add T-1.13 (auth core and ownership layer, see section 8) and reduce T-4.1 and T-4.2 to what is left (Google OAuth, lockout, tier policy, abuse). Or state explicitly that Phases 2 to 3 run with a dev-only single-user stub and delete the 403/404 criterion from T-2.14. |
| T-0.1 | Listed before its dependency T-0.0. Done criteria omit P0-4 hard-set floor and confidence AUROC (QUALITY 12). | Reorder T-0.0 first. Add the numeric hard-set floor (F1 >= 0.60) and the QUALITY 14 pin-down items. |
| T-0.2 | Threshold (>= 12 usable clips) differs from QUALITY P0-11 (>= 10). | Pick one number and put it in DECISIONS 6 or the gate. |
| T-0.3 | Does not test A/V sync across iOS Safari, Android Chrome and desktop Chrome (P0-9) or the sync canary (QM-069). | Add canary video played on 3 devices, 3 raters. |
| T-0.4, T-0.5 | Done criteria depend on external parties with no timeout besides a 10-day follow-up. | Add a decision-by date and a stated fallback on silence (already in G0 for Pexels; add for counsel). |
| T-0.8 | "Top-3 relevant for >= 80% of 20 prompts" does not match P0-12 (P@1 >= 0.75 on 50 keywords x 20 clips, kappa >= 0.6, lift >= +10 pts). | Align to P0-12. |
| T-0.9 | Cost model is a PO task; no input for LLM, fingerprint vendor or R2 egress. | List unit-cost inputs. |
| T-1.1 | "Approve DESIGN.md and the skeleton design spec" mixes two approvals, and DESIGN.md and UX-SPEC already exist (nothing to author). | Split: T-1.1a user approves DESIGN.md and UX-SPEC.md; T-1.1b skeleton design only if a UI exists. |
| T-1.2 | Too big for one PR: monorepo, toolchain pins, `.env.example`, compose for all services. "Documented commands" is untestable. | Split: scaffold and toolchains; compose and seed (T-1.10); config catalogue (T-1.12). Done: fresh clone to running stack in <= 10 min, timed. |
| T-1.3 | One task for format, lint, types, tests, build, dependency scan and secret scan. No definition of the pipeline (G-08). No Trivy, SBOM, hadolint, import-linter, config-malware CI check, OpenAPI drift gate (they are in STANDARDS 13). | Split into T-1.3 (CI gates) and T-1.11 (release pipeline and supply chain). |
| T-1.4 | API skeleton, Alembic, OpenAPI export, structured logs and `/healthz` in one task; DB CHANGE for an "initial schema" is vague (which tables?). `/healthz` conflicts with ARCH `/v1/health/live|ready`. | Split API skeleton from DB baseline. Fix health path. State which tables exist at G1 (likely none besides `alembic_version` and a `jobs` stub). |
| T-1.5 | Done: "job killed mid-run is re-queued" has no method. | Specify chaos test (kill -9 the worker, assert completion). |
| T-1.6 | TTL <= 15 min (PRD) vs 10 min (ARCH, SEC-072) vs 5 min presigned PUT (SEC-002). | Use SEC numbers, update PRD FR-017. |
| T-1.7 | "Lighthouse accessibility >= 95 (inference)" is the only web metric; no perf budget. | Add LCP and JS-size budget from UX-SPEC 3.5. |
| T-1.8 | "DB backup job configured" has no restore test until T-4.7 (Phase 4). Restore proof should exist before real data. | Add restore into a scratch DB once in Phase 1. |
| T-2.1 | Names `POST /uploads`; ARCH defines `POST /projects`, `/projects/{id}/upload-url`, `/upload-complete`. SEC-001 uses `POST /uploads`. | Make ARCH the contract; update ROADMAP and SEC-001. |
| T-2.2 | Golden-set F1 criterion depends on T-2.12, which comes later and depends on T-2.9. | Move the golden-set harness into T-2.2 (a minimal harness) or make T-2.12 depend on T-2.2 and drop F1 from T-2.2 done. |
| T-2.5 | Prompt-injection and budget controls SEC-040..045 absent. | Add to done criteria or new task T-2.17. |
| T-2.6 | No host allowlist/SSRF/size limits (SEC-019). | Add (see T-2.18). |
| T-2.7 | Depends on T-2.6 only, but ARCH 3 normalises before ranking (OQ-4 unresolved). | Resolve OQ-4 before T-2.7 or add dependency on T-2.8. |
| T-2.9 | Largest backend task: normalised-clip render, frame math, watermark, 720p and 1080p, mode A and B, cut-list JSON and CSV, verify_render with 7 checks. Not one PR. | Split: (a) frame-index render and mux, (b) watermark and tier variants, (c) mode B and cut lists, (d) verify_render (QM-051..064, 068, 075, 077). Each with its own QM IDs. |
| T-2.10 | Orchestrator, idempotency, SSE, retries, timeouts, quota refund in one task. | Split: state machine and orchestrator; idempotency and quota reserve and refund; SSE endpoint. |
| T-2.12 | Depends only on T-2.9 yet needs T-2.10 (success rate) and T-2.11. Does not build the `ci-lite`, `nightly` and `release` modes. Also G2 says "0 internal hard cuts" while QM-036 says <= 1% and P0-13 says <= 3%. | Add dependencies; add harness modes; reconcile the three tolerances in DECISIONS 6. |
| T-2.13 | Throwaway UI "not linked publicly" needs auth (see Phase order). Includes `design spec stating it is throwaway`, which contradicts "No UI design phase skipped" rules. | Decide dev-only; state auth stub explicitly. |
| T-2.14 | 403/404 authz needs users (see above). Corpus of 50 files; SECURITY 10 asks a 24 h mutation fuzz run. | Align to the SEC checklist: >= 24 h fuzz, 0 unresolved crashes. |
| T-3.1 | Design spec exists for most screens already (DESIGN, UX-SPEC, mockup). | State what T-3.1 adds beyond UX-SPEC, or reduce it to "approval of UX-SPEC S3 to S8 + mock". |
| T-3.2 | Bundles upload, warranty, analysis review, waveform, beat markers, tempo override: 3 screens. Links US-007 but no vibe UI. | Split: upload and warranty (S3), analysis (S5 and tempo). Add vibe chips to T-3.5. |
| T-3.4 | Preview engine plus proxy render job plus Safari iOS and Android testing. Offset <= 1 frame "inference tolerance". | Split FE preview engine from BE proxy job. |
| T-3.7 | Includes a11y, cross-browser matrix and 320 px; single QA task. | Acceptable as a gate task but add the UX-SPEC 3.5 performance budgets and AC-X-1 to AC-X-9 as the explicit checklist. |
| T-4.1 | Largest Phase 4 task (signup, verify email, reset, Google OAuth, sessions, CSRF, lockout, screens). No email provider task. | Split: password auth and sessions; email service; Google OAuth; auth screens. |
| T-4.2 | Policy layer, tier enforcement, quotas, rate limits and abuse limits in one. No usage meter or limit dialog UI. | Split into ownership/policy, quotas and limits, rate limits and abuse (T-4.14); add UI. |
| T-4.3 | Vendor decision (OQ-07) is an input, not an output of any task; no UI design for the S4 states; DPA and data minimisation (SEC-143) missing. | Add decision task in Phase 0 or 1; add DPA. |
| T-4.4 | Mixes legal registration and engineering. US-023 says the operator acts on notices; no tool (SEC-077 says no admin UI in MVP; ARCH has two admin endpoints). | Add T-4.10 admin tool; counter-notice flow (SEC-152). |
| T-4.6 | "Deletion verified across DB, R2, Redis, logs policy" is vague. | Define the checks: object listing under `u/{id}/` empty, DB rows gone or tombstoned, Redis keys gone, backups replay tombstones (SEC-142, 135). |
| T-4.7 | Observability plus backups plus alerts plus restore drill. | Split observability/alerts from backup/restore drill. |
| T-4.8 | Uses `security-audit` skill only. SECURITY 10 requires an independent pen test and fuzz; nothing books it (SEC Q-17 says "book 4 to 6 weeks pre-launch"). | Add T-4.16. |
| T-4.9 | Closed beta has no size, duration or exit numbers. | Add (for example >= 20 invitees, 14 days, 0 sev-1). |
| T-5.1 | Whole billing module; fine for one plan but long. | Allow split: Checkout and Portal; webhooks and entitlement sync. |
| T-5.2 | Allowance reset on "billing cycle" vs `usage_counters` calendar month (ARCH). | Specify anchor. |
| T-5.4 | "3x expected beta peak" has no number. | State the expected peak (renders per hour). |
| T-5.5 | "Every item in CHECKLIST D ticked" is the only link to most SEC controls. | Replace with explicit tasks (section 8). |
| T-6.x | Fine for post-launch. T-6.1 appears before its dependency T-6.0. | Reorder. |

Cycles: none found. Forward dependencies on later phases: Phase 2 and 3 on Phase 4 auth (above); T-2.14 on T-4.2; T-1.8 backup restore on T-4.7.

### 3.2 Go/no-go gate measurability

| Gate | Measurable? | Issues |
|---|---|---|
| G0 | Mostly: items 1 to 4 numeric. Item 5 is binary (reply or fallback). Item 6 "counsel has not flagged a blocker" is binary but depends on a third party. | Missing numeric items from QUALITY 12: hard-set F1 floor (P0-4), octave rate (P0-5), A/V sync on 3 devices (P0-9), SigLIP P@1 (P0-12), human check (P0-14). Different thresholds than QUALITY in 3 places (12 vs 10 clips; top-3 vs P@1; zero vs <= 3% internal cuts). Fallback column is truncated in print ("Re-plan: swap model (smaller/other MIT)"). |
| G1 | Yes (all binary and verifiable). | Add restore-into-scratch proof and one SEC baseline (non-root, secret scan red on planted key). |
| G2 | Numeric. | Hardware spec for p95 ("4-vCPU") stated in DECISIONS, not in the gate. Golden-set size not stated (need N tracks). "100 consecutive renders": on which song mix and tiers? Success rate denominator ("excluding user-input errors") should be a defined list. Add QM-072 VMAF, QM-069 canary, QM-067. |
| G3 | Numeric for a11y and preview; "UX-SPEC acceptance flows pass" is OK; "user approves" is binary. | No LCP, INP, bundle size thresholds (UX-SPEC 3.5, NFR-013). No pass-rate for browser matrix. |
| G4 | Mixed: "counsel sign-off", "0 critical/high", "restore drill passed" are measurable; "abuse limits tested" is vague. | No pen test, no 24 h fuzz, no list of which SEC IDs are required (should reference SECURITY 10 explicitly). |
| G5 | Numeric (>= 50 activated users, >= 98%, COGS <= $0.06); "live-mode smoke refunded" binary. | Activated defined in PRD KPI table but the 30-day window and start are unstated. |

---

## 4. Implementability gaps

Severity: BLOCKER = an engineer cannot start or must invent the answer; MAJOR = likely rework or divergence; MINOR = low-risk guess.

| ID | Sev | What is missing | Owning doc | Proposed content |
|---|---|---|---|---|
| G-01 | BLOCKER | Auth and ownership arrive in Phase 4, but Phases 2 and 3 build a user-scoped pipeline (see 3.1 Phase order). | ROADMAP + ARCHITECTURE | Add auth core (users, sessions, CSRF, ownership repositories, dev seed users) to Phase 1 as T-1.13; keep Google OAuth, lockout and tiers in Phase 4. |
| G-02 | BLOCKER | Origin topology undecided (SECURITY Q-01, ARCH OQ-6): `api.<domain>/v1` vs single origin with Traefik path proxy. It decides cookie prefix (`__Host-`), CORS, CSRF, SSE and the Next.js server-to-API path, so it must be fixed before T-1.7. ARCH 7 states `https://api.<domain>/v1` while SEC recommends single origin. | ARCHITECTURE + ADR | ADR-0009: single origin; Traefik routes `/v1` to API, everything else to web; no CORS; `__Host-sc_session`; CSRF header; bucket CORS only for R2. Reflect in ARCH 7 and 14. |
| G-03 | BLOCKER | Transactional email is unspecified: no provider (only "SMTP"), no sender domain, SPF/DKIM/DMARC, templates (verify, reset, takedown acknowledged, content removed, strike, deletion done, notify-me), bounce and complaint handling, no dev mailbox, no outbox or retry. T-4.1, T-4.4 and US-023 all depend on it. | ARCHITECTURE (+ADR) + ROADMAP | ADR: provider (Postmark, SES or Resend), DKIM domain, `emails` outbox table via `maintenance` queue, template list with merge fields and copy owner, Mailpit in compose, bounce webhook. Add T-1.14. |
| G-04 | BLOCKER (pre-launch) | DMCA/moderation tooling: US-023 and FR-033 require the operator to act on notices. ARCH lists two `/admin/dmca` endpoints; SEC-077 says no admin UI in MVP; no CLI, no counter-notice restore, no strike ledger table (only `users.strike_count`), no user-notice templates, no runbook. G4 tabletop "notice to removal to user notice to strike in < 24 h" cannot be run. | ARCHITECTURE + SECURITY + ROADMAP | Minimal operator CLI or admin page behind SSO/IP allowlist: list notices, validate checklist (17 USC 512(c)(3) elements), take-down (delete objects, mark project), notify user, record strike (`strikes` table: user_id, notice_id, at), counter-notice and 10 to 14 business day restore timer, all written to `audit_log`. Add T-4.10. |
| G-05 | MAJOR | Endpoints that UX screens need but ARCH 7 lacks: resend verification email (US-003); rename project (S9 menu); delete song and renders only, keeping project and beat map (US-017 "Delete now"; `DELETE /projects/{id}` deletes everything); change password and email (S11); list or revoke sessions, "log out everywhere" (SEC-055); re-authentication for account deletion (S11 AC-S11-3); export my data (SEC-147; S11); notify-me/waitlist for pricing (S10); "Report an issue" (QM-102, CHECKLIST D4); manual "tap tempo / enter BPM / use even grid" (UX S5, ARCH 16); clip lock (UX S6 has "lock"; PATCH ops in ARCH row 21 omit it and any reorder, though UX 3.4 offers "Move earlier/later"); per-render attribution list for S8; legal document versions for warranty (`tos_version` source); `GET /me` fields for plan, locale, flags. | ARCHITECTURE 7 | Add rows 34+ with request, response, errors, auth, rate limit. Extend PATCH plan ops (`lock`, `reorder`, `set_bpm`). |
| G-06 | MAJOR | ROADMAP and ARCH disagree on API names: `POST /uploads` and `GET /jobs/{id}/events` (ROADMAP, SEC-001) vs `/projects/{id}/upload-url`, `/projects/{id}/events` (ARCH); `/healthz` (ROADMAP, STANDARDS web) vs `/v1/health/live|ready`; "jobs" vs "renders" vocabulary; ARCH row 1 says both "201" and "202 always" for register. | ARCH is the contract; fix ROADMAP, SEC-001, STANDARDS | One pass to align names; make register return 202 always. |
| G-07 | MAJOR | Local dev setup: no compose file spec. Needs Postgres, two Redis (broker and cache), MinIO or R2 dev bucket, Mailpit, egress-proxy optional, web, api, worker profile with and without torch. No `make dev`, no model-weights download step, no seed data (users, a synthetic click-track project, stock API recorded fixtures), no `.env.example` yet. STANDARDS mentions MinIO/moto but not compose. | STANDARDS 9 + new `docs/DEV-SETUP.md` or `infra/README` | Table of services with ports, `make up/seed/test`, fixture files (<= 200 KB per STANDARDS), "fresh clone to first render in 15 min" criterion. Add T-1.10. |
| G-08 | MAJOR | CI/CD definition missing. STANDARDS 13 lists gates but not the pipeline: host (GitHub assumed by PR template; not decided in DECISIONS), triggers, job graph, caching, matrix, nightly eval, image build and push to which registry, Dokploy deploy trigger (webhook?) and rollback, secrets in CI, SHA-pinned actions, who may deploy. | STANDARDS + new `docs/CICD.md` | Pipeline diagram, jobs (lint, type, unit, integration with testcontainers, contract diff, migration check, golden, build, scan, e2e), deploy job manual-approved, tags `sha-<commit>`. Add T-1.11. |
| G-09 | MAJOR | No canonical env/config catalogue. STANDARDS 9 lists groups as "indicative". Missing: Turnstile keys, LLM kill-switch and daily call caps, queue-depth limit (200), tier limits, `BILLING_ENABLED`, fingerprint excerpt settings, egress proxy URL, Sentry env, trusted-proxy, Redis ACL users, watermark asset path, CORS/origin, cookie names, signed URL TTLs, per-user storage cap (500 MB), feature flag for the driver UI. | STANDARDS 9 or `infra/ENV.md` | Table: name, type, default, required, secret?, service, owner doc. CI check that `Settings` and `.env.example` agree (already planned). Add T-1.12. |
| G-10 | MAJOR | Data model lacks fields for features the docs promise: age attestation (SEC-145; no DOB or `age_confirmed_at`); consent/preferences log (SEC-146/147); per-user storage and concurrent-upload counters (SEC-008; `usage_counters` has only renders and analyses); clip locks and manual edits flags; watermark version used per render; fingerprint match log with its own 12-month retention (SEC Q-11) separate from `songs`, which is purged; strike events; email outbox; waitlist; user reports; legal document versions table; account-deletion tombstones (SEC-142); `projects.expires_at` start (upload-complete vs project creation, SEC Q-15). | ARCHITECTURE 6 | Add the tables and columns; map each to the phase in which it ships (see G-19). |
| G-11 | MAJOR | Backup and restore contradictions: ARCH says daily dump retained 7 days and restore tested monthly; SEC-135 says nightly encrypted dumps 14 days and quarterly restore; PRD NFR-025 RPO 24 h, RTO 4 h; ARCH 14 mentions PITR vs dump; privacy notice must state backup retention; backups must replay deletion tombstones. | SECURITY 6.3 (owner) | Single table: cadence, retention, encryption, restore frequency, tombstone replay, RPO and RTO, and the restore drill procedure. |
| G-12 | MAJOR | Analytics and consent: FR-039 and OQ-05 leave the decision open, yet KPIs (activation, retention, mode B share, QM-100..106) need events. No tool chosen (self-hosted? none?), no event list, no consent banner spec, no cookie list. | PRD + SECURITY 5.13 + DESIGN | Decision: server-side first-party events in Postgres or a privacy-friendly tool; event schema; banner only if non-essential cookies exist. Add T-4.12 and T-4.17. |
| G-13 | MAJOR | Support and feedback channel: CHECKLIST D4 expects support; QUALITY 11 relies on a "Report issue" form that carries beat map and plan; UX-SPEC and ARCH have no screen, endpoint or mailbox. Also no status page, FAQ or help. | UX-SPEC + ARCHITECTURE + CHECKLIST D4 | `POST /reports` (category, free text, project_id, auto-attached beat map, no audio unless user opts in), `support@` mailbox, help/FAQ page, status page link. Add T-3.13 and T-5.9. |
| G-14 | MAJOR | Watermark specification (OQ-10): ARCH describes an overlay PNG at `W-w-24:H-h-120`, but no asset, size, opacity, safe zone, anti-removal approach, or check that it does not obscure captions or the Pexels "no unaltered resale" rule; Pro has none. | DESIGN + ARCHITECTURE 11 | Asset spec (SVG source, PNG at 720p, opacity, position outside platform UI safe zones), versioned in `renders.watermark_version`, a verify_render check that the Free output contains it. |
| G-15 | MAJOR | Mode B packaging (UX Q5) and render cost: one MP4 plus separate JSON and CSV vs ZIP; ARCH makes `audio_mode` a render attribute so B means a second render and a second quota decrement unless specified. | PRD + ARCH + UX | Decision: both modes derive from one render (silent MP4 plus cutlists always produced; A adds mux of the song) and only one quota unit consumed per plan version. |
| G-16 | MAJOR | Inconsistent numbers an engineer must pick between: upload limit 50 MB (PRD, ARCH, SEC) vs 100 MB (UX-SPEC S3, mockup); signed GET TTL 15 min (PRD FR-017) vs 10 min (ARCH, SEC-072); mezzanine TTL 24 h (ARCH) vs 7 d (SEC Q-04); FFmpeg 7.x (DECISIONS) vs 8.x (ARCH OQ-1, SEC Q-05); three queues (DECISIONS) vs four (ARCH `maintenance`); `-protocol_whitelist file` (DECISIONS) vs `file,pipe` (SEC-010); internal hard cut tolerance 0 (DECISIONS, G2) vs <= 1% (QM-036) vs <= 3% (P0-13); AMLt >= 0.88 (QM-004) vs >= 0.85 (P0-2); clip availability >= 12 (G0) vs >= 10 (P0-11); backup retention (G-11); concurrent job caps. | DECISIONS (single source) | Amend DECISIONS with the chosen value for each, via ADRs where DECISIONS changes. |
| G-17 | MAJOR | Error codes: ARCH 7 has 13 generic codes, but other docs rely on domain codes that are not catalogued: `email_unverified` (PRD US-003; ARCH only has `forbidden`), `stock_unavailable`, `verification_failed`, `FAILED_PLAN`, `FAILED_RENDER`, file-rejection reasons ("specific codes", T-2.1: `file_too_long`, `unsupported_codec`, `too_many_streams`, ...), `pool_exhausted`, `quota_exceeded` details, `tos_not_accepted`, expiry `410`. No map from code to UX S12 copy. | ARCH 7 + UX S12 | Table: code, HTTP, retryable, user message key, UX surface. Put it in OpenAPI as enum for the generated client. |
| G-18 | MAJOR | Worker sandbox feasibility unproven: SEC-013/014 and ARCH 14 assume internal networks, an egress proxy, read-only rootfs, `cap_drop`, seccomp, per-FFmpeg netns. ARCH OQ-9 and SEC Q-07 admit Dokploy and Swarm may not allow it and the VPS may be shared. | ARCH + SECURITY | A Phase 1 spike (T-1.16): prove the compose/Swarm settings on the actual staging VPS; record the fallback (egress proxy only, dedicated worker host). |
| G-19 | MINOR | Migration plan by phase: policy exists (expand/contract, Alembic, DB CHANGE notice) but there is no table-to-phase map, no initial baseline, no rollback runbook, and the DB CHANGE text must contain exact SQL. | STANDARDS 5 + ROADMAP | Table: phase, tables or columns introduced, DB CHANGE ID. Each task that changes schema lists it. |
| G-20 | MINOR | i18n stance: DESIGN says copy is externalised and `users.locale` exists, but no statement that MVP is English-only, no locale detection rule (guideline: Accept-Language), no `Intl` default locale. | DECISIONS 1 or DESIGN 7 | "English only at launch; strings externalised; formats via `Intl` using `Accept-Language`." |
| G-21 | MINOR | Legal text location: ToS, Privacy, DMCA policy, Acceptable Use have no draft or folder; ToS version IDs used by warranty need a source of truth. | ROADMAP T-4.5 + `docs/legal/` | Folder and versioning rule (`tos_version` equals file hash or date). |
| G-22 | MINOR | Stripe operations: trial or none, proration, dunning, downgrade at period end vs 72 h data, tax mode, refund and chargeback account pause (SEC-104 P2), invoice details. | ARCH + SEC 5.8 | Short billing policy table. |
| G-23 | MINOR | Operations runbooks: deploy, rollback, DLQ requeue (`saveclock jobs requeue-dead` is mentioned but not specified), on-call, staging-vs-prod runbook (ARCH calls it out of scope). | new `docs/RUNBOOK.md` | Per-alert action list. |
| G-24 | MINOR | UX promises behaviours that the architecture does not support: "Upload pauses and resumes" (UX 3.6) vs single presigned PUT; "changes saved on your device and will sync" (offline banner) vs server-side autosave via `PATCH /plan` that creates a new plan version each time (60/min). | UX + ARCH | Either specify S3 multipart or tus, and a local draft queue, or soften the copy. Define whether each autosave is a plan version. |
| G-25 | MINOR | Landing page content, SEO basics, `robots.txt`, OG tags, and legal footer are not in any task. | UX S1 + ROADMAP | Add T-3.9. |

Counts: 4 BLOCKER, 14 MAJOR, 7 MINOR (25 total).

---

## 5. UX, design and accessibility findings

Skill applied: `web-interface-guidelines` to UX-SPEC.md, DESIGN.md and mockups/index.html. Line numbers refer to `mockups/index.html` unless named.

### 5.1 Strengths (pass)

Skip link (L130), single h1 and ordered h2 (L133), `color-scheme` set for both themes (L17, L22) and `meta color-scheme` (L7), `:focus-visible` outline (L62), 44 px minimum targets (L34, L53, L100, L113), `prefers-reduced-motion` gates the beat pulse and the toggle is disabled (L91 to 94, L368), `touch-action` on `.btn`, tabular numbers (L51, L98), `text-wrap: balance` (L27), `overscroll-behavior: contain` on the sheet body (L48), progress bars have names and values (L159, L181), `aria-live` regions exist (L190), non-breaking spaces in units (L156, L232), explicit pressed state on toggles, `translate="no"` rule documented. UX-SPEC covers: the non-drag alternative table (3.4) covering all 8 drag interactions, single-key shortcut off switch (WCAG 2.1.4), destructive confirmations with focus on Cancel, URL-backed state, `beforeunload` only during save, empty/loading/error/offline states.

### 5.2 Findings

mockups/index.html
- L5 to L7: no `<meta name="theme-color">` (DESIGN 13 claims `theme-color` passes; light and dark values are needed).
- L190: `id="x"` is repeated for every cloned phone (duplicate IDs) and is not unique per instance.
- L207, L339: mute toggle has `aria-pressed` and a visible label ("Muted"), but `aria-label` is "Unmute" and flips on press. Label-in-name (WCAG 2.5.3) fails and pressed plus changing label double-announces. Use a fixed label "Sound" with `aria-pressed`, or drop `aria-pressed`.
- L216: `role="tablist"` without `role="tabpanel"`, `aria-controls`, roving `tabindex` or arrow-key handling (0 `tabpanel` in file).
- L210: slider has no `aria-valuetext` ("12.4 s, beat 26"); pointer seek handler (L342) is fine, keyboard (L340) is fine.
- L53 vs L100, L110, L113, L34: `touch-action: manipulation` only on `.btn`; chips, toggles, tabs and segmented controls lack it.
- Hover feedback only on `.btn.p` and `.btn.s` (L56, L58); chips, tabs, toggles, nav links have none.
- L70: progress bar `transition: transform` is not inside the reduced-motion media query (low risk, but the file's own rule says all motion respects the setting).
- L162: terms link is `href="#"`; L10 loads Google Fonts from a third party (IP disclosure to Google, CSP and privacy implications; DESIGN 3.2 should state self-hosting for production).
- L156: copy says "Up to 10 min · 100 MB" while PRD/ARCH/SEC cap at 50 MB.
- L318 and JS strings use straight apostrophes ("We're"); the guideline wants curly quotes.
- Sheet and sticky nav: no `scroll-padding-bottom` so focused elements in the editor may sit under the bottom sheet or nav (WCAG 2.4.11, NFR-015). Add to the spec and test.

UX-SPEC.md
- 3.4: "Reorder clips" and "Move earlier/later" have no API operation (ARCH row 21 ops: swap, density, nudge) and conflict with the rule that cuts stay on beats; clarify what is reorderable (clip assignment per slot) and add the op.
- 3.6 offline banner and upload resume: see G-24.
- Beat pulse default on (Q10): at 180 BPM the pulse is 3 Hz, the WCAG 2.3.1 flash threshold; the effect is a small scale/opacity ring (not a luminance flash), but get a photosensitivity review before making it default, and cap at 2 Hz or off below `prefers-reduced-motion`.
- Q11 landscape editor not designed; Q12 uses 100 MB (conflict with PRD).
- Copy is sentence case ("Choose a song", "Try another song"); the web-interface guideline suggests Title Case on buttons. Record this as a deliberate deviation in DESIGN 7.
- Form rules are strong for auth (autocomplete, paste, spellcheck) but nothing is said for non-auth fields (vibe text `autocomplete="off"`, placeholder pattern with `…`, `inputmode`, `maxlength` 100 chars per SEC-040).
- Account deletion requires typing "delete": add `aria-describedby` and no paste blocking (fine) but specify the re-auth fallback for Google-only accounts.
- S12 copy: map each row to the error-code table (G-17).

DESIGN.md
- 3.2: confirm fonts are self-hosted and preloaded (`font-display: swap`), 70 KB budget includes Bricolage Grotesque variable range used in the mockup.
- 13 "Web Interface Guidelines check" says `theme-color` passes: fix the mockup or the doc.

### 5.3 Screen to story map

| Screen | PRD stories | Notes |
|---|---|---|
| S1 Landing | none | No story or requirement; add a story or mark as non-functional marketing scope. |
| S2 Sign up/in | US-001, 002, 003 | OK |
| S3 Upload | US-004, 015 | OK |
| S4 Rights/match notice | US-015 | OK; blocked state undefined (OQ-01) |
| S5 Analysis | US-005 | Tap tempo, BPM entry and even grid have no story or API |
| S6 Editor | US-006, 007, 009, 010, 011, 024 | Lock, reorder, and cut nudging have no story |
| S7 Render progress | US-012, 022 | OK |
| S8 Export | US-013, 014, 016, 017 | OK |
| S9 Projects list | US-017 (partial) | Rename and list have no story |
| S10 Pricing | US-018, 019, 020 | "Notify me" waitlist has no story |
| S11 Account | US-017, 021, 025 | Password change, export my data, appearance have no stories; add stories |
| S12 Errors | US-022 | OK |
| (no screen) | US-023 | Public takedown form page and operator tool lack a screen spec |

### 5.4 Drag interactions

All 8 drag interactions in UX-SPEC 3.4 have a non-drag alternative. Gaps: the "reorder" alternative needs an API (above); the bottom-sheet handle is a button in the mockup (L215 `aria-label="Expand tools"`) which is correct; the range slider alternative is specified but not shown in the mockup.

---

## 6. Standards findings (STANDARDS.md and ARCHITECTURE.md vs sattva-production-grade-engineering)

Definition of Done check:

| DoD item | Result | Evidence or gap |
|---|---|---|
| No secrets in code/config/logs | PASS | STANDARDS 9, SEC-080, gitleaks pre-commit and CI; `.env.example` drift test. Add: the secret-store backup (who holds the Dokploy secrets if the VPS is lost). |
| Parameterised queries, ownership scoping | PASS | STANDARDS 2 (repository methods take `user_id`; 404 on other user; test per resource), 5. Gap: workers re-check ownership only in SEC-020, not in STANDARDS 12 reviewer checklist. Add a reviewer item. |
| Input validation, status codes, no leaks | PASS | Pydantic `extra="forbid"`, envelope, central handler. Gap: error code catalogue incomplete (G-17); ARCH 7 row 1 contradicts itself. |
| Layering, thin handlers | PASS | Routers, services, repositories, adapters; import-linter. |
| Central auth, protected routes | PASS | SEC-070 (unauth route inventory test), session-only. Gap: in the ROADMAP auth is built last (G-01). |
| Tests on critical path | PARTIAL | STANDARDS 6 is strong (coverage floors, mandatory test list). ROADMAP tasks do not point to the mandatory test list and no task creates the CI coverage gate before Phase 2. |
| Pinned deps, lockfile, build works | PASS | uv.lock, pnpm-lock, Beat This by commit SHA, base images by digest, FFmpeg checksum. Gap: ARCH uses `node:22-slim` while STANDARDS says "current LTS" (decide and pin; Node 22 is in maintenance by Nov 2026). |
| Style consistent | PASS | Ruff, mypy strict, ESLint strict. Pick mypy vs pyright and Prettier vs Biome in PR 1 (STANDARDS 14 admits it). |

Anti-pattern check:

| Anti-pattern | Result |
|---|---|
| String-built SQL | None; ruff `S608` should be explicitly enabled (S set is on). |
| Hardcoded secrets | None specified. |
| Endpoint without auth/ownership | Admin and public endpoints are explicit; public inventory test exists. |
| Fast hashes | argon2id (OWASP m=19 MiB, t=2, p=1). |
| God-files, logic in handlers | Rules present. |
| Swallowed errors | `except Exception: pass` banned. |
| Unpinned dependencies | Covered. |
| Root containers, `COPY . .` | Non-root `USER 10001`, `.dockerignore`. Gap: SEC-013 read-only rootfs, cap_drop and seccomp are not in the ARCH 14 service table. |
| Blocking requests on long work | Queue + 202 + SSE. |
| Disabled type checks / `any` | Banned. |

Additional standards findings:
- S-1 (MAJOR): ARCH 14 says workers use "same image as api + torch, ffmpeg". STANDARDS 14 defaults to two multi-stage targets (`api` and `worker`). The API (internet-facing) should not carry torch, ffmpeg or model weights. Make two targets mandatory.
- S-2 (MINOR): ARCH row 1 register (201 with user vs 202 always) vs STANDARDS API rule "POST create 201 plus Location". Decide 202 with a generic body.
- S-3 (MINOR): Security headers and CSP are specified in SECURITY but not in STANDARDS 13 gates; add an automated header test and CSP report-only soak to the pipeline.
- S-4 (MINOR): Redis broker holds queue and rate-limit counters with `noeviction`; memory exhaustion by abusive keys would block enqueue. Add a size alarm or move rate limits to the cache instance (OQ-7).
- S-5 (MINOR): STANDARDS 6 coverage floor "enforced from Phase 1" is not a task; add to T-1.3 done criteria.
- S-6 (MINOR): The PR template and CODEOWNERS assume GitHub (not recorded in DECISIONS).
- S-7 (MINOR): Graceful shutdown (90 s), liveness and readiness exist; add an explicit test in T-1.5 (SIGTERM during render).
- S-8 (INFO): Idempotency keys and `job_hash` are well designed; document what happens on Redis loss (24 h key store is volatile; the DB `job_hash` unique index must be the backstop).

---

## 7. Cross-document contradictions (summary for the owner)

See G-16 for the full table. The most dangerous: internal-cut tolerance (zero in DECISIONS and G2 vs 1% and 3% in QUALITY) because G2 can never pass honestly if detector recall is the 0.477 F1 that QUALITY cites; and upload cap 50 vs 100 MB because it changes R2 limits, UX copy and abuse math.

---

## 8. Proposed new ROADMAP items

IDs follow the existing scheme. "Deps" refers to existing task IDs or new ones below. Every item lists done criteria that are verifiable.

### Phase 0

| ID | Title | Deps | Done criteria |
|---|---|---|---|
| T-0.11 | Spike addenda from QUALITY 12 and 14 | T-0.1, T-0.3, T-0.8 | P0-4, P0-5, P0-9, P0-12, P0-14, P0-15 each has a recorded number; 10 videos x 5 raters rated (mean "on beat" >= 3.8); sync canary on iOS Safari, Android Chrome and desktop Chrome with 3 testers; confidence-score distribution and first band thresholds saved; early-bias decision record written. |
| T-0.12 | Decision ADRs required before Phase 1 | T-0.4, T-0.7 | ADRs accepted for: origin topology (G-02), FFmpeg 7.x vs 8.x, email provider (G-03), two-Redis topology, fingerprint vendor (OQ-07), worker sandbox plan; DECISIONS amended in the same PR; G-16 contradictions each resolved with one number. |

### Phase 1

| ID | Title | Deps | Done criteria |
|---|---|---|---|
| T-1.10 | Local dev environment and seed data | T-1.2, T-0.12 | `make dev` starts web, api, worker, Postgres, 2 Redis, MinIO, Mailpit; `make seed` adds 2 users and a synthetic click-track project; fresh-clone-to-running timed <= 15 min; no committed fixture > 200 KB. |
| T-1.11 | CI and release pipeline definition | T-1.3 | Pipeline doc and file: lint, type, unit, integration, contract diff, migration check, golden, build, Trivy, SBOM, gitleaks, import-linter; images tagged `sha-<commit>`; manual-approved deploy job; actions pinned by SHA; planted failure goes red for each gate. |
| T-1.12 | Config catalogue and `Settings` | T-1.2 | `infra/ENV.md` table complete (G-09); `.env.example` and `Settings` agree (CI test); startup fails on a missing required variable (test). |
| T-1.13 | Auth core and ownership layer | T-1.4 | Users, sessions, CSRF, email/password login and verify-email (Mailpit), repository pattern with required `user_id`; two-user authz matrix test on every route that exists at G1; unauthenticated route inventory test. |
| T-1.14 | Transactional email service | T-0.12, T-1.4 | Provider integrated behind an adapter; outbox table; templates for verify and reset; SPF, DKIM, DMARC pass for the staging domain (mail-tester >= 9/10 or equivalent header evidence); bounce webhook updates a flag. |
| T-1.15 | Edge and web hardening | T-1.8 | CSP (report-only soak), HSTS, nosniff, Referrer-Policy verified by automated header test; `testssl` grade A on staging; Traefik body limits; Cloudflare proxy and origin lock evidenced (SEC-110..114). |
| T-1.16 | Worker sandbox feasibility on the real VPS | T-1.8 | In-container tests show non-root, read-only rootfs, cap_drop ALL, no Docker socket, no route to Postgres or internet except via allowlist proxy; fallback recorded if any control is unavailable (SEC-013, 014, 131, 133). |
| T-1.17 | Supply chain baseline | T-1.3 | Hash-pinned installs, digest-pinned images, Renovate or Dependabot active, branch protection on `main`, Trivy and SBOM per build, MFA evidenced on GitHub, Cloudflare, Dokploy, Stripe, registrar (SEC-090..095, 098, 099). |
| T-1.18 | Restore proof in Phase 1 | T-1.8 | A dump is restored into a scratch database and verified; time recorded. |

### Phase 2

| ID | Title | Deps | Done criteria |
|---|---|---|---|
| T-2.16 | Model weights supply chain | T-2.2 | Weights fetched at build, SHA-256 manifest verified at start, `HF_HUB_OFFLINE=1`, start fails on mismatch (test); no bare `torch.load` (lint); licences recorded (SEC-030..033). |
| T-2.17 | LLM safety and cost controls | T-2.5 | Features-only prompt (no ID3 text); injection corpus yields valid schema or fallback; per-user daily cap, global budget alarm and kill-switch tested (SEC-040..046). |
| T-2.18 | Untrusted-input hardening | T-2.1, T-2.6 | Filename normalisation, metadata strip, decode-once canonical audio, stock download host allowlist and size and redirect limits, job payloads carry IDs only, scratch dir 0700 removed in `finally` (SEC-004, 009, 018, 019, 020, 023), each with a negative test. |
| T-2.19 | Evaluation harness modes and CI gates | T-2.12 | `ci-lite`, `nightly`, `release` modes; baselines file; paired bootstrap; determinism check; thresholds from QUALITY 5.4 fail CI on a planted regression; QM-003, 004, 009 to 012, 015 to 018, 020 to 025 reported. |
| T-2.20 | Verify-render metric completeness | T-2.9 | QM-050..052, 060..064, 067..070, 075, 077 implemented with Block/Warn levels as in QUALITY 3.3; sync canary QM-069 in CI; VMAF QM-072 on the sample set. |
| T-2.21 | Human rating tool and protocol | T-2.12 | Rating app or sheet per QUALITY 8; release gate runs QM-090..093 with a stated sample size. |
| T-2.22 | Resolve OQ-4 (normalise-all vs lazy) | T-0.3, T-0.8 | Decision recorded with benchmark numbers; T-2.7 and T-2.8 dependency order updated. |

### Phase 3

| ID | Title | Deps | Done criteria |
|---|---|---|---|
| T-3.9 | Landing (S1), legal shell and SEO basics | T-3.1 | Page meets UX-SPEC S1 acceptance; `/legal/*` routes exist; LCP <= 2.0 s on the budget profile; `robots.txt`. |
| T-3.10 | Projects list (S9) and project rename | T-3.6 | AC-S9-1..4 pass; `PATCH /projects/{id}` exists and is authz-tested; list of 200 projects INP <= 200 ms. |
| T-3.11 | Error, empty, offline and session-expiry catalogue (S12) | T-3.1 | Every row of S12 has a component and e2e test; AC-S12-1..3; error-code to message map (G-17) complete. |
| T-3.12 | UI performance budgets in CI | T-3.7 | Bundle-size and Lighthouse-CI budgets from UX-SPEC 3.5 enforced and red on a planted breach; NFR-013 verified. |
| T-3.13 | Report-an-issue and support channel | T-3.6 | `POST /reports`; auto-attached beat map and plan, no audio by default; `support@` mailbox; QM-102 counter visible in metrics. |
| T-3.14 | Tempo override extras | T-3.2 | Tap tempo, BPM entry, and "use even grid" work end to end with API ops (G-05); e2e covers each. |

### Phase 4

| ID | Title | Deps | Done criteria |
|---|---|---|---|
| T-4.10 | DMCA operator tool and notice workflow | T-4.4, T-1.14 | Operator can list, validate, action and restore notices; user notice emails sent; `strikes` ledger; counter-notice timer; tabletop passes in < 24 h; every step in `audit_log` (G-04). |
| T-4.11 | Account screen (S11) and self-service APIs | T-4.1 | Change password, email, sessions list and revoke, re-auth for deletion, `GET /me/export` produce JSON within 1 minute; AC-S11-1..4 pass. |
| T-4.12 | Age gate, consent and analytics decision | T-4.5 | Age confirmation recorded (SEC-145); cookie inventory shows only essential cookies, or a consent banner meets EDPB guidance; event schema approved (G-12). |
| T-4.13 | Privacy operations | T-4.5 | DPAs signed for each processor and stored; sub-processor list published; RoPA and DPIA screening recorded; DSAR runbook drilled; `security.txt` and `abuse@` live (SEC-144, 147, 149, 155). |
| T-4.14 | Abuse prevention | T-4.2 | Turnstile validated server-side; disposable-email and alias normalisation; queue fairness (Free gets a minimum share), per-user concurrency, compute budget alarm and render kill-switch tested (SEC-061, 063, 064, 066). |
| T-4.15 | Secrets, access and host hardening | T-1.8 | Rotation calendar set; per-bucket R2 tokens; DB roles (app, migrator, readonly) enforced; Redis ACL; host hardening checklist evidenced; staging and prod separation verified (SEC-081..084, 130..136). |
| T-4.16 | Independent pen test and 24 h fuzz | T-4.8 | Vendor booked 4 to 6 weeks before G4; 24 h mutation fuzz with 0 unresolved crashes; high/critical findings fixed and retested; incident-response tabletop held with a 72 h notification drill. |
| T-4.17 | Uptime, SLO and product telemetry | T-4.7 | External uptime monitor; SLO dashboards for the ARCH 15 table; time-to-first-video and activation KPIs computed from events. |
| T-4.18 | Audit log and security alerts | T-1.13 | Append-only `audit_log` with the SEC-121 events; alerts for SEC-122 conditions fire in a drill. |

### Phase 5

| ID | Title | Deps | Done criteria |
|---|---|---|---|
| T-5.7 | Pricing (S10), checkout and billing UI | T-5.0, T-5.1 | AC-S10-1..4; "Coming soon/Notify me" path stores consented emails; limit dialog deep-links with project preserved. |
| T-5.8 | Billing policy and refund or chargeback path | T-5.3 | Policy table (trial, proration, dunning, downgrade at period end); chargeback pauses renders and flags the account (SEC-104); restricted Stripe keys (SEC-083). |
| T-5.9 | Support operations | T-3.13 | Published support SLA, FAQ, status page; first-response test passes within the stated SLA on 3 test tickets. |

Total new items proposed: 2 + 9 + 7 + 6 + 9 + 3 = 36. Re-scoping of existing tasks (splits listed in 3.1) adds roughly 12 more sub-tasks if executed.

### Suggested ROADMAP gate edits
- G0: add P0-4, P0-5, P0-9, P0-12, P0-14 numerics; reconcile 12 vs 10 clips.
- G1: add restore proof (T-1.18), sandbox feasibility (T-1.16), auth core (T-1.13).
- G2: add QM-067, 069, 072; define hardware and song mix; resolve internal-cut tolerance.
- G3: add LCP/INP/bundle budgets (T-3.12).
- G4: list required SEC IDs by reference to SECURITY 10, add pen test, fuzz and DMCA tool drill.
- G5: define the 30-day window for the 50 activated users.

---

## 9. Verdict

The documents are internally rich and mostly consistent on product behaviour, rendering rules and engineering standards. They are NOT yet complete enough to start implementation without guessing: four blockers (auth ordering, origin topology, email delivery, DMCA operator tooling) and fourteen major gaps. The ROADMAP covers 100% of user stories and functional requirements by task, but only 26% of security controls and 24% of quality gates have an owner task. Fix the four blockers and add the proposed Phase 0 and Phase 1 items (T-0.11, T-0.12, T-1.10 to T-1.18) before G0, then fold the remaining items into the phase plans produced by the `improve` skill.
