# SaveClock Studio — Roadmap and Master To-Do

Status: DRAFT · Date: 2026-11-08 · Owner: project owner · **Rev 2.2** (reconciled to DECISIONS Rev 2.2, §8a canonical-owner rules)
Agrees with [DECISIONS.md](DECISIONS.md) (Rev 2.2, canonical). Requirements: [PRD.md](PRD.md). Related: [ARCHITECTURE.md](ARCHITECTURE.md) · [STANDARDS.md](STANDARDS.md) · [adr/](adr/) · [SECURITY.md](SECURITY.md) · [QUALITY.md](QUALITY.md) · [DESIGN.md](DESIGN.md) · [UX-SPEC.md](UX-SPEC.md) · [CHECKLIST.md](CHECKLIST.md)

## Rev 2.2 changelog (2026-11-08)

- **Rev 2.2 (final verification):** T-0.11 now measures contended load (analysis + fetch + render concurrently on one 4-vCPU worker VM, p95 per stage, worker-concurrency recommendation) (V-02); speed gates reference hard limit vs target (40/20, 180/120, 90/60, 10/5 s) (V-03); T-0.8 label "QUALITY P0-12" → G0-18 and G4 "P0 control" → "L0 control" (V-07); `lead_frames` positive = earlier (V-05).

## Rev 2.1 changelog

- **Rev 2.1 (final cross-doc fixes):** gates G0/G2 now REFERENCE QUALITY §12 (G0-x IDs) and QM IDs instead of restating numbers (superseded restated values removed; stock bar = QUALITY G0-17); endpoint and state names follow ARCHITECTURE §7/§4 (`/api/v1/...`, `POST /projects/{id}/upload` + `upload/parts` + `upload/complete`, `POST /feedback`, `POST /me/data-export`); Mode A audio source = validated original (DECISIONS §8a); re-attach starts a new 72 h clock; pricing "Notify me" cut; editor ops `move_clip`/`nudge_cut`; benchmarks on 4 vCPU with 4 threads; hard set ungated; traceability re-run for SEC-024..029, SEC-156, QM-026, QM-085..087 (Appendix A: 122 SEC, 78 QM, 58 gating QM, 0 orphans).

## Rev 2 changelog

- **Phase order:** minimal real auth (users, sessions, CSRF, ownership, age 16+ attestation) moved into Phase 1 (T-1.13); email verification, Google OAuth, lockout, tiers/quotas and abuse controls stay in Phase 4 (C-19, G-01).
- **Tasks:** 69 before, **126 after** (new tasks, plus splits of oversized tasks). All 36 tasks proposed in completeness-review §8 are merged under their proposed IDs; additional new tasks: T-0.13 (FFmpeg pin), T-0.14 (TransNetV2 weights), T-1.19 (worker VM + egress proxy), T-2.23 (re-attach by hash), T-2.24 (confidence/fallback ladder). Old-to-new mapping in the table below.
- **DECISIONS Rev 2 applied:** upload limits 100 MB / 10 min / >= 15 s; mode chosen after render (silent master + cut list always; Mode A = remux; separate downloads); one 72 h clock from upload-complete; re-attach by SHA-256; sign-in before upload and 16+; fingerprint warn-only wording; in-app attribution; cookie-free analytics; four queues (`analysis`, `fetch`, `render`, `maintenance`); single origin; dedicated worker VM behind an egress proxy; email provider chosen in Phase 1 with Mailpit in dev; FFmpeg >= 8.1 pinned in the spike; Free/Pro numbers deferred to T-5.0.
- **Targets split:** analysis p95 <= 20 s, draft p95 <= 120 s, render p95 <= 60 s, Mode A remux p95 <= 5 s; render fidelity (QM-064) separated from musical alignment (QM-026); internal hard cuts per QUALITY QM-036; beat co-gates per QUALITY §12.1 (G0-1…G0-5).
- **Gates:** G0 and G4 now have numeric criteria; G1, G2, G3, G5 tightened. Every task has a `Covers:` entry; Appendix A is the full traceability matrix (0 orphans for US/FR/NFR, every SEC control and every QM metric).
- **Findings applied:** C-01..C-08, C-11..C-20, C-25..C-46 where they touch this file; G-01..G-18, G-21; F-07, F-20, F-22, F-27, F-37. Endpoint names follow ARCHITECTURE §7 (C-17, G-06).

### ID mapping, old to new

| Old (Rev 1) | New (Rev 2) |
|---|---|
| T-0.0..T-0.10 | unchanged IDs; T-0.0 now runs before T-0.1; T-0.2 threshold and T-0.8 criterion aligned to QUALITY P0; new T-0.11, T-0.12, T-0.13, T-0.14 |
| T-1.1 | T-1.1a (approve DESIGN.md + UX-SPEC.md), T-1.1b (skeleton design, only if needed) |
| T-1.2 | T-1.2 (scaffold + toolchains), T-1.10 (compose/dev env), T-1.12 (env-var inventory) |
| T-1.3 | T-1.3 (CI gates), T-1.11 (release pipeline/supply chain) |
| T-1.4 | T-1.4a (API skeleton), T-1.4b (DB baseline) |
| T-1.5..T-1.9 | unchanged IDs (T-1.5 now four queues); new T-1.13..T-1.19 from completeness-review §8 plus T-1.19 (worker VM + egress proxy) |
| T-2.1..T-2.8, T-2.11..T-2.15 | unchanged IDs; T-2.7 now also depends on T-2.22; T-2.12 depends on T-2.9d/T-2.10c/T-2.11 |
| T-2.9 | T-2.9a (frame-index render), T-2.9b (watermark/tiers), T-2.9c (silent master, cut lists, Mode A remux), T-2.9d (verify_render core) |
| T-2.10 | T-2.10a (state machine + draft-first), T-2.10b (idempotency + quota), T-2.10c (SSE) |
| (new) | T-2.16..T-2.22 (completeness-review §8), T-2.23 (re-attach by hash), T-2.24 (confidence + fallback ladder) |
| T-3.2 | T-3.2a (upload + warranty, S3), T-3.2b (analysis review, S5) |
| T-3.4 | T-3.4a (FE preview engine), T-3.4b (BE proxy render) |
| T-3.0, T-3.1, T-3.3, T-3.5..T-3.8 | unchanged IDs (T-3.1 reduced to approval of UX-SPEC S3-S8 + mock); new T-3.9..T-3.14 |
| T-4.1 | T-1.13 (auth core, Phase 1) + T-4.1a (verification/reset/lockout), T-4.1b (Google OAuth), T-4.1c (auth screens) |
| T-4.2 | T-4.2a (tier policy/ownership), T-4.2b (quotas), T-4.2c (usage UI); abuse limits moved to T-4.14 |
| T-4.7 | T-4.7a (observability/alerts), T-4.7b (backups/restore drill); first restore proof now T-1.18 |
| T-4.3..T-4.6, T-4.8, T-4.9 | unchanged IDs; new T-4.10..T-4.18 |
| T-5.1 | T-5.1a (Checkout/Portal), T-5.1b (webhooks/entitlements) |
| T-5.0, T-5.2..T-5.6 | unchanged IDs; new T-5.7..T-5.9 |
| T-6.0..T-6.5 | unchanged IDs (T-6.0 now listed before T-6.1); new T-6.6 (SEC-022 deferral) |

## How to read this file

- One table per phase. Columns: checkbox, **ID**, task, **Owner**, **Deps**, **Done criteria** (verifiable), **Covers:** (the US/FR/NFR/SEC/QM/gate IDs the task implements or verifies; `—` marks process/enabler tasks).
- Owner roles: **PO** product owner, **BE** backend/API, **ML** audio/ML, **FE** frontend, **DES** design (Sonnet design subagent, reviewed by main model), **OPS** infra/devops, **LEG** counsel, **QA**.
- Time estimates are not given (none are reliable before Phase 0 results).
- Requirement IDs come from [PRD.md](PRD.md), [SECURITY.md](SECURITY.md) (SEC-xxx) and [QUALITY.md](QUALITY.md) (QM-xxx). Appendix A is generated from these `Covers:` entries.

## Process rules applied to every phase (DECISIONS §8)

| Rule | How it applies |
|---|---|
| Plans via `improve` | Each phase 1–6 starts with a plan `plans/NNN-*.md` authored by the `improve` skill (item `T-n.0`) |
| Design gate | Any UI-touching plan gets `plans/NNN-*.design.md` from a Sonnet subagent (`sattva-design-phase`), approved by the user before UI execution. Backend-only plans state "no UI — design phase skipped" |
| Gates green | format, lint, type-check, tests, build green before commit |
| Config-malware guard | Run the config-malware grep before any npm/next/vite/jest/eslint/build command, and after pull/checkout/rebase |
| DB change notice | Any schema change announced as "DB CHANGE: ... — run this SQL: ..." and acknowledged before commit |
| Pre-deploy scan | Malware scan from CHECKLIST.md section C before every push/deploy |
| Post-execution audit | `ponytail-review` on the diff after each plan; `web-interface-guidelines` on changed UI files |
| Change confirmation | Summary of changes presented and confirmed by the user before moving to the next task |
| No pushes | Never push without an explicit instruction |

## Phase overview and gates

| Phase | Goal | Exit gate |
|---|---|---|
| 0 Validation spike | Retire the biggest unknowns cheaply (incl. FFmpeg pin, TransNetV2 licence) | G0 |
| 1 Walking skeleton (incl. minimal auth) | Thinnest end-to-end slice: CI, worker VM, auth core, email, staging | G1 |
| 2 Core pipeline MVP (stock-only) | Song in, correct beat-synced MP4 out; mode chosen after render | G2 |
| 3 Editor UX + preview | Tweakable, previewable, accessible | G3 |
| 4 Accounts hardening / limits / compliance | Safe to open to strangers | G4 |
| 5 Paid launch (Stripe) | Take money; Free/Pro values fixed here | G5 |
| 6 Post-launch | AI hero shots, structure models, PWA | per-item |

### Go/no-go gates

Hardware for every speed number: 4-vCPU worker running 4 threads (DECISIONS §6, §8a). Golden set: 30 core + 20 hard tracks; gating numbers use the core set; the hard set is reported only (ungated in MVP). **Numeric thresholds live in QUALITY.md (§12 for G0, the QM catalog for G2); this table only references them by ID and never restates a number** (DECISIONS §8a).

