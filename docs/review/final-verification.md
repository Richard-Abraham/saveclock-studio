# SaveClock Studio — Final Independent Verification (docs Rev 2.1)

Verifier: independent, read-only on docs · Date: 2026-11-08 · Scope: DECISIONS, PRD, ROADMAP, CHECKLIST, ARCHITECTURE, STANDARDS, adr/*, SECURITY, QUALITY, DESIGN, UX-SPEC, mockups/index.html, against consistency-review (C-xx), completeness-review (G-xx), fact-check (F-xx) and final-fixes-log.
Method: every claim below was re-checked by grep or read in the current files; the fixes log was used only as an index, never as evidence. Line numbers are as of this run.

**Headline:** 0 BLOCKER, 3 MAJOR, 15 MINOR new/remaining issues. 58 earlier BLOCKER/MAJOR/WRONG/OUTDATED items: 52 RESOLVED, 6 PARTIAL, 0 OPEN. Traceability is complete (0 orphans). Dependency graph is acyclic with no forward-phase dependencies.

---

## 1. Resolution audit

### 1.1 Consistency review (30 items: 5 BLOCKER + 25 MAJOR) — 29 RESOLVED, 1 PARTIAL, 0 OPEN

| ID | Sev | Status | Evidence (current docs) |
|---|---|---|---|
| C-01 frame rule | BLOCKER | RESOLVED | `floor((t_i − t0)·fps + 0.5)` identical in DECISIONS §4, ARCH §5 inv.2 (l.410) and §11.1 (l.795), PRD FR-012, QUALITY QM-050, CHECKLIST E1, ROADMAP T-2.4. No `round(t*30)` remains outside review files. `lead_frames` default 0 present in all (but see V-05 sign convention). |
| C-02 render target scope | BLOCKER | RESOLVED | Four separate metrics: DECISIONS §6 (20/120/60/5 s), ARCH §3, QUALITY G0-13..16, ROADMAP G2/T-5.4. UX S7 render steps no longer include fetching. |
| C-03 analysis 20 s | MAJOR | RESOLVED | ARCH §3 analysis budget sums to 20 s at 4 threads; DECISIONS §8a pins "4 vCPU, 4 threads". Caveat V-02/V-03 (zero slack, contention). |
| C-04 G0 vs QUALITY P0 | MAJOR | RESOLVED | ROADMAP G0 now references QUALITY §12 G0-x IDs; QUALITY D8 closed. |
| C-05 FFmpeg 7.x | MAJOR | RESOLVED | FFmpeg ≥ 8.1, build pinned by spike (T-0.13, G0-20..25) in DECISIONS §3, ARCH l.38, SEC-017, PRD FR-014, CHECKLIST, STANDARDS. |
| C-06 protocol whitelist | MAJOR | RESOLVED | `-protocol_whitelist file` only everywhere (DECISIONS §4, ARCH l.730/809, SEC-010, STD l.259, ADR-0002); SEC Q-16 closed; progress via `-progress <file>` (ARCH OQ-1). |
| C-07 queues / Redis | MAJOR | RESOLVED | Four queues in DECISIONS §3, ARCH §8, PRD FR-034, ROADMAP T-1.5, SEC l.38; two Redis (ADR-0011, T-1.10). |
| C-08 "zero hard cuts" | MAJOR | RESOLVED | DECISIONS §6 "0 detected by admission detectors, ≤1% of 100 audited"; per-render check is Warn (CHECKLIST E6 = QM-066); G0-19 / ROADMAP G2 reference QM-036. |
| C-11 draft-first flow | BLOCKER | RESOLVED | ARCH §3 l.136 and §4: one automatic pipeline to `draft_ready`; `POST /plan` does not exist (l.323); UX S5 steps map to states (UX l.340). |
| C-12 export flow | BLOCKER | RESOLVED | Silent master + cut list always; Mode A = remux at export, Mode B = separate downloads (DECISIONS §2; ARCH `job_hash` has no audio mode, l.487; endpoint #42; UX S8; PRD US-013/014). No `audio_mode` anywhere. |
| C-13 UI statuses | MAJOR | RESOLVED | ARCH §4 UI-status mapping table (Song removed / Files expired). |
| C-14 editor ops | MAJOR | RESOLVED | ARCH §5 op table includes swap, lock, remove, toggle_cut, move_clip, nudge_cut, set_density, set_tempo_octave; UX undo/redo 50 steps in UX l.445. ("Frantic" stop is the exception, see V-01.) |
| C-15 replan modes | MAJOR | RESOLVED | ARCH §4 "Replan modes": local (sync, 200) vs fetch (202, `planning`). |
| C-16 missing endpoints | MAJOR | RESOLVED | #3 resend-verification, #13 PATCH /me (password/email/unlink), #22 rename, #24 delete media, #16 data-export, #17/18 sessions, #49 feedback. |
| C-17 API names | MAJOR | RESOLVED | `POST /uploads`, `/healthz`, `/jobs/{id}/events`, `/upload-url`, `/v1/health` no longer appear outside ARCH §7 (grep). ROADMAP uses `/api/v1/...` names. |
| C-18 per-render checks | MAJOR | RESOLVED | QUALITY §7 declared authority (ARCH l.806); CHECKLIST E1-E12 restates Block/Warn levels consistently. |
| C-19 auth phase | MAJOR | RESOLVED | T-1.13 auth core in Phase 1; verification/OAuth/lockout stay in T-4.1a/b. |
| C-25 retention clocks | BLOCKER | RESOLVED | One clock `expires_at = upload_completed_at + 72 h` for every blob (DECISIONS §2, ARCH §4 rules + l.704, SEC-140, PRD). |
| C-26 mezzanine TTL | MAJOR | RESOLVED | Per-project mezzanines on the 72 h clock; no `cache/mezz/` or `MEZZ_*` (ARCH l.15, l.720). |
| C-27 buckets | MAJOR | RESOLVED | Four buckets `uploads, work, renders, backups`; no `quarantine` (SEC-081, Q-20, ARCH l.681). |
| C-28 canonical audio | MAJOR | RESOLVED | Canonical FLAC for analysis/fingerprint/proxy; Mode A reads gated `audio_source` through the same hardened gate (SEC-018, Q-19, ARCH l.317/779). Residual risk V-04. |
| C-29 worker network | MAJOR | RESOLVED | SEC-014/020/024/025/026 now one network model (worker VM, egress proxy, `worker_rw` over tunnel). |
| C-30 size/length caps | MAJOR | RESOLVED | 100 MB / 10 min / 15 s in DECISIONS, PRD, ARCH (`MAX_UPLOAD_MB=100`), SEC-003, UX, DESIGN, STD, mockup. Only stale hit: UX-SPEC l.47 research row "5–50 MB" (V-09). |
| C-31 resumable upload | MAJOR | RESOLVED | Multipart init / parts / complete / abort (#25-28), 8 MiB parts, 5 min part URLs. |
| C-37 origin/cookie | MAJOR | RESOLVED | Single origin, `__Host-sc_session`, no Domain, no CORS on API (ADR-0010, ARCH l.513, SEC-054). R2 browser CORS only on `uploads` bucket (ARCH l.710), which is correct. |
| C-38 verify-before | MAJOR | RESOLVED | Gate at `POST /projects` (403 `email_unverified`) in PRD US-003, SEC-052, ARCH error table, T-4.1a. |
| C-39 age gate | MAJOR | RESOLVED | US-027/FR-043, `users.age_attested_at`, `consents`, T-1.13/T-4.12. |
| C-40 fingerprint strikes | MAJOR | RESOLVED | "Never a strike" in ARCH l.483/970/1153, PRD US-015, SEC-153/156, T-4.3. |
| C-42 rights record | MAJOR | RESOLVED | `projects.rights_warranty_at` + `rights_warranty_tos_version` NOT NULL (ARCH l.481). |
| C-47 min shot / energy vocab | MAJOR | **PARTIAL** | Min shot rule still differs: QUALITY §10.3 = 9 frames (0.3 s; 6 f in E4 bursts), UX l.427 and ARCH l.442 = 0.5 s min clip for Frantic. Frantic also conflicts with beat grid. See V-01. |

### 1.2 Completeness review (18 BLOCKER/MAJOR) — 14 RESOLVED, 4 PARTIAL, 0 OPEN

| ID | Status | Evidence / remaining gap |
|---|---|---|
| G-01 auth phase order | RESOLVED | T-1.13. |
| G-02 origin | RESOLVED | ADR-0010, DECISIONS §3. |
| G-03 transactional email | PARTIAL | Specified: outbox `emails` table, templates (ARCH l.1145), `POST /webhooks/email`, Mailpit, T-1.14. Provider (Postmark/Resend/SES), sender domain, DMARC still undecided (ARCH OQ-13, T-0.12). Owner decision, fine to track. |
| G-04 DMCA tooling | RESOLVED | `dmca_notices`, `strikes`, `banned_email_hashes` tables, admin endpoints #52-56, ARCH §25, SEC-077 (API only, no UI). |
| G-05 missing endpoints | RESOLVED | see C-16. |
| G-06 API naming | RESOLVED | see C-17. |
| G-07 local dev | RESOLVED | ARCH §19/§22, T-1.10, `make dev`. |
| G-08 CI/CD | RESOLVED | ARCH §20 stages, T-1.3/T-1.11; CI host (GitHub) still an assumption (OQ-16). |
| G-09 env catalogue | RESOLVED | ARCH §18 table; STD points to it; T-1.12. |
| G-10 data model fields | RESOLVED | `age_attested_at`, `consents`, `usage_counters`, locks in plan, `watermark_version`. |
| G-11 backups | RESOLVED | 14 d / monthly-then-quarterly drill in ARCH l.1132, SEC-135, PRD NFR-025, T-4.7b. |
| G-12 analytics | PARTIAL | Decision made (first-party, cookie-free, aggregates), but no event table/endpoint exists for the events KPIs QM-100..106 need (ARCH OQ-18 defers to QUALITY §11). V-13. |
| G-13 support / feedback | PARTIAL | `POST /feedback` (#49) exists; no screen, no mailbox/runbook; UX OQ #10 open. V-12. |
| G-14 watermark spec | PARTIAL | Overlay geometry in ARCH l.776 and `watermark_version`; no asset spec/safe zone/Pexels-resale check; PRD OQ-10 open (design gate Phase 3). V-12. |
| G-15 Mode B packaging/cost | RESOLVED | Three separate downloads; one render; no extra quota (DECISIONS §2). |
| G-16 inconsistent numbers | RESOLVED | See §2 sweep; one residual (V-06, UX 15 min signed URL). |
| G-17 error codes | RESOLVED | Catalogue at ARCH l.522-548 incl. `email_unverified`, `stock_unavailable`, `verification_failed`, `file_rejected.reason`. |
| G-18 sandbox feasibility | RESOLVED | T-1.16 on the real worker VM, ARCH OQ-9, SEC Q-18. (Feasibility is proved in Phase 1 after the ADR is accepted in Phase 0, see V-18.) |

### 1.3 Fact-check (10 WRONG/OUTDATED) — 9 RESOLVED, 1 PARTIAL, 0 OPEN

| ID | Status | Evidence |
|---|---|---|
| F-12 FFmpeg | RESOLVED | ≥ 8.1, 8.1.x vs 9.0.x decided by spike (ARCH l.38, T-0.13, QUALITY G0-20..25). |
| F-14 CVE-2025-22920 | RESOLVED | "DoS only per NVD" in SECURITY T-01, §11 sources. |
| F-37 TransNetV2 | RESOLVED | Code MIT, weights check T-0.14/T-0.6 (DECISIONS §3, ADR-0008). |
| F-38 arXiv cite | RESOLVED | QUALITY and ADR-0008 use the PySceneDetect v0.7 benchmark (F1 ≈ 55.8) and arXiv 2008.04838; 2501.03575 and "0.477" no longer appear. |
| F-39 Next.js | RESOLVED | 16.4.5 (ARCH l.34), 16.4.x (STANDARDS). |
| F-40 FastAPI | RESOLVED | 0.162.2 / "0.16x", pin exact (ARCH l.35). |
| F-41 Pydantic | RESOLVED | 2.14.3. |
| F-42 SQLAlchemy | **PARTIAL** | Both lines documented; 2.0.x vs 2.1.x deliberately left to scaffold (ARCH OQ-17). Acceptable as tracked. |
| F-43 Dramatiq | RESOLVED | 2.2.1; every limit/retry set explicitly per actor, 1.x defaults marked unverified (ARCH l.37, §8). |
| F-44 PySceneDetect | RESOLVED | 0.7.x (0.7.2). |

---

## 2. Fresh contradiction sweep

Checked by grep across all docs plus the mockup. **Consistent:** all items below not listed under "Remaining conflicts".

| Check | Result |
|---|---|
| State names vs ARCH §4 (15 states) | Consistent. No `PLAN_READY/ANALYZED/UPLOADED` etc. UX l.714 and DESIGN use the canonical names. |
| Endpoint paths vs ARCH §7 (56 endpoints) | Consistent in PRD (`POST /feedback`), ROADMAP, UX l.716, SEC. Shorthand variants in ARCH prose only (V-08). |
| 100 MB / 10 min / 15 s | Consistent (DECISIONS §1, PRD FR-001, ARCH, SEC-003, UX S3, DESIGN §7, STD, mockup copy). No `50 MB` / `15 min` limits remain (only DESIGN/UX notes saying they are gone, and UX l.47 research text). |
| 72 h one clock, 73 h audit tolerance | Consistent. Sweeper authoritative, R2 lifecycle backstop. |
| 20 / 120 / 60 / 5 s | Consistent (DECISIONS §6, ARCH §3 and §15 alerts, PRD NFR-006/007/026, QUALITY G0-13..16, CHECKLIST E12, ROADMAP T-5.4). |
| Beat co-gates | F1 ≥ 0.85, AMLt ≥ 0.85, CMLt ≥ 0.75, downbeat F1 ≥ 0.75, octave ≤ 5% identical in DECISIONS §6, PRD NFR-001, QUALITY §12.1. ROADMAP G0/G2 reference IDs and restate no numbers. |
| Stock threshold G0-17 | ≥ 20 portrait clips ≥ 1080p per keyword for ≥ 80% of 50 keywords in DECISIONS §8a, PRD A-02, QUALITY G0-17/QM-032, T-0.2. ROADMAP RQ-1 still lists ">= 40/50 keywords" as a "proposal" (same number, fine). |
| ±1 frame / 21.3 ms | Consistent (DECISIONS §4/§6, NFR-003/004, QUALITY QM-062..064, G0-10/12). QUALITY l.106 mislabels "±1 frame (±16.7 ms)" (V-09). |
| Export flow | Consistent everywhere (silent master; Mode A remux ≤ 5 s; Mode B separate downloads; switching never re-renders). |
| Single origin / no CORS / `__Host-` | Consistent. No `api.<domain>` base remains except historic note in ADR-0010. |
| 4 queues, 2 Redis, 2 images, 4 buckets | Consistent. ARCH l.690/704/706 say "three buckets" for `uploads/work/renders` (backups excluded), accurate in context. |
| Worker VM isolation | Consistent (DECISIONS §3, ADR-0009, SEC-014/024/025/026, T-1.19/T-1.16, ROADMAP G1). |
| FFmpeg ≥ 8.1 pinned in spike | Consistent; no `7.x` pin remains (only "7.1.x only as a control" in T-0.13). |
| `-protocol_whitelist file`; `-progress` | `file` only everywhere; `file,pipe` and `pipe:` gone; `-progress <file>` used, with a spike check (ARCH OQ-1, SEC Q-21, ADR-0002). |
| Sign-in first + 16+ | Consistent (DECISIONS §1, PRD US-027/FR-043, UX, DESIGN, mockup, T-1.13, T-4.12). |
| Fingerprint warn-only, no title, never a strike | Consistent in 12 locations. |
| "Notify me" removed | Gone from DECISIONS §8a, PRD, UX, DESIGN, ARCH (OQ-12 closed), ROADMAP T-5.7, mockup (static "Coming soon"). No `waitlist` or notify email template. |
| Frame formula + `lead_frames` | Present in DECISIONS §4, ARCH schema (l.358) and invariants, PRD FR-012, QUALITY, ROADMAP T-2.4. Sign convention differs (V-05). |
| `move_clip` / `nudge_cut` | In ARCH op table (l.435-436), validation (l.439-440), endpoint #35, UX map rows (l.639-640); UX §3.4/l.132-133/l.149-150 (shortcuts), ROADMAP T-3.5, DESIGN. |

### Remaining conflicts / residue (all folded into the table in section 5)
V-01 Frantic density (UX/ARCH/QUALITY), V-05 `lead_frames` sign, V-06 UX 15 min signed URL, V-07 ROADMAP T-0.8 "QUALITY P0-12" and G4 "P0 control", V-08 ARCH shorthand paths, V-09 header/units drift, V-10 UX "typical 20-40 s", V-14 PRD OQ-02 "cache" wording and DESIGN "extension offered".

---

## 3. Traceability spot-check (independent count)

| Item | Defined | Referenced in ROADMAP task/gate rows (before Appendix A) | Orphans |
|---|---|---|---|
| SEC-### (SECURITY.md) | 122 | 122 | 0 |
| QM-### (QUALITY.md) | 78 (58 gating) | 78 | 0 |
| US-### (PRD) | 34 | 34 | 0 |
| FR-### (PRD) | 45 | 45 | 0 |
| NFR-### (PRD) | 28 | 28 | 0 |
| Undefined IDs referenced by ROADMAP | — | none | — |

Counts match ROADMAP Appendix A.1 exactly. The appendix is generated from the `Covers:` column; I re-derived coverage from the task rows themselves, not from the appendix.

**Dependencies:** all 126 task rows parsed (not a sample; phase counts 15/22/30/17/24/11/7 match the "Item count summary"). 0 undefined dependency IDs, 0 cycles, 0 forward-phase dependencies. Gate dependencies are strictly sequential: T-1.0←G0, T-2.0←G1, T-3.0←G2, T-4.0←G3, T-5.0←G4, T-6.x←G5. Five same-phase deps point at a task listed later in the file (T-0.2→T-0.7, T-0.3→T-0.13, T-1.13→T-1.14, T-2.14→T-2.18, T-3.4a→T-3.4b): ordering cosmetic only, not a defect. Gate rows G0-G5 reviewed: every task they cite exists and sits in or before the gate's phase. Two stale labels (V-07).

---

## 4. Sanity judgement

**Technically wrong or risky**
1. **"Frantic" refused above 100 BPM (V-01).** The 100 BPM figure actually matches the QUALITY 9-frame (0.3 s) minimum (half beat at 100 BPM = 0.3 s), but UX and ARCH also say "minimum clip length 0.5 s", which only allows half-beat cuts at ≤ 60 BPM. Worse, half-beat positions are not on the Beat This grid and `beat_ref.kind` is only `downbeat|beat`, so the plan schema cannot represent them (every-cut-on-the-grid invariant). Cut the stop from MVP.
2. **Single 4-vCPU worker serves three queues at once (V-02).** Analysis (4 torch threads), fetch (2 procs x 4 threads, 2 concurrent FFmpeg) and render (`-threads 4`) are budgeted as if each had the whole box. With any concurrency every p95 in §3 is optimistic; the draft path is exactly the sum of its parts (120 s, zero slack).
3. **Beat This CPU feasibility (V-03).** 14 s for 4 min at 4 threads is an inference; the same ARCH §8 once cited 10-30 s. G0-13 (p95 ≤ 20 s) is a Must gate and a NO-GO trigger although analysis latency is hidden behind a progress screen. Make the hard gate draft-level (≤ 120 s) and relax analysis to Should / ≤ 30-40 s.
4. **`-progress` under file-only whitelist.** Acceptable: `-progress <local path>` is the `file` protocol; the docs already switched from `pipe:1` and schedule a spike check (OQ-1, Q-21). Low risk. One caveat: parse the file from the worker, never let it be user-influenced.
5. **Presigned PUT size enforcement.** R2 does not document signed Content-Length enforcement; the docs correctly assume it is not enforced and compensate (multipart with fixed 8 MiB parts, HEAD at complete, abort/reap, 500 MB per-user storage cap, lifecycle abort of incomplete multiparts). Residual: a client can PUT oversized parts before complete; verify the per-user cap and incomplete-multipart lifecycle actually bound this (add as explicit T-0.7 test, it already tests Content-Length enforcement).
6. **Mode A reparses attacker bytes (V-04).** Rev 2.1 reads the gated original `audio_source` in the render worker, partly reopening the SEC-018 decode-once rationale. Accepted by owner decision; ensure the remux command is fully constrained (`-map 0:a:0 -vn -sn -dn -map_metadata -1`, forced `-f`) and the malformed-media corpus (T-2.14/G0-25) runs against the remux path too.
7. **AAC stream copy trimmed at an arbitrary start** is packet-granular (±21.3 ms) and can leave priming/edit-list artefacts; docs accept ±1 AAC frame and G0-12 tests it. Fine.
8. **`Alt+←/→` clip-move shortcut (V-11)** collides with browser Back/Forward on Windows/Linux. Pick another chord.
9. **10-min WAV is ~106 MB** (16-bit/44.1 kHz stereo), so the 100 MB cap rejects the longest lossless files before the 10-min cap triggers (V-15). Copy is specific so it is acceptable; decide knowingly.
10. **Workers reach Postgres and Redis over a WireGuard tunnel from a remote VM**: latency and flaps affect Dramatiq heartbeat/visibility. Reconnect/backoff is specified (ARCH l.676); add a tunnel-flap soak to the G1 checks.

**Over-engineered for an MVP (specific cuts/deferrals)** — owner decisions are not overridden; these are recommendations.
- Cut the "Frantic" density stop (and the half-beat concept).
- Defer admin DMCA endpoints #52-56 to an operator SQL/CLI runbook (SEC-077 already says no admin UI); defer #17-18 session list/revoke and `logout-all`, and `POST /me/data-export` automation (already operator-fulfilled).
- Single stock provider (Pexels) for MVP; add Pixabay only if T-0.2 shows a shortfall (removes a second adapter, portrait probing and dedupe).
- Fingerprint vendor (AudD/ACRCloud, T-4.3) is warn-only and legally undecided: defer until counsel decides, keep the schema hook.
- Two Redis instances (ADR-0011) could be one `noeviction` Redis with TTL'd cache keys for MVP.
- Golden set: gate on 30 core tracks; defer the 20 hard tracks (report-only, ungated) and dual annotation of them to after G0. This is the spike's critical path.
- Pen test + 24 h fuzz + Stripe + Pro tier all sit before public traffic; consider an invite-only free beta before Phase 5 (already structurally possible).
- Dedicated worker VM + WireGuard + egress proxy + per-FFmpeg netns is heavy; it is an owner decision, so keep it, but stage the netns/seccomp extras after G1.
- Email: build the outbox + bounce/complaint webhook minimally; use the provider's suppression list.
- Optional OpenTelemetry tracing is already marked optional; keep it out of Phase 1.

---

## 5. Remaining issues

| ID | Severity | Location | Issue | Fix |
|---|---|---|---|---|
| V-01 | MAJOR | UX-SPEC l.427; ARCH §5 l.442; QUALITY §10.3 l.550 | "Frantic" (half-beat) stop: min clip 0.5 s vs QUALITY 9-frame min; half-beats not representable (`beat_ref.kind` is `downbeat|beat`); 100 BPM cut-off only matches the 0.3 s rule. C-47 not fully closed. | Drop Frantic from MVP (4 stops, remove `density_not_allowed`), or define a half-beat grid + `kind=half` and use one min-shot value (QUALITY) everywhere. |
| V-02 | MAJOR | ARCH §8 table l.659-661; §3 budgets; DECISIONS §6 | One 4-vCPU worker VM runs analysis, fetch and render concurrently while every p95 assumes exclusive 4 vCPUs; no contended measurement planned. | Add to T-0.11: p95 with a realistic mixed load; define per-VM concurrency (one heavy stage at a time, or >= 8 vCPU); state in DECISIONS §6 that numbers are for an exclusive 4 vCPU. |
| V-03 | MAJOR | QUALITY G0-13 (Must, p95 ≤ 20 s); ARCH §3 (budgets sum exactly to 20 s / 120 s) | Zero-slack budgets and a hard NO-GO on an unmeasured Beat This CPU number that the UX hides behind a progress screen. | Keep draft ≤ 120 s as Must; make analysis ≤ 20 s a target (Should) with a G0 floor of 30-40 s; add 10-15% slack to stage allocations. |
| V-04 | MINOR | ARCH l.779; SEC-018 | Remux parses the raw validated original in the render worker. | Constrain remux argv (`-map 0:a:0 -vn -sn -dn -map_metadata -1`), run the malformed corpus against remux, record as accepted risk. |
| V-05 | MINOR | QUALITY l.559 vs ARCH l.410/795 | `lead_frames` sign: ARCH subtracts `lead_frames` (positive = earlier); QUALITY calls the candidates `lead_frames = b ∈ {0,-1,-2}` and adds `b`. | Pick one (ARCH: positive = earlier) and restate QUALITY l.559/G0-9. |
| V-06 | MINOR | UX-SPEC l.552 (AC-S8-2) | Signed URL "≤ 15 min"; every other doc says ≤ 10 min. | Change to ≤ 10 min. |
| V-07 | MINOR | ROADMAP T-0.8 (l.107), G4 (l.87) | Stale labels: "QUALITY P0-12" (now G0-18), "every P0 control in SECURITY §10" (levels are L0/L1/L2). | Replace with G0-18 and "every L0 control". |
| V-08 | MINOR | ARCH l.235, 245, 275, 281, 674 | Shorthand `POST /renders`, `POST /exports` differ from #39 `POST /projects/{id}/renders` and #42 `POST /renders/{id}/exports`. | Use canonical paths or label as shorthand. |
| V-09 | MINOR | DECISIONS l.3; SECURITY l.3/16/558; CHECKLIST l.11; UX-SPEC l.47; QUALITY l.106 | DECISIONS header still "Rev 2" (content is 2.1); SECURITY says "reconciled to DECISIONS Rev 2"; UX research row "songs are 5-50 MB"; QUALITY says "±1 frame (±16.7 ms)" (that is ±0.5 frame; ±1 = 33.3 ms). | Header/number clean-up pass. |
| V-10 | MINOR | UX-SPEC l.83 | "Typical 20-40 s on the happy path" has no basis in the budgets (analysis alone is 20 s p95; draft p95 120 s). | Add a draft p50 target to NFR/QUALITY or soften the copy; UX l.346 ETA logic then follows it. |
| V-11 | MINOR | UX-SPEC l.132-133, 150 | `Alt+←/→` conflicts with browser Back/Forward; `Alt+[ ]` collides on some layouts. | Use other chords (e.g. `Ctrl+Alt+←/→` or `[`/`]` with focus). |
| V-12 | MINOR | G-13/G-14 | No UI for `POST /feedback`; no watermark asset/safe-zone spec. | Add a small S11 "Report a problem" entry (or defer feedback to a mailto) and a watermark spec in DESIGN before the Phase 3 design gate. |
| V-13 | MINOR | ARCH OQ-18; PRD FR-039; QUALITY QM-100..106 | No table/endpoint for first-party aggregate events needed by the KPIs. | Define a tiny `event_counts(day, name, n)` table + one internal increment path, or derive from DB (projects/renders). |
| V-14 | MINOR | PRD OQ-02 (l.279); DESIGN l.211 | PRD OQ-02 still says "Mezzanine cache design"; DESIGN says 72 h "extension is offered where policy allows", conflicting with DECISIONS "no extension without counsel". | Reword both. |
| V-15 | MINOR | DECISIONS §1; SEC-003 | 10-min stereo 16-bit WAV (~106 MB) exceeds the 100 MB cap. | Accept knowingly or raise to 120 MB. |
| V-16 | MINOR | ROADMAP T-0.0; QUALITY §12 | Hand-annotating 30 core + 20 hard tracks by two annotators is the spike's critical-path labour. | Gate on 30 core; hard set after G0; allow vetted public datasets for part of the core. |
| V-17 | MINOR | ARCH §8 `maintenance` row (app host) vs SEC-024 ("maintenance-media workers" on the VM) | Ambiguous where `purge_media`/sweeper run and which credentials they hold. | State per actor: DB/R2 maintenance on the app host; no media parsing there. |
| V-18 | MINOR | ROADMAP T-0.12 vs T-1.16; ARCH OQ-9 | Worker-VM design ADR is accepted in Phase 0 but its feasibility is only proved in Phase 1. | Add a one-day isolation probe (VM, nftables, tunnel, proxy) to Phase 0, or record that ADR-0009 may be revised after T-1.16. |

---

## 6. Open decisions

### 6.1 OWNER decisions still open (non-legal)
1. Transactional email provider (Postmark / Resend / SES), sender domain, DMARC policy (T-0.12, ARCH OQ-13).
2. Fingerprint vendor (AudD vs ACRCloud), audio scope sent to vendor, and whether fingerprinting ships in the MVP at all (PRD OQ-07, ARCH OQ-15, SEC Q-11).
3. Keep or cut the "Frantic" density stop (V-01); analysis-speed gate wording (V-03); worker concurrency policy / VM size (V-02).
4. CI host confirmation (GitHub) and PR-template assumptions (ARCH OQ-16, STD Q4); linter/type-checker pick; coverage floors; Node LTS pin (STD Q1, Q2, Q5).
5. Worker-VM provider/size, private-tunnel choice (WireGuard vs provider network), egress-proxy technology, pull-agent vs Dokploy remote deployment (SEC Q-18, ARCH OQ-9).
6. FFmpeg build 8.1.x vs 9.0.x (spike decides); SQLAlchemy 2.0.x vs 2.1.x (OQ-17).
7. Preview proxy resolution 270x480 / 360x640 / 540x960 (PRD OQ-14, UX #11, ARCH OQ-14).
8. Free daily cap, Pro allowance and price (PRD OQ-04, Phase 5); availability target 99.5% and RPO/RTO confirmation (PRD OQ-11).
9. Watermark design and placement (PRD OQ-10); "Report an issue" entry point in MVP or not (UX #10).
10. UX items: free-tier queue-position copy (#3), single-key shortcuts default (#4), beat pulse default on (#5, DESIGN #3), phone landscape not designed (#6), sentence-case buttons (#7), brand colour on real stock thumbnails (DESIGN #4), font licensing check (DESIGN #2).
11. ROADMAP RQ-1 thresholds (40/50 keywords, 30 s Pro queue wait, 50 beta users, 20 invitees), RQ-4 time estimates after Phase 0, RQ-5 pen-test vendor and date (SEC Q-17).
12. QUALITY Q3 budget for evaluation audio and rater payments, Q4 second annotator, Q8 on-call owner, Q10 physical devices (iOS Safari, Android Chrome) for G0-11, Q7 who owns stock-clip content safety (NSFW/faces).
13. Golden-set scope for the spike (V-16) and whether to defer Pixabay, second Redis, admin DMCA endpoints (section 4 cuts).

### 6.2 COUNSEL questions (consolidated)
1. Should a fingerprint match ever block (repeat or exact commercial match)? (PRD OQ-01, SEC Q-13, ARCH OQ-2, UX #1)
2. Pexels/Pixabay terms: transient storage of normalized mezzanines, delivering transformed outputs to paying users, attribution wording, rate-limit uplift (T-0.5; PRD OQ-02). May need counsel if the reply is silent.
3. Is the beat map kept beyond 72 h acceptable, and for how long? (PRD OQ-03)
4. First-party cookie-free analytics with no consent banner under ePrivacy (PRD OQ-05, SEC Q-12).
5. Beat This README training-data caveat and commercial use (PRD OQ-06, ARCH OQ-8).
6. Fingerprint vendor DPA, excerpt-only upload, retention of match results (12 months proposed), whether the matched title must be retained (SEC Q-11, ARCH OQ-15).
7. Account deletion SLA (30 days assumed) (PRD OQ-12).
8. Age threshold 16+ vs 13+ in some jurisdictions (PRD OQ-13, SEC Q-12).
9. Audit-log (12 months) and DMCA-record (3 years) retention periods (ARCH OQ-6/10, DECISIONS §2).
10. Re-attach after expiry starts a new 72 h clock (DECISIONS §8a, ARCH OQ-11, PRD US-028).
11. LLM provider retention/training terms, DPA, EU residency (SEC Q-08).
12. EU/UK establishment, lead authority, representative/DPO, DPIA need, CCPA applicability, lawful bases (SEC Q-12, Q-14).
13. ToS (warranty + indemnity), Privacy, DMCA and repeat-infringer policy; DMCA agent registration and current fee (RQ-2); safe-harbor fit for a transformation service (T-0.4).
14. Use of CC-licensed tracks for internal evaluation in a commercial company, and consented user-report tracks in the golden set (QUALITY Q1, Q2; T-0.0).
15. TransNetV2 weights terms (T-0.14), librosa/FFmpeg build licence (x264 is GPL) decisions (T-0.6).

---

## 7. Verdict

**Phase A (documentation): COMPLETE ENOUGH FOR OWNER APPROVAL.** The two canonical rules the earlier reviews cared about most (DECISIONS as source of truth, §8a owner-of-topic table) are now actually honoured: every substantive contradiction found by the prior reviews is closed, traceability is 100% both ways, the roadmap graph is sound, and the sweep found no BLOCKER. Before the owner signs, fix the three MAJOR items as quick edits (they are small and local): V-01 (cut or properly spec Frantic), V-03 (soften the analysis-speed Must / add slack), and add V-02 (contended-load measurement) to T-0.11. Everything else (V-04 to V-18) can be tracked as a single clean-up pass or as open questions and does not block approval.

**Phase 0 (validation spike): READY TO START** once the owner provides the non-doc inputs: annotators/budget and devices (QUALITY Q3, Q4, Q10), a named counsel (T-0.4), and API keys (T-0.7). Tasks with no dependencies can begin immediately: T-0.0, T-0.4, T-0.5, T-0.7, T-0.13 (T-0.6 and T-0.14 follow). Must be fixed first: nothing blocking. Should be adjusted first (cheap): V-02/V-03 wording, V-07 stale labels in T-0.8, V-16 golden-set scope. Track as open questions: all items in sections 6.1 and 6.2.

Process reminders for implementation (not doc defects): every schema-bearing task needs the "DB CHANGE: ... — run this SQL" notice before commit (ARCH §6 has many NOT NULL columns); `ponytail-review` after each phase; UI work needs the `sattva-design-phase` spec (DESIGN/UX are drafts for design approval).
