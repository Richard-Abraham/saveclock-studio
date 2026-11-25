# SaveClock Studio — Reusable Checklists

Status: DRAFT · **Rev 2.2** · Date: 2026-11-08 · Owner: project owner
Agrees with [DECISIONS.md](DECISIONS.md). See [PRD.md](PRD.md), [ROADMAP.md](ROADMAP.md), [SECURITY.md](SECURITY.md), [QUALITY.md](QUALITY.md), [STANDARDS.md](STANDARDS.md).
Copy a section into a PR/issue and tick it. Every box needs evidence (link, command output, screenshot). Legal items need counsel's review; none of this is legal advice.

## Rev 2.2 changelog (2026-11-08)

- **Rev 2.2 (final verification):** header refreshed to Rev 2.2; speed gates now have targets plus G0 hard limits in QUALITY G0-13..G0-16 (V-03); no checklist item changed.

## Rev 2.1 changelog (DECISIONS §8a)

- **Rev 2.1:** gate numbers live in QUALITY §12 (G0-x IDs) and the QM catalog, not in ROADMAP or here; E-section audio checks follow the Mode A source rule; release-level periodic metrics reference QM IDs.

## Rev 2 changelog (reconciled to DECISIONS Rev 2)

- **A (readiness):** FFmpeg >= 8.1 pinned by the spike (T-0.13), not "7.x"; added worker VM + egress proxy, email provider/Mailpit, single origin, env-var inventory, TransNetV2 weights check, and "ROADMAP Appendix A has 0 orphans".
- **A2/D1 (legal):** decision record now reads: no public sharing, one 72 h clock from upload-complete, re-attach by hash, fingerprint warn-only (no title shown, not a strike). Age attestation 16+; cookie-free analytics instead of a consent banner; attribution in-app (not burned in); DMCA operator-tooling drill; Beat This training-data caveat (F-01) and TransNetV2 note (F-37) in the licence notices; Pixabay attribution request (F-22).
- **C/D2 (security/ops):** signed URL TTL <= 10 min (PUT <= 5 min); `-protocol_whitelist file`; worker VM with no inbound ports and allow-listed egress; retention audit tolerance 73 h; backups 14 days with monthly restore drill until launch; speed targets split (draft <= 120 s, render <= 60 s).
- **E (per-render checks):** cut frame is `floor((t_i - t0) * 30 + 0.5)` (C-01); checks now follow QUALITY §7 Block/Warn levels (C-18); internal hard cuts are a Warn (QM-066), with the release-level audit target in ROADMAP G2 (C-08).
- Gate ownership lives in [ROADMAP.md](ROADMAP.md); numeric G0 criteria are QUALITY §12 (G0-x IDs) and G2 criteria are the QUALITY QM catalog thresholds. G4 numeric criteria live in ROADMAP.

---

## A. Pre-implementation readiness (before writing any product code)

### A1. Decisions and docs
- [ ] DECISIONS.md approved by owner (status changed from DRAFT, date recorded)
- [ ] PRD.md approved; open questions OQ-01..OQ-14 each have an owner and a needed-by phase
- [ ] ARCHITECTURE.md, STANDARDS.md, SECURITY.md, QUALITY.md, DESIGN.md, UX-SPEC.md and `adr/` exist and do not contradict DECISIONS.md
- [ ] Licence register (ROADMAP T-0.6) complete: every MVP dependency/model is commercially usable or has an owner; TransNetV2 weights terms checked (T-0.14)
- [ ] ROADMAP Appendix A shows 0 orphans for US/FR/NFR, every SEC control and every gating QM
- [ ] Phase 0 spike report written and **G0 passed with the user's explicit "go"** (ROADMAP T-0.10; numeric G0 criteria in QUALITY §12, G0-x IDs)

### A2. Legal and terms
- [ ] Counsel engaged in writing (T-0.4); question list sent
- [ ] Pexels email sent, reply (or documented fallback) archived (T-0.5)
- [ ] Pixabay live terms re-read and answers recorded (report cites terms updated 20 Oct 2026)
- [ ] Decision recorded: no public sharing, one 72 h retention clock from upload-complete (re-attach by song hash), fingerprint warn-only (no title shown; not a strike), mode chosen after render, until counsel says otherwise

