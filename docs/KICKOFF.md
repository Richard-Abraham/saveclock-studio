# SaveClock Studio — Kickoff Proposal (Personal edition, for owner approval)

Status: **AWAITING APPROVAL** · 2026-11-26 (Rev 3.6) · Closes Phase A when approved.
**Rev 3.6 (2026-11-26):** aligned to DECISIONS Rev 3.5/3.6 (§8f local-only, §8g trimmed Phase 0): no VPS, no Tailscale; ports on 127.0.0.1 with Host/Origin checks; web editor plus a `saveclock` CLI driven by Claude Code; auto-detected concurrency/threads; no golden set, labelling, canary or speed run in Phase 0; FFmpeg pinned to the BtbN 9.0.x GPL static build by sha256; Phase 0 steps 1-7 done. New tasks T-1.22, T-2.26, T-2.27, T-2.28; T-0.15 dropped.
**Rev 3.3 (2026-11-08):** DECISIONS §8d simplifications: one streamed upload, no signed file tokens, no `op_id`, `exports` folded into `renders` (8 tables), 27 endpoints, one simple eval script; T-0.16 browser feasibility is non-gating (not part of G0); baseline migration tables stated exactly (`users` incl. `settings`, `projects`, `songs`, `jobs`).
**Rev 3.2 (2026-11-08):** aligned to DECISIONS Rev 3.2 (§8c): `worker-maint` service, owner seeded by the baseline migration, `tailscale serve` verification with Caddy fallback in T-0.15, Settings endpoints; traceability closed.
**Rev 3 changelog:** rewritten for the single-owner personal edition on Tailscale (DECISIONS Rev 3.1). No accounts, billing or compliance tables; no lawyer; Phase 0 drops all legal tasks and adds Tailscale reachability and `tailscale serve` verification with a Caddy fallback (T-0.15) and browser-side feasibility (T-0.16). The public-edition kickoff is archived unchanged in `archive/public-edition-rev2.2/KICKOFF.md`.
Approving this file approves the doc set at Rev 3.6 and authorizes **Phase 0 only**. Phase 1 needs its own plan (`plans/001-walking-skeleton.md`, via the `improve` skill) and approval after gate G0.

**No lawyer is needed now** (one user, own files, Pexels license allows personal and commercial use). **Phase P (public edition) is designed to stay lawyer-free** (DECISIONS §8b): songs and outputs stay on the user's device, minimal data, a merchant of record (Paddle or Lemon Squeezy) for payments, standard templates, no features that need legal judgment.

## 1. Product summary
SaveClock Studio is a mobile-first web app for one user, the owner, running only on the owner's own machine (no login screen; reached at `localhost`, from the browser or from Claude Code through the `saveclock` CLI). The owner uploads a song (≤ 100 MB, 15 s–10 min). The app finds beats, downbeats and energy sections (Beat This!, DSP), generates stock-search keywords (typed in the editor or set by Claude Code; Claude Haiku only if a key is set; else an offline fallback table), fetches and ranks vertical clips (Pexels by default, Pixabay as a toggle; SigLIP 2), rejects clips with internal cuts, and builds a draft cut list snapped to the beat. The owner tweaks tempo, density, segment and clips, previews in the browser, and renders a 1080×1920 silent master. At export they choose **Mode A** (song remuxed in, private download) or **Mode B** (silent MP4 + JSON/CSV beat map). Files stay until the owner deletes the project; intermediates are housekept after 7 days. Details: `PRD.md`.

