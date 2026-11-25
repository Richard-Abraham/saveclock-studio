# SaveClock Studio — Reusable Checklists

Status: DRAFT · **Rev 3.3 — Personal edition** · Date: 2026-11-08 · Owner: project owner
**Rev 3.3 (2026-11-08):** DECISIONS §8d: upload item says single streamed 100 MB upload; Settings checks use `GET /settings`; no signed-link checks.
**Rev 3.2 (2026-11-08):** aligned to DECISIONS Rev 3.2: serve-verification and Caddy fallback items, key-status check, quota wording removed.
**Rev 3 changelog:** public-launch legal/compliance sections (old D) removed and replaced by a pointer to the archive (section D); pre-implementation, per-PR DoD, pre-deploy (malware guard + pre-push scan) and per-render checks kept; new personal deploy checklist (Tailscale ACL, no public ports, backups, restore test). Rev 2.2 checklists are archived unchanged in `archive/public-edition-rev2.2/CHECKLIST.md`.
Agrees with [DECISIONS.md](DECISIONS.md). See [PRD.md](PRD.md), [ROADMAP.md](ROADMAP.md), [SECURITY.md](SECURITY.md), [QUALITY.md](QUALITY.md), [STANDARDS.md](STANDARDS.md).
Copy a section into a PR/issue and tick it. Every box needs evidence (link, command output, screenshot). No lawyer is needed for the personal edition; Phase P is designed to stay lawyer-free (DECISIONS §8b).

---

## A. Pre-implementation readiness (before writing any product code)

### A1. Decisions and docs
- [ ] DECISIONS.md (Rev 3.2) approved by owner (status changed from DRAFT, date recorded)
- [ ] PRD.md approved; open questions OQ-02, OQ-06, OQ-11, OQ-14, OQ-15, OQ-16 each have an owner and a needed-by phase
- [ ] ARCHITECTURE.md, STANDARDS.md, SECURITY.md, QUALITY.md, DESIGN.md, UX-SPEC.md and `adr/` exist and do not contradict DECISIONS.md
- [ ] Licence register (ROADMAP T-0.6) complete: every MVP dependency/model is commercially usable or marked for Phase P
- [ ] ROADMAP Appendix A shows 0 orphans for every active US/FR/NFR, SEC and QM ID
- [ ] Phase 0 spike report written and **G0 passed with the user's explicit "go"** (ROADMAP T-0.10; numeric G0 criteria in QUALITY §12, G0-x IDs); browser-feasibility go/no-go recorded (T-0.16)

### A2. Access and environment
- [ ] API keys obtained and smoke-tested: Pexels (free), Anthropic (optional; offline fallback otherwise) (T-0.7)
- [ ] Tailscale account (free Personal plan) with the VPS, phone and laptop joined; `tailscale serve` hello page reachable from phone and laptop, and path routing, SSE streaming, 100 MB streamed upload and identity headers verified (Caddy-on-tailnet-IP fallback if not) (T-0.15)
- [ ] 4-vCPU x86 box chosen for benchmarks (the VPS if it qualifies, OQ-16)
- [ ] Secrets live in `.env`/a secret store; `.env.example` has names only; env-var inventory `infra/ENV.md` complete (T-1.12); secret scan configured
- [ ] Toolchains pinned: Python 3.12, Node (current LTS, exact version pinned), FFmpeg >= 8.1 with the exact build chosen in the spike (T-0.13), PostgreSQL 16, Redis 7 (single instance, `noeviction`)
- [ ] Config-malware guard command available in the shell history/alias and run before first npm/next/vite command