### A3. Access and environment
- [ ] API keys obtained and smoke-tested: Pexels, Pixabay, Anthropic (Haiku), Cloudflare R2, Sentry, fingerprint vendor trial, email provider trial (T-0.7)
- [ ] Email provider chosen (Postmark, Resend or SES; T-0.12) and sender domain SPF/DKIM/DMARC plan agreed; Mailpit in the dev compose (T-1.10, T-1.14)
- [ ] Secrets live in a secret store; `.env.example` has names only; env-var inventory `infra/ENV.md` complete (T-1.12); secret scan configured
- [ ] Staging host (Dokploy/Traefik VPS) reachable; single origin `app.<domain>` with Traefik path routing (`/api/*` to FastAPI) and TLS plan agreed
- [ ] Dedicated worker VM provisioned (T-1.19): no inbound ports, outbound only via the allow-listed egress proxy (Pexels, Pixabay, R2, LLM, fingerprint vendor); sandbox verified (T-1.16)
- [ ] Toolchains pinned: Python 3.12, Node (current LTS, exact version pinned), FFmpeg >= 8.1 with the exact build chosen in the spike (T-0.13), PostgreSQL 16, Redis 7 (two instances: broker `noeviction`, cache `allkeys-lru`)
- [ ] Config-malware guard command available in the shell history/alias and run before first npm/next/vite command

### A4. Process
- [ ] Plan for the phase authored with the `improve` skill (`plans/NNN-*.md`)
- [ ] If UI is touched: Sonnet-authored `plans/NNN-*.design.md` exists and the user approved it in writing; otherwise plan states "no UI — design phase skipped"
- [ ] Golden-set manifest (30 core + 20 hard tracks) exists with licence per track; no copyrighted audio in git
- [ ] Rollback approach written down for the first deploy

---

## B. Per-PR / Definition of Done

### B1. Before opening the PR
- [ ] Config-malware grep run before any npm/pnpm/yarn/next/vite/jest/eslint/build command, and after pull/checkout/rebase: `grep -lE "global\.[a-z]='[0-9]-|_\$_[0-9a-f]{4}=\(function" *.config.* 2>/dev/null` printed nothing
- [ ] Scope matches a plan item (T-id referenced in the PR body)
- [ ] Format, lint, type-check (TS strict / Python types), build all green
- [ ] Targeted tests pass 100%; **full suite** run and counts reported if the change touches shared code, schema, auth, build config, or before push
- [ ] New behaviour has tests (acceptance criteria from the US-id in PRD); bug fixes have a regression test; no skipped/deleted/loosened tests, no `any`/`@ts-ignore` to dodge types
- [ ] No hardcoded secrets; no string-built SQL; inputs validated (Pydantic); ownership check on every resource access
- [ ] FFmpeg/ffprobe calls go through the single audited runner: argument lists, `-protocol_whitelist file`, forced `-f` demuxer, probe limits; no user-controlled filter strings
- [ ] Model licence/dependency additions recorded in the licence ADR
- [ ] Logs contain no audio content, tokens or personal data beyond IDs

### B2. DB and contracts
- [ ] If a table/column/index/constraint/enum changed: message "DB CHANGE: ... — run this SQL: ..." posted and **acknowledged before commit**
- [ ] Migration has up and down, tested on a copy; backwards-compatible with the previous app version (zero-downtime)
- [ ] OpenAPI regenerated; generated TS client in `packages/contracts` updated; CI diff clean

### B3. UI changes only
- [ ] Matches the approved design spec; reuses existing components/tokens (`sattva-frontend-design-system`)
- [ ] Keyboard-only walkthrough done; visible focus not obscured; targets >= 24x24 CSS px; no horizontal scroll at 320 px
- [ ] axe-core: 0 serious/critical
- [ ] `web-interface-guidelines` run on changed UI files; accepted findings applied
- [ ] States covered: empty, loading, error, offline/retry