| Gate | Criteria (all must hold) | If failed |
|---|---|---|
| **G0** (before any product code) | (1) Every **Must** row of QUALITY §12 passes: beat/alignment G0-1…G0-6, render/sync/speed G0-10…G0-16 (analysis, draft, render, Mode A remux speed targets as defined there), stock availability G0-17 and clip relevance G0-18, FFmpeg comparison G0-20…G0-25 (FFmpeg >= 8.1 build chosen and pinned, T-0.13), golden-set legality G0-26; every **Should** row (G0-8, G0-9, G0-19) passes or has a written mitigation; **G0-7 (hard set) is report-only, never a gate**. Numbers are those in QUALITY §12, not repeated here. (2) Legal: counsel engaged in writing with question list sent and a decision-by date; Pexels email sent and reply (or documented fallback after 10 business days); no blocker flagged for Mode A/B if counsel has answered. (3) Licence register complete incl. TransNetV2 weights outcome (T-0.14); decision ADRs accepted (T-0.12). | Re-plan: swap model (smaller/other MIT), narrow scope, or stop (NO-GO triggers per QUALITY §12) |
| **G1** | Walking skeleton deployed to staging (web/API/Postgres/Redis on the Dokploy VPS, workers on the worker VM); CI (format, lint, type, test, coverage floor, build, secret scan, config-malware check) green on main and red on planted failures; one stub job traverses web -> API -> 4 queues -> worker -> R2 -> download as a signed-in user; two-user authz matrix green; worker sandbox verified (non-root, no route except via egress proxy); restore-into-scratch proven; `/api/v1/health/ready` and a Sentry event verified | Do not start Phase 2 |
| **G2** | Golden-set core numbers meet QUALITY §12.1 / QM-001, QM-003, QM-004, QM-010, QM-016 (hard set reported, ungated); musical alignment QM-026; 100 consecutive renders (stated song mix, both tiers, 4-vCPU worker, 4 threads): every render passes the Block checks QM-060…064 and QM-068, no repeated clip (QM-038), internal cuts per QM-036, Mode A integrity QM-087; speed gates QM-080 (analysis), QM-085 (draft), QM-081 (render), QM-086 (Mode A remux) at the QUALITY thresholds; success rate per T-2.12; sync canary QM-069 and VMAF QM-072 pass | Fix pipeline; no UI polish |
| **G3** | UX-SPEC acceptance flows pass e2e on the NFR-021 browser matrix; axe-core 0 serious/critical; manual keyboard + screen-reader pass; preview first frame <= 3 s on 4G; LCP <= 2.5 s and the UX-SPEC §3.5 bundle/INP budgets enforced in CI; user (not agent) approves live UI | Fix before accounts |
| **G4** | (1) Counsel written sign-off on ToS, Privacy, DMCA policy, age 16+ and cookie-free analytics; DMCA agent visible in the Copyright Office directory. (2) Retention audit: 0 objects older than 73 h over >= 3 days staging plus the closed beta. (3) Security: every L0 control in SECURITY §10 checked with evidence (see Appendix A); `security-audit` 0 critical/high open; independent pen test complete with high/critical retested; 24 h mutation fuzz with 0 unresolved crashes; incident tabletop (72 h notification) held. (4) Restore drill passed: RPO <= 24 h, RTO <= 4 h measured. (5) Abuse: rate limits return 429 above threshold; 100-way concurrent quota race yields exactly cap successes; Turnstile enforced. (6) DMCA tabletop notice -> removal -> user notice -> strike in < 24 h. (7) DSAR export <= 1 min and account-deletion drill pass. (8) Closed beta >= 20 invitees for 14 days: 0 sev-1, render success >= 98%, quality pass >= 99% | No public traffic |
| **G5** | Stripe test-mode e2e green; live-mode smoke with a real card refunded; webhook idempotency tested; 30-day private beta (clock starts at beta open) with >= 50 activated users (activation per PRD §9) and render success >= 98% (inference); load test at 3x stated peak holds NFR-006/026; COGS <= $0.06/Free video | Stay free-only |

---

## Phase 0 — Validation spike

Output: `docs/SPIKE-REPORT.md` (written then, not now) with numbers for G0. No product code; scripts live in `eval/` and the scratchpad only. Golden-set manifests never contain copyrighted audio (DECISIONS §7). Golden set = 30 core + 20 hard tracks (QUALITY §12); gating numbers use the core set, the hard set is reported separately.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-0.0** | Curate the golden set legally: 30 core tracks (at least 20 pop/EDM/hip-hop) + 20 hard tracks (slow, swing, rubato, non-Western) with ground-truth beats/downbeats. | ML + LEG | — | Manifest with licence/permission per track (public-domain, CC or own); none stored in git; genre tags; annotation source recorded (hand-annotated or tapped by 2 people); dataset licences and `mir_eval` behaviour pinned (QUALITY §14 items 1-2) | NFR-001 |
| [ ] | **T-0.1** | Beat This accuracy and runtime test on the golden set. | ML | T-0.0 | `eval/beat_this/` script + CSV. Untrimmed, `min_beat_time=0`, 70 ms window. Core-set pass criteria are QUALITY §12.1 G0-1…G0-5 (QM-001, QM-003, QM-004, QM-010, QM-016). Hard set reported only, ungated (G0-7, DECISIONS §8a). Wall-clock analysis of a 4-min song on a 4-vCPU x86 worker with 4 threads (state CPU model): median and p95 over >= 50 runs against G0-13 (QM-080); `small` vs final model compared | FR-003, NFR-001, NFR-002, NFR-007, QM-001, QM-002, QM-003, QM-004, QM-006, QM-009, QM-010, QM-011, QM-012, QM-015, QM-016, QM-017, QM-080 |
| [ ] | **T-0.2** | Pexels/Pixabay 50-keyword portrait availability test. | BE | T-0.7 | Script + table: per keyword, Pexels count (`orientation=portrait`), Pixabay count (no orientation filter; report share portrait after probing), duration/resolution distribution, duplicate rate over 3 repeated requests. Pass: QUALITY §12.3 G0-17 (>= 20 portrait clips at >= 1080p per keyword for >= 80% of the 50 keywords, DECISIONS §8a); also record the exact provider CDN hostnames seen, for the egress allow-list (SECURITY SEC-025, Q-21). Rate-limit headroom computed against Pexels 200/h and Pixabay 100/60 s; Pexels `video_files` fields and Pixabay field names confirmed with one live call each (F-20, F-23) | FR-007, QM-032, SEC-025 |
| [ ] | **T-0.3** | FFmpeg frame-accuracy prototype (also the FFmpeg version test bench). | BE | T-0.13 | Normalize the mixed fps/GOP/SAR sample clip set to the mezzanine spec (DECISIONS §4). Render 30 s and 60 s videos with cuts `f_i = floor((t_i - t0) * 30 + 0.5)` and trim by frame index. Pass criteria are QUALITY §12.2 G0-10 (frame-exact rendering), G0-12 (Mode A remux from the validated original: stream copy if AAC-LC else AAC-LC 48 kHz, no other processing, DECISIONS §8a), G0-15 (render p95, QM-081) and G0-16 (remux p95, QM-086). `-progress pipe:1` verified to work under `-protocol_whitelist file`. Argument-list invocation only. Also run on candidate builds (see T-0.13) | FR-011, FR-012, FR-014, FR-015, FR-016, FR-042, NFR-003, NFR-004, NFR-006, NFR-027, QM-060, QM-061, QM-062, QM-063, QM-064, SEC-010, QM-067, QM-068, QM-081, QM-086, QM-087 |
| [ ] | **T-0.4** | Legal review kickoff. | PO + LEG | — | Counsel named and engaged in writing; briefing pack (DECISIONS §2, report legal section, PRD) sent; question list covers OQ-01, OQ-03, OQ-05, OQ-06, OQ-12, age 16+ (D-12), cookie-free analytics, safe-harbor fit for a transformation service, EU/UK exposure, ToS/Privacy/DMCA drafting scope; delivery dates agreed. Decision-by date set; on counsel silence by that date the escalation and fallback (proceed Free/closed beta only, no public launch) is recorded | NFR-024 |
| [ ] | **T-0.5** | Confirm Pexels storage and attribution terms by email; re-read Pixabay live terms. | PO | — | Email asks in writing: (a) transient storage of normalized mezzanines and TTL (per-project, 72 h), (b) delivery of transformed outputs to paying users, (c) attribution wording required in UI (in-app credits, not burned into video), (d) rate-limit uplift. Reply archived in `docs/legal/`; after 10 business days a follow-up is sent and the fallback documented (Pixabay-only / no mezzanine storage). Pixabay terms (updated 20 Oct 2026) re-read, including its request to show users the source (F-22) | FR-026, FR-040 |
| [ ] | **T-0.6** | Licence register for every MVP dependency and model. | BE + LEG | — | `docs/adr/` licence ADR: component, version, code licence, weights licence, commercial OK? Covers Beat This (MIT; note the README training-data caveat, F-01, to counsel), SigLIP 2, PySceneDetect (BSD-3), librosa (DSP only), FFmpeg build flags (LGPL/GPL decided; x264 is GPL), Dramatiq. `dbn=True` / `--dbn` needs madmom and stays banned; the plain CLI does not (F-07). Every unclear item has an owner | SEC-032 |
| [ ] | **T-0.14** | TransNetV2 weights licence check. | BE + LEG | T-0.6 | Code licence confirmed MIT (F-37); weights terms read in the repo README/release page and recorded in the licence ADR as cleared, not cleared, or asked of the author in writing. Outcome decides whether T-6.3 can start; MVP stays on PySceneDetect either way | FR-009 |
| [ ] | **T-0.7** | Obtain API keys and accounts (Pexels, Pixabay, Anthropic, Cloudflare R2, Sentry, fingerprint vendor trial, email provider trial). | OPS | — | Keys in the secret store (not in repo); each works in a smoke call; none appears in git history or logs; R2 presigned-PUT Content-Length enforcement tested (SECURITY Q-02, SEC-002); the config-malware guard (SEC-096) and pre-push scan (SEC-097) are installed on every developer machine before any Phase 0 script runs | SEC-080, SEC-002, SEC-096, SEC-097 |
| [ ] | **T-0.8** | SigLIP 2 + PySceneDetect evaluation on 100 fetched clips. | ML | T-0.2 | Aligned to QUALITY G0-18: ranking P@1 >= 0.75 on 50 keywords x 20 clips with Cohen kappa >= 0.6 between 2 raters and lift >= +10 pts over stock default order; frame-sampling cost per clip on CPU measured; PySceneDetect fixture result recorded against QUALITY §12.3 G0-19 / QM-036 and the false-reject rate is reported; second detector agreement noted | FR-008, FR-009, QM-033, QM-034, QM-035, QM-036, QM-037 |
| [ ] | **T-0.9** | Cost model update from measurements. | PO | T-0.1, T-0.3, T-0.8 | Spreadsheet/section in the spike report. Unit-cost inputs listed: worker VM, Haiku calls, fingerprint vendor, R2 storage and egress, Sentry. COGS per Free video compared with NFR-023 ($0.06) | NFR-023, QM-084 |
| [ ] | **T-0.11** | Spike addenda from QUALITY §12 and §14. | ML + QA | T-0.1, T-0.3, T-0.8 | QUALITY §12 rows G0-6 (musical alignment, QM-026), G0-7 (hard set, report only), G0-8 (confidence AUROC), G0-9, G0-11 and G0-14 (draft speed, QM-085) each have a recorded number: hard-set F1 and confidence AUROC; A/V sync canary on iOS Safari, Android Chrome and desktop Chrome with 3 testers; 10 videos x 5 raters (mean 'feels on beat' vs the QM-090 threshold); confidence-score distribution and first band thresholds saved; early-bias (`lead_frames`, positive = cut earlier) decision record written (default stays 0); **contended-load run (QUALITY G0-27):** analysis + fetch + render running concurrently on the same 4-vCPU worker VM, p95 per stage under contention reported against the hard limits (analysis 40 s, draft 180 s, render 90 s, remux 10 s) and a worker-concurrency recommendation written (one heavy stage at a time vs >= 8 vCPU vs split queues); hard-limit vs target results recorded for G0-13..G0-16 | QM-002, QM-016, QM-022, QM-023, QM-069, QM-090, QM-024, QM-026, QM-085 |
| [ ] | **T-0.12** | Decision ADRs required before Phase 1. | PO + BE | T-0.4, T-0.7 | ADRs accepted and DECISIONS amended in the same PR for: single origin (formalises DECISIONS §3), email provider (Postmark, Resend or SES), two-Redis topology, fingerprint vendor (OQ-07; audio-scope per NFR-018), dedicated worker VM and egress-proxy design, FFmpeg pin (from T-0.13), per-project mezzanines vs OQ-4 default. Every number conflict from G-16 resolved with one value | NFR-018 |
| [ ] | **T-0.13** | FFmpeg version pin decision. | BE | — | Run the T-0.3 templates and golden render tests on FFmpeg 8.1.x and the 9.0.x line (7.1.x only as a control); compare frame-accuracy, speed, and the CVE list for each; pick the pin (>= 8.1) with source checksum and configure flags, passing QUALITY §12.4 G0-20…G0-25 (incl. hostile playlist/concat tests for `-protocol_whitelist file` + forced `-f`, SEC-010/011); record in the licence/FFmpeg ADR and DECISIONS §3 | SEC-017, FR-014, SEC-010, SEC-011, QM-072 |
| [ ] | **T-0.10** | Write the spike report and hold the G0 decision. | PO | T-0.1..T-0.9, T-0.11..T-0.14 | `docs/SPIKE-REPORT.md`; every G0 criterion marked pass/fail with evidence; DECISIONS changelog updated if anything changed; user explicitly approves 'go' | G0 |