### A3. Process
- [ ] Plan for the phase authored with the `improve` skill (`plans/NNN-*.md`)
- [ ] If UI is touched: Sonnet-authored `plans/NNN-*.design.md` exists and the user approved it in writing; otherwise plan states "no UI — design phase skipped"
- [ ] Golden-set manifest (30 core + 20 hard tracks from the owner's library) exists; no audio in git
- [ ] Backup destination and tool decided (OQ-15)
- [ ] Rollback approach written down for the first deploy

---

## B. Per-PR / Definition of Done

### B1. Before opening the PR
- [ ] Config-malware grep run before any npm/pnpm/yarn/next/vite/jest/eslint/build command, and after pull/checkout/rebase: `grep -lE "global\.[a-z]='[0-9]-|_\$_[0-9a-f]{4}=\(function" *.config.* 2>/dev/null` printed nothing
- [ ] Scope matches a plan item (T-id referenced in the PR body)
- [ ] Format, lint, type-check (TS strict / Python types), build all green
- [ ] Targeted tests pass 100%; **full suite** run and counts reported if the change touches shared code, schema, auth/tailnet guard, build config, or before push
- [ ] New behaviour has tests (acceptance criteria from the US-id in PRD); bug fixes have a regression test; no skipped/deleted/loosened tests, no `any`/`@ts-ignore` to dodge types
- [ ] No hardcoded secrets; no string-built SQL; inputs validated (Pydantic); every query scoped by `user_id`
- [ ] FFmpeg/ffprobe calls go through the single audited runner: argument lists, `-protocol_whitelist file`, forced `-f` demuxer, probe limits; no user-controlled filter strings
- [ ] Model licence/dependency additions recorded in the licence ADR
- [ ] Logs contain no audio content or tokens

### B2. DB and contracts
- [ ] If a table/column/index/constraint/enum changed: message "DB CHANGE: ... — run this SQL: ..." posted and **acknowledged before commit**
- [ ] Migration has up and down, tested on a copy; backwards-compatible with the previous app version
- [ ] OpenAPI regenerated; generated TS client in `packages/contracts` updated; diff clean

### B3. UI changes only
- [ ] Matches the approved design spec; reuses existing components/tokens (`sattva-frontend-design-system`)
- [ ] Keyboard-only walkthrough done; visible focus not obscured; targets >= 24x24 CSS px; no horizontal scroll at 320 px
- [ ] axe-core: 0 serious/critical
- [ ] `web-interface-guidelines` run on changed UI files; accepted findings applied
- [ ] States covered: empty, loading, error, offline/retry, tailnet-disconnected

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
- [ ] Full suite green with counts recorded; type-check, lint, build green (`make check`, or CI if enabled)
- [ ] Per-render quality suite (section E) green; images built from the `api` (no torch/ffmpeg) and `worker` targets
- [ ] Containers built from the exact commit; run as non-root with CPU/memory/time limits
- [ ] Smoke: open over Tailscale -> upload -> automatic draft -> preview -> render -> export Mode A and Mode B (switching does not re-render)

### C3. Data and rollout
- [ ] Migrations announced via DB CHANGE and run on a copy; down-migration tested
- [ ] Backup taken immediately before the deploy; restore procedure known
- [ ] **Rollback plan written**: previous image tag, migration down or forward-fix, who executes, time budget
- [ ] Env vars/secrets diff reviewed (new ones set in the target environment)
- [ ] User gave the explicit deploy instruction

### C4. After deploy
- [ ] `/api/v1/health/ready` green; no new error class in the logs in 30 min
- [ ] Synthetic render passes quality checks
- [ ] Queue depth, draft (NFR-026) and render (NFR-006) timings within target for 1 h
- [ ] Housekeeping job ran; no intermediates older than 7 days + 1 h grace (NFR-017)

---

## D. Phase P — see archive

The public-launch legal/compliance checklist (ToS, Privacy, DMCA agent, rights warranty, age gate, analytics consent, GDPR basics, Stripe/tax, pen test, status page, support) is archived unchanged in `archive/public-edition-rev2.2/CHECKLIST.md` (old section D). It is not used in this edition. When Phase P starts, a new checklist is written from DECISIONS §8b (songs and outputs stay on the device, minimal data, merchant of record, standard templates, no features needing legal judgment); items that would need counsel are redesigned out.

---

## D2. Personal deploy checklist (every deploy of the live stack)

### Network exposure
- [ ] Tailscale ACL reviewed: only the owner's devices can reach the node; node key expiry understood
- [ ] No public ports: external scan of the VPS public IP shows no app/Postgres/Redis port open (NFR-029); no Traefik/public route; compose publishes no host ports for app services
- [ ] App reachable only at the `*.ts.net` HTTPS URL; checked from phone and laptop; unreachable from a device off the tailnet
- [ ] Tailnet guard test green: requests without the Tailscale proxy identity are rejected (FR-047)
- [ ] SSH key-only, auto-updates on, Docker socket not mounted into any container

### Backups and recovery
- [ ] Last nightly backup succeeded (DB dump + project files, off-box, encrypted) and is no older than 24 h
- [ ] **Restore test** into scratch done after any backup-config change and at least quarterly; app lists projects and file checksums match (NFR-030); elapsed time recorded
- [ ] Disk: free space above the warning threshold; housekeeping ran; Settings disk usage matches `du` (FR-048)

### Config and keys
- [ ] Pexels key present; Anthropic key present or deliberately unset (offline fallback verified); Settings key status shows the expected Set / Not set for each provider (`GET /settings`); Pixabay switch in the intended state (FR-051)
- [ ] Secrets rotated if ever shared or committed; `.env` not in git

---

## E. Per-render quality checks (summary; details in [QUALITY.md](QUALITY.md) §7)

Automatic, run on every render. **Block** failures fail the job and (FR-036); **Warn** failures are recorded and surfaced but do not fail the job. QUALITY §7 is the authority for levels.

| # | Check | Pass criterion | Level | Source |
|---|---|---|---|---|
| E1 | Cut timing (render fidelity) | every cut within +-1 frame of the planned index `f_i = floor((t_i - t0) * 30 + 0.5)`; any cut > 1 frame off blocks, exactly 1 warns | Block / Warn | NFR-003, QM-064 |
| E2 | A/V drift and start offset | <= 1 frame over the full duration (60 s max); start offset > 33.3 ms blocks | Block | NFR-004, QM-067, QM-068 |
| E3 | Duration and frame count | equals selected length +-1 frame | Block (> 1) / Warn (= 1) | NFR-004, QM-062, QM-063 |
| E4 | Audio integrity | Mode A: audio comes from the validated original `audio_source`, trimmed once (AAC-LC stream copy, otherwise one AAC-LC 48 kHz encode, no other processing); Mode B: no audio stream | Block | FR-015, FR-018, QM-087 |
| E5 | Stream spec and sanity | H.264 High, yuv420p, 30 fps CFR, AAC-LC 48 kHz, `+faststart`, 1080x1920; exactly 1 video + <= 1 audio stream; playable end to end | Block | FR-016, QM-060, QM-061, QM-075, QM-077 |
| E6 | Internal hard cuts / unplanned cuts | detectors find no unplanned cut in the output; release target is QM-036 (QUALITY; G0-19, ROADMAP G2 references it) | Warn | NFR-005, QM-066 |
| E7 | Repeats | 0 repeated clips unless pool exhausted (flag recorded) | Block (plan) | NFR-005, QM-038 |
| E8 | Attribution | every clip has source + link recorded for the in-app credits list | Block | FR-026 |
| E9 | Beat sanity | BPM within 70-180 after clamp; user override honoured | Block | NFR-002 |
| E10 | Black/frozen frames, loudness | black frames >= 6 block (3-5 warn); frozen > 0.5 s warns; loudness/silence warnings | Block / Warn | QM-070, QM-071, QM-073, QM-074 |
| E11 | Timing/cost | stage timings logged; analysis <= 20 s, draft <= 120 s, render <= 60 s, Mode A remux <= 5 s at p95; cost recorded | Monitor | NFR-006, NFR-007, NFR-010, NFR-026, NFR-027 |

Periodic (not per render): golden-set core metrics per QUALITY QM-001, QM-003, QM-004, QM-010, QM-016 (NFR-001; hard set reported only) and musical alignment QM-026 (NFR-028) on each release; 100-render soak before G2; owner spot review of 10 random renders during the G4 dogfood (inference).

---

---

## Sources and notes
- WCAG 2.2: https://www.w3.org/TR/WCAG22/ (new AA criteria: 2.4.11, 2.5.7, 2.5.8, 3.3.8).
- Items marked (inference) are proposals, not facts from sources.