### B4. Review and close
- [ ] `ponytail-review` run on the diff; findings triaged with the user; accepted ones applied
- [ ] Change summary posted: files changed, type (bug fix/feature/refactor), DB/infra impact, risks
- [ ] Docs updated if behaviour/limits changed (PRD, UX-SPEC, QUALITY)
- [ ] User confirmed before moving on or pushing; **no push without an explicit instruction**

---

## C. Pre-release / pre-deploy

Run on every `git push`, deploy or publish. Read-only; report FOUND / NOT FOUND with evidence. **Never push if anything is FOUND**; stop, tell the user, do not clean it unless asked.

### C1. Malware and secrets scan
- [ ] Outgoing diff: `git diff origin/<branch>..<branch> | grep -nE "global\.[a-z]='[0-9]-[0-9]+'|_\$_[0-9a-f]{4}=\(function"`
- [ ] Working tree: `grep -rIlE "global\.[a-z]='[0-9]-[0-9]+'|_\$_[0-9a-f]{4}=\(function" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next`
- [ ] Config line-length check (any `*.config.{js,mjs,cjs,ts}` with a line > 1000 chars is SUSPICIOUS)
- [ ] `grep -rln "createRequire" --include="*.config.*" . --exclude-dir=node_modules` reviewed
- [ ] Committed history/refs checked: `git grep -lE "<regex>" $(git for-each-ref --format='%(refname)' refs/heads refs/remotes)` (a clean working tree is not a clean repo)
- [ ] Machine indicators absent: no `~/.node_module` dropper folder, no npm log with `--prefix ~/.node_module install axios socket.io-client`; if present, treat machine as compromised and revoke credentials from a different device
- [ ] Secret scanner (gitleaks or equivalent, inference) clean on the diff and history; `.env*` not tracked
- [ ] Dependency audit: no new critical/high advisories; lockfile committed; images pinned by digest/version

### C2. Build and verify
- [ ] Full suite green with counts recorded; type-check, lint, build green in CI
- [ ] Per-render quality suite (section E) green on the staging build; images built from the `api` (no torch/ffmpeg) and `worker` targets
- [ ] Container images built from the exact commit; run as non-root; workers on the worker VM have CPU/memory/time limits and read-only rootfs
- [ ] Staging smoke: signup (16+) -> upload -> automatic draft -> preview -> render -> export Mode A and Mode B (switching does not re-render)

### C3. Data and rollout
- [ ] Migrations announced via DB CHANGE and run on staging; down-migration tested
- [ ] Backup taken immediately before the deploy; restore procedure known
- [ ] Feature flags set (Stripe off until Phase 5)
- [ ] **Rollback plan written**: previous image tag, migration down or forward-fix, who executes, time budget
- [ ] Env vars/secrets diff reviewed (new ones set in the target environment)
- [ ] Deploy window chosen outside peak; user gave the explicit deploy instruction

### C4. After deploy
- [ ] Health checks green; Sentry shows no new error class in 30 min
- [ ] Synthetic render on production passes quality checks
- [ ] Queue depth, draft p95 (NFR-026) and render p95 (NFR-006) within target for 1 h
- [ ] Retention job ran; no object older than 73 h (72 h from upload-complete + 1 h grace)

---

## D. Public launch

Legal items require counsel's review before launch (DECISIONS §2).

