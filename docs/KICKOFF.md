# SaveClock Studio — Kickoff Proposal (Personal edition, for owner approval)

Status: **AWAITING APPROVAL** · 2026-11-08 · Closes Phase A when approved.
**Rev 3.3 (2026-11-08):** DECISIONS §8d simplifications: one streamed upload, no signed file tokens, no `op_id`, `exports` folded into `renders` (8 tables), 27 endpoints, one simple eval script; T-0.16 browser feasibility is non-gating (not part of G0); baseline migration tables stated exactly (`users` incl. `settings`, `projects`, `songs`, `jobs`).
**Rev 3.2 (2026-11-08):** aligned to DECISIONS Rev 3.2 (§8c): `worker-maint` service, owner seeded by the baseline migration, `tailscale serve` verification with Caddy fallback in T-0.15, Settings endpoints; traceability closed.
**Rev 3 changelog:** rewritten for the single-owner personal edition on Tailscale (DECISIONS Rev 3.1). No accounts, billing or compliance tables; no lawyer; Phase 0 drops all legal tasks and adds Tailscale reachability and `tailscale serve` verification with a Caddy fallback (T-0.15) and browser-side feasibility (T-0.16). The public-edition kickoff is archived unchanged in `archive/public-edition-rev2.2/KICKOFF.md`.
Approving this file approves the doc set at Rev 3.3 and authorizes **Phase 0 only**. Phase 1 needs its own plan (`plans/001-walking-skeleton.md`, via the `improve` skill) and approval after gate G0.

**No lawyer is needed now** (one user, own files, Pexels license allows personal and commercial use). **Phase P (public edition) is designed to stay lawyer-free** (DECISIONS §8b): songs and outputs stay on the user's device, minimal data, a merchant of record (Paddle or Lemon Squeezy) for payments, standard templates, no features that need legal judgment.

## 1. Product summary
SaveClock Studio is a mobile-first web app for one user, the owner, reachable only over the owner's Tailscale network (no login screen). The owner uploads a song (≤ 100 MB, 15 s–10 min). The app finds beats, downbeats and energy sections (Beat This!, DSP), generates stock-search keywords (Claude Haiku, with an offline fallback table when no key is set), fetches and ranks vertical clips (Pexels by default, Pixabay as a toggle; SigLIP 2), rejects clips with internal cuts, and builds a draft cut list snapped to the beat. The owner tweaks tempo, density, segment and clips, previews in the browser, and renders a 1080×1920 silent master. At export they choose **Mode A** (song remuxed in, private download) or **Mode B** (silent MP4 + JSON/CSV beat map). Files stay until the owner deletes the project; intermediates are housekept after 7 days. Details: `PRD.md`.

## 2. Milestone scope
| Phase | Scope | Exit gate |
|---|---|---|
| **0 — Validation spike** (next) | Throwaway scripts only, in `eval/` / scratch: Beat This accuracy and CPU speed on ~50 tracks from the owner's library, Pexels availability for 50 keywords, FFmpeg frame-exact prototype with an 8.1 vs 9.0 comparison, contended-load timing, licence register, Tailscale reachability (T-0.15), non-gating browser-side feasibility note for Phase P (T-0.16) | **G0** = `QUALITY.md` §12 + T-0.15 (`ROADMAP.md`); T-0.16 does not gate G0 |
| 1 — Walking skeleton | Repo, local gates, compose stack (web, api, worker, worker-maint, postgres, redis, tailscale sidecar with `tailscale serve`), `/api/v1/health/live` and `/api/v1/health/ready`, baseline migration with the owner user seeded, filesystem `BlobStore`, nightly backup and a restore proof | G1 |
| 2 — Core pipeline | Upload, analysis, plan, stock, render, export | G2 |
| 3 — Editor UX | Design approval gate, then the screens | G3 |
| 4 — Personal polish & ops | Observability, restore drill, hardening, error handling, performance | G4 |
| 5 — Extras | AI hero shots, structure models, TransNetV2, PWA | per item |
| P — Public edition | Deferred; starts with a decision on browser-side processing (T-P.0) | defined when P starts |

## 3. Stack and key decisions
Next.js 16 · FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic · Dramatiq 2 (queues: analysis, fetch, render, maintenance) · Postgres 16 · one Redis · local-disk `BlobStore` · FFmpeg ≥ 8.1 · Beat This! · SigLIP 2 · PySceneDetect · Claude Haiku. Everything runs as one Docker Compose stack on the existing VPS, exposed only through Tailscale (`tailscale serve`, HTTPS on `*.ts.net`, no public port, no worker VM). The full list with reasons is in `DECISIONS.md` and `adr/`.

## 4. Data model sketch
Phase 1 baseline migration `0001_baseline` creates exactly four tables: `users` (one seeded owner row, incl. `settings` jsonb), `projects`, `songs` (sha256 kept), `jobs` (`render_id` is a plain nullable column until `renders` exists).
Phase 2: `analyses`, `clip_candidates` (attribution metadata), `edit_plans` (versioned JSON contract), `renders` (silent master + cut lists; Mode A kept as `mode_a_key`/`mode_a_state` on the same row, no separate exports table).
No accounts, sessions, consents, billing, DMCA, fingerprint or usage tables in this edition (they live in the archived design for Phase P).
Every row carries `user_id` and every query is scoped by it (the seam for Phase P). Full detail: `ARCHITECTURE.md`.

## 5. Folder tree
The monorepo layout (`apps/web`, `services/api`, `packages/contracts`, `infra/`, `eval/`, `docs/`, `plans/`) is defined in `STANDARDS.md` §1. Folders are created only when their first file is written.

## 6. First vertical slice (Phase 2 entry, after skeleton)
Upload, validate, analyze, then show the beat map. The owner uploads a song; the worker validates it with ffprobe and runs Beat This. The API returns `analyses.beat_map`, and a dev page lists the BPM and beat times. Tests cover `user_id` scoping, the tailnet guard, a rejected malformed file, and a frame-exact golden click-track.

## 7. What the owner must provide to start Phase 0
- [ ] **Pexels API key** (free)
- [ ] **Anthropic API key** (optional; without it keywords come from the offline fallback table)
- [ ] **Tailscale account** (free Personal plan) with the VPS, your phone and your laptop joined to the tailnet
- [ ] **A 4-vCPU x86 box for benchmarks**: the VPS itself if it qualifies (say so, and I will measure it), otherwise another machine
- [ ] **About 50 tracks from your own library** (30 core + 20 hard; stored privately, never committed) plus time to tap/correct beat annotations, or accept model-seeded annotations that you correct for a 20-track subset
- [ ] **An iPhone and/or an Android phone** for preview and A/V sync testing
- [ ] **A backup destination** you control (restic/borg target or an rclone remote); needed by Phase 1
- No lawyer, counsel budget, DMCA agent, payment account or email provider is needed.

## 8. Approval
Reply **"approve kickoff"**, with any changes, to close Phase A and start Phase 0.
Open owner decisions are PRD §12 (OQ-11, OQ-15, OQ-16). None of them block Phase 0 except OQ-16 (which box to benchmark on).