## 2. Milestone scope
| Phase | Scope | Exit gate |
|---|---|---|
| **0 — Validation spike** (next) | Throwaway scripts only, in `eval/` / scratch. Steps 1-7 are done: synthetic beat self-tests, FFmpeg frame-exact harness with the 8.1.3 vs 9.0.x screen (BtbN 9.0.x pinned by sha256), hardening tests, licence-register draft. Still to run: Pexels availability for 50 keywords (needs the Pexels key) and a SigLIP/PySceneDetect smoke test. **Dropped (DECISIONS §8g/§8f):** golden set, clip-rating session, phone sync canary, speed and contended-load runs, Tailscale (T-0.15). Non-gating browser-side feasibility note for Phase P (T-0.16) | **G0** = the measured rows of `QUALITY.md` §12 (see ROADMAP G0, rewritten per DECISIONS §8g); the dropped rows are "not measured"; T-0.16 does not gate G0 |
| 1 — Walking skeleton | Repo, local gates, compose stack on the owner's machine (web, api, worker, worker-maint, postgres, redis; ports on 127.0.0.1; Host/Origin middleware), `/api/v1/health/live` and `/api/v1/health/ready`, baseline migration with the owner user seeded, filesystem `BlobStore`, nightly backup and a restore proof | G1 |
| 2 — Core pipeline | Upload, analysis, plan, stock, render, export | G2 |
| 3 — Editor UX | Design approval gate, then the screens | G3 |
| 4 — Personal polish & ops | Observability, restore drill, hardening, error handling, performance | G4 |
| 5 — Extras | AI hero shots, structure models, TransNetV2, PWA | per item |
| P — Public edition | Deferred; starts with a decision on browser-side processing (T-P.0) | defined when P starts |

## 3. Stack and key decisions
Next.js 16 · FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic · Dramatiq 2 (queues: analysis, fetch, render, maintenance) · Postgres 16 · one Redis · local-disk `BlobStore` · FFmpeg 9.0.x (BtbN GPL static) · Beat This! · SigLIP 2 · PySceneDetect · Claude Haiku. Everything runs as one Docker Compose stack on the owner's own machine, every port bound to 127.0.0.1 (no VPS, no Tailscale, no public port, no worker VM). FFmpeg is the BtbN 9.0.x GPL static build, pinned by sha256. The full list with reasons is in `DECISIONS.md` and `adr/`.

## 4. Data model sketch
Phase 1 baseline migration `0001_baseline` creates exactly four tables: `users` (one seeded owner row, incl. `settings` jsonb), `projects`, `songs` (sha256 kept), `jobs` (`render_id` is a plain nullable column until `renders` exists).
Phase 2: `analyses`, `clip_candidates` (attribution metadata), `edit_plans` (versioned JSON contract), `renders` (silent master + cut lists; Mode A kept as `mode_a_key`/`mode_a_state` on the same row, no separate exports table).
No accounts, sessions, consents, billing, DMCA, fingerprint or usage tables in this edition (they live in the archived design for Phase P).
Every row carries `user_id` and every query is scoped by it (the seam for Phase P). Full detail: `ARCHITECTURE.md`.

## 5. Folder tree
The monorepo layout (`apps/web`, `services/api`, `packages/contracts`, `infra/`, `eval/`, `docs/`, `plans/`) is defined in `STANDARDS.md` §1. Folders are created only when their first file is written.

## 6. First vertical slice (Phase 2 entry, after skeleton)
Upload, validate, analyze, then show the beat map. The owner uploads a song; the worker validates it with ffprobe and runs Beat This. The API returns `analyses.beat_map`, and a dev page lists the BPM and beat times. Tests cover `user_id` scoping, the Host/Origin guard, a rejected malformed file, and a frame-exact golden click-track.

## 7. What the owner must provide to start Phase 0
- [ ] **Pexels API key** (free)
- [ ] **Anthropic API key** (optional; without it keywords come from the offline fallback table)
- ~~**Tailscale account** with the VPS, phone and laptop~~ dropped in Rev 3.5 (local-only)
- [ ] **The machine's specs** (`lscpu`, RAM, disk): the app auto-detects its concurrency; no separate benchmark box is needed (DECISIONS §8g)
- ~~**About 50 tracks from your own library** with annotations~~ dropped in Phase 0 (DECISIONS §8g: no golden set); a few real songs of your own are enough to judge beats in the editor
- ~~**An iPhone and/or an Android phone** for sync testing~~ dropped (no phone access, no sync canary)
- [ ] **A backup destination** you control: a local or external folder/drive (restic or plain copy); needed by Phase 1
- No lawyer, counsel budget, DMCA agent, payment account or email provider is needed.

## 8. Approval
Reply **"approve kickoff"**, with any changes, to close Phase A and start Phase 0.
Open owner decisions are PRD §12 (OQ-11, OQ-15, OQ-16). None of them block Phase 0 except OQ-16 (which box to benchmark on).