### D1. Legal and policy
- [ ] Terms of Service: rights warranty, indemnity, DMCA policy, repeat-infringer policy, acceptable use, billing terms; counsel sign-off recorded
- [ ] Privacy Policy: data collected, processors (Anthropic, fingerprint vendor, Stripe, Sentry, R2), retention (72 h media from upload-complete; beat map, plan and song hash kept), deletion rights, age 16+ attestation (counsel confirms 16 vs 13, OQ-13), backups (14 days), international transfers
- [ ] **DMCA designated agent registered** with the US Copyright Office online directory ([Copyright Office DMCA directory](https://www.copyright.gov/dmca-directory/)); designations must be renewed every 3 years ([renewal guidance](https://www.copyright.gov/dmca-directory/transcripts/renew.pdf)); fee was $6 per 2016–17 alerts ([Greenberg Traurig](https://www.gtlaw.com/ar/insights/2016/12/new-dmca-regulations-existing-new-designated-agents-must-register-online)), re-verify the current fee at registration (F-27); renewal reminder in calendar; agent contact published in ToS/footer; operator tooling drilled (tabletop notice -> removal -> user notice -> strike < 24 h, T-4.10)
- [ ] Repeat-infringer policy implemented in code (strike log, threshold, suspension) and tested
- [ ] Takedown inbox and public form monitored; response SLA written (e.g. act within 24 h, inference); fingerprint matches are NOT strikes (only validated notices are)
- [ ] Rights warranty tick-box recorded with ToS version for every upload
- [ ] Cookies/analytics: first-party, cookie-free, aggregate event counts only, so no consent banner (DECISIONS §2); cookie inventory shows only essential cookies; counsel confirms (OQ-05); a banner is added only if this ever changes
- [ ] Pexels/Pixabay attribution shown in-app (export screen, credits sheet, "copy credits"), not burned into the video; link to each source as their current terms require (Pexels API docs ask for a prominent link back to Pexels; exact wording confirmed by email, T-0.5; Pixabay also asks to show users the source, F-22; [Pexels API](https://www.pexels.com/api/documentation/), [Pixabay terms](https://pixabay.com/service/terms/))
- [ ] Watermark does not misrepresent clip authorship; no "unaltered resale" of stock clips
- [ ] Third-party licence notices page (Beat This MIT, with the README caveat that some training data is copyright/CC-limited passed to counsel (F-01); SigLIP 2 Apache-2.0; PySceneDetect BSD-3; FFmpeg per build flags; TransNetV2 code MIT, weights per T-0.14)
- [ ] Stripe/tax/refund policy published (Phase 5)
- [ ] GDPR/UK basics (inference, counsel to confirm): lawful basis, DSAR process, DPA with processors, breach-notification procedure

### D2. Security
- [ ] `security-audit` (standard profile) run; 0 critical/high open; NEEDS-VALIDATION items triaged
- [ ] Authn/z: argon2id, email verification, CSRF, `__Host-` httpOnly Secure SameSite=Lax cookie on the single origin, Google OAuth PKCE, per-user ownership tests green
- [ ] Rate limits, Turnstile and abuse controls on signup, upload, render; email verification enforced
- [ ] Malformed-media corpus test passes; FFmpeg non-root, no network (worker VM egress proxy allow-list only), `-protocol_whitelist file`
- [ ] Security headers (CSP, HSTS, X-Content-Type-Options, frame-ancestors) set; TLS A-grade (inference)
- [ ] Presigned GET TTL <= 10 min and PUT <= 5 min; buckets private with per-bucket tokens; no public listing
- [ ] Secrets rotated from any value ever used in dev/test; Stripe webhook secret set

### D3. Observability and operations
- [ ] Sentry in web, API, workers; sourcemaps uploaded; alert routing tested
- [ ] Metrics and dashboards: render success rate, queue age, stage timings, p95s, COGS per video
- [ ] Alerts: failure rate > 5% / 15 min, queue age, disk, certificate expiry, DMCA inbox
- [ ] Status page or documented incident comms
- [ ] On-call/owner and runbook (links to `infra/` notes) exist

### D4. Support
- [ ] Support email and in-app "Report an issue" path (needed for octave/beat errors, R-05; T-3.13)
- [ ] Canned replies: takedown, refund, tempo wrong, clip complaint
- [ ] FAQ: modes A/B, retention, music rights, watermark, limits
- [ ] Account deletion works end to end (US-025)

### D5. Backups and recovery
- [ ] Nightly encrypted PostgreSQL dumps stored off-host, 14-day retention; **restore drill passed** (monthly until launch, then quarterly; RPO <= 24 h, RTO <= 4 h; inference targets); deletion tombstones replayed on restore
- [ ] R2 holds only ephemeral media (72 h), so no media backup required; confirm this stays true
- [ ] Redis loss tested: jobs recover or fail cleanly

### D6. Product and performance
- [ ] G4 (and G5 if charging) passed with evidence
- [ ] Load test: 3x expected peak, render p95 <= 60 s and draft p95 <= 120 s (ROADMAP T-5.4)
- [ ] WCAG 2.2 AA audit passed; browser matrix e2e green
- [ ] Analytics events for KPIs (activation, render success, time-to-first-video, conversion) verified (cookie-free, aggregate)
- [ ] Landing page copy reviewed for rights claims (no "use any song freely" language)

---

## E. Per-render quality checks (summary; details in [QUALITY.md](QUALITY.md) §7)

Automatic, run on every render. **Block** failures fail the job and do not decrement quota (FR-036); **Warn** failures are recorded and surfaced but do not fail the job. QUALITY §7 is the authority for levels.

| # | Check | Pass criterion | Level | Source |
|---|---|---|---|---|
| E1 | Cut timing (render fidelity) | every cut within +-1 frame of the planned index `f_i = floor((t_i - t0) * 30 + 0.5)`; any cut > 1 frame off blocks, exactly 1 warns | Block / Warn | NFR-003, QM-064 |
| E2 | A/V drift and start offset | <= 1 frame over the full duration (60 s max); start offset > 33.3 ms blocks | Block | NFR-004, QM-067, QM-068 |
| E3 | Duration and frame count | equals selected length +-1 frame | Block (> 1) / Warn (= 1) | NFR-004, QM-062, QM-063 |
| E4 | Audio integrity | Mode A: audio comes from the validated original `audio_source`, trimmed once (AAC-LC stream copy, otherwise one AAC-LC 48 kHz encode, no other processing); Mode B: no audio stream | Block | FR-015, FR-018, QM-087 |
| E5 | Stream spec and sanity | H.264 High, yuv420p, 30 fps CFR, AAC-LC 48 kHz, `+faststart`, resolution per tier; exactly 1 video + <= 1 audio stream; playable end to end | Block | FR-016, QM-060, QM-061, QM-075, QM-077 |
| E6 | Internal hard cuts / unplanned cuts | detectors find no unplanned cut in the output; release target is QM-036 (QUALITY; G0-19, ROADMAP G2 references it) | Warn | NFR-005, QM-066 |
| E7 | Repeats | 0 repeated clips unless pool exhausted (flag recorded) | Block (plan) | NFR-005, QM-038 |
| E8 | Watermark | present iff Free tier | Block | FR-030 |
| E9 | Attribution | every clip has source + link recorded for the in-app credits list | Block | FR-026 |
| E10 | Beat sanity | BPM within 70-180 after clamp; user override honoured | Block | NFR-002 |
| E11 | Black/frozen frames, loudness | black frames >= 6 block (3-5 warn); frozen > 0.5 s warns; loudness/silence warnings | Block / Warn | QM-070, QM-071, QM-073, QM-074 |
| E12 | Timing/cost | stage timings logged; analysis <= 20 s, draft <= 120 s, render <= 60 s, Mode A remux <= 5 s at p95; cost recorded | Monitor | NFR-006, NFR-007, NFR-010, NFR-026, NFR-027 |

Periodic (not per render): golden-set core metrics per QUALITY QM-001, QM-003, QM-004, QM-010, QM-016 (NFR-001; hard set reported only) and musical alignment QM-026 (NFR-028) on each release; 100-render soak before G2; human spot review of 10 random renders weekly during beta (inference).

---

## Sources and notes
- DMCA agent renewal every 3 years: Copyright Office guidance linked above (search summary; the page itself could not be fetched here). Fee figure comes from 2016–17 law-firm alerts and must be re-verified.
- WCAG 2.2: https://www.w3.org/TR/WCAG22/ (new AA criteria: 2.4.11, 2.5.7, 2.5.8, 3.3.8).
- Pexels attribution wording was not retrieved verbatim (fetch blocked); the report states a prominent link back is required. Confirm per T-0.5.
- Items marked (inference) are proposals, not facts from sources.
