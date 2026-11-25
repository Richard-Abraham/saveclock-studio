# SaveClock Studio — Roadmap and Master To-Do

Status: DRAFT · Date: 2026-11-08 · Owner: project owner · **Rev 3.3 — Personal edition** (reconciled to DECISIONS Rev 3.3: §8a canonical-owner rules, §8b lawyer-free rule, §8c clarifications, §8d simplifications)
Agrees with [DECISIONS.md](DECISIONS.md) (Rev 3.3, canonical). Requirements: [PRD.md](PRD.md). Related: [ARCHITECTURE.md](ARCHITECTURE.md) · [STANDARDS.md](STANDARDS.md) · [adr/](adr/) · [SECURITY.md](SECURITY.md) · [QUALITY.md](QUALITY.md) · [DESIGN.md](DESIGN.md) · [UX-SPEC.md](UX-SPEC.md) · [CHECKLIST.md](CHECKLIST.md)

## Rev 3 changelog (2026-11-08)

- **Rev 3.3 (DECISIONS §8d + final verification fixes V3-01..V3-14):** (a) **Process listed once.** The per-phase plan/design/review rows are gone; the process is the table "Process rules applied to every phase" below. **Removed task IDs:** T-1.0, T-1.1b, T-2.0, T-3.0, T-4.0, T-5.0 (phase plan / design-spec rows; dependants now depend on the previous gate) and T-2.19, T-2.21 (see c). The gate-decision rows T-1.9, T-2.15, T-3.8, T-4.9 keep their IDs (closing tasks of G1-G4). (b) **T-0.16 is non-gating**: removed from the G0 criteria and from T-0.10's Deps. (c) **One eval script:** T-2.19 (multi-mode harness, paired bootstrap) and T-2.21 (rating tool) are merged into T-2.12 (`make eval`, owner review as a CSV sheet); VMAF parity (G0-22) and sampled VMAF (QM-072) and the paired-preference protocol (QM-093) are deferred (QM-072/QM-093 marked deferred in QUALITY, G0-22 deferred; Phase 5 row T-5.7 and Phase P row T-P.12). Active QM 77 -> 75, total active 239 -> 237. (d) **API simplifications:** streamed single upload, no signed file tokens, no `op_id`/idempotency keys, `exports` folded into `renders`, `GET/PUT /settings` + `POST /housekeeping/run` (27 endpoints, 8 tables; T-1.6, T-2.1, T-2.9c, T-2.10b, T-2.25, T-3.15). (e) **V3 fixes:** T-1.4b lists exactly `users`+`settings`, `projects`, `songs`, `jobs` (V3-01); T-0.8/T-0.11 use the single-owner protocol of QUALITY §8 (V3-02); T-0.3 -> T-0.13 -> T-0.12 order made linear (V3-04); spike-home, keyword/prompt, clip-set source, explicit T-0.10 Deps, T-1.6 vs T-2.1 scope (V3-05..V3-09); Phase 5 tasks renumbered T-5.1..T-5.6 (V3-12; old IDs T-0.14, T-6.0..T-6.4).
- **Rev 3.2 (final reconciliation, DECISIONS §8c):** traceability closed (239 active IDs, all owned; Appendix A regenerated); deferred IDs (SEC-008, 014, 028, 029, 113, 134, 140, 154, QM-105) moved from active tasks to Phase P rows; new SEC-122/136/157-164 owners added; T-0.15 extended with the `tailscale serve` verification and Caddy fallback; `worker-maint` service named in T-1.10/T-1.8; owner seeded by the baseline migration (T-1.4b); settings endpoints (T-2.25, T-3.15; renumbered in Rev 3.3); G0-1 gates on the mean (CIs reported, not gated).
- **Rev 3 (personal edition rescope):** phases are now 0 Spike, 1 Walking skeleton, 2 Core pipeline, 3 Editor UX, 4 Personal polish & ops, 5 Post-MVP extras, P Public edition (deferred). Gates are G0-G4 (G5 paid launch moved to Phase P). Removed from the active plan and listed in Phase P: accounts/auth, email, billing, tiers/quotas/watermark, DMCA and legal tooling, fingerprinting, worker VM + egress proxy, R2, re-attach, landing/pricing/legal pages, report-an-issue, account deletion, abuse limits, pen test. Phase 0 drops all legal/counsel/DMCA/Pexels-email tasks and API keys are Pexels + Anthropic only. Retained task IDs are unchanged (some tasks changed meaning; titles show it); T-0.14 and T-6.0..T-6.4 were renumbered T-5.1..T-5.6 in Rev 3.3. New IDs: T-0.15, T-0.16, T-1.20, T-1.21, T-2.25, T-3.15, T-4.19..T-4.21, T-P.x.
- **Rev 3.1 (lawyer-free rule, DECISIONS §8b):** new T-0.16 (browser-side feasibility: ONNX Runtime Web + WebCodecs, go/no-go for an on-device Phase P); Phase P starts with T-P.0 (decide browser-side processing) and contains no task that requires counsel.
- The Rev 2.2 roadmap (126 tasks, G0-G5) is archived unchanged in `archive/public-edition-rev2.2/ROADMAP.md`.

## How to read this file

- One table per phase. Columns: checkbox, **ID**, task, **Owner**, **Deps**, **Done criteria** (verifiable), **Covers:** (the US/FR/NFR/SEC/QM/gate IDs the task implements or verifies; `—` marks process/enabler tasks).
- Owner roles: **PO** product owner (the owner), **BE** backend/API, **ML** audio/ML, **FE** frontend, **DES** design (Sonnet design subagent, reviewed by main model), **OPS** infra/devops, **QA**. There is no LEG role in this edition.
- Time estimates are not given (none are reliable before Phase 0 results).
- Requirement IDs come from [PRD.md](PRD.md), [SECURITY.md](SECURITY.md) (SEC-xxx) and [QUALITY.md](QUALITY.md) (QM-xxx). Appendix A is generated from these `Covers:` entries (Rev 3.2: every active ID has an owner).

## Process rules applied to every phase (DECISIONS §8)