---

## Phase 1 — Walking skeleton (incl. minimal auth)

Scope: thinnest end-to-end path with quality gates from commit one (`sattva-project-kickoff`). Minimal real users and sessions land here (DECISIONS §3) so Phases 2-3 are built user-scoped from the start; email verification, Google OAuth, tiers and quotas stay in Phase 4. Fake processing is allowed ONLY behind a clearly named stub that Phase 2 removes. Repo created only after G0 and user approval (DECISIONS §7). Endpoint names follow ARCHITECTURE §7 under `/api/v1` (`/health/live|ready`, `POST /projects`, `/projects/{id}/upload` + `/upload/parts` + `/upload/complete`, `/projects/{id}/events`).

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-1.0** | Author the Phase 1 plan with the `improve` skill (`plans/001-walking-skeleton.md`), design gate stated. | PO | G0 | Plan lists files, gates, rollback; states 'UI: minimal shell + sign-in only, design spec approved' or 'design phase skipped' with reason | — |
| [ ] | **T-1.1a** | User approves DESIGN.md and UX-SPEC.md. | PO | T-1.0 | Written approval recorded; changes requested are applied to the docs | — |
| [ ] | **T-1.1b** | Skeleton design spec (only if a UI beyond the shell is built). | DES + PO | T-1.1a | `plans/001-*.design.md` produced by a Sonnet subagent using frontend-design, sattva-frontend-design-system, web-interface-guidelines; user approves explicitly. Otherwise state 'design phase skipped' | — |
| [ ] | **T-1.2** | Monorepo scaffold and pinned toolchains (DECISIONS §7). | OPS | T-1.0 | `apps/web`, `services/api`, `packages/contracts`, `infra/`, `docs/`, `plans/`, `eval/`, `scripts/check-config-malware.sh`; pinned Python 3.12, Node (current LTS, exact version pinned), FFmpeg per T-0.13, PostgreSQL 16, Redis 7; `.gitignore`; malware config guard run before the first npm command | SEC-096 |
| [ ] | **T-1.10** | Local docker-compose dev environment and seed data. | OPS | T-1.2, T-0.12 | `make dev` starts web, api, worker (profile with and without torch), Postgres 16, 2x Redis (broker `noeviction`, cache `allkeys-lru`), MinIO (or R2 dev bucket), Mailpit; `make seed` adds 2 users and a synthetic click-track project; fresh clone to running stack <= 15 min, timed; no committed fixture > 200 KB | SEC-028 |
| [ ] | **T-1.12** | Environment-variable inventory and `Settings`. | BE | T-1.2 | `infra/ENV.md` table complete (name, type, default, required, secret?, service, owner doc) including Turnstile, LLM caps, queue limits, tier limits (placeholders), `BILLING_ENABLED`, egress proxy URL, cookie names, signed-URL TTLs, per-user storage cap, upload limits (100 MB / 10 min / 15 s), 72 h retention (config refuses > 72 h); `.env.example` (names only) and `Settings` agree (CI test); startup fails on a missing required variable (test) | SEC-080 |
| [ ] | **T-1.3** | CI with all gates. | OPS | T-1.2 | Format, lint, type-check (TS strict, mypy/pyright), tests with coverage floor (STANDARDS §6) enforced from here, build, OpenAPI drift check, import-linter, secret scan, dependency scan. Red on a deliberately failing test, lint error, type error; secret scan catches a planted fake key; config-malware CI check red on seeded fixture; CI asserts `ffmpeg` and `torch` are absent from the `api` image target (SEC-027) | FR-038, SEC-096, SEC-097, SEC-027 |
| [ ] | **T-1.11** | Release pipeline and supply-chain baseline. | OPS | T-1.3 | Two Docker targets (`api` without torch/ffmpeg, `worker`) built per commit; images tagged `sha-<commit>`; Trivy fails on HIGH/CRITICAL; SBOM per image; hadolint; GitHub Actions pinned by SHA; manual-approved deploy job; no secrets in build args/layers; a planted failure goes red for each gate | SEC-085, SEC-092, SEC-093 |
| [ ] | **T-1.4a** | API skeleton: FastAPI, Pydantic v2, SQLAlchemy 2, OpenAPI export, structured logs, error envelope. | BE | T-1.2 | `/api/v1/health/live` and `/api/v1/health/ready` (DB + both Redis; ARCHITECTURE §7 #50-51); JSON logs carry request ID (propagated to workers) and no PII; central error handler with correlation ID, no stack traces; `extra="forbid"` input models; OpenAPI exported and TS client generated into `packages/contracts` with CI diff check | FR-035, FR-038, NFR-010, SEC-074, SEC-075, SEC-076, SEC-120, SEC-123 |
| [ ] | **T-1.4b** | DB baseline: Alembic and initial schema. | BE | T-1.4a | DB CHANGE notice lists exact tables at G1 (`alembic_version`, `users`, `sessions`, `jobs` stub; nothing else) and is acknowledged; migration up/down tested on a copy; separate DB roles: app (DML only), migrator (DDL) and the restricted worker role `worker_rw` (SEC-026) | SEC-084, SEC-026 |
| [ ] | **T-1.13** | Auth core and ownership layer (minimal real users and sessions). | BE + FE | T-1.4b, T-1.14 | Sign-up and login with email + password (argon2id, min length 12, breached-password check), 16+ self-declared age attestation recorded (`age_attested_at`), logout; `__Host-` httpOnly Secure SameSite=Lax session cookie on the single origin, session ID rotated on login, idle/absolute timeout; CSRF token on state-changing requests; no CORS needed (test); signup/login anti-enumeration; repository pattern with required `user_id`; two-user authz matrix test on every route that exists at G1; unauthenticated-route inventory test; basic per-IP rate limit on the auth endpoints (SEC-060, the rest of the limit table lands in T-4.14). Verification mail is sent via Mailpit but enforcement is Phase 4. DB CHANGE acknowledged | US-001, US-027, FR-029, FR-043, SEC-050, SEC-051, SEC-053, SEC-054, SEC-055, SEC-057, SEC-058, SEC-070, SEC-071, SEC-060 |
| [ ] | **T-1.14** | Transactional email service. | BE + OPS | T-0.12, T-1.4b | Provider (chosen in T-0.12) behind an adapter; `emails` outbox via the `maintenance` queue with retry; templates for verify and reset; Mailpit in dev; SPF, DKIM, DMARC pass for the staging sender domain (mail-tester >= 9/10 or header evidence); bounce/complaint webhook sets a flag. DB CHANGE acknowledged | FR-044 |
| [ ] | **T-1.5** | Workers skeleton: Dramatiq with queues `analysis`, `fetch`, `render`, `maintenance`. | BE | T-1.4a | Stub job traverses all four queues; chaos test: `kill -9` the worker mid-job and assert the job completes (re-queued, idempotent); SIGTERM during a job drains within 90 s; `max_retries` <= 2 with backoff and per-actor time limits; one process per job; broker payloads are IDs only, no PII, re-validated against Postgres by the worker through the `worker_rw` role (SEC-020, SEC-026); broker and cache are separate Redis instances with separate ACL users (SEC-028); per-stage timing logged | FR-034, NFR-012, SEC-021, SEC-065, SEC-136, SEC-020, SEC-026, SEC-028 |
| [ ] | **T-1.6** | R2 storage layer with presigned URLs and lifecycle. | BE + OPS | T-1.4a, T-0.7 | Private buckets scoped per ARCHITECTURE §9 / SEC-081 with per-bucket tokens; upload and download only via presigned URL (PUT <= 5 min, GET <= 10 min, test); unguessable server-generated object keys never derived from client input or filenames (SEC-001, SEC-004); presigned PUT signs Content-Type, HEAD size check rejects and deletes > 100 MB (SEC-002, SEC-003); downloads only via R2 S3-endpoint presigned GET, never from the app origin (SEC-007); lifecycle/cleanup deletes a test object at the configured age; bucket CORS only where R2 needs it; the four buckets `uploads`, `work`, `renders`, `backups` exist with per-bucket tokens (ARCHITECTURE §9) | FR-017, FR-027, NFR-019, SEC-072, SEC-081, SEC-140, SEC-001, SEC-002, SEC-003, SEC-004, SEC-007 |
| [ ] | **T-1.7** | Web shell: Next.js App Router, TS strict, Tailwind + tokens, generated TS client, sign-in/up pages. | FE | T-1.1a, T-1.4a, T-1.13 | Single origin `app.<domain>` (Traefik routes `/api/*` to FastAPI, rest to Next.js); page calls the API; Lighthouse accessibility >= 95 and web budgets from UX-SPEC §3.5 (LCP <= 2.5 s on the mid-range-phone 4G profile, JS size) on the shell; `dangerouslySetInnerHTML` lint ban; no secrets in the client bundle (build-output scan) | FR-038, NFR-013, NFR-014, SEC-112, SEC-115 |
| [ ] | **T-1.19** | Dedicated worker VM provisioning and egress proxy. | OPS | T-1.5, T-1.11, T-0.12 | VM provisioned with SSH key-only, no inbound ports, automatic security updates, NTP; outbound only through an allow-listed egress proxy (Pexels, Pixabay, R2, LLM, fingerprint vendor) - curl to any other host fails; worker containers non-root, read-only rootfs, cgroup CPU/memory/time limits; worker image deployable from the pipeline; analysis, fetch and render workers consume the Redis broker over a private path (outbound-initiated tunnel) and reach Postgres only as `worker_rw` (SEC-026); egress allow-list lists the exact CDN hosts confirmed in T-0.2 (SEC-025); SECURITY threat T-41 (worker pivot) tests: outbound deny test, `worker_rw` privilege audit, token-scope audit | SEC-013, SEC-014, SEC-123, SEC-130, SEC-132, SEC-024, SEC-025, SEC-026 |
| [ ] | **T-1.16** | Worker sandbox verification on the real worker VM. | OPS + QA | T-1.19 | In-container tests show non-root, read-only rootfs, `cap_drop` ALL, seccomp, no Docker socket, no route to Postgres or the internet except via the allow-list proxy; any control that is unavailable is recorded with its fallback | SEC-013, SEC-014, SEC-131, SEC-132, SEC-133, SEC-024 |
| [ ] | **T-1.8** | Deploy skeleton to staging. | OPS | T-1.3, T-1.4b, T-1.5, T-1.6, T-1.7, T-1.11, T-1.13, T-1.19 | Web + API + Postgres + Redis on the Dokploy/Traefik VPS (Postgres and Redis internal-only, external port scan clean), workers on the worker VM; separate staging and production secrets; pre-deploy scan (CHECKLIST C) clean; health checks pass; rollback to the previous image demonstrated once; Sentry receives a test error; nightly DB backup job configured | NFR-025, SEC-133, SEC-134 |
| [ ] | **T-1.15** | Edge and web hardening. | OPS + FE | T-1.8 | CSP (report-only soak), HSTS, nosniff, Referrer-Policy and `Cache-Control: private/no-store` on user endpoints verified by an automated header test; `testssl` grade A; Traefik body limits; Cloudflare proxy with WAF managed rules and origin lock evidenced | SEC-073, SEC-110, SEC-111, SEC-113, SEC-114 |
| [ ] | **T-1.17** | Supply-chain and account baseline. | OPS | T-1.3 | Hash-pinned installs (`uv.lock`, pnpm lockfile), base images pinned by digest, Renovate/Dependabot active, branch protection and required checks on `main`, MFA and hardware keys evidenced on GitHub, Cloudflare, Dokploy, Stripe, registrar, Sentry, developer disk encryption | SEC-090, SEC-091, SEC-094, SEC-095, SEC-098, SEC-099 |
| [ ] | **T-1.18** | Restore proof in Phase 1. | OPS | T-1.8 | A nightly dump (encrypted, 14-day retention) is restored into a scratch database and verified; elapsed time recorded | NFR-025, SEC-135 |
| [ ] | **T-1.9** | `ponytail-review` on the Phase 1 diff, change summary, G1 check. | PO | T-1.8, T-1.15..T-1.18 | Findings triaged with the user and accepted ones applied; G1 criteria evidenced; user confirms | G1 |

---

## Phase 2 — Core pipeline MVP (stock-only)

Mostly backend, built on the Phase 1 users/sessions (every route is authenticated and user-scoped). UI limited to a dev-only driver until Phase 3 design is approved. Draft-first flow: upload-complete triggers analysis then an automatic draft with default settings (30 s highest-energy segment); the user tweaks afterwards (C-11). Every render produces a silent master + cut list; Mode A is a fast remux chosen on the export screen, so switching modes never re-renders (DECISIONS §2).

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-2.0** | Phase 2 plan via `improve` (`plans/002-core-pipeline.md`). | PO | G1 | Plan states 'No UI - design phase skipped' for pipeline items, or links a design spec for any UI item | — |
| [ ] | **T-2.1** | Upload endpoints, `ffprobe` validation and warranty record. | BE | T-1.6, T-1.13 | Per ARCHITECTURE §7: `POST /projects`, `POST /projects/{id}/upload` (init multipart), `POST …/upload/parts`, `POST …/upload/complete`, `DELETE …/upload` (authenticated; sign-in required before upload). Limits <= 100 MB, <= 10 min, >= 15 s; formats MP3, M4A/AAC, WAV, FLAC, OGG (Vorbis/Opus); per-part presigned PUT <= 5 min with signed Content-Type (R2 Content-Length enforcement per the T-0.7 result); HEAD size check on complete; unclaimed uploads reaped in 15 min; magic-byte sniff must match MIME and extension; codec allowlist; per-user storage and concurrent-upload caps; specific rejection codes; warranty stored per upload (user, time, ToS version); the 72 h retention clock starts at upload-complete; DB CHANGE acknowledged | US-004, FR-001, FR-002, SEC-001, SEC-002, SEC-003, SEC-005, SEC-006, SEC-008, SEC-154 |
| [ ] | **T-2.2** | Analysis worker: Beat This + octave clamp + override recompute. | ML | T-2.1, T-0.1 | Beat map JSON validated by schema; p95 <= 20 s for a 4-min song on the 4-vCPU worker (4 torch threads; fingerprint runs in parallel and is excluded); half/double recompute without re-upload; BPM within 70-180 after clamp; F1 gate is carried by T-2.12 using this task's output | US-005, FR-003, NFR-002, NFR-007 |
| [ ] | **T-2.3** | Energy segmenter snapped to downbeats and segment selection. | ML | T-2.2 | Every boundary is a downbeat (test); default highest-energy segment for 15/30/60 s; output duration exactly N x 30 frames; section boundary hit-rate and energy kappa measured on the golden set | US-006, FR-004, FR-005, QM-018, QM-020, QM-021 |
| [ ] | **T-2.4** | Cut-plan generator (data-driven rules table, versioned) and plan validator. | ML | T-2.3 | Cut frames `f_i = floor((t_i - t0) * fps + 0.5)` using `math.floor(x + 0.5)`, never Python `round()`; `lead_frames` field default 0; shot lengths are index differences; every cut on a beat; first cut per section on a downbeat; density control monotonic (property test); rules table version stored per render; plan validator checks integer-frame purity, rounding error <= 16.7 ms and heuristic compliance | US-011, FR-012, FR-013, FR-024, QM-050, QM-051, QM-052, QM-026 |
| [ ] | **T-2.5** | Vibe to keywords service (Claude Haiku, strict schema, fallback table). | BE | T-0.7 | Follows `sattva-llm-features`: invalid JSON, timeout (8 s), refusal and 429 each trigger the fallback in tests; one repair retry; max_tokens 300; <= 8 keywords; prompt versioned; cost per call logged; golden prompts test; JSON validity >= 99% on recorded fixtures | US-007, FR-006, QM-030 |
| [ ] | **T-2.22** | Resolve OQ-4: normalize-all vs lazy top-K. | ML + BE | T-0.3, T-0.8 | Decision recorded with benchmark numbers (default: rank on low-res frames, normalize only top-K ~1.3x cuts); T-2.7 / T-2.8 dependency order updated | — |
| [ ] | **T-2.6** | Stock fetch workers (Pexels primary, Pixabay secondary). | BE | T-0.5, T-2.5 | Recorded-fixture tests; respects 200/h Pexels and 100/60 s Pixabay with backoff and a global token bucket; keys server-side only; no persistent mirror (mezzanines live per project and die at 72 h); attribution metadata captured per clip; search-yield measured | FR-007, FR-040, SEC-067, SEC-068, QM-032 |
| [ ] | **T-2.7** | Clip ranking (SigLIP 2) and shot-cut rejection (PySceneDetect). | ML | T-2.6, T-2.22, T-0.8 | Fixtures: clips with internal cuts always rejected; no repeat in a plan (property test) unless pool exhausted; technical floor enforced (>= 720p, >= 24 fps, duration); ranking reproducible given seed; near-duplicate and diversity warnings; internal-cut target = QUALITY QM-036 / G0-19 (detector check plus the 100-segment human audit) | FR-008, FR-009, FR-010, NFR-005, QM-033, QM-034, QM-035, QM-036, QM-037, QM-038, QM-039, QM-040, QM-041 |
| [ ] | **T-2.8** | Mezzanine normalizer and the audited FFmpeg runner. | BE | T-0.3, T-0.13 | Single `ffmpeg_runner` builds all argv (SAST bans `shell=True`/`os.system`); `-protocol_whitelist file` only, forced `-f` from sniffed type, probe limits, non-root, cgroup limits; ffprobe asserts 1080x1920, 30 fps CFR, yuv420p, SAR 1, common timescale on 30 diverse inputs; FFmpeg is the pinned build >= 8.1; every FFmpeg/ffprobe call runs as a short-lived no-network child with an empty environment (SEC-029) | FR-011, FR-014, SEC-010, SEC-011, SEC-012, SEC-015, SEC-016, SEC-017, SEC-029 |
| [ ] | **T-2.9a** | Renderer part 1: frame-index render and untouched-audio mux. | BE | T-2.4, T-2.7, T-2.8 | Silent master rendered from normalized clips with trim by frame index; audio source for Mode A = the validated original `audio_source` (DECISIONS §8a), trimmed once for the segment; no gain, loudness, EQ or other processing; unit + render tests on cut error and drift | FR-012, FR-015, NFR-003, NFR-004 |
| [ ] | **T-2.9b** | Renderer part 2: watermark and tier variants. | BE | T-2.9a | 720p + watermark (Free) and 1080p (Pro) from the same plan; watermark asset spec (SVG source, PNG at 720p, opacity, position outside platform UI safe zones, `watermark_version` stored per render, OQ-10); present iff Free | FR-016, FR-030 |
| [ ] | **T-2.9c** | Renderer part 3: silent master + cut lists, Mode A remux and downloads. | BE | T-2.9a | Every render yields a silent master MP4 + JSON and CSV cut lists as separate downloads; Mode A = fast remux onto the silent master (video stream untouched) of the validated original `audio_source`, trimmed to the segment, stream-copied when AAC-LC else transcoded once to AAC-LC 48 kHz, no other processing (DECISIONS §8a); speed per QM-086, integrity per QM-087; switching modes never re-renders and consumes no extra quota (one unit per plan version); owner-only signed GET URLs <= 10 min, repeat downloads within retention; user uploads never served from the app origin | US-013, US-014, FR-017, FR-018, FR-042, NFR-027, SEC-007, QM-086, QM-087 |
| [ ] | **T-2.9d** | Renderer part 4: `verify_render` core checks. | BE + QA | T-2.9a, T-2.9c | Runs on every render and fails the job on Block-level breach (QUALITY §7): container/stream probe, CFR, frame count, duration, cut position error (any > 1 frame blocks), A/V drift, playability, output sanity (exactly 1 video + <= 1 audio stream), size/bitrate warn; results stored | FR-036, QM-060, QM-061, QM-062, QM-063, QM-064, QM-068, QM-075, QM-076, QM-077 |
| [ ] | **T-2.10a** | Job state machine, orchestrator and draft-first automation. | BE | T-2.9c, T-2.2, T-2.6 | ARCHITECTURE §4 state machine; upload-complete triggers analysis then an automatic draft with defaults; timeout kills the FFmpeg process tree (5 min hard render timeout); 1-2 retries; draft (upload-complete to draft ready) measured per stage against QM-085 | US-008, FR-020, NFR-009, NFR-026, QM-085 |
| [ ] | **T-2.10b** | Idempotency and quota reserve/refund. | BE | T-2.10a | Same inputs map to the same job (DB `job_hash` unique index is the backstop if Redis loses keys); failed job decrements no quota (reserve then commit/refund); quota counter hooks exist with placeholder limits (values set in Phase 5) | FR-020, FR-031, US-022 |
| [ ] | **T-2.10c** | Progress SSE endpoint. | BE | T-2.10a | `GET /api/v1/projects/{id}/events` (ARCHITECTURE §7 #29) on the same origin; stage + percent at least every 5 s; reconnect resumes the correct state (test) | US-012, FR-019 |
| [ ] | **T-2.11** | Retention enforcer: one 72 h clock and 'delete now'. | BE | T-1.6, T-2.9c | Sweeper on the `maintenance` queue deletes ALL project media (song, mezzanines, intermediates, silent master, mode-A export) 72 h after upload-complete; keeps project metadata, beat map, edit plan and the song SHA-256; 'delete now' removes media synchronously within 5 min; audit query shows 0 objects older than 73 h across 3 days of staging use; purge-lag alert | US-017, FR-027, FR-028, NFR-017, SEC-140, SEC-141 |
| [ ] | **T-2.23** | Re-attach the same song by hash. | BE | T-2.11 | After media expiry the project keeps the beat map and plan; uploading a file (`POST /projects/{id}/upload` from `expired`, ARCHITECTURE §4) whose SHA-256 matches the stored hash re-attaches it and restores analysis without re-running it, and starts a new 72 h clock because it is a new upload-complete [counsel confirms]; mismatch offers a new project; endpoint + tests (UI in T-3.6) | US-028, FR-041 |
| [ ] | **T-2.24** | Beat confidence score and 4-step fallback ladder. | ML | T-2.2, T-0.11 | Confidence score per QUALITY §4; fallback energy grid auto-applied only when confidence < 0.5, with the banner flag and 'use detected beats' toggle in the API; ECE, AUROC, recall-at-10%-flag and fallback-grid F1 reported on the golden set | QM-022, QM-023, QM-024, QM-025, QM-103 |
| [ ] | **T-2.12** | Golden set, eval harness and 100-render soak in `eval/`. | QA + ML | T-2.9d, T-2.10c, T-2.11 | `eval/` scripts + manifests only. Core-set metrics meet QUALITY §12.1 / QM-001, QM-003, QM-004, QM-010, QM-016 (hard set reported, ungated); musical alignment per QM-026; 100 consecutive renders (stated song mix, both tiers, 4-vCPU worker with 4 threads) all pass QM-060…064 and QM-068, with QM-038 (no repeats), QM-036 (internal cuts) and QM-087 (Mode A integrity); speed per QM-080, QM-081, QM-085, QM-086; success rate >= 98% against a defined list of excluded user-input errors; results table committed | FR-036, NFR-001, NFR-005, NFR-009, NFR-028, QM-001, QM-002, QM-080, QM-081, QM-026, QM-085, QM-086, QM-087 |
| [ ] | **T-2.13** | Dev-only driver UI (upload, generate, download) behind a feature flag. | FE | T-2.10c, T-2.9c | Runs behind real sign-in on staging; flag off in production; not linked publicly; explicitly throwaway, so no design spec is required | US-008 |
| [ ] | **T-2.14** | Security pass on the pipeline. | BE + QA | T-2.9d, T-2.18 | Malformed-media corpus (>= 50 files incl. m3u8/concat/hostile names, probe bombs) causes no crash beyond job failure; two-user matrix: another user's project, upload, render and download returns 403/404; FFmpeg in-container tests: non-root, no network, protocol whitelist `file`; runaway job killed by cgroup; signed URLs <= 10 min | NFR-020, SEC-005, SEC-006, SEC-013, SEC-014, SEC-015, SEC-016, SEC-071, SEC-072 |
| [ ] | **T-2.16** | Model weights supply chain. | ML + BE | T-2.2 | Weights fetched at build time, SHA-256 manifest verified at start, `HF_HUB_OFFLINE=1`, start fails on mismatch (test); no bare `torch.load` (lint); torch >= 2.6; inference sandboxed with no network; licences recorded in the models manifest | SEC-030, SEC-031, SEC-032, SEC-033 |
| [ ] | **T-2.17** | LLM safety and cost controls. | BE | T-2.5 | Features-only prompt (no ID3 text); strict filter if title/artist ever used; injection corpus yields valid schema or fallback; keywords only as URL-encoded values to allow-listed hosts; per-user daily cap, global budget alarm and kill-switch tested; client wrapper logs tokens/latency; golden-prompt regression | SEC-040, SEC-041, SEC-042, SEC-043, SEC-044, SEC-045, SEC-046 |
| [ ] | **T-2.18** | Untrusted-input hardening. | BE | T-2.1, T-2.6 | Filename normalisation, metadata strip, decode-once canonical audio in the sandbox plus a byte-identical validated copy `audio_source` for Mode A (downstream stages never read the raw `uploads` object; remux runs in the no-network child), stock download host allowlist/HTTPS/size/redirect limits (SSRF test against internal IPs), job payloads carry IDs only, scratch dir 0700 removed in `finally`; each with a negative test | SEC-004, SEC-009, SEC-018, SEC-019, SEC-020, SEC-023 |
| [ ] | **T-2.19** | Evaluation harness modes and CI gates. | QA + ML | T-2.12 | `ci-lite`, `nightly` and `release` modes; baselines file; paired bootstrap; determinism check; thresholds from QUALITY §5.4 fail CI on a planted regression; all gating beat, downbeat, tempo, segment, energy, confidence and perf metrics reported | QM-001, QM-002, QM-003, QM-004, QM-005, QM-006, QM-007, QM-008, QM-009, QM-010, QM-011, QM-012, QM-013, QM-014, QM-015, QM-016, QM-017, QM-018, QM-019, QM-020, QM-021, QM-022, QM-023, QM-024, QM-025, QM-082, QM-083, QM-084, QM-026, QM-085, QM-086, QM-087 |
| [ ] | **T-2.20** | Verify-render metric completeness. | BE + QA | T-2.9d | Remaining checks with Block/Warn levels per QUALITY §3.3: cut presence, unplanned cuts (Warn), A/V start offset, sync-calibration canary (CI), black/frozen frames, VMAF on the sample set, loudness and silence warnings | QM-065, QM-066, QM-067, QM-068, QM-069, QM-070, QM-071, QM-072, QM-073, QM-074 |
| [ ] | **T-2.21** | Human rating tool and protocol. | QA | T-2.12 | Rating app or sheet per QUALITY §8; release gate runs 'feels on beat' MOS, off-beat incident rate, relevance/visual/variety MOS, A/B preference and keyword relevance with a stated sample size | QM-031, QM-090, QM-091, QM-092, QM-093 |
| [ ] | **T-2.15** | `ponytail-review` of the Phase 2 diff, change summary and G2 decision. | PO | T-2.12, T-2.14, T-2.19..T-2.21 | All G2 numbers pasted with evidence; user approves | G2 |

---

## Phase 3 — Editor UX + preview

All FE items require the approved design spec (T-3.1) before execution.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-3.0** | Phase 3 plan via `improve` (`plans/003-editor-ux.md`). | PO | G2 | Lists screens: upload, analysis review, vibe/duration, generate/progress, preview/edit, export | — |
| [ ] | **T-3.1** | Design phase: approval of UX-SPEC S3-S8 plus a clickable mock. | DES + PO | T-3.0 | Spec adds only what UX-SPEC lacks (preview proxy resolution, watermark treatment OQ-10, in-app attribution/copy-credits, re-attach flow, mode choice on export screen); mobile-first 360 px, states, WCAG 2.2 AA notes; user approval recorded in writing | NFR-022 |
| [ ] | **T-3.2a** | Upload and rights-warranty screen (S3). | FE | T-3.1 | e2e: US-004 acceptance passes with limits 100 MB / 10 min / 15 s shown; keyboard operable | US-004 |
| [ ] | **T-3.2b** | Analysis review screen (S5): waveform, beat markers, half/double tempo. | FE | T-3.1, T-2.2 | e2e: US-005 acceptance passes; waveform peaks (<= 2000 points) served by the API; low-confidence banner and toggle | US-005 |
| [ ] | **T-3.14** | Tempo override extras: tap tempo, BPM entry, even grid. | FE + BE | T-3.2b | API ops and UI work end to end; e2e covers each | US-032 |
| [ ] | **T-3.3** | Generate/progress screen with SSE. | FE | T-3.1, T-2.10c | e2e: progress updates <= 5 s; reconnect works; announced via live region; single bar spans analysis and draft build | US-012, NFR-016 |
| [ ] | **T-3.4a** | Browser preview engine (proxy clips sequenced against the song clock). | FE | T-3.1, T-3.4b | First frame <= 3 s on the 4G profile; works on Safari iOS and Chrome Android; preview vs proxy render offset <= 1 frame on 10 samples | US-009, FR-021 |
| [ ] | **T-3.4b** | Proxy render job and verification. | BE | T-2.9d | Proxy resolution decided by a bandwidth/CPU test (270x480 vs 540x960, C-23) and recorded; same cut list as the final render; wording 'preview' (not 'share') | FR-022 |
| [ ] | **T-3.5** | Clip swap, lock/reorder, cut density, segment picker and vibe chips. | FE + BE | T-3.4a | US-006, US-007 (UI), US-010, US-011 acceptance pass; swapping and locking never move cut points (test); PATCH plan ops cover swap, density, lock, `move_clip` (reorder) and `nudge_cut` (±1 beat / ±1 bar) per ARCHITECTURE §5 with their validation rules; each has a keyboard-only UI alternative (WCAG 2.5.7) | US-006, US-007, US-010, US-011, FR-023, FR-024 |
| [ ] | **T-3.6** | Export screen: mode chosen after render, credits, deletion countdown, re-attach. | FE | T-3.5, T-2.23 | User renders first, then picks Mode A (with song) or Mode B (silent MP4 + JSON + CSV as separate downloads) on the export screen; switching takes seconds and never re-renders; in-app attribution list with 'copy credits'; countdown to the 72 h deletion; 'Delete now'; re-attach by hash flow; US-013, US-014, US-016, US-017, US-028 pass | US-013, US-014, US-016, US-017, US-028, FR-026, FR-042 |
| [ ] | **T-3.7** | Accessibility and cross-browser pass. | QA + FE | T-3.2a..T-3.6 | axe-core 0 serious/critical on all screens; manual keyboard walk-through and VoiceOver + NVDA pass; WCAG 2.2 AA criteria 2.4.11, 2.5.7, 2.5.8, 3.3.8 checked; NFR-021 browser matrix e2e green; 320 px no horizontal scroll; UX-SPEC AC-X-1..AC-X-9 as the checklist | US-024, NFR-014, NFR-015, NFR-016, NFR-021, NFR-022 |
| [ ] | **T-3.9** | Landing (S1), legal shell and SEO basics. | FE | T-3.1 | S1 acceptance; `/legal/*` routes exist; pricing shows 'Coming soon'; LCP <= 2.0 s on the budget profile; `robots.txt`; fonts self-hosted | US-034 |
| [ ] | **T-3.10** | Projects list (S9) and project rename. | FE + BE | T-3.6 | AC-S9-1..4 pass; `PATCH /projects/{id}` authz-tested; list of 200 projects INP <= 200 ms; status pills map to the ARCHITECTURE state machine | US-029 |
| [ ] | **T-3.11** | Error, empty, offline and session-expiry catalogue (S12). | FE | T-3.1 | Every S12 row has a component and e2e test; error-code to message map complete (G-17) | — |
| [ ] | **T-3.12** | UI performance budgets in CI. | FE + QA | T-3.7 | Bundle-size and Lighthouse-CI budgets from UX-SPEC §3.5 enforced; red on a planted breach | NFR-013 |
| [ ] | **T-3.13** | Report-an-issue and support channel. | FE + BE | T-3.6 | `POST /feedback` (ARCHITECTURE §7 #49) with auto-attached beat map and plan (no audio unless opted in); `support@` mailbox; report-issue rate visible in metrics | US-031, FR-045, QM-102 |
| [ ] | **T-3.8** | `web-interface-guidelines` on changed UI + `ponytail-review`; G3 decision. | PO | T-3.7, T-3.9..T-3.13 | Findings triaged and accepted ones applied; G3 numbers pasted; user approves the live UI | G3 |

---

## Phase 4 — Accounts hardening, limits, compliance

Minimal auth already exists (T-1.13); this phase adds verification, OAuth, lockout, tiers/quotas mechanism, abuse controls and compliance. Free/Pro numeric values (daily cap, allowance, price) are NOT set here; the mechanism uses config placeholders until T-5.0.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-4.0** | Phase 4 plan via `improve` (`plans/004-accounts-compliance.md`) + design spec for auth/limit/legal UI. | PO + DES | G3 | Plan + approved design spec; user approval recorded | — |
| [ ] | **T-4.1a** | Auth completion: email verification, reset, lockout. | BE | T-4.0, T-1.13, T-1.14 | Verification required at `POST /projects` (403 `email_unverified`, resend rate-limited); single-use 32+ byte tokens; password reset; progressive lockout; identical responses and timing for signup/login/reset; breached-password check; DB CHANGE acknowledged | US-003, FR-029, SEC-052, SEC-053, SEC-056 |
| [ ] | **T-4.1b** | Google OAuth. | BE | T-4.1a | Authorization Code with PKCE (S256) and signed state; denial returns to sign-in with a non-technical message; unverified Google email rejected; state/PKCE tamper tests | US-002, SEC-059 |
| [ ] | **T-4.1c** | Auth screens (S2) and verification UX. | FE | T-4.1a, T-4.0 | US-001..003 e2e pass; non-interactive Turnstile only; 16+ checkbox | US-001, US-002, US-003 |
| [ ] | **T-4.2a** | Tier policy and ownership on every resource. | BE | T-4.1a | Free = 720p + watermark, Pro = 1080p + no watermark enforced server-side; two-user matrix extended to billing/usage endpoints | FR-030, SEC-071 |
| [ ] | **T-4.2b** | Quotas and limits mechanism. | BE | T-4.2a, T-2.10b | Daily/monthly counters (UTC day; Pro counters anchored to the subscription period), atomic enforcement (100 concurrent requests yield exactly cap successes), decrement only on success; limit values are config (placeholders) | FR-031, FR-030, SEC-062 |
| [ ] | **T-4.2c** | Usage meter and limit dialog UI. | FE | T-4.2b, T-4.0 | Remaining count visible before starting; at cap Generate is disabled with reset time; US-018 e2e | US-018 |
| [ ] | **T-4.14** | Abuse prevention and rate limits. | BE | T-4.2b | Rate limits on auth, upload, render with 429s tested; Turnstile validated server-side; disposable-email and alias normalisation; queue fairness (Free gets a minimum share); per-user concurrency; compute-budget alarm and render kill-switch tested | FR-037, SEC-060, SEC-061, SEC-063, SEC-064, SEC-066 |
| [ ] | **T-4.3** | Upload fingerprinting (vendor from T-0.12): warn-only. | BE + FE | T-4.2a, T-0.7 | Mock match shows 'this may be a released track' (never the title) and a nudge to Mode B, never blocks; match logged for audit with its own retention, not a strike; vendor failure does not block; vendor receives only a short excerpt; S4 states designed | US-015, FR-025, NFR-018, SEC-143, SEC-156 |
| [ ] | **T-4.4** | DMCA: designated agent, policy page, takedown intake. | PO + LEG | T-0.4 | Agent registered in the Copyright Office directory (fee re-verified at copyright.gov; $6 per 2016-17 alerts, F-27; renew every 3 years) and visible in the public directory; renewal reminder; takedown mailbox and public form page live; contact in ToS | FR-033, SEC-150 |
| [ ] | **T-4.10** | DMCA operator tool and notice workflow. | BE | T-4.4, T-1.14 | Operator CLI or admin page behind SSO/IP allowlist: list, validate (17 USC 512(c)(3) elements), take down (delete objects, mark project), user-notice email, strike ledger table, counter-notice with 10-14 business-day restore timer; all steps in `audit_log`; strikes come only from validated notices; tabletop notice to removal to user notice to strike in < 24 h passes. DB CHANGE acknowledged | US-023, FR-033, SEC-077, SEC-151, SEC-152, SEC-153 |
| [ ] | **T-4.5** | Legal documents: ToS, Privacy, Acceptable Use; counsel sign-off. | LEG | T-0.4 | Texts in `docs/legal/` with version IDs; counsel written sign-off; ToS version recorded on each warranty; privacy notice lists processors, 72 h retention, backups (14 days), age 16+, cookie-free analytics; OQ-01, 03, 05, 12 answered and reflected in the PRD changelog | NFR-024, SEC-148 |
| [ ] | **T-4.6** | Data lifecycle: account deletion and retention disclosure. | BE | T-4.1a, T-2.11 | US-025 passes; checks defined: object listing under the user prefix empty, DB rows gone or tombstoned, Redis keys gone, backups replay tombstones; hard delete within 30 days | US-025, FR-028, SEC-142 |
| [ ] | **T-4.11** | Account screen (S11) and self-service APIs. | FE + BE | T-4.1a | Change password and email, sessions list and revoke, 'log out everywhere', re-auth for deletion (fallback for Google-only accounts), `POST /me/data-export` (ARCHITECTURE §7 #16) produces the JSON export within the stated SLA (<= 1 minute in staging); AC-S11-1..4 pass | US-030, SEC-147 |
| [ ] | **T-4.12** | Age gate, consent and analytics decision. | BE + LEG | T-4.5 | Age 16+ attestation verified end to end and consent log in place; cookie inventory shows only essential cookies; first-party, cookie-free, aggregate event schema approved so no banner is needed (counsel confirms) | US-027, FR-039, FR-043, SEC-145, SEC-146 |
| [ ] | **T-4.13** | Privacy operations. | PO + LEG | T-4.5 | DPAs signed for each processor and stored; sub-processor list published; RoPA and DPIA screening recorded; DSAR runbook drilled; `security.txt` and `abuse@` live | SEC-144, SEC-149, SEC-155 |
| [ ] | **T-4.15** | Secrets, access and host hardening. | OPS | T-1.8 | Rotation calendar set; per-bucket R2 token-scope audit script green; Redis ACL; web-VPS host hardening checklist evidenced (SSH key-only, fail2ban/CrowdSec, auto-updates, Docker socket unmounted); staging/production separation verified | SEC-081, SEC-082, SEC-130, SEC-134, SEC-136 |
| [ ] | **T-4.7a** | Observability and alerts. | OPS | T-1.8 | Sentry in web, API, workers with PII scrubber test; metrics and per-job dashboards; alerts: render failure rate > 5% over 15 min, queue age, disk, certificate expiry, DMCA inbox, auth-failure spikes, sandbox kills, purge lag | NFR-010, SEC-120, SEC-122, QM-104 |
| [ ] | **T-4.7b** | Backups and restore drill. | OPS | T-1.18 | Nightly encrypted dumps retained 14 days, stored off-host; restore drill monthly until launch then quarterly; RPO <= 24 h and RTO <= 4 h measured; deletion tombstones replayed on restore | NFR-025, SEC-135 |
| [ ] | **T-4.17** | Uptime, SLO and product telemetry. | OPS + BE | T-4.7a, T-4.12 | External uptime monitor (>= 99.5% target); SLO dashboards from the ARCHITECTURE §15 table; activation, time-to-first-video and production-monitoring events (QM-100..106) computed from first-party cookie-free events | NFR-008, NFR-011, QM-100, QM-101, QM-102, QM-103, QM-104, QM-105, QM-106 |
| [ ] | **T-4.18** | Audit log and security alerts. | BE | T-1.13 | Append-only `audit_log` with the SEC-121 events; alerts for SEC-122 conditions fire in a drill | SEC-121, SEC-122 |
| [ ] | **T-4.8** | Security review (`security-audit`, standard profile) and fixes. | BE + QA | T-4.1a..T-4.6, T-4.10, T-4.14, T-4.15, T-4.18 | Report outside repo; 0 critical/high open; NEEDS-VALIDATION items triaged | NFR-020 |
| [ ] | **T-4.16** | Independent pen test and 24 h fuzz. | QA + OPS | T-4.8 | Vendor booked 4-6 weeks before G4; 24 h mutation fuzz with 0 unresolved crashes; high/critical findings fixed and retested; incident-response tabletop with a 72 h notification drill | NFR-020 |
| [ ] | **T-4.9** | Closed beta, `ponytail-review` and G4 decision. | PO | T-4.1a..T-4.18 | Closed beta >= 20 invitees for 14 days with 0 sev-1; G4 criteria evidenced; user approves opening to the public Free tier | G4 |

---

## Phase 5 — Paid launch (Stripe)

Free/Pro numeric values are decided in T-5.0 and nowhere earlier.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-5.0** | Phase 5 plan via `improve` + design spec for pricing/checkout/billing UI; fix tier values. | PO + DES | G4 | Free daily cap, Pro monthly allowance, price ($9.99 vs $14.99 A/B), expected beta peak (renders/hour) fixed (OQ-04); billing policy table (trial, proration, dunning, downgrade at period end); approved design | — |
| [ ] | **T-5.1a** | Stripe Checkout and Customer Portal. | BE | T-5.0 | Behind feature flag; DB CHANGE acknowledged; test-mode: subscribe and manage/cancel via portal | US-019, US-021 |
| [ ] | **T-5.1b** | Webhooks and entitlement sync. | BE | T-5.1a | Signed, idempotent (processed `event.id` unique), out-of-order tolerant; subscribe, renew, fail payment, cancel, refund each update entitlement within 60 s; replay is a no-op; bad signature rejected; entitlements only from verified state; no card data on our servers | FR-032, SEC-100, SEC-101, SEC-102, SEC-103 |
| [ ] | **T-5.2** | Pro tier: 1080p, no watermark, allowance counter, priority queue. | BE + FE | T-5.1b | US-020 passes; Pro job dequeued before Free in load test; allowance anchored to `subscriptions.current_period_start/end` | US-020, FR-016, FR-030, FR-034 |
| [ ] | **T-5.7** | Pricing (S10), checkout and billing UI. | FE | T-5.0, T-5.1a | AC-S10-1..4; pre-launch Pro card is static 'Coming soon' text with no form and no email capture (DECISIONS §8a); limit dialog deep-links with the project preserved | US-033 |
| [ ] | **T-5.3** | Legal/tax: billing terms, refund policy, VAT/sales-tax decision, invoices. | LEG + PO | T-5.0 | Counsel sign-off; tax approach documented; test invoice correct | NFR-024 |
| [ ] | **T-5.8** | Billing policy and refund/chargeback path. | BE | T-5.3 | Chargeback pauses renders and flags the account; restricted Stripe keys with separate test/live keys | SEC-083, SEC-104 |
| [ ] | **T-5.4** | Capacity and cost validation: load test at 3x expected beta peak. | OPS + QA | T-5.2 | At the peak stated in T-5.0: render p95 <= 60 s, draft p95 <= 120 s, Pro queue wait p95 <= 30 s (inference), COGS <= $0.06 per Free video; decision on serverless GPU only if profiling justifies | NFR-006, NFR-023, NFR-026, QM-084 |
| [ ] | **T-5.9** | Support operations. | PO | T-3.13 | Published support SLA, FAQ, status page; first-response test passes within the SLA on 3 test tickets | — |
| [ ] | **T-5.5** | Public-launch checklist (CHECKLIST D) fully ticked; live-mode smoke payment refunded. | PO | T-5.1b, T-5.2, T-5.3, T-5.4, T-5.7..T-5.9 | Every CHECKLIST D item checked with an evidence link; pre-deploy scan clean | — |
| [ ] | **T-5.6** | `ponytail-review`, G5 decision, user explicitly instructs the deploy. | PO | T-5.5 | G5 numbers evidenced, incl. the production metrics QM-100…QM-106 observed during the private beta; written go from the user | G5, QM-100, QM-101, QM-102, QM-103, QM-104, QM-105, QM-106 |

---

## Phase 6 — Post-launch

Each item needs its own plan, design gate if UI, and mini-gate.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-6.0** | Vendor and pricing re-research for AI video. | PO | G5 | Current prices from official pages, API sunset status, latency, 9:16 support | — |
| [ ] | **T-6.1** | AI hero shots + credits ledger. | PO + BE | G5, T-6.0 | Vendor supports 9:16 and commercial terms verified in writing; cost per hybrid video <= $0.80 over the free tier; ledger consumes credits only on success; follows `sattva-llm-features` | US-026 |
| [ ] | **T-6.2** | Structure models (SongFormer / allin1) after licence clearance. | ML + LEG | G5 | Weights and backbone licences cleared in writing; boundary hit-rate@0.5 s beats the DSP segmenter on the golden set; no regression in NFR-007 | — |
| [ ] | **T-6.3** | TransNetV2 shot detection (code MIT; weights per T-0.14). | ML | G5, T-0.14 | Weights terms cleared per T-0.14; false-reject rate on the fixture lower than PySceneDetect | — |
| [ ] | **T-6.4** | PWA (installable, offline shell only). | FE | G5 | Lighthouse PWA checks pass; no caching of user media in the service worker; 72 h retention unaffected | — |
| [ ] | **T-6.5** | Review decisions to relax (Mode-A re-download limits, retention, public share, premium stock, licensed-music partner). | PO + LEG | G5 | Each change recorded in DECISIONS.md with date and rationale; public share only with counsel sign-off | — |
| [ ] | **T-6.6** | Optional stronger sandbox (gVisor/Firecracker) for the analysis worker. | OPS | G5 | Decision recorded after profiling; deliberately deferred P2 control | SEC-022 |

---

## Item count summary

Phase 0: 15 · Phase 1: 22 · Phase 2: 30 · Phase 3: 17 · Phase 4: 24 · Phase 5: 11 · Phase 6: 7 = **126 items** (69 in Rev 1), 6 gates (G0–G5).

## Open questions

| ID | Question |
|---|---|
| RQ-1 | Thresholds marked (inference) in gates (>= 40/50 keywords, 30 s Pro queue wait, 50 beta users, 20 closed-beta invitees) are proposals; approve or change |
| RQ-2 | DMCA agent fee: only 2016–17 secondary sources found ($6); confirm the current fee on copyright.gov at registration (F-27) |
| RQ-3 | Pexels attribution wording: not retrieved verbatim; confirm in T-0.5 (F-19, F-20) |
| RQ-4 | No time estimates given; add after Phase 0 results |
| RQ-5 | Pen-test vendor and date (SEC Q-17): book 4–6 weeks before G4 (T-4.16) |

---

## Appendix A — Traceability (requirement ID to task IDs)

Generated from the `Covers:` entries above. "Phase / gate" for SEC and QM is the earliest phase of an owning task; SEC controls are all MVP/pre-launch (P0/P1) except SEC-022 and SEC-104 (P2), which are owned too. QM gate set = metrics whose QUALITY.md level is CI, Release or Block.

### A.1 Coverage result

| Category | Total | Owned by >= 1 task | Orphans |
|---|---|---|---|
| User stories US-001..034 | 34 | 34 (100%) | 0 |
| Functional FR-001..045 | 45 | 45 (100%) | 0 |
| Non-functional NFR-001..028 | 28 | 28 (100%) | 0 |
| SECURITY controls SEC (all 122 defined in SECURITY.md incl. P2; Rev 2.1 adds SEC-024..029 and SEC-156) | 122 | 122 (100%) | 0 |
| QUALITY gate metrics (CI/Release/Block; Rev 2.1 adds QM-026, QM-085, QM-086, QM-087) | 58 | 58 (100%) | 0 |
| QUALITY metrics, all 78 defined QM | 78 | 78 (100%) | 0 |

Deliberately deferred (still owned, but not before launch): **SEC-022** (optional gVisor/Firecracker sandbox, P2) -> T-6.6; **SEC-104** (chargeback path, P2) -> T-5.8, Phase 5; all billing controls SEC-083, SEC-100..103 -> Phase 5 (Stripe is off until then); **US-026** -> T-6.1 (Later). No MVP SEC control and no gating QM is without an owner task. Rev 2.1 re-run: SEC-024/025/026 -> T-1.19 (+T-1.16, T-0.2, T-1.4b, T-1.5), SEC-027 -> T-1.3, SEC-028 -> T-1.5/T-1.10, SEC-029 -> T-2.8, SEC-156 -> T-4.3; QM-026 -> T-0.11/T-2.4/T-2.12/T-2.19, QM-085 -> T-0.11/T-2.10a/T-2.12/T-2.19, QM-086 and QM-087 -> T-0.3/T-2.9c/T-2.12/T-2.19; earlier-phase tags in SECURITY/QUALITY now have a Phase-0/1 co-owner task (e.g., SEC-001/002/003/004/007 -> T-1.6, SEC-010 -> T-0.3/T-0.13, QM-067/068 -> T-0.3).

Verification note: a task *owns* an ID when its done criteria implement or measure it. Metrics first measured in the Phase 0 spike (T-0.x) are enforced as CI/release gates by T-2.12 and T-2.19.

### A.2 User stories, functional and non-functional requirements

| Requirement | Tasks |
|---|---|
| US-001 | T-1.13, T-4.1c |
| US-002 | T-4.1b, T-4.1c |
| US-003 | T-4.1a, T-4.1c |
| US-004 | T-2.1, T-3.2a |
| US-005 | T-2.2, T-3.2b |
| US-006 | T-2.3, T-3.5 |
| US-007 | T-2.5, T-3.5 |
| US-008 | T-2.10a, T-2.13 |
| US-009 | T-3.4a |
| US-010 | T-3.5 |
| US-011 | T-2.4, T-3.5 |
| US-012 | T-2.10c, T-3.3 |
| US-013 | T-2.9c, T-3.6 |
| US-014 | T-2.9c, T-3.6 |
| US-015 | T-4.3 |
| US-016 | T-3.6 |
| US-017 | T-2.11, T-3.6 |
| US-018 | T-4.2c |
| US-019 | T-5.1a |
| US-020 | T-5.2 |
| US-021 | T-5.1a |
| US-022 | T-2.10b |
| US-023 | T-4.10 |
| US-024 | T-3.7 |
| US-025 | T-4.6 |
| US-026 | T-6.1 |
| US-027 | T-1.13, T-4.12 |
| US-028 | T-2.23, T-3.6 |
| US-029 | T-3.10 |
| US-030 | T-4.11 |
| US-031 | T-3.13 |
| US-032 | T-3.14 |
| US-033 | T-5.7 |
| US-034 | T-3.9 |
| FR-001 | T-2.1 |
| FR-002 | T-2.1 |
| FR-003 | T-0.1, T-2.2 |
| FR-004 | T-2.3 |
| FR-005 | T-2.3 |
| FR-006 | T-2.5 |
| FR-007 | T-0.2, T-2.6 |
| FR-008 | T-0.8, T-2.7 |
| FR-009 | T-0.14, T-0.8, T-2.7 |
| FR-010 | T-2.7 |
| FR-011 | T-0.3, T-2.8 |
| FR-012 | T-0.3, T-2.4, T-2.9a |
| FR-013 | T-2.4 |
| FR-014 | T-0.3, T-0.13, T-2.8 |
| FR-015 | T-0.3, T-2.9a |
| FR-016 | T-0.3, T-2.9b, T-5.2 |
| FR-017 | T-1.6, T-2.9c |
| FR-018 | T-2.9c |
| FR-019 | T-2.10c |
| FR-020 | T-2.10a, T-2.10b |
| FR-021 | T-3.4a |
| FR-022 | T-3.4b |
| FR-023 | T-3.5 |
| FR-024 | T-2.4, T-3.5 |
| FR-025 | T-4.3 |
| FR-026 | T-0.5, T-3.6 |
| FR-027 | T-1.6, T-2.11 |
| FR-028 | T-2.11, T-4.6 |
| FR-029 | T-1.13, T-4.1a |
| FR-030 | T-2.9b, T-4.2a, T-4.2b, T-5.2 |
| FR-031 | T-2.10b, T-4.2b |
| FR-032 | T-5.1b |
| FR-033 | T-4.4, T-4.10 |
| FR-034 | T-1.5, T-5.2 |
| FR-035 | T-1.4a |
| FR-036 | T-2.9d, T-2.12 |
| FR-037 | T-4.14 |
| FR-038 | T-1.3, T-1.4a, T-1.7 |
| FR-039 | T-4.12 |
| FR-040 | T-0.5, T-2.6 |
| FR-041 | T-2.23 |
| FR-042 | T-0.3, T-2.9c, T-3.6 |
| FR-043 | T-1.13, T-4.12 |
| FR-044 | T-1.14 |
| FR-045 | T-3.13 |
| NFR-001 | T-0.0, T-0.1, T-2.12 |
| NFR-002 | T-0.1, T-2.2 |
| NFR-003 | T-0.3, T-2.9a |
| NFR-004 | T-0.3, T-2.9a |
| NFR-005 | T-2.7, T-2.12 |
| NFR-006 | T-0.3, T-5.4 |
| NFR-007 | T-0.1, T-2.2 |
| NFR-008 | T-4.17 |
| NFR-009 | T-2.10a, T-2.12 |
| NFR-010 | T-1.4a, T-4.7a |
| NFR-011 | T-4.17 |
| NFR-012 | T-1.5 |
| NFR-013 | T-1.7, T-3.12 |
| NFR-014 | T-1.7, T-3.7 |
| NFR-015 | T-3.7 |
| NFR-016 | T-3.3, T-3.7 |
| NFR-017 | T-2.11 |
| NFR-018 | T-0.12, T-4.3 |
| NFR-019 | T-1.6 |
| NFR-020 | T-2.14, T-4.8, T-4.16 |
| NFR-021 | T-3.7 |
| NFR-022 | T-3.1, T-3.7 |
| NFR-023 | T-0.9, T-5.4 |
| NFR-024 | T-0.4, T-4.5, T-5.3 |
| NFR-025 | T-1.8, T-1.18, T-4.7b |
| NFR-026 | T-2.10a, T-5.4 |
| NFR-027 | T-0.3, T-2.9c |
| NFR-028 | T-2.12 |

### A.3 SECURITY controls

| Control | Tasks | Earliest phase |
|---|---|---|
| SEC-001 | T-2.1, T-1.6 | 1 |
| SEC-002 | T-2.1, T-0.7, T-1.6 | 0 |
| SEC-003 | T-2.1, T-1.6 | 1 |
| SEC-004 | T-2.18, T-1.6 | 1 |
| SEC-005 | T-2.1, T-2.14 | 2 |
| SEC-006 | T-2.1, T-2.14 | 2 |
| SEC-007 | T-2.9c, T-1.6 | 1 |
| SEC-008 | T-2.1 | 2 |
| SEC-009 | T-2.18 | 2 |
| SEC-010 | T-2.8, T-0.3, T-0.13 | 0 |
| SEC-011 | T-2.8, T-0.13 | 0 |
| SEC-012 | T-2.8 | 2 |
| SEC-013 | T-1.19, T-1.16, T-2.14 | 1 |
| SEC-014 | T-1.19, T-1.16, T-2.14 | 1 |
| SEC-015 | T-2.8, T-2.14 | 2 |
| SEC-016 | T-2.8, T-2.14 | 2 |
| SEC-017 | T-0.13, T-2.8 | 0 |
| SEC-018 | T-2.18 | 2 |
| SEC-019 | T-2.18 | 2 |
| SEC-020 | T-2.18, T-1.5 | 1 |
| SEC-021 | T-1.5 | 1 |
| SEC-022 | T-6.6 | 6 |
| SEC-023 | T-2.18 | 2 |
| SEC-024 | T-1.16, T-1.19 | 1 |
| SEC-025 | T-0.2, T-1.19 | 0 |
| SEC-026 | T-1.4b, T-1.5, T-1.19 | 1 |
| SEC-027 | T-1.3 | 1 |
| SEC-028 | T-1.5, T-1.10 | 1 |
| SEC-029 | T-2.8 | 2 |
| SEC-030 | T-2.16 | 2 |
| SEC-031 | T-2.16 | 2 |
| SEC-032 | T-0.6, T-2.16 | 0 |
| SEC-033 | T-2.16 | 2 |
| SEC-040 | T-2.17 | 2 |
| SEC-041 | T-2.17 | 2 |
| SEC-042 | T-2.17 | 2 |
| SEC-043 | T-2.17 | 2 |
| SEC-044 | T-2.17 | 2 |
| SEC-045 | T-2.17 | 2 |
| SEC-046 | T-2.17 | 2 |
| SEC-050 | T-1.13 | 1 |
| SEC-051 | T-1.13 | 1 |
| SEC-052 | T-4.1a | 4 |
| SEC-053 | T-1.13, T-4.1a | 1 |
| SEC-054 | T-1.13 | 1 |
| SEC-055 | T-1.13 | 1 |
| SEC-056 | T-4.1a | 4 |
| SEC-057 | T-1.13 | 1 |
| SEC-058 | T-1.13 | 1 |
| SEC-059 | T-4.1b | 4 |
| SEC-060 | T-4.14, T-1.13 | 1 |
| SEC-061 | T-4.14 | 4 |
| SEC-062 | T-4.2b | 4 |
| SEC-063 | T-4.14 | 4 |
| SEC-064 | T-4.14 | 4 |
| SEC-065 | T-1.5 | 1 |
| SEC-066 | T-4.14 | 4 |
| SEC-067 | T-2.6 | 2 |
| SEC-068 | T-2.6 | 2 |
| SEC-070 | T-1.13 | 1 |
| SEC-071 | T-1.13, T-2.14, T-4.2a | 1 |
| SEC-072 | T-1.6, T-2.14 | 1 |
| SEC-073 | T-1.15 | 1 |
| SEC-074 | T-1.4a | 1 |
| SEC-075 | T-1.4a | 1 |
| SEC-076 | T-1.4a | 1 |
| SEC-077 | T-4.10 | 4 |
| SEC-080 | T-0.7, T-1.12 | 0 |
| SEC-081 | T-1.6, T-4.15 | 1 |
| SEC-082 | T-4.15 | 4 |
| SEC-083 | T-5.8 | 5 |
| SEC-084 | T-1.4b | 1 |
| SEC-085 | T-1.11 | 1 |
| SEC-100 | T-5.1b | 5 |
| SEC-101 | T-5.1b | 5 |
| SEC-102 | T-5.1b | 5 |
| SEC-103 | T-5.1b | 5 |
| SEC-104 | T-5.8 | 5 |
| SEC-110 | T-1.15 | 1 |
| SEC-111 | T-1.15 | 1 |
| SEC-112 | T-1.7 | 1 |
| SEC-113 | T-1.15 | 1 |
| SEC-114 | T-1.15 | 1 |
| SEC-115 | T-1.7 | 1 |
| SEC-120 | T-1.4a, T-4.7a | 1 |
| SEC-121 | T-4.18 | 4 |
| SEC-122 | T-4.7a, T-4.18 | 4 |
| SEC-123 | T-1.4a, T-1.19 | 1 |
| SEC-090 | T-1.17 | 1 |
| SEC-091 | T-1.17 | 1 |
| SEC-092 | T-1.11 | 1 |
| SEC-093 | T-1.11 | 1 |
| SEC-094 | T-1.17 | 1 |
| SEC-095 | T-1.17 | 1 |
| SEC-096 | T-1.2, T-1.3, T-0.7 | 0 |
| SEC-097 | T-1.3, T-0.7 | 0 |
| SEC-098 | T-1.17 | 1 |
| SEC-099 | T-1.17 | 1 |
| SEC-130 | T-1.19, T-4.15 | 1 |
| SEC-131 | T-1.16 | 1 |
| SEC-132 | T-1.19, T-1.16 | 1 |
| SEC-133 | T-1.16, T-1.8 | 1 |
| SEC-134 | T-1.8, T-4.15 | 1 |
| SEC-135 | T-1.18, T-4.7b | 1 |
| SEC-136 | T-1.5, T-4.15 | 1 |
| SEC-140 | T-1.6, T-2.11 | 1 |
| SEC-141 | T-2.11 | 2 |
| SEC-142 | T-4.6 | 4 |
| SEC-143 | T-4.3 | 4 |
| SEC-144 | T-4.13 | 4 |
| SEC-145 | T-4.12 | 4 |
| SEC-146 | T-4.12 | 4 |
| SEC-147 | T-4.11 | 4 |
| SEC-148 | T-4.5 | 4 |
| SEC-149 | T-4.13 | 4 |
| SEC-150 | T-4.4 | 4 |
| SEC-151 | T-4.10 | 4 |
| SEC-152 | T-4.10 | 4 |
| SEC-153 | T-4.10 | 4 |
| SEC-154 | T-2.1 | 2 |
| SEC-155 | T-4.13 | 4 |
| SEC-156 | T-4.3 | 4 |

### A.4 QUALITY metrics

| Metric | Gate? | Tasks | Earliest phase |
|---|---|---|---|
| QM-001 | gate | T-0.1, T-2.12, T-2.19 | 0 |
| QM-002 | gate | T-0.1, T-0.11, T-2.12, T-2.19 | 0 |
| QM-003 | gate | T-0.1, T-2.19 | 0 |
| QM-004 | gate | T-0.1, T-2.19 | 0 |
| QM-005 | report/monitor | T-2.19 | 2 |
| QM-006 | gate | T-0.1, T-2.19 | 0 |
| QM-007 | report/monitor | T-2.19 | 2 |
| QM-008 | report/monitor | T-2.19 | 2 |
| QM-009 | gate | T-0.1, T-2.19 | 0 |
| QM-010 | gate | T-0.1, T-2.19 | 0 |
| QM-011 | gate | T-0.1, T-2.19 | 0 |
| QM-012 | gate | T-0.1, T-2.19 | 0 |
| QM-013 | report/monitor | T-2.19 | 2 |
| QM-014 | report/monitor | T-2.19 | 2 |
| QM-015 | gate | T-0.1, T-2.19 | 0 |
| QM-016 | gate | T-0.1, T-0.11, T-2.19 | 0 |
| QM-017 | gate | T-0.1, T-2.19 | 0 |
| QM-018 | gate | T-2.3, T-2.19 | 2 |
| QM-019 | report/monitor | T-2.19 | 2 |
| QM-020 | gate | T-2.3, T-2.19 | 2 |
| QM-021 | gate | T-2.3, T-2.19 | 2 |
| QM-022 | gate | T-0.11, T-2.24, T-2.19 | 0 |
| QM-023 | gate | T-0.11, T-2.24, T-2.19 | 0 |
| QM-024 | gate | T-2.24, T-2.19, T-0.11 | 0 |
| QM-025 | gate | T-2.24, T-2.19 | 2 |
| QM-026 | gate | T-0.11, T-2.4, T-2.12, T-2.19 | 0 |
| QM-030 | gate | T-2.5 | 2 |
| QM-031 | gate | T-2.21 | 2 |
| QM-032 | gate | T-0.2, T-2.6 | 0 |
| QM-033 | gate | T-0.8, T-2.7 | 0 |
| QM-034 | gate | T-0.8, T-2.7 | 0 |
| QM-035 | gate | T-0.8, T-2.7 | 0 |
| QM-036 | gate | T-0.8, T-2.7 | 0 |
| QM-037 | report/monitor | T-2.7, T-0.8 | 0 |
| QM-038 | gate | T-2.7 | 2 |
| QM-039 | report/monitor | T-2.7 | 2 |
| QM-040 | report/monitor | T-2.7 | 2 |
| QM-041 | gate | T-2.7 | 2 |
| QM-050 | gate | T-2.4 | 2 |
| QM-051 | gate | T-2.4 | 2 |
| QM-052 | gate | T-2.4 | 2 |
| QM-060 | gate | T-0.3, T-2.9d | 0 |
| QM-061 | gate | T-0.3, T-2.9d | 0 |
| QM-062 | gate | T-0.3, T-2.9d | 0 |
| QM-063 | gate | T-0.3, T-2.9d | 0 |
| QM-064 | gate | T-0.3, T-2.9d | 0 |
| QM-065 | report/monitor | T-2.20 | 2 |
| QM-066 | gate | T-2.20 | 2 |
| QM-067 | gate | T-2.20, T-0.3 | 0 |
| QM-068 | gate | T-2.9d, T-2.20, T-0.3 | 0 |
| QM-069 | gate | T-0.11, T-2.20 | 0 |
| QM-070 | gate | T-2.20 | 2 |
| QM-071 | gate | T-2.20 | 2 |
| QM-072 | gate | T-2.20, T-0.13 | 0 |
| QM-073 | report/monitor | T-2.20 | 2 |
| QM-074 | report/monitor | T-2.20 | 2 |
| QM-075 | gate | T-2.9d | 2 |
| QM-076 | report/monitor | T-2.9d | 2 |
| QM-077 | gate | T-2.9d | 2 |
| QM-080 | gate | T-2.12, T-0.1 | 0 |
| QM-081 | gate | T-2.12, T-0.3 | 0 |
| QM-082 | gate | T-2.19 | 2 |
| QM-083 | gate | T-2.19 | 2 |
| QM-084 | gate | T-0.9, T-2.19, T-5.4 | 0 |
| QM-085 | gate | T-0.11, T-2.10a, T-2.12, T-2.19 | 0 |
| QM-086 | gate | T-0.3, T-2.9c, T-2.12, T-2.19 | 0 |
| QM-087 | gate | T-0.3, T-2.9c, T-2.12, T-2.19 | 0 |
| QM-090 | gate | T-0.11, T-2.21 | 0 |
| QM-091 | gate | T-2.21 | 2 |
| QM-092 | gate | T-2.21 | 2 |
| QM-093 | gate | T-2.21 | 2 |
| QM-100 | report/monitor | T-4.17, T-5.6 | 4 |
| QM-101 | report/monitor | T-4.17, T-5.6 | 4 |
| QM-102 | report/monitor | T-3.13, T-4.17, T-5.6 | 3 |
| QM-103 | report/monitor | T-2.24, T-4.17, T-5.6 | 2 |
| QM-104 | report/monitor | T-4.7a, T-4.17, T-5.6 | 4 |
| QM-105 | report/monitor | T-4.17, T-5.6 | 4 |
| QM-106 | report/monitor | T-4.17, T-5.6 | 4 |

### A.5 Gates

| Gate | Closing task |
|---|---|
| G0 | T-0.10 |
| G1 | T-1.9 |
| G2 | T-2.15 |
| G3 | T-3.8 |
| G4 | T-4.9 |
| G5 | T-5.6 |

