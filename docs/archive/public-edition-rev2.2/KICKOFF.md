# SaveClock Studio — Kickoff Proposal (for owner approval)

Status: **AWAITING APPROVAL** · 2026-11-08 · Closes Phase A when approved.
Approving this file approves the doc set at Rev 2.2 and authorizes **Phase 0 only**. Phase 1 needs its own plan (`plans/001-walking-skeleton.md`, via the `improve` skill) and approval after gate G0.

## 1. Product summary
SaveClock Studio is a mobile-first web app. A signed-in user (16+) uploads a song (≤ 100 MB, 15 s–10 min). The app finds beats, downbeats and energy sections (Beat This!, DSP), generates stock-search keywords (Claude Haiku), fetches and ranks vertical clips (Pexels/Pixabay, SigLIP 2), rejects clips with internal cuts, and builds a draft cut list snapped to the beat. The user can tweak tempo, density, segment and clips, preview in the browser, and render a silent 9:16 master. At export they choose **Mode A** (song remuxed in, private download) or **Mode B** (silent MP4 + JSON/CSV beat map). All media is deleted 72 h after upload. Details: `PRD.md`.

## 2. Milestone scope
| Phase | Scope | Exit gate |
|---|---|---|
| **0 — Validation spike** (next) | Throwaway scripts only, in `eval/` / scratch: Beat This accuracy and CPU speed on 50 tracks, stock availability for 50 keywords, FFmpeg frame-exact prototype with an 8.1 vs 9.0 comparison, contended-load timing, R2 size enforcement, legal engagement, Pexels terms email, license register | **G0** = `QUALITY.md` §12 (G0-1…G0-27) |
| 1 — Walking skeleton | Repo, gates, CI, Docker (api/worker/web), compose dev environment, `/api/v1/health`, migration `0001_baseline`, minimal auth (users, sessions, CSRF, age attestation), worker VM + egress proxy, backup-restore proof | G1 |
| 2–5 | Core pipeline → editor UX → accounts/compliance → paid launch | G2–G5 (`ROADMAP.md`) |

## 3. Stack and key decisions
Next.js 16 · FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic · Dramatiq 2 (queues: analysis, fetch, render, maintenance) · Postgres 16 · Redis · Cloudflare R2 (4 private buckets) · FFmpeg ≥ 8.1 · Beat This! · SigLIP 2 · PySceneDetect · Claude Haiku. Single origin behind Traefik. Web, API and DB on the Dokploy VPS; workers on a dedicated isolated VM. The full list with reasons is in `DECISIONS.md` and `adr/0001–0011`.

## 4. Data model sketch
Phase 1 tables: `users`, `consents`, `sessions`, `projects` (status, rights warranty, single `expires_at` clock), `songs` (sha256 kept for re-attach), `jobs`, `audit_log`.
Phase 2: `analyses`, `clip_candidates` (attribution metadata), `edit_plans` (versioned JSON contract), `renders` (silent master + cut lists), `exports` (Mode A), `fingerprint_events`.
Phases 4–5: OAuth, email tokens/outbox, usage counters, DMCA notices/strikes, subscriptions, Stripe events.
Every user-owned query is scoped by `user_id`; cross-user access returns 404. Full detail: `ARCHITECTURE.md` §6 and §21.

## 5. Folder tree
The monorepo layout (`apps/web`, `services/api`, `packages/contracts`, `infra/`, `eval/`, `docs/`, `plans/`) is defined in `STANDARDS.md` §1. Folders are created only when their first file is written.

## 6. First vertical slice (Phase 2 entry, after skeleton)
Upload, validate, analyze, then show the beat map. A signed-in user uploads a song via a presigned URL. The worker validates it with ffprobe and runs Beat This. The API returns `analyses.beat_map`, and a dev page lists the BPM and beat times. Tests cover the ownership check (another user gets 404), a rejected malformed file, and a frame-exact golden click-track.

## 7. What the owner must provide to start Phase 0
- [ ] A named counsel, or a budget for one (T-0.4)
- [ ] API keys: Pexels, Pixabay, Anthropic, Cloudflare R2, Sentry (T-0.7)
- [ ] Annotation help or budget for the 50-track spike set, plus a second annotator for agreement (QUALITY Q3/Q4)
- [ ] Test devices: an iPhone with Safari and an Android phone with Chrome (QUALITY Q10)
- [ ] Choice of x86 4-vCPU box for benchmarks (the future worker VM size)

## 8. Approval
Reply **"approve kickoff"**, with any changes, to close Phase A and start Phase 0.
Open owner decisions and counsel questions are listed in `review/final-verification.md` §6. None of them block Phase 0.