| Rule | How it applies |
|---|---|
| Plans via `improve` | Each phase 1-5 starts with a plan `plans/NNN-*.md` authored by the `improve` skill (no task row; the phase table lists the plan's scope) |
| Design gate | Any UI-touching plan gets `plans/NNN-*.design.md` from a Sonnet subagent (`sattva-design-phase`), approved by the user before UI execution. Backend-only plans state "no UI — design phase skipped" |
| Gates green | format, lint, type-check, tests, build green before commit |
| Config-malware guard | Run the config-malware grep before any npm/next/vite/jest/eslint/build command, and after pull/checkout/rebase |
| DB change notice | Any schema change announced as "DB CHANGE: ... — run this SQL: ..." and acknowledged before commit |
| Pre-deploy scan | Malware scan from CHECKLIST.md section C before every push/deploy |
| Post-execution audit | `ponytail-review` on the diff after each plan; `web-interface-guidelines` on changed UI files |
| Change confirmation | Summary of changes presented and confirmed by the user before moving to the next task |
| No pushes | Never push without an explicit instruction |

This table is the only place the per-phase ceremony is listed (Rev 3.3): plan -> (UI) design approval -> small steps -> gates green -> `ponytail-review` -> change summary -> owner confirmation. Each phase ends with its gate-decision row (T-1.9, T-2.15, T-3.8, T-4.9), which evidences the gate criteria only.

## Phase overview and gates

| Phase | Goal | Exit gate |
|---|---|---|
| 0 Validation spike | Retire the biggest unknowns cheaply (accuracy, stock, FFmpeg pin, contended load, Tailscale reachability; browser feasibility is a non-gating side note) | G0 |
| 1 Walking skeleton | Compose stack on the VPS behind Tailscale, health, owner seam, filesystem BlobStore, backups with a restore proof | G1 |
| 2 Core pipeline MVP (stock-only) | Song in, correct beat-synced MP4 out; mode chosen after render | G2 |
| 3 Editor UX + preview | Tweakable, previewable, accessible (design approval gate first) | G3 |
| 4 Personal polish & ops | Observability, backups drill, hardening, error handling, performance tuning | G4 |
| 5 Post-MVP extras | AI hero shots, structure models, TransNetV2, PWA (each with its own plan) | per item |
| P Public edition (deferred) | Lawyer-free public launch per DECISIONS §8b; starts with T-P.0 | own gates, defined when P starts |

### Go/no-go gates

Hardware for every speed number: 4-vCPU x86 box running 4 threads (DECISIONS §6, §8a). Golden set: 30 core + 20 hard tracks from the owner's own library; gating numbers use the core set, the hard set is reported only. **Numeric thresholds live in QUALITY.md (§12 for G0, the QM catalog for G2) and in PRD NFR rows; this table only references them by ID and never restates a number** (DECISIONS §8a).

| Gate | Criteria (all must hold) | If failed |
|---|---|---|
| **G0** (before any product code) | (1) Every **Must** row of QUALITY §12 passes (beat/alignment rows gate on the **mean** over the golden core set; 95% CIs are reported, not gated, DECISIONS §8c): beat/alignment G0-1…G0-6, render/sync/speed G0-10…G0-16, stock availability G0-17 and clip relevance G0-18, FFmpeg comparison G0-20, G0-21, G0-23…G0-25 (FFmpeg >= 8.1 build chosen and pinned, T-0.13; G0-22 VMAF parity is deferred, Rev 3.3), golden-set handling G0-26 (as rescoped in QUALITY §12 for the owner's private library); every **Should** row (G0-8, G0-9, G0-19) passes or has a written mitigation; **G0-7 (hard set) is report-only, never a gate**; contended-load result G0-27 recorded with a worker-concurrency recommendation. (2) Tailscale reachability and `tailscale serve` verification (path routing, SSE, a 100 MB streamed upload, identity headers; Caddy fallback if needed) proven from phone and laptop with a clean external port scan (T-0.15, NFR-029). (3) Licence register complete (T-0.6) and decision ADRs accepted (T-0.12). T-0.16 (browser feasibility) is **non-gating**: it never blocks or delays G0 and only informs T-P.0. | Re-plan: swap model (smaller/other MIT), narrow scope, enable Pixabay, move to a bigger box, or stop (NO-GO triggers per QUALITY §12) |
| **G1** | Walking skeleton deployed on the VPS as one compose stack reachable only at the `*.ts.net` HTTPS URL from phone and laptop; external port scan clean (NFR-029); CI-or-local `make check` (format, lint, type, test, coverage floor, build, secret scan, config-malware check) green and red on planted failures; one stub job traverses web -> API -> 4 queues -> worker -> BlobStore -> direct API file download; owner-scoping test and tailnet-guard test green; container sandbox verified (T-1.16); nightly backup ran and a restore into scratch passed (NFR-030); `/api/v1/health/ready` green | Do not start Phase 2 |
| **G2** | Golden-set core numbers meet QUALITY §12.1 / QM-001, QM-003, QM-004, QM-010, QM-016 (hard set reported, ungated); musical alignment QM-026; 100 consecutive renders (stated song mix, 4-vCPU box, 4 threads): every render passes the Block checks QM-060…064 and QM-068, no repeated clip (QM-038), internal cuts per QM-036, Mode A integrity QM-087; speed gates QM-080 (analysis), QM-085 (draft), QM-081 (render), QM-086 (Mode A remux) at the QUALITY thresholds; success rate per NFR-009 via T-2.12; sync canary QM-069 passes; offline-keyword run completes with no Anthropic key (FR-050) | Fix pipeline; no UI polish |
| **G3** | UX-SPEC acceptance flows pass e2e on the NFR-021 browser matrix; axe-core 0 serious/critical (NFR-014); manual keyboard + screen-reader pass; preview first frame within the US-009 budget; LCP per NFR-013 and the UX-SPEC §3.5 bundle/INP budgets enforced; settings screen (disk usage, Pixabay toggle) works; user (not agent) approves live UI | Fix before Phase 4 |
| **G4** | (1) Restore test passed again after the final backup configuration (NFR-025, NFR-030). (2) Housekeeping audit: 0 stale intermediates over >= 3 days of use (NFR-017) and keepers untouched. (3) `security-audit` quick profile: 0 critical/high open; external port scan clean (NFR-020, NFR-029). (4) Contended-load rerun on the deployed box meets the QM-080/081/085/086 hard limits (T-4.20). (5) Disk-pressure drill passed (T-4.21). (6) 14-day dogfood: 0 sev-1, render success per NFR-009, quality pass per PRD §9 | Fix before declaring the personal edition done |

---

## Phase 0 — Validation spike

Output: `docs/SPIKE-REPORT.md` (written then, not now) with numbers for G0. No product code; spike scripts live in a scratch directory (e.g. `~/saveclock-spike/`, Python 3.12 venv, lockfile) and are copied into `eval/` when the repo is created (V3-05). Golden-set manifests never contain audio (DECISIONS §7). API keys needed: Pexels (free) and optionally Anthropic.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-0.0** | Build the golden set from the owner's own library: 30 core tracks (at least 20 pop/EDM/hip-hop) + 20 hard tracks (slow, swing, rubato, non-Western) with ground-truth beats/downbeats. | ML + PO | — | Private manifest (paths/hashes, genre tags) kept out of git; annotation format fixed here (one `.beats` text file per track: one beat time in seconds per line, optional second column `1` marks a downbeat; made in Sonic Visualiser or tapped); no audio committed; annotation source recorded per track (owner-tapped/corrected beats, or model-seeded annotations corrected by the owner for a 20-track subset, stating which); `mir_eval` behaviour pinned (QUALITY §14 items 1-2) | NFR-001 |
| [ ] | **T-0.1** | Beat This accuracy and runtime test on the golden set. | ML | T-0.0 | `eval/beat_this/` script + CSV. Untrimmed, `min_beat_time=0`, 70 ms window. Core-set pass criteria are QUALITY §12.1 G0-1…G0-5 (QM-001, QM-003, QM-004, QM-010, QM-016). Gate on the mean over the core set; report 95% CIs but do not gate on the lower bound (DECISIONS §8c). Hard set reported only, ungated (G0-7, DECISIONS §8a). Wall-clock analysis of a 4-min song on a 4-vCPU x86 worker with 4 threads (state CPU model): median and p95 over >= 50 runs against G0-13 (QM-080); `small` vs final model compared | FR-003, NFR-001, NFR-002, NFR-007, QM-001, QM-002, QM-003, QM-004, QM-006, QM-009, QM-010, QM-011, QM-012, QM-015, QM-016, QM-017, QM-080 |
| [ ] | **T-0.2** | Pexels 50-keyword portrait availability test (Pixabay measured as fallback only). | BE | T-0.7 | Script + table: per keyword, Pexels count (`orientation=portrait`), duration/resolution distribution, duplicate rate over 3 repeated requests; Pixabay counts recorded for comparison. Pass: QUALITY §12.3 G0-17 (>= 20 portrait clips at >= 1080p per keyword for >= 80% of the 50 keywords). If Pexels passes, Pixabay stays off by default; if not, the default for the settings toggle (FR-051) is documented. Keywords: a throwaway LLM prompt and the 50-keyword list (plus fallback-table keywords) are recorded in the spike report; the production prompt and fallback table are T-2.5 outputs (V3-06). Rate-limit headroom computed against Pexels 200/h; `video_files` field names confirmed with one live call; live Pexels/Pixabay terms re-read and the outcome noted (no email needed for personal use) | FR-007, FR-051, QM-032 |
| [ ] | **T-0.3** | FFmpeg frame-accuracy prototype (builds the harness and templates; the version comparison is T-0.13). | BE | T-0.2 | Normalize the mixed fps/GOP/SAR sample clip set (8-10 Pexels clips fetched in T-0.2 plus 2 synthetic `ffmpeg testsrc` clips with odd fps/SAR) to the mezzanine spec (DECISIONS §4). Render 30 s and 60 s videos with cuts `f_i = floor((t_i - t0) * 30 + 0.5)` and trim by frame index. Pass criteria are QUALITY §12.2 G0-10 (frame-exact rendering), G0-12 (Mode A remux from the validated original: stream copy if AAC-LC else AAC-LC 48 kHz, no other processing, DECISIONS §8a), G0-15 (render p95, QM-081) and G0-16 (remux p95, QM-086). `-progress pipe:1` verified to work under `-protocol_whitelist file`. Argument-list invocation only. Runs on the default FFmpeg build here; the candidate-build comparison is T-0.13 | FR-011, FR-012, FR-014, FR-015, FR-016, FR-042, NFR-003, NFR-004, NFR-006, NFR-027, QM-060, QM-061, QM-062, QM-063, QM-064, SEC-010, QM-067, QM-068, QM-081, QM-086, QM-087 |
| [ ] | **T-0.6** | Licence register for every MVP dependency and model (kept so the app stays public-ready). | BE | — | `docs/adr/` licence ADR: component, version, code licence, weights licence, commercial OK? Covers Beat This (MIT; note the README training-data caveat), SigLIP 2, PySceneDetect (BSD-3), librosa (DSP only), FFmpeg build flags (LGPL/GPL decided; x264 is GPL), Dramatiq, Tailscale (Personal plan, non-commercial). `dbn=True` / `--dbn` needs madmom and stays banned. No counsel step: unclear items are marked for Phase P, not blocking | SEC-032 |
| [ ] | **T-0.7** | Obtain API keys and accounts: Pexels (free) and Anthropic (optional); Tailscale account. | OPS + PO | — | Tailscale auth key is tagged, single-use or ephemeral with short expiry (SEC-163); keys in a local `.env` / secret store (not in repo); Pexels key works in a smoke call; Anthropic key works or is deliberately unset (offline fallback path then tested in T-2.5); none appears in git history or logs; the config-malware guard (SEC-096) and pre-push scan (SEC-097) are installed on every developer machine before any Phase 0 script runs | SEC-080, SEC-096, SEC-097, SEC-163 |
| [ ] | **T-0.8** | SigLIP 2 + PySceneDetect evaluation on 100 fetched clips. | ML | T-0.2 | Aligned to QUALITY G0-18: ranking P@1 >= 0.75 on 50 keywords x 20 clips (owner labels) with self-agreement kappa >= 0.6 between the first pass and a blind owner re-label of 10 keywords a week later (single-owner protocol, no inter-rater statistics) and lift >= +10 pts over stock default order; frame-sampling cost per clip on CPU measured; PySceneDetect fixture result recorded against QUALITY §12.3 G0-19 / QM-036 and the false-reject rate is reported; second detector agreement noted if cheap | FR-008, FR-009, QM-033, QM-034, QM-035, QM-036, QM-037 |
| [ ] | **T-0.9** | Capacity and cost measurements from the spike. | PO | T-0.1, T-0.3, T-0.8 | Section in the spike report: disk used per project (song, mezzanines, proxies, renders) and projected space for 50 projects; Haiku cost per video against the per-video cap (A-08); CPU/RAM headroom on the target box. Reported, not gated (QM-084 reported) | QM-084 |
| [ ] | **T-0.11** | Spike addenda from QUALITY §12 and §14. | ML + QA | T-0.1, T-0.3, T-0.8 | QUALITY §12 rows G0-6 (musical alignment, QM-026), G0-7 (hard set, report only), G0-8 (confidence AUROC), G0-9, G0-11 and G0-14 (draft speed, QM-085) each have a recorded number: hard-set F1 and confidence AUROC; A/V sync canary on the owner's own devices (iOS Safari and/or Android Chrome, and desktop Chrome; wired or low-latency audio), G0-11; the owner's 20-video rubric sheet (QUALITY §8, one person, no raters) giving the QM-090 mean 'feels on beat' vs its threshold; confidence-score distribution and first band thresholds saved; early-bias (`lead_frames`, positive = cut earlier) decision record written (default stays 0); **contended-load run (QUALITY G0-27):** analysis + fetch + render running concurrently on the same 4-vCPU box, p95 per stage under contention reported against the hard limits (analysis 40 s, draft 180 s, render 90 s, remux 10 s) and a worker-concurrency recommendation written (one heavy stage at a time vs >= 8 vCPU vs split queues); hard-limit vs target results recorded for G0-13..G0-16 | QM-002, QM-016, QM-022, QM-023, QM-069, QM-090, QM-024, QM-026, QM-085 |
| [ ] | **T-0.12** | Decision ADRs required before Phase 1. | PO + BE | T-0.7, T-0.11, T-0.13 | ADRs accepted and DECISIONS amended in the same PR for: Tailscale topology (sidecar + `tailscale serve`, single origin), local-disk `BlobStore` layout, backup tool and destination (OQ-15), FFmpeg pin (from T-0.13), per-project mezzanines vs OQ-4 default, worker concurrency (from T-0.11) | — |
| [ ] | **T-0.13** | FFmpeg version pin decision. | BE | T-0.3 | Run the T-0.3 harness and templates and golden render tests on FFmpeg 8.1.x and the 9.0.x line (7.1.x only as a control); compare frame-accuracy, speed, and the CVE list for each; pick the pin (>= 8.1) with source checksum and configure flags, passing QUALITY §12.4 G0-20, G0-21, G0-23…G0-25 (G0-22 VMAF parity deferred, Rev 3.3; incl. hostile playlist/concat tests for `-protocol_whitelist file` + forced `-f`, SEC-010/011); record in the licence/FFmpeg ADR and DECISIONS §3 | SEC-017, FR-014, SEC-010, SEC-011 |
| [ ] | **T-0.15** | Tailscale reachability spike and `tailscale serve` verification (with Caddy fallback). | OPS + PO | T-0.7 | Tailscale (free Personal plan) installed on the VPS, phone and laptop; a hello page is served with `tailscale serve` over HTTPS on `*.ts.net` and opens from the phone and the laptop; ACL limits it to the owner's devices; an external port scan of the VPS public IP shows no app port open; **serve verification (DECISIONS §8c), from phone and laptop on the real VPS:** path routing `/api/*` to a stub api and `/` to a stub web; an SSE stream through the proxy arrives unbuffered (event cadence <= 2 s for 60 s); a 100 MB single streamed `POST` upload completes over the tailnet (direct and DERP-relayed if reachable); `Tailscale-User-Login` identity headers reach the upstream (or the finding is recorded; the `TRUSTED_PROXY_CIDRS` check works without them). If any check fails, the same tests are re-run against a **Caddy container on the tailnet IP** and the working proxy is recorded as the ADR-0012 topology (ARCHITECTURE §14); result recorded | US-035, FR-046, NFR-029, SEC-157, SEC-158, SEC-164 |
| [ ] | **T-0.16** | Browser-side feasibility (non-gating side note; informs Phase P only; DECISIONS §8b, §8d). | ML + FE | T-0.0, T-0.1 | Short report in the spike report with numbers and a go/no-go for a future on-device Phase P: (a) Beat This exported to ONNX and run with ONNX Runtime Web (WASM and WebGPU where available) vs the Python version on the same 50 tracks: beat F1 / AMLt / CMLt / downbeat F1 deltas (parity within noise or the gap stated), and wall-clock for a 4-min song on a mid-range phone and a laptop; (b) WebCodecs (with a muxer) rendering or remuxing a 30 s 1080p beat edit: seconds taken on the same phone and laptop vs the Mode A remux and render targets in QUALITY §12; (c) memory ceiling hit or not. Non-gating: not part of G0, may run any time before T-P.0 (after G0 is fine); the result decides T-P.0 | — |
| [ ] | **T-0.10** | Write the spike report and hold the G0 decision. | PO | T-0.1, T-0.2, T-0.3, T-0.6, T-0.7, T-0.8, T-0.9, T-0.11, T-0.12, T-0.13, T-0.15 | `docs/SPIKE-REPORT.md`; every G0 criterion marked pass/fail with evidence; DECISIONS changelog updated if anything changed; user explicitly approves 'go' | G0 |

---

## Phase 1 — Walking skeleton

Scope: thinnest end-to-end path with quality gates from commit one (`sattva-project-kickoff`): repo, gates (local `make check`; hosted CI optional), compose stack including the Tailscale sidecar and `tailscale serve`, health endpoint, baseline migration with the owner user seeded, filesystem `BlobStore`, nightly backups. Fake processing is allowed ONLY behind a clearly named stub that Phase 2 removes. Repo created only after G0 and user approval (DECISIONS §7). Endpoint names follow ARCHITECTURE §7 under `/api/v1`.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-1.1a** | User approves DESIGN.md and UX-SPEC.md. | PO | G0 | Written approval recorded; changes requested are applied to the docs | — |
| [ ] | **T-1.2** | Monorepo scaffold and pinned toolchains (DECISIONS §7). | OPS | G0 | `apps/web`, `services/api`, `packages/contracts`, `infra/`, `docs/`, `plans/`, `eval/`, `scripts/check-config-malware.sh`; pinned Python 3.12, Node (current LTS, exact version pinned), FFmpeg per T-0.13, PostgreSQL 16, Redis 7; `.gitignore`; malware config guard run before the first npm command | SEC-096 |
| [ ] | **T-1.10** | Local docker-compose dev/prod stack and seed data. | OPS | T-1.2, T-0.12 | `make dev` starts web, api, worker, worker-maint (same worker image, `maintenance` queue only; DECISIONS §8c) (worker profile with and without torch), Postgres 16, one Redis (`noeviction`) and the Tailscale sidecar (optional in dev); `make seed` creates a synthetic click-track project under the owner row already created by the baseline migration (T-1.4b); own Compose project network, no shared external networks or host mounts (SEC-164); fresh clone to running stack <= 15 min, timed; no committed fixture > 200 KB | SEC-164 |
| [ ] | **T-1.12** | Environment-variable inventory and `Settings`. | BE | T-1.2 | `infra/ENV.md` table complete (name, type, default, required, secret?, service, owner doc) including Pexels/Anthropic keys, LLM per-video cap, queue limits, Tailscale auth key, backup destination, data-volume path, upload limits (100 MB / 10 min / 15 s), housekeeping age (7 days); `.env.example` (names only) and `Settings` agree (CI test); startup fails on a missing required variable (test) | SEC-080 |
| [ ] | **T-1.3** | Local quality gates (`make check`) with optional CI mirror. | OPS | T-1.2 | One command runs format, lint, type-check (TS strict, mypy/pyright), tests with coverage floor (STANDARDS §6), build, OpenAPI drift check, import-linter, secret scan, dependency scan, config-malware check; red on a deliberately failing test, lint error, type error, a planted fake key and a seeded malware fixture; asserts `ffmpeg` and `torch` are absent from the `api` image target (SEC-027); a hosted CI run is optional and mirrors the same command | FR-038, SEC-096, SEC-097, SEC-027 |
| [ ] | **T-1.11** | Image build baseline. | OPS | T-1.3 | Two Docker targets (`api` without torch/ffmpeg, `worker`) built per commit and tagged `sha-<commit>`; hadolint clean; image scan (Trivy) run with HIGH/CRITICAL findings triaged; no secrets in build args/layers | SEC-085, SEC-092, SEC-093 |
| [ ] | **T-1.4a** | API skeleton: FastAPI, Pydantic v2, SQLAlchemy 2, OpenAPI export, structured logs, error envelope. | BE | T-1.2 | `/api/v1/health/live` and `/api/v1/health/ready` (DB + Redis; ARCHITECTURE §7 #26-27); JSON logs carry request ID (propagated to workers) and no PII; central error handler with correlation ID, no stack traces; `extra="forbid"` input models; OpenAPI exported and TS client generated into `packages/contracts` with CI diff check | FR-035, FR-038, NFR-010, SEC-074, SEC-075, SEC-076, SEC-120, SEC-123 |
| [ ] | **T-1.4b** | DB baseline: Alembic and initial schema with the owner user seeded. | BE | T-1.4a | `0001_baseline` creates exactly these tables (ARCHITECTURE §6/§21, KICKOFF §4): `alembic_version`, `users` (incl. `settings` jsonb NOT NULL DEFAULT '{}', with the owner row seeded by the baseline data migration itself: fixed UUID `00000000-0000-4000-8000-000000000001`, `OWNER_DISPLAY_NAME` from env; no manual step, `make seed` creates no user; test: fresh `alembic upgrade head` yields exactly one owner row), `projects`, `songs`, `jobs` (`render_id` a plain nullable uuid; its FK to `renders` arrives in `0002`); nothing else. The DB CHANGE notice lists exactly these and is acknowledged before commit; migration up/down tested on a copy; app role (DML only) separate from migrator (DDL) | SEC-084, FR-047 |
| [ ] | **T-1.20** | Owner identity seam and tailnet guard. | BE | T-1.4b | All repository calls require `user_id` and the API resolves it to the seeded owner; the API rejects any request not carrying the Tailscale proxy identity header/peer (test with and without); no sessions, passwords, CSRF or sign-up exist; scoping test with a second synthetic user proves queries never leak across `user_id`; unauthenticated-route inventory test (only health) | US-035, FR-047, SEC-071 |
| [ ] | **T-1.5** | Workers skeleton: Dramatiq with queues `analysis`, `fetch`, `render`, `maintenance`. | BE | T-1.4a | Stub job traverses all four queues; chaos test: `kill -9` the worker mid-job and assert the job completes (re-queued, idempotent); SIGTERM during a job drains within 90 s; `max_retries` <= 2 with backoff and per-actor time limits; one process per job; broker payloads are IDs only, re-validated against Postgres by the worker; single Redis (`noeviction`), any cache key carries a TTL; per-stage timing logged | FR-034, NFR-012, SEC-021, SEC-065, SEC-020, SEC-136 |
| [ ] | **T-1.6** | `BlobStore` filesystem adapter and path-contained file serving. | BE + OPS | T-1.4a | `BlobStore` interface with a filesystem implementation on the data volume (S3/R2 implementation is Phase P); server-generated keys never derived from client input or filenames; `put(stream)` with a running 100 MB cap that rejects and deletes oversize files (the HTTP upload endpoint, a single streamed `POST`, lands in T-2.1); files are served by the API directly through `BlobStore.open` with `Range` support, no signed tokens (DECISIONS §8d), and only for allowlisted keys (test: `songs/` and `work/*/raw|mezz` are never served); path-traversal tests (realpath containment under the root; absolute, `..`, NUL and backslash keys rejected; symlinks not followed; SEC-160); free-space check before accepting an upload | FR-017, NFR-019, SEC-001, SEC-003, SEC-004, SEC-007, SEC-160 |
| [ ] | **T-1.7** | Web shell: Next.js App Router, TS strict, Tailwind + tokens, generated TS client. | FE | T-1.1a, T-1.4a | Single origin via `tailscale serve` (`/api/*` to FastAPI, rest to Next.js); page calls the API; no sign-in pages; Lighthouse accessibility >= 95 and web budgets from UX-SPEC §3.5 on the shell; `dangerouslySetInnerHTML` lint ban; no secrets in the client bundle (build-output scan) | FR-038, NFR-013, NFR-014, SEC-112, SEC-115 |
| [ ] | **T-1.16** | Container sandbox verification on the compose stack. | OPS + QA | T-1.5 | In-container tests show worker/ffmpeg run non-root with cgroup CPU/memory/time limits, `cap_drop` ALL, no Docker socket mounted, no published host ports; any unavailable control is recorded with its fallback | SEC-013, SEC-131 |
| [ ] | **T-1.8** | Deploy skeleton to the VPS. | OPS | T-1.3, T-1.4b, T-1.5, T-1.6, T-1.7, T-1.11, T-1.20, T-0.15 | Whole compose stack (web, API, Postgres, Redis, worker, worker-maint, Tailscale sidecar), own Compose project network (SEC-164), Tailscale auth key tagged/single-use (SEC-163), on the VPS, reachable at the `*.ts.net` HTTPS URL from phone and laptop; Postgres and Redis internal-only; external port scan clean (NFR-029); `/api/v1/health/ready` green; pre-deploy scan (CHECKLIST C) clean; rollback to the previous image demonstrated once | NFR-029, SEC-133, SEC-163, SEC-164 |
| [ ] | **T-1.15** | Tailnet exposure and web hardening. | OPS + FE | T-1.8 | Tailscale ACL is deny-by-default and restricts the node to the owner's devices; `tailscale funnel` disabled in `nodeAttrs` (SEC-157, SEC-158); requests that do not come from the sidecar address, or lack the owner's tailnet login when `OWNER_TAILSCALE_LOGIN` is set, get 403 (SEC-159); no Traefik/public route and no published port (scan evidence); HSTS/nosniff/Referrer-Policy and `Cache-Control: private/no-store` on API responses verified by an automated header test; CSP in report-only soak | NFR-029, SEC-073, SEC-110, SEC-111, SEC-157, SEC-158, SEC-159 |
| [ ] | **T-1.17** | Supply-chain and account baseline. | OPS | T-1.3 | Lockfiles committed (`uv.lock`, pnpm), base images pinned by digest, Dependabot/Renovate or a monthly manual update note; 2FA on GitHub, Tailscale and the VPS provider; developer disk encryption evidenced | SEC-090, SEC-091, SEC-094, SEC-095, SEC-098, SEC-099 |
| [ ] | **T-1.21** | Nightly backup job. | OPS | T-1.8, T-0.12 | Nightly job (restic/borg or rclone, per T-0.12) writes the Postgres dump and project files to the owner-chosen off-box destination, client-side encrypted with the repo passphrase also held in the owner's password manager and write-only backup credentials (SEC-162), with a retention policy stated; failure surfaces in the logs and the disk/backup alert (T-4.7a); a run is evidenced | US-037, FR-049, NFR-025, SEC-162 |
| [ ] | **T-1.18** | Restore proof in Phase 1. | OPS | T-1.21 | The latest backup is restored into a scratch environment, the app lists the seeded project, file checksums match, elapsed time recorded (NFR-030) | US-037, NFR-025, NFR-030, SEC-135 |
| [ ] | **T-1.9** | G1 decision (evidence for the G1 criteria; ceremony per the process table). | PO | T-1.8, T-1.15, T-1.16, T-1.17, T-1.18 | G1 criteria evidenced; user confirms | G1 |

---

## Phase 2 — Core pipeline MVP (stock-only)

Mostly backend, built on the Phase 1 owner seam (every route is user-scoped). UI limited to a dev-only driver until Phase 3 design is approved. Draft-first flow: upload-complete triggers analysis then an automatic draft with default settings (30 s highest-energy segment); the owner tweaks afterwards. Every render produces a silent master + cut list; Mode A is a fast remux chosen on the export screen, so switching modes never re-renders (DECISIONS §2).

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-2.1** | Upload endpoints and `ffprobe` validation. | BE | T-1.6, T-1.20 | Per ARCHITECTURE §7: `POST /projects` (#1) and the single streamed `POST /projects/{id}/song` (#6): `Content-Length` <= 100 MB required, running byte cap, `.part` + rename; no chunked or resumable endpoints (DECISIONS §8d). Limits <= 100 MB, <= 10 min, >= 15 s; formats MP3, M4A/AAC, WAV, FLAC, OGG (Vorbis/Opus); size check; stale `incoming.bin.part` reaped after 24 h; magic-byte sniff must match MIME and extension; codec allowlist; specific rejection codes; DB CHANGE acknowledged | US-004, FR-001, SEC-001, SEC-003, SEC-005, SEC-006 |
| [ ] | **T-2.2** | Analysis worker: Beat This + octave clamp + override recompute. | ML | T-2.1, T-0.1 | Beat map JSON validated by schema; p95 <= 20 s for a 4-min song on the 4-vCPU worker (4 torch threads); half/double recompute without re-upload; BPM within 70-180 after clamp; F1 gate is carried by T-2.12 using this task's output | US-005, FR-003, NFR-002, NFR-007 |
| [ ] | **T-2.3** | Energy segmenter snapped to downbeats and segment selection. | ML | T-2.2 | Every boundary is a downbeat (test); default highest-energy segment for 15/30/60 s; output duration exactly N x 30 frames; section boundary hit-rate and energy kappa measured on the golden set | US-006, FR-004, FR-005, QM-018, QM-020, QM-021 |
| [ ] | **T-2.4** | Cut-plan generator (data-driven rules table, versioned) and plan validator. | ML | T-2.3 | Cut frames `f_i = floor((t_i - t0) * fps + 0.5)` using `math.floor(x + 0.5)`, never Python `round()`; `lead_frames` field default 0; shot lengths are index differences; every cut on a beat; first cut per section on a downbeat; density control monotonic (property test); rules table version stored per render; plan validator checks integer-frame purity, rounding error <= 16.7 ms and heuristic compliance | US-011, FR-012, FR-013, FR-024, QM-050, QM-051, QM-052, QM-026 |
| [ ] | **T-2.5** | Vibe to keywords service (Claude Haiku, strict schema, fallback table). | BE | T-0.7 | Follows `sattva-llm-features`: invalid JSON, timeout (8 s), refusal and 429 each trigger the fallback in tests; one repair retry; max_tokens 300; <= 8 keywords; prompt versioned; cost per call logged; golden prompts test; JSON validity >= 99% on recorded fixtures | US-007, FR-006, QM-030, FR-050 |
| [ ] | **T-2.22** | Resolve OQ-4: normalize-all vs lazy top-K. | ML + BE | T-0.3, T-0.8 | Decision recorded with benchmark numbers (default: rank on low-res frames, normalize only top-K ~1.3x cuts); T-2.7 / T-2.8 dependency order updated | — |
| [ ] | **T-2.6** | Stock fetch workers (Pexels default, Pixabay toggle). | BE | T-2.5 | Recorded-fixture tests; respects Pexels 200/h (and Pixabay limits when enabled) with backoff and a global token bucket; Pixabay is queried only when the settings toggle is on (test both states); keys server-side only; no persistent mirror (mezzanines are per project and housekept after 7 days); attribution metadata captured per clip; search-yield measured | FR-007, FR-040, FR-051, US-038, SEC-067, SEC-068, QM-032 |
| [ ] | **T-2.7** | Clip ranking (SigLIP 2) and shot-cut rejection (PySceneDetect). | ML | T-2.6, T-2.22, T-0.8 | Fixtures: clips with internal cuts always rejected; no repeat in a plan (property test) unless pool exhausted; technical floor enforced (>= 720p, >= 24 fps, duration); ranking reproducible given seed; near-duplicate and diversity warnings; internal-cut target = QUALITY QM-036 / G0-19 (detector check plus the 100-segment human audit) | FR-008, FR-009, FR-010, NFR-005, QM-033, QM-034, QM-035, QM-036, QM-037, QM-038, QM-039, QM-040, QM-041 |
| [ ] | **T-2.8** | Mezzanine normalizer and the audited FFmpeg runner. | BE | T-0.3, T-0.13 | Single `ffmpeg_runner` builds all argv (SAST bans `shell=True`/`os.system`); `-protocol_whitelist file` only, forced `-f` from sniffed type, probe limits, non-root, cgroup limits; ffprobe asserts 1080x1920, 30 fps CFR, yuv420p, SAR 1, common timescale on 30 diverse inputs; FFmpeg is the pinned build >= 8.1; every FFmpeg/ffprobe call runs as a short-lived child with an empty environment (per-job network namespaces are Phase P) | FR-011, FR-014, SEC-010, SEC-011, SEC-012, SEC-015, SEC-016, SEC-017 |
| [ ] | **T-2.9a** | Renderer part 1: frame-index render and untouched-audio mux. | BE | T-2.4, T-2.7, T-2.8 | Silent master rendered from normalized clips with trim by frame index; audio source for Mode A = the validated original `audio_source` (DECISIONS §8a), trimmed once for the segment; no gain, loudness, EQ or other processing; unit + render tests on cut error and drift | FR-012, FR-015, NFR-003, NFR-004 |
| [ ] | **T-2.9c** | Renderer part 3: silent master + cut lists, Mode A remux and downloads. | BE | T-2.9a | Every render yields a silent master MP4 + JSON and CSV cut lists as separate downloads; Mode A = fast remux onto the silent master (video stream untouched) of the validated original `audio_source`, trimmed to the segment, stream-copied when AAC-LC else transcoded once to AAC-LC 48 kHz, no other processing (DECISIONS §8a); speed per QM-086, integrity per QM-087; switching modes never re-renders; Mode A is `POST /renders/{id}/mode-a` (state in `renders.mode_a_state`/`mode_a_key`, no exports table); downloads are streamed directly by `GET /renders/{id}/download` (#21), repeatable | US-013, US-014, FR-017, FR-018, FR-042, NFR-027, SEC-007, QM-086, QM-087 |
| [ ] | **T-2.9d** | Renderer part 4: `verify_render` core checks. | BE + QA | T-2.9a, T-2.9c | Runs on every render and fails the job on Block-level breach (QUALITY §7): container/stream probe, CFR, frame count, duration, cut position error (any > 1 frame blocks), A/V drift, playability, output sanity (exactly 1 video + <= 1 audio stream), size/bitrate warn; results stored | FR-036, QM-060, QM-061, QM-062, QM-063, QM-064, QM-068, QM-075, QM-076, QM-077 |
| [ ] | **T-2.10a** | Job state machine, orchestrator and draft-first automation. | BE | T-2.9c, T-2.2, T-2.6 | ARCHITECTURE §4 state machine; upload-complete triggers analysis then an automatic draft with defaults; timeout kills the FFmpeg process tree (5 min hard render timeout); 1-2 retries; draft (upload-complete to draft ready) measured per stage against QM-085 | US-008, FR-020, NFR-009, NFR-026, QM-085 |
| [ ] | **T-2.10b** | Job de-duplication and failed-job handling (no per-op idempotency keys). | BE | T-2.10a | Same inputs map to the same job (DB `job_hash` unique index is the backstop if Redis loses keys); a failed job leaves no partial Mode A file and offers retry with a plain-language error | FR-020, US-022 |
| [ ] | **T-2.10c** | Progress SSE endpoint. | BE | T-2.10a | `GET /api/v1/projects/{id}/events` (ARCHITECTURE §7 #7) on the same origin; stage + percent at least every 5 s; reconnect resumes the correct state (test) | US-012, FR-019 |
| [ ] | **T-2.11** | Retention: owner-controlled keepers, 7-day housekeeping and 'delete now'. | BE | T-1.6, T-2.9c | Sweeper on the `maintenance` queue (service `worker-maint`) deletes intermediates (raw stock downloads, mezzanines, proxies) 7 days after last use and all files of deleted projects; never deletes songs, plans or renders (incl. the Mode A file) of live projects (negative test); 'delete now' removes a project's files within 5 min; audit query shows 0 stale objects (older than 7 days + 1 h grace) across 3 days of use | US-017, FR-027, FR-028, FR-052, NFR-017, SEC-141, SEC-161 |
| [ ] | **T-2.24** | Beat confidence score and 4-step fallback ladder. | ML | T-2.2, T-0.11 | Confidence score per QUALITY §4; fallback energy grid auto-applied only when confidence < 0.5, with the banner flag and 'use detected beats' toggle in the API; ECE, AUROC, recall-at-10%-flag and fallback-grid F1 reported on the golden set | QM-022, QM-023, QM-024, QM-025, QM-103 |
| [ ] | **T-2.12** | Golden set, one eval script (`make eval`) and 100-render soak in `eval/`. | QA + ML | T-2.9d, T-2.10c, T-2.11 | `eval/` scripts + manifests only; **one script** (Rev 3.3, DECISIONS §8d): beat/downbeat/tempo/segment/energy/confidence metrics, render-fidelity checks and stage timings, written to a results table; no `ci-lite`/`nightly`/`release` modes, no paired bootstrap, no rating tool (owner review is the CSV sheet of QUALITY §8; QM-031, QM-090…092 read from it). Core-set metrics meet QUALITY §12.1 / QM-001, QM-003, QM-004, QM-010, QM-016 (mean over the core set; hard set reported, ungated); musical alignment per QM-026; 100 consecutive renders (stated song mix, 4-vCPU box with 4 threads) all pass QM-060…064 and QM-068, with QM-038 (no repeats), QM-036 (internal cuts) and QM-087 (Mode A integrity); speed per QM-080, QM-081, QM-085, QM-086; success rate >= 98% (NFR-009) against a defined list of excluded input errors; results table committed | FR-036, NFR-001, NFR-005, NFR-009, NFR-028, QM-001, QM-002, QM-003, QM-004, QM-005, QM-006, QM-007, QM-008, QM-009, QM-010, QM-011, QM-012, QM-013, QM-014, QM-015, QM-016, QM-017, QM-018, QM-019, QM-020, QM-021, QM-022, QM-023, QM-024, QM-025, QM-026, QM-031, QM-080, QM-081, QM-082, QM-083, QM-084, QM-085, QM-086, QM-087, QM-090, QM-091, QM-092 |
| [ ] | **T-2.13** | Dev-only driver UI (upload, generate, download) behind a feature flag. | FE | T-2.10c, T-2.9c | Served on the tailnet only; flag off by default; explicitly throwaway, so no design spec is required | US-008 |
| [ ] | **T-2.14** | Security pass on the pipeline. | BE + QA | T-2.9d, T-2.18 | Malformed-media corpus (>= 50 files incl. m3u8/concat/hostile names, probe bombs) causes no crash beyond job failure; scoping test: a second synthetic `user_id` cannot reach the owner's project, upload, render or download; requests without the Tailscale proxy identity are rejected; FFmpeg in-container tests: non-root, protocol whitelist `file`, no published ports; runaway job killed by cgroup; path-containment test: no served path (`..`, symlink, absolute) escapes `BLOB_ROOT` | NFR-020, SEC-005, SEC-006, SEC-013, SEC-015, SEC-016, SEC-071, SEC-072, SEC-159 |
| [ ] | **T-2.16** | Model weights supply chain. | ML + BE | T-2.2 | Weights fetched at build time, SHA-256 manifest verified at start, `HF_HUB_OFFLINE=1`, start fails on mismatch (test); no bare `torch.load` (lint); torch >= 2.6; inference sandboxed with no network; licences recorded in the models manifest | SEC-030, SEC-031, SEC-032, SEC-033 |
| [ ] | **T-2.17** | LLM safety and cost controls. | BE | T-2.5 | Features-only prompt (no ID3 text); injection corpus yields valid schema or fallback; keywords only as URL-encoded values to allow-listed hosts; per-video cost cap, monthly budget alarm and kill-switch tested; with the Anthropic key unset the pipeline completes via the fallback table (FR-050); client wrapper logs tokens/latency; golden-prompt regression | FR-050, NFR-018, SEC-040, SEC-041, SEC-042, SEC-043, SEC-044, SEC-045, SEC-046 |
| [ ] | **T-2.18** | Untrusted-input hardening. | BE | T-2.1, T-2.6 | Filename normalisation, metadata strip, decode-once canonical audio in the sandbox plus a byte-identical validated copy `audio_source` for Mode A (downstream stages never read the raw `uploads` object; remux runs in the no-network child), stock download host allowlist/HTTPS/size/redirect limits (SSRF test against internal IPs), job payloads carry IDs only, scratch dir 0700 removed in `finally`; each with a negative test | SEC-004, SEC-009, SEC-018, SEC-019, SEC-020, SEC-023 |
| [ ] | **T-2.20** | Verify-render metric completeness. | BE + QA | T-2.9d | Remaining checks with Block/Warn levels per QUALITY §3.3: cut presence, unplanned cuts (Warn), A/V start offset, sync-calibration canary (CI), black/frozen frames, loudness and silence warnings | QM-065, QM-066, QM-067, QM-068, QM-069, QM-070, QM-071, QM-073, QM-074 |
| [ ] | **T-2.25** | Settings and housekeeping APIs. | BE | T-2.11, T-2.6 | ARCHITECTURE §7 #24 `GET /settings` (API-key status as booleans only, never a key; `api` gets only the derived `*_KEY_CONFIGURED` flags; Pixabay switch state; data-volume free/used and per-project usage split keepers vs intermediates, matches `du` within 1%), #25 `PUT /settings` (Pixabay switch, 409 `pixabay_not_configured` without a key) and #23 `POST /housekeeping/run`; low-space flag below the configured threshold; tests | FR-048, FR-051 |
| [ ] | **T-2.15** | G2 decision (evidence for the G2 criteria; ceremony per the process table). | PO | T-2.12, T-2.14, T-2.20 | All G2 numbers pasted with evidence; user approves | G2 |

---

## Phase 3 — Editor UX + preview

All FE items require the approved design spec (T-3.1, the design approval gate) before execution.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-3.1** | Design phase: approval of UX-SPEC S3-S8 plus a clickable mock (design approval gate). | DES + PO | G2 | Spec adds only what UX-SPEC lacks (in-app attribution/copy-credits, mode choice on export screen, settings screen with disk usage and stock toggle); mobile-first 360 px, states, WCAG 2.2 AA notes; user approval recorded in writing before any FE task starts | NFR-022 |
| [ ] | **T-3.2a** | Upload screen (S3). | FE | T-3.1 | e2e: US-004 acceptance passes with limits 100 MB / 10 min / 15 s shown; keyboard operable | US-004 |
| [ ] | **T-3.2b** | Analysis review screen (S5): waveform, beat markers, half/double tempo. | FE | T-3.1, T-2.2 | e2e: US-005 acceptance passes; waveform peaks (<= 2000 points) served by the API; low-confidence banner and toggle | US-005 |
| [ ] | **T-3.14** | Tempo override extras: tap tempo, BPM entry, even grid. | FE + BE | T-3.2b | API ops and UI work end to end; e2e covers each | US-032 |
| [ ] | **T-3.3** | Generate/progress screen with SSE. | FE | T-3.1, T-2.10c | e2e: progress updates <= 5 s; reconnect works; announced via live region; single bar spans analysis and draft build | US-012, NFR-016 |
| [ ] | **T-3.4a** | Browser preview engine (proxy clips sequenced against the song clock). | FE | T-3.1, T-3.4b | First frame <= 3 s on the 4G profile; works on Safari iOS and Chrome Android; preview vs proxy render offset <= 1 frame on 10 samples | US-009, FR-021 |
| [ ] | **T-3.4b** | Proxy render job and verification. | BE | T-2.9d | Proxy at 540x960 (DECISIONS §8e) plays without stutter on the owner's phone over the tailnet, otherwise switch to 360x640 and record it; same cut list as the final render; wording 'preview' (not 'share') | FR-022 |
| [ ] | **T-3.5** | Clip swap, lock/reorder, cut density, segment picker and vibe chips. | FE + BE | T-3.4a | US-006, US-007 (UI), US-010, US-011 acceptance pass; swapping and locking never move cut points (test); PATCH plan ops cover swap, density, lock, `move_clip` (reorder) and `nudge_cut` (±1 beat / ±1 bar) per ARCHITECTURE §5 with their validation rules; each has a keyboard-only UI alternative (WCAG 2.5.7) | US-006, US-007, US-010, US-011, FR-023, FR-024 |
| [ ] | **T-3.6** | Export screen: mode chosen after render, credits, delete project. | FE | T-3.5 | User renders first, then picks Mode A (with song) or Mode B (silent MP4 + JSON + CSV as separate downloads) on the export screen; switching takes seconds and never re-renders; in-app attribution list with 'copy credits'; 'Delete project' with confirmation; US-013, US-014, US-016, US-017 pass | US-013, US-014, US-016, US-017, FR-026, FR-042 |
| [ ] | **T-3.7** | Accessibility and cross-browser pass. | QA + FE | T-3.2a..T-3.6 | axe-core 0 serious/critical on all screens; manual keyboard walk-through and VoiceOver + NVDA pass; WCAG 2.2 AA criteria 2.4.11, 2.5.7, 2.5.8, 3.3.8 checked; NFR-021 browser matrix e2e green; 320 px no horizontal scroll; UX-SPEC AC-X-1..AC-X-9 as the checklist | US-024, NFR-014, NFR-015, NFR-016, NFR-021, NFR-022 |
| [ ] | **T-3.10** | Projects list (S9) and project rename. | FE + BE | T-3.6 | AC-S9-1..4 pass; `PATCH /projects/{id}` authz-tested; list of 200 projects INP <= 200 ms; status pills map to the ARCHITECTURE state machine | US-029 |
| [ ] | **T-3.11** | Error, empty, offline and tailnet-disconnected catalogue (S12). | FE | T-3.1 | Every S12 row has a component and e2e test (including 'not connected to Tailscale' and 'backend unreachable'); error-code to message map complete | — |
| [ ] | **T-3.12** | UI performance budgets in CI. | FE + QA | T-3.7 | Bundle-size and Lighthouse-CI budgets from UX-SPEC §3.5 enforced; red on a planted breach | NFR-013 |
| [ ] | **T-3.15** | Settings screen: API-key status, disk usage, Pixabay switch, housekeeping, retention info. | FE | T-3.1, T-2.25 | e2e: API-key status shows Set / Not set per provider from `GET /settings` (#24) and never a key value; disk usage matches the API (#24); Pixabay toggle persists and affects the next fetch; housekeeping can be run now; low-space warning shown; keyboard operable | US-036, US-038, FR-048, FR-051 |
| [ ] | **T-3.8** | G3 decision (evidence for the G3 criteria; ceremony per the process table). | PO | T-3.7, T-3.10, T-3.11, T-3.12, T-3.15 | G3 numbers pasted; user approves the live UI | G3 |

---

## Phase 4 — Personal polish & ops

Backups and housekeeping are built earlier; this phase proves them under real use and tunes the system. No public-facing compliance work.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-4.7a** | Observability and simple alerts. | OPS | T-1.8 | Structured JSON logs and per-job stage timings viewable; Sentry optional (PII scrubber test if enabled); alerts (log line, ntfy or email to self) for render failure rate, disk free below threshold, backup failure and housekeeping lag | NFR-010, SEC-120, QM-104, SEC-122 |
| [ ] | **T-4.7b** | Backups and restore drill. | OPS | T-1.18 | Restore drill repeated after any backup-config change and at least quarterly; RPO <= 24 h and RTO <= 4 h measured and recorded; file checksums match | NFR-025, NFR-030, SEC-135 |
| [ ] | **T-4.15** | Secrets, access and host hardening. | OPS | T-1.8 | Secrets rotated from any dev value; Tailscale ACL reviewed; SSH key-only, auto-updates on, Docker socket unmounted, Redis/Postgres not published; dev data never on the live volume; Tailscale auth key and node-key expiry reviewed (SEC-163); no shared Docker networks/volumes with other Dokploy services (SEC-164) | SEC-082, SEC-130, SEC-163, SEC-164 |
| [ ] | **T-4.17** | Local timing report. | BE | T-4.7a | A script/page summarising time-to-first-video, per-stage p95s, render success rate and quality pass rate from job logs; no external telemetry | NFR-008, QM-100, QM-101, QM-102, QM-103, QM-104, QM-106 |
| [ ] | **T-4.19** | Error handling and recovery pass. | BE + FE | T-3.11 | Every pipeline failure class (stock fetch, LLM, FFmpeg, disk full, worker crash) produces a plain-language message and a working retry; fault-injection test per class | US-022 |
| [ ] | **T-4.20** | Performance tuning from the contended-load result. | BE + ML | T-0.11, T-2.12 | Worker concurrency and queue settings set from the G0-27 recommendation; contended-load rerun on the deployed box meets QM-080/081/085/086 hard limits; before/after table recorded | NFR-006, NFR-007, NFR-026, NFR-027 |
| [ ] | **T-4.21** | Disk-pressure drill. | OPS + BE | T-2.11, T-4.7a | Fill the data volume to the warning threshold: alert fires, housekeeping run frees intermediates, uploads are refused cleanly below the hard floor, no partial files left | FR-048, FR-052 |
| [ ] | **T-4.8** | Security review (`security-audit`, quick profile) and fixes. | BE + QA | T-4.7b, T-4.15 | Report outside repo; 0 critical/high open; NEEDS-VALIDATION items triaged; external port scan clean | NFR-020, NFR-029 |
| [ ] | **T-4.9** | Two-week dogfood and G4 decision (ceremony per the process table). | PO | T-4.7a, T-4.7b, T-4.8, T-4.15, T-4.17, T-4.19, T-4.20, T-4.21 | Owner uses the app for 14 days on real songs; G4 criteria evidenced; user approves the personal edition as done | G4 |

---

## Phase 5 — Post-MVP extras

Each item needs a mini-gate. Rev 3.3: Phase 5 is numbered T-5.1..T-5.7 (old IDs: T-0.14 -> T-5.1, T-6.0..T-6.4 -> T-5.2..T-5.6). Each item needs its own plan per the process table.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-5.1** | TransNetV2 weights licence check. | BE | T-0.6 | Code licence confirmed MIT (F-37); weights terms read in the repo README/release page and recorded in the licence ADR as cleared, not cleared, or asked of the author in writing. Outcome decides whether T-5.5 can start; MVP stays on PySceneDetect either way. Moved here from Phase 0 (not needed before G0) | FR-009 |
| [ ] | **T-5.2** | Vendor and pricing re-research for AI video. | PO | G4 | Current prices from official pages, API sunset status, latency, 9:16 support | — |
| [ ] | **T-5.3** | AI hero shots (no credits ledger). | PO + BE | G4, T-5.2 | Vendor supports 9:16 and its terms are read for personal use; per-clip cost shown before generating; owner-set spend cap; follows `sattva-llm-features` | — |
| [ ] | **T-5.4** | Structure models (SongFormer / allin1) after licence check. | ML | G4 | Weights and backbone licences recorded in the licence ADR; boundary hit-rate@0.5 s beats the DSP segmenter on the golden set; no regression in NFR-007 | — |
| [ ] | **T-5.5** | TransNetV2 shot detection (code MIT; weights per T-5.1). | ML | G4, T-5.1 | Weights terms cleared per T-5.1; false-reject rate on the fixture lower than PySceneDetect | — |
| [ ] | **T-5.6** | PWA (installable, offline shell only). | FE | G4 | Lighthouse PWA checks pass; no caching of user media in the service worker; housekeeping unaffected | — |
| [ ] | **T-5.7** | Full evaluation harness (deferred from Phase 2, DECISIONS §8d). | QA + ML | G4 | `ci-lite` / `nightly` / `release` modes with a baselines file, paired-bootstrap regression gates and determinism check (QUALITY §5.3-5.4), a rating app if a sheet stops being enough, and the owner's A/B tooling; only built if the single `make eval` script (T-2.12) proves too thin | — |

---

## Phase P — Public edition (deferred)

Not started and not scheduled. Archived design: `archive/public-edition-rev2.2/` (ROADMAP, PRD, SECURITY, ARCHITECTURE and the rest, unchanged). Phase P follows the **lawyer-free rule** (DECISIONS §8b): songs and outputs stay on the user's device, only the beat map / edit plan / stock-clip IDs reach the server, minimal data (no analytics or tracking cookies; email or a licence key at most), payments through a merchant of record (Paddle or Lemon Squeezy), standard published templates for terms and privacy, and no feature that needs legal judgment. A feature that cannot meet the rule is redesigned or dropped, not sent to counsel.

Not carried into Phase P because they would require counsel or hosting users' music: counsel engagement and question list (old T-0.4), Pexels legal email (T-0.5), DMCA agent and operator tooling (T-4.4, T-4.10), custom ToS/Privacy drafting with sign-off (T-4.5), DPAs/RoPA/DPIA (T-4.13), fingerprint vendor (T-4.3), age gate (T-4.12) and server-side song storage with re-attach (T-2.23). They remain readable in the archive only.

| | ID | Task | Owner | Deps | Done criteria | Covers: |
|---|---|---|---|---|---|---|
| [ ] | **T-P.0** | Decide browser-side processing so songs never leave the user's device. | PO + ML + FE | T-0.16 | Decision record (ADR) using the T-0.16 numbers: go = analysis and render/remux in the browser, server sees only beat map, edit plan and stock-clip IDs (DECISIONS §8b); no-go = list which part stays server-side and how §8b is still met without counsel. Everything below is gated on this | — |
| [ ] | **T-P.1** | Accounts and auth: minimal sign-in only if needed (email or licence key, nothing else stored); no verification mail required | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-1.13, T-1.14, T-4.1a-c, T-4.11 in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: US-001..003, US-027, US-030, FR-029, FR-043, FR-044 |
| [ ] | **T-P.2** | Merchant of record billing (Paddle or Lemon Squeezy: tax, VAT, invoices, refunds); never handle card data; tiers/quotas only if still wanted | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-2.9b, T-4.2a-c, T-5.0..T-5.8 in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: US-018..021, US-033, FR-030..032 |
| [ ] | **T-P.3** | Output stays on the device; no hosted renders, share links or gallery | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-3.6 (server-side download), T-6.5 in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: US-013, US-014 (server variants) |
| [ ] | **T-P.4** | Standard published templates for terms and privacy notice; stock attribution per Pexels/Pixabay guidelines | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-4.5, T-3.9, T-5.3 in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: US-034, NFR-024, SEC-154 |
| [ ] | **T-P.5** | Abuse and rate limits for a public endpoint (only what the on-device design still needs) | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-4.14 in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: FR-037, SEC-008 (per-user storage and upload caps) |
| [ ] | **T-P.6** | Object storage adapter (S3/R2 `BlobStore`) only if any server storage remains after T-P.0 | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-1.6 (R2 variant), T-1.19 in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: FR-017 (R2 variant) |
| [ ] | **T-P.7** | Public-grade security: pen test, fuzz, WAF/edge, audit log, independent review | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-1.15 (Cloudflare), T-4.16, T-4.18, T-6.6 in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: NFR-020 (public level), SEC-121, SEC-022, SEC-014, SEC-024, SEC-025, SEC-026, SEC-028, SEC-029, SEC-113, SEC-114, SEC-132, SEC-134 |
| [ ] | **T-P.8** | Privacy minimum: no analytics or tracking cookies; data inventory kept to the minimum | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-4.12, T-4.13, T-4.17 (telemetry part) in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: FR-039, NFR-011, NFR-023, QM-105 |
| [ ] | **T-P.9** | Support: FAQ and a contact address (no ticket tooling needed) | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-3.13, T-5.9 in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: US-031, FR-045 |
| [ ] | **T-P.10** | Capacity and cost at public scale | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-5.4 in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: NFR-023 |
| [ ] | **T-P.11** | Relaxation review of stored decisions (re-download limits, retention) once public | PO | T-P.0 | Planned with `improve` when Phase P starts; Rev 2.2 design and tasks: T-6.5 in `archive/public-edition-rev2.2/ROADMAP.md`; adapted to DECISIONS §8b, no counsel step | Deferred: SEC-140 (72 h retention clock) |
| [ ] | **T-P.12** | Deferred quality tooling: VMAF encode-quality parity and sampled VMAF check; paired-preference (A/B sign-test) protocol | QA | T-P.0 | Moved out of the MVP in Rev 3.3 (DECISIONS §8d): FFmpeg-build VMAF parity (G0-22), sampled VMAF check, paired preference sign test. Planned with `improve` if/when needed (also reachable from Phase 5 item T-5.7) | Deferred: QM-072, QM-093 |

---

## Item count summary

Phase 0: 14 · Phase 1: 19 · Phase 2: 26 · Phase 3: 15 · Phase 4: 9 · Phase 5: 7 · Phase P: 13 (1 decision task + 12 area rows) = **103 items** (126 in Rev 2.2; Rev 3.2 had 109; the per-phase plan/design/review rows are listed once in the process table), 5 gates (G0–G4).

## Open questions

| ID | Question |
|---|---|
| RQ-1 | Thresholds marked (inference) (e.g. 14-day dogfood, >20% free disk) are proposals; approve or change |
| RQ-2 | Backup destination and tool (OQ-15) must be fixed in T-0.12 |
| RQ-3 | Does the VPS qualify as the 4-vCPU x86 benchmark box (OQ-16)? Otherwise a separate box is needed for T-0.1/T-0.3/T-0.11 |
| RQ-4 | No time estimates given; add after Phase 0 results |

---

## Appendix A — Traceability (requirement ID to task IDs)

Regenerated in Rev 3.2 from the `Covers:` entries of the active phases (0-5; Phase P rows are excluded). Active IDs are those outside the "Deferred to Phase P" tables of PRD §13, SECURITY §6 and QUALITY §16. Every active ID has at least one owner task; no active task covers a deferred ID.

### A.1 Coverage result

| Category | Active | Owned by >= 1 task | Orphans |
|---|---|---|---|
| User stories | 21 | 21 | 0 |
| Functional | 39 | 39 | 0 |
| Non-functional | 27 | 27 | 0 |
| SECURITY controls (SECURITY §5) | 75 | 75 | 0 |
| QUALITY metrics (QM catalog) | 75 | 75 | 0 |
| **Total** | **237** | **237** | **0** |

Deferred (not in the active catalogs, see PRD §13, SECURITY §6, QUALITY §16): PRD US 17, FR 13, NFR 3; SEC 55; QM-105, QM-072, QM-093 (the last two deferred in Rev 3.3, DECISIONS §8d). Their former tasks are listed under Phase P.

### A.2 User stories, functional and non-functional requirements

| Requirement | Tasks |
|---|---|
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
| US-016 | T-3.6 |
| US-017 | T-2.11, T-3.6 |
| US-022 | T-2.10b, T-4.19 |
| US-024 | T-3.7 |
| US-029 | T-3.10 |
| US-032 | T-3.14 |
| US-035 | T-0.15, T-1.20 |
| US-036 | T-3.15 |
| US-037 | T-1.21, T-1.18 |
| US-038 | T-2.6, T-3.15 |
| FR-001 | T-2.1 |
| FR-003 | T-0.1, T-2.2 |
| FR-004 | T-2.3 |
| FR-005 | T-2.3 |
| FR-006 | T-2.5 |
| FR-007 | T-0.2, T-2.6 |
| FR-008 | T-0.8, T-2.7 |
| FR-009 | T-0.8, T-2.7, T-5.1 |
| FR-010 | T-2.7 |
| FR-011 | T-0.3, T-2.8 |
| FR-012 | T-0.3, T-2.4, T-2.9a |
| FR-013 | T-2.4 |
| FR-014 | T-0.3, T-0.13, T-2.8 |
| FR-015 | T-0.3, T-2.9a |
| FR-016 | T-0.3 |
| FR-017 | T-1.6, T-2.9c |
| FR-018 | T-2.9c |
| FR-019 | T-2.10c |
| FR-020 | T-2.10a, T-2.10b |
| FR-021 | T-3.4a |
| FR-022 | T-3.4b |
| FR-023 | T-3.5 |
| FR-024 | T-2.4, T-3.5 |
| FR-026 | T-3.6 |
| FR-027 | T-2.11 |
| FR-028 | T-2.11 |
| FR-034 | T-1.5 |
| FR-035 | T-1.4a |
| FR-036 | T-2.9d, T-2.12 |
| FR-038 | T-1.3, T-1.4a, T-1.7 |
| FR-040 | T-2.6 |
| FR-042 | T-0.3, T-2.9c, T-3.6 |
| FR-046 | T-0.15 |
| FR-047 | T-1.4b, T-1.20 |
| FR-048 | T-2.25, T-3.15, T-4.21 |
| FR-049 | T-1.21 |
| FR-050 | T-2.5, T-2.17 |
| FR-051 | T-0.2, T-2.6, T-2.25, T-3.15 |
| FR-052 | T-2.11, T-4.21 |
| NFR-001 | T-0.0, T-0.1, T-2.12 |
| NFR-002 | T-0.1, T-2.2 |
| NFR-003 | T-0.3, T-2.9a |
| NFR-004 | T-0.3, T-2.9a |
| NFR-005 | T-2.7, T-2.12 |
| NFR-006 | T-0.3, T-4.20 |
| NFR-007 | T-0.1, T-2.2, T-4.20 |
| NFR-008 | T-4.17 |
| NFR-009 | T-2.10a, T-2.12 |
| NFR-010 | T-1.4a, T-4.7a |
| NFR-012 | T-1.5 |
| NFR-013 | T-1.7, T-3.12 |
| NFR-014 | T-1.7, T-3.7 |
| NFR-015 | T-3.7 |
| NFR-016 | T-3.3, T-3.7 |
| NFR-017 | T-2.11 |
| NFR-018 | T-2.17 |
| NFR-019 | T-1.6 |
| NFR-020 | T-2.14, T-4.8 |
| NFR-021 | T-3.7 |
| NFR-022 | T-3.1, T-3.7 |
| NFR-025 | T-1.21, T-1.18, T-4.7b |
| NFR-026 | T-2.10a, T-4.20 |
| NFR-027 | T-0.3, T-2.9c, T-4.20 |
| NFR-028 | T-2.12 |
| NFR-029 | T-0.15, T-1.8, T-1.15, T-4.8 |
| NFR-030 | T-1.18, T-4.7b |

### A.3 SECURITY controls

| Control | Tasks | Earliest phase |
|---|---|---|
| SEC-001 | T-1.6, T-2.1 | 1 |
| SEC-003 | T-1.6, T-2.1 | 1 |
| SEC-004 | T-1.6, T-2.18 | 1 |
| SEC-005 | T-2.1, T-2.14 | 2 |
| SEC-006 | T-2.1, T-2.14 | 2 |
| SEC-007 | T-1.6, T-2.9c | 1 |
| SEC-009 | T-2.18 | 2 |
| SEC-010 | T-0.3, T-0.13, T-2.8 | 0 |
| SEC-011 | T-0.13, T-2.8 | 0 |
| SEC-012 | T-2.8 | 2 |
| SEC-013 | T-1.16, T-2.14 | 1 |
| SEC-015 | T-2.8, T-2.14 | 2 |
| SEC-016 | T-2.8, T-2.14 | 2 |
| SEC-017 | T-0.13, T-2.8 | 0 |
| SEC-018 | T-2.18 | 2 |
| SEC-019 | T-2.18 | 2 |
| SEC-020 | T-1.5, T-2.18 | 1 |
| SEC-021 | T-1.5 | 1 |
| SEC-023 | T-2.18 | 2 |
| SEC-027 | T-1.3 | 1 |
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
| SEC-065 | T-1.5 | 1 |
| SEC-067 | T-2.6 | 2 |
| SEC-068 | T-2.6 | 2 |
| SEC-071 | T-1.20, T-2.14 | 1 |
| SEC-072 | T-2.14 | 2 |
| SEC-073 | T-1.15 | 1 |
| SEC-074 | T-1.4a | 1 |
| SEC-075 | T-1.4a | 1 |
| SEC-076 | T-1.4a | 1 |
| SEC-080 | T-0.7, T-1.12 | 0 |
| SEC-082 | T-4.15 | 4 |
| SEC-084 | T-1.4b | 1 |
| SEC-085 | T-1.11 | 1 |
| SEC-090 | T-1.17 | 1 |
| SEC-091 | T-1.17 | 1 |
| SEC-092 | T-1.11 | 1 |
| SEC-093 | T-1.11 | 1 |
| SEC-094 | T-1.17 | 1 |
| SEC-095 | T-1.17 | 1 |
| SEC-096 | T-0.7, T-1.2, T-1.3 | 0 |
| SEC-097 | T-0.7, T-1.3 | 0 |
| SEC-098 | T-1.17 | 1 |
| SEC-099 | T-1.17 | 1 |
| SEC-110 | T-1.15 | 1 |
| SEC-111 | T-1.15 | 1 |
| SEC-112 | T-1.7 | 1 |
| SEC-115 | T-1.7 | 1 |
| SEC-120 | T-1.4a, T-4.7a | 1 |
| SEC-122 | T-4.7a | 4 |
| SEC-123 | T-1.4a | 1 |
| SEC-130 | T-4.15 | 4 |
| SEC-131 | T-1.16 | 1 |
| SEC-133 | T-1.8 | 1 |
| SEC-135 | T-1.18, T-4.7b | 1 |
| SEC-136 | T-1.5 | 1 |
| SEC-141 | T-2.11 | 2 |
| SEC-157 | T-0.15, T-1.15 | 0 |
| SEC-158 | T-0.15, T-1.15 | 0 |
| SEC-159 | T-1.15, T-2.14 | 1 |
| SEC-160 | T-1.6 | 1 |
| SEC-161 | T-2.11 | 2 |
| SEC-162 | T-1.21 | 1 |
| SEC-163 | T-0.7, T-1.8, T-4.15 | 0 |
| SEC-164 | T-0.15, T-1.10, T-1.8, T-4.15 | 0 |

### A.4 QUALITY metrics

| Metric | Gate? | Tasks | Earliest phase |
|---|---|---|---|
| QM-001 | gate | T-0.1, T-2.12 | 0 |
| QM-002 | gate | T-0.1, T-0.11, T-2.12 | 0 |
| QM-003 | gate | T-0.1, T-2.12 | 0 |
| QM-004 | gate | T-0.1, T-2.12 | 0 |
| QM-005 | report | T-2.12 | 2 |
| QM-006 | gate | T-0.1, T-2.12 | 0 |
| QM-007 | report | T-2.12 | 2 |
| QM-008 | report | T-2.12 | 2 |
| QM-009 | gate | T-0.1, T-2.12 | 0 |
| QM-010 | gate | T-0.1, T-2.12 | 0 |
| QM-011 | gate | T-0.1, T-2.12 | 0 |
| QM-012 | gate | T-0.1, T-2.12 | 0 |
| QM-013 | report | T-2.12 | 2 |
| QM-014 | report | T-2.12 | 2 |
| QM-015 | gate | T-0.1, T-2.12 | 0 |
| QM-016 | gate | T-0.1, T-0.11, T-2.12 | 0 |
| QM-017 | gate | T-0.1, T-2.12 | 0 |
| QM-018 | gate | T-2.3, T-2.12 | 2 |
| QM-019 | report | T-2.12 | 2 |
| QM-020 | gate | T-2.3, T-2.12 | 2 |
| QM-021 | gate | T-2.3, T-2.12 | 2 |
| QM-022 | gate | T-0.11, T-2.24, T-2.12 | 0 |
| QM-023 | gate | T-0.11, T-2.24, T-2.12 | 0 |
| QM-024 | gate | T-0.11, T-2.24, T-2.12 | 0 |
| QM-025 | gate | T-2.24, T-2.12 | 2 |
| QM-026 | gate | T-0.11, T-2.4, T-2.12 | 0 |
| QM-030 | gate | T-2.5 | 2 |
| QM-031 | gate | T-2.12 | 2 |
| QM-032 | gate | T-0.2, T-2.6 | 0 |
| QM-033 | gate | T-0.8, T-2.7 | 0 |
| QM-034 | gate | T-0.8, T-2.7 | 0 |
| QM-035 | gate | T-0.8, T-2.7 | 0 |
| QM-036 | gate | T-0.8, T-2.7 | 0 |
| QM-037 | report | T-0.8, T-2.7 | 0 |
| QM-038 | gate | T-2.7 | 2 |
| QM-039 | report | T-2.7 | 2 |
| QM-040 | report | T-2.7 | 2 |
| QM-041 | gate | T-2.7 | 2 |
| QM-050 | gate | T-2.4 | 2 |
| QM-051 | gate | T-2.4 | 2 |
| QM-052 | gate | T-2.4 | 2 |
| QM-060 | gate | T-0.3, T-2.9d | 0 |
| QM-061 | gate | T-0.3, T-2.9d | 0 |
| QM-062 | gate | T-0.3, T-2.9d | 0 |
| QM-063 | gate | T-0.3, T-2.9d | 0 |
| QM-064 | gate | T-0.3, T-2.9d | 0 |
| QM-065 | report | T-2.20 | 2 |
| QM-066 | gate | T-2.20 | 2 |
| QM-067 | gate | T-0.3, T-2.20 | 0 |
| QM-068 | gate | T-0.3, T-2.9d, T-2.20 | 0 |
| QM-069 | gate | T-0.11, T-2.20 | 0 |
| QM-070 | gate | T-2.20 | 2 |
| QM-071 | gate | T-2.20 | 2 |
| QM-073 | report | T-2.20 | 2 |
| QM-074 | report | T-2.20 | 2 |
| QM-075 | gate | T-2.9d | 2 |
| QM-076 | report | T-2.9d | 2 |
| QM-077 | gate | T-2.9d | 2 |
| QM-080 | gate | T-0.1, T-2.12 | 0 |
| QM-081 | gate | T-0.3, T-2.12 | 0 |
| QM-082 | gate | T-2.12 | 2 |
| QM-083 | gate | T-2.12 | 2 |
| QM-084 | gate | T-0.9, T-2.12 | 0 |
| QM-085 | gate | T-0.11, T-2.10a, T-2.12 | 0 |
| QM-086 | gate | T-0.3, T-2.9c, T-2.12 | 0 |
| QM-087 | gate | T-0.3, T-2.9c, T-2.12 | 0 |
| QM-090 | gate | T-0.11, T-2.12 | 0 |
| QM-091 | gate | T-2.12 | 2 |
| QM-092 | gate | T-2.12 | 2 |
| QM-100 | report | T-4.17 | 4 |
| QM-101 | report | T-4.17 | 4 |
| QM-102 | report | T-4.17 | 4 |
| QM-103 | report | T-2.24, T-4.17 | 2 |
| QM-104 | report | T-4.7a, T-4.17 | 4 |
| QM-106 | report | T-4.17 | 4 |

### A.5 Gates

| Gate | Closing task |
|---|---|
| G0 | T-0.10 |
| G1 | T-1.9 |
| G2 | T-2.15 |
| G3 | T-3.8 |
| G4 | T-4.9 |
