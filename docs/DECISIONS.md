# SaveClock Studio — Canonical Decisions (source of truth)

Status: **Rev 3.6 — Personal edition, local-only (public-ready)** · Date: 2026-11-26 · Owner: project owner
Every other doc in `docs/` MUST be consistent with this file. If a doc needs to deviate, it raises it in its "Open questions" section instead of silently changing a decision.

**Rescope (Rev 3):** the app is for **one user — the owner** — reachable only over the owner's private **Tailscale** network. It may go public later, so the code keeps the seams needed for that (user-scoped data, adapters, layering), but none of the public-SaaS machinery is built now. The full public-edition design (Rev 2.2: accounts, billing, DMCA, compliance, worker VM) is archived unchanged in `archive/public-edition-rev2.2/` and becomes **Phase P** if/when the owner decides to launch.

Background: `../reports/SaveClock Studio feasibility.md`, `review/` (Rev 2 reviews).
Legend: **[spike]** = confirmed by Phase 0 measurements.

## 1. Product
- **What:** owner uploads a song → app detects beats/downbeats/sections/energy → fetches matching stock clips → auto-generates a beat-synced vertical video draft → owner tweaks, previews, renders, exports.
- **Platform:** responsive web app, mobile-first (used from the owner's phone and laptop over Tailscale). No native app, no PWA in MVP.
- **Users:** single owner. **No sign-up, no login screen, no accounts UI.** Tailscale is the access boundary.
- **Upload limits:** ≤ 100 MB, ≤ 10 min, ≥ 15 s (sanity limits, not abuse limits). Output length ≤ song length.
- **Output:** 9:16, **1080×1920**, 30 fps CFR, H.264 High, AAC-LC 48 kHz, MP4 `+faststart`. No watermark. Durations 15 / 30 / 60 s or a selected segment.
- **Non-goals now:** accounts/auth UI, billing/tiers/quotas/watermark, DMCA/takedown tooling, song fingerprinting, age gate, ToS/Privacy pages, analytics, email, public share links, AI-generated video, PWA, team features, non-commercial/unclear-license models (madmom weights, essentia models, MERT, allin1, SongFormer). Beat This `dbn=True` banned (needs madmom).

## 2. Song / audio & media policy
- **Export flow:** every render produces a **silent master MP4 + cut list**. At export the owner picks **Mode A — With song** (fast remux, no video re-encode) or **Mode B — Silent + beat map** (MP4 + JSON + CSV, separate downloads; add the sound inside TikTok/IG to avoid muting/claims). Switching modes never re-renders.
- **Mode A audio:** source = the validated original upload, trimmed to the segment; stream-copied when AAC, otherwise transcoded to AAC-LC 48 kHz. Never loudness-normalized, no gain/EQ. Loudness measured and a warning shown if far from platform targets.
- **Retention:** owner's files are kept **until the owner deletes the project**. Housekeeping job removes **intermediates** (raw stock downloads, mezzanines, proxies) **7 days** after last use and anything for deleted projects; songs, plans, renders and exports stay until deleted. Disk-usage shown in settings.
- **Stock attribution:** credits (author + link) shown in-app on the export screen with "copy credits"; not burned into video.
- **No lawyer needed for personal use.** Posting to TikTok/IG/YouTube is governed by those platforms' music rules (Mode B is the recommended path for commercial songs). Phase P is designed to stay lawyer-free (§8b).

## 3. Stack & topology
| Layer | Choice |
|---|---|
| Frontend | Next.js 16.x (App Router), TypeScript strict, Tailwind + design tokens |
| API | Python 3.12, FastAPI (0.16x), Pydantic v2, SQLAlchemy 2.x + Alembic |
| Workers | Dramatiq 2.x on Redis. Queues: `analysis`, `fetch`, `render`, `maintenance` (housekeeping). FFmpeg via subprocess with argument lists only. Concurrency set from the Phase 0 contended-load test. |
| Images | One Python codebase, two build targets: `api` (no torch/ffmpeg) and `worker` (torch CPU, ffmpeg, models) |
| DB | PostgreSQL 16 (kept for public-readiness) |
| Redis | **One** instance (`noeviction`), used as broker; any cache keys carry a TTL |
| Storage | **Local disk volume on the VPS** behind a `BlobStore` adapter (filesystem impl now; S3/R2 impl in Phase P). Files served by the API via short-lived signed tokens. |
| FFmpeg | ≥ 8.1; exact build (8.1.x vs 9.0.x) pinned by the Phase 0 spike |
| Beat/downbeat | Beat This! (MIT), octave clamp ~70–180 BPM, owner half/double override |
| Sections/energy | DSP energy segmenter snapped to downbeats (librosa for DSP features only) |
| Vibe → keywords | Claude Haiku (`claude-haiku-5-5`), strict JSON schema + validation + fallback keyword table + per-video cost cap; works offline with the fallback table if no key |
| Clip ranking | SigLIP 2 (Apache-2.0) on low-res sampled frames |
| Shot-cut rejection | PySceneDetect 0.7.x; TransNetV2 (code MIT) once weights terms are checked |
| Stock | **Pexels** (primary, `orientation=portrait`); **Pixabay optional**, enabled only if Pexels fails the G0 stock test |
| **Access** | **Tailscale** (free Personal plan, non-commercial). App served only on the tailnet via `tailscale serve` (HTTPS on `*.ts.net`). **No public Traefik route, no public port.** Single origin: `/api/*` → FastAPI, rest → Next.js. |
| Identity | Single seeded **owner** user row; every project/song/render row still carries `user_id` and every query is scoped by it (seam for Phase P). No sessions/passwords/CSRF in this edition; the API rejects requests that did not come through the Tailscale proxy. |
| Hosting | All services as one Docker Compose stack on the existing VPS (deployed via Dokploy or plain compose), no worker VM. Can also run on the owner's laptop for dev. |
| Observability | Structured JSON logs, per-stage job timing; Sentry optional |
| Backups | Nightly Postgres dump + project files to an off-box location the owner chooses (restic/borg or rclone); restore tested once |

## 4. Rendering rules (non-negotiable)
- **Frame rule:** `f_i = floor((t_i − t0)·fps + 0.5) − lead_frames` (`t_i` absolute beat time, `t0` segment start; `lead_frames` default 0, positive = cut earlier, applied for i > 0). Plans store integer frame indices; shot lengths are index differences, never summed rounded durations. **Minimum shot 0.5 s (15 frames); cuts on beats/downbeats only; every-beat cutting only ≤ 120 BPM, above that every 2 beats.**
- **Clip pipeline:** rank on low-res frames; normalize only top-K (~1.3× cuts) to the mezzanine (1080×1920 scale+crop, 30 fps CFR, yuv420p, SAR 1, common timescale, short GOP) [spike validates K]. Mezzanines live with the project and are housekept per §2.
- **Tolerances:** video duration ±1 frame; audio ±1 AAC frame (21.3 ms); A/V offset ≤ 1 frame.
- **No MoviePy** in production.
- **FFmpeg hardening (cheap, kept):** `-protocol_whitelist file`; forced input demuxer allowlist; no playlist/concat/HLS demuxers on uploaded or downloaded media; ffprobe validation with limits; containers non-root with CPU/mem/time limits. (Stock files and the owner's songs are semi-trusted; full worker isolation returns in Phase P.)

## 5. Tiers
None in this edition. (Phase P: Free/Pro per `archive/public-edition-rev2.2/`.)

## 6. Quality targets (validated in Phase 0) — unchanged from Rev 2.2
- **Beat accuracy (golden core set, untrimmed, `min_beat_time=0`, 70 ms):** beat F1 ≥ 0.85, AMLt ≥ 0.85, CMLt ≥ 0.75, downbeat F1 ≥ 0.75, octave-error ≤ 5%. Hard set reported, not gated.
- **Render fidelity:** every rendered cut within ±1 frame of plan (every render).
- **Musical alignment:** ≥ 90% of planned cuts within 70 ms of an annotated beat (golden set).
- **Internal hard cuts:** 0 detected by admission detectors + ≤ 1% on a 100-segment audit.
- **Speed (4 vCPU, 4 threads) [spike], target / hard limit:** analysis 20 / 40 s (4-min song); draft 120 / 180 s; render 60 / 90 s (30 s 1080p); remux 5 / 10 s. Contended-load per stage measured in Phase 0 (G0-27).
- **Low confidence:** fallback energy grid only when beat confidence < 0.5, with banner + "use detected beats" toggle.
- No repeated clip within one video unless the pool is exhausted.
- **Golden set (personal edition):** the owner's own music library may be used for evaluation (private, never committed); public/CC sets optional.

## 7. Repo shape (created only when implementation is approved)
Monorepo: `apps/web`, `services/api` (two Docker targets), `packages/contracts` (OpenAPI → TS client), `infra/` (compose: postgres, redis, api, worker, web, tailscale sidecar), `docs/`, `plans/`, `eval/` (manifests + scripts; no audio committed).

## 8. Process
- **Phases:** 0 Spike → 1 Walking skeleton → 2 Core pipeline → 3 Editor UX → 4 Personal polish & ops (backups, housekeeping, error handling, perf) → 5 Post-MVP extras (AI hero shots, structure models after license check) → **P Public edition (deferred)**: accounts, billing, compliance, isolation — from the archive; first decide on browser-side processing (songs never leave the user's device), which removes most of the legal work.
- Each phase: plan via `improve` skill → (UI) design approval → small steps → gates green → `ponytail-review` (+ `web-interface-guidelines` for UI) → change summary → owner confirmation before commit. Never push without explicit instruction.
- Gates: format, lint, type-check, tests, build green before commit. Malware config guard before any npm/next/vite/etc. command; pre-push malware scan.
- Any DB schema change announced as "DB CHANGE: … — run this SQL: …" before commit.

## 8c. Rev 3.2 clarifications
- **Services:** `web`, `api`, `worker` (analysis/fetch/render), `worker-maint` (same worker image, `maintenance` queue only), `postgres`, `redis`, `tailscale`.
- **Owner user** is created by the baseline Alembic data migration (fixed UUID, from env `OWNER_DISPLAY_NAME`); no manual step.
- **Beat-accuracy gate statistic:** gate on the **mean** over the golden core set (thresholds as §6); 95% confidence intervals are reported, not gated (n ≈ 30–50 too small for a lower-bound gate).
- **Tailscale serve verification** (path routing to web/api, SSE streaming, large chunked uploads, identity headers) is a Phase 0/1 test task; fallback is a Caddy container on the tailnet IP if `tailscale serve` path handlers fall short.
- **Settings** (superseded in detail by §8d: `GET/PUT /settings` + `POST /housekeeping/run`) shows API-key status and disk usage read-only and offers a housekeeping trigger (ARCHITECTURE owns the paths). The Pixabay on/off switch is stored in `users.settings` (jsonb) via `PUT /settings/stock`. The env var supplies the default. The column ships in the baseline migration and is announced with a DB CHANGE notice at implementation time.

## 8g. Self-tuning, trimmed Phase 0 and the FFmpeg pin (Rev 3.6, owner directive 2026-11-26)
- **Concurrency and threads are auto-detected, and every value can be overridden.** At worker start, `spike`-measured costs plus the machine's own facts set the defaults, and all of them can be overridden in `.env` or Settings:
  - `cpu = os.cpu_count()` (or the container's CPU quota) and `ram_gb` = total memory (or the cgroup limit).
  - `TORCH_THREADS = cpu`, with analysis running one job at a time.
  - `FFMPEG_THREADS = cpu`.
  - `WORKER_HEAVY_CONCURRENCY = max(1, min(cpu // 4, (ram_gb - 2) // 3))`. A render peaks at about 2.2 GB RSS (spike Step 5), hence 3 GB per slot and 2 GB kept for the rest of the stack.
  - `FETCH_CONCURRENCY = 4`.
  - `DEVICE = cpu`. A CUDA path is a later option.
  - The worker logs the chosen values at start, and `GET /settings` shows them read-only.
  - Speed targets (§6) remain targets. The app records per-stage timings on every job, so real speed is visible on the owner's machine instead of being gated by a pre-launch benchmark.
- **Phase 0 trimmed.** There is no golden song set, no clip-rating session, no phone sync canary, and no separate speed run (spike Steps 9, 10, 13 labels, 14 and 16 are dropped):
  - **Beat accuracy** rests on the synthetic self-tests (passed), Beat This's published results, and the owner's judgement on real songs. The editor's beat nudge and the half/double override are the remedy.
  - **G0-1..G0-9, G0-11, G0-13..G0-16, G0-18 and G0-27** become "not measured in Phase 0". QUALITY keeps the metrics for later use.
  - **Clip ranking** is judged by the owner on real videos.
  - **The Pexels availability test (G0-17)** and a SigLIP/PySceneDetect smoke test still run, once the Pexels key is in `secrets/env`.
- **FFmpeg pin: 9.0.x.**
  - The worker image uses the BtbN `release/9.0` GPL static build. libx264 is required, and Fedora's 8.1.3 lacks it. The build is pinned by URL plus sha256 and cached locally, so rebuilds don't depend on the URL staying up.
  - Why 9.0.x:
    - Every row the spike could evaluate passed (G0-20/21/24/25).
    - The same-encoder comparison was bit-identical and 26 % faster.
    - 9.0 carries five CVE fixes that are not listed for any 8.1.x.
  - The `--disable-network` source build is deferred to Phase P. Locally, safety comes from the `-protocol_whitelist file` plus forced-`-f` templates and the magic-byte sniff (all proven in the spike).

- **Resolved open questions (Rev 3.6, from the doc reconciliation):**
  - **OQ-25 (CLI gaps).**
    - `new <song> --vibe "<text>"` stores the text in a new optional `options.vibe` string (≤ 200 chars).
    - Claude Code usually passes keywords up front (`--keywords`, mapped to the existing `options.keywords_override`), choosing them from the vibe text. `keywords set` after the draft triggers the normal replan.
    - `plan` is read-only. `open` is client-side only.
  - **OQ-28.** There is no new "await keywords" state, because keywords supplied up front avoid the wasted fetch.
  - **OQ-27 / SECURITY OQ-6.**
    - The API accepts a state-changing request that has **no** `Origin` header (the CLI).
    - It rejects a request whose `Origin` is present but is not `APP_ORIGIN`.
    - It also rejects `Sec-Fetch-Site: cross-site`.
    - Browsers always send `Origin` on cross-site POSTs, so this blocks other tabs.
  - **SECURITY OQ-1.** Loopback bind plus the Host/Origin checks is enough for a single-user machine, so there is no CLI token.
  - **OQ-26 (single origin through a Next.js rewrite).** The Phase 1 walking skeleton verifies that SSE and a 100 MB upload stream through the rewrite without buffering. If they don't, the API gets its own localhost origin with CORS allowing only `APP_ORIGIN`. **Measured 2026-11-26 (plan 002 Step 7): SSE passed, and the 100 MB upload failed (Next 16.4.6 rewrites cut request bodies at 10 MB; `experimental.proxyClientMaxBodySize` would buffer the body in the web process). So Branch B applies: the browser calls the API directly at `http://localhost:8000`, with CORS allowing only `APP_ORIGIN`, no credentials, and the API's Host/Origin/Sec-Fetch guard unchanged. Next.js server-side code calls the API over the internal network.**
  - **RQ-5.** G2's golden-set numbers become "not measured" (§8g). G0-19 (TransNetV2) stays open, and G0-26 is not applicable.

## 8f. Local-only edition (Rev 3.5, owner directive 2026-11-26) — overrides §3, §8c, §8d where they mention the VPS or Tailscale
- **Where it runs:** on the owner's own capable machine only, as the same Compose stack (or natively for dev). **No VPS, no Tailscale, no Dokploy.** The `tailscale` service is removed from the §8c service list.
- **Access boundary:** every published port binds to **`127.0.0.1` only** (never `0.0.0.0`); the app is opened at `http://localhost:<port>`. Because a local app with no login can still be reached by other websites open in the same browser, the API **must** (a) reject any `Host` header other than `localhost` / `127.0.0.1` (blocks DNS rebinding) and (b) reject state-changing requests whose `Origin` is not the app's own origin. These replace the "request came through Tailscale" check. No auth UI is added.
- **Phone access:** not provided. If wanted later, add Tailscale back as an optional sidecar (ADR-0012 stays as the recipe); nothing else changes.
- **Speed targets (§6)** are measured on the owner's machine (its CPU/RAM/GPU recorded in the spike report) instead of a 4-vCPU VPS. Torch stays CPU by default; a GPU path is a later option, not a requirement.
- **Two ways in, one pipeline (owner choice, option 3):** (1) the **web editor** (screens as in UX-SPEC) and (2) a **`saveclock` command-line tool** that calls the same local HTTP API, so Claude Code can drive the whole flow (`new`, `show --json`, `keywords set`, `plan`, `render`, `export`, `status`). There is no second code path: the CLI is a thin API client. A project skill (`.claude/skills/saveclock/`) tells Claude Code how to use it.
- **Vibe → keywords, no API key needed:** the keyword source order is **explicit keywords** (set by Claude Code through `saveclock keywords set`, or typed in the editor) → Claude Haiku **only if** `ANTHROPIC_API_KEY` is set → the **offline keyword table**. In the normal flow Claude Code reads the analysis summary (`saveclock show <id> --json`: tempo, sections, energy, the owner's vibe text) and writes the keywords. Audio is never sent to Claude; only that summary is visible to it. The app itself never calls `claude`, because the worker runs in a container without the owner's Claude Code login.
- **Backups:** to a folder or disk the owner chooses on the same machine/external drive (restic or plain copy); restore tested once.
- **Phase 0 impact:** spike Step 15 (Tailscale) dropped; Step 16 (speed + contended load) runs on the owner's machine; Step 14 (sync canary) plays the exported file on the owner's phone.

## 8e. Owner design choices (Rev 3.4)
- **Beat pulse:** on by default. It stays capped at 2 Hz, can be turned off in Settings, and is removed under reduced motion.
- **Copy case:** sentence case everywhere, including buttons. This is a deliberate deviation from the Web Interface Guidelines' Title Case suggestion.
- **Preview proxy:** **540×960**. Fall back to 360×640 only if the T-3.4b test over the tailnet stutters on the owner's phone.
- **"Report an issue" button:** none. The owner-only "this cut feels off" flag (QM-102) is enough.

## 8d. Rev 3.3 simplifications (single-user right-sizing)
- **Upload:** a single streamed `POST` upload (≤ 100 MB), no chunked/resumable upload endpoints.
- **File access:** files are served by the API directly to the tailnet client. No signed file tokens, because Tailscale is the boundary. Path containment (SEC) still applies.
- **Edit plans:** keep an integer `version` per plan for undo/history. No `op_id` or per-op idempotency keys. Renders are de-duplicated by plan content hash only.
- **Exports:** folded into `renders` (a nullable `mode_a_key` and its state). No separate `exports` table.
- **Settings:** one `GET/PUT /settings` (key status read-only, Pixabay toggle, disk usage) plus `POST /housekeeping/run`.
- **Eval:** one simple eval script (beat metrics, render-fidelity, timing). No multi-mode harness, rater tooling or VMAF parity in MVP.
- **Browser feasibility (T-0.16):** stays in Phase 0 as **non-gating** (does not affect G0); it informs Phase P only.
- **Process:** per-phase ceremony stays as in §8 but is listed once in ROADMAP rather than repeated as rows in every phase.

## 8b. Lawyer-free rule (owner directive, Rev 3)
**Avoid any design that requires legal counsel.** This edition needs none (single user, own files, Pexels license allows personal and commercial use). If the app goes public, Phase P MUST follow a lawyer-free design:
1. **Songs never leave the user's device.** Beat analysis and the final remux/render run in the browser (WebAssembly/WebGPU/WebCodecs). The server only ever sees the beat map, the edit plan and stock-clip IDs, never audio. That avoids hosting/copying users' music, which is what triggers DMCA safe-harbor duties. Phase 0 adds a feasibility check (T-0.x): can Beat This run in the browser via ONNX Runtime Web, and can WebCodecs render at the target speed on a mid-range phone.
2. **Outputs stay on the user's device.** No hosting of rendered videos, no share links, no gallery.
3. **Collect almost no personal data:** no analytics or tracking cookies; an account at most (email only) or a license key; nothing else stored.
4. **Payments through a merchant of record** (e.g. Paddle or Lemon Squeezy) that handles tax, VAT, invoices and consumer-law refunds. Never take card data directly.
5. **Standard published templates** for terms and the privacy notice; stock attribution per the Pexels/Pixabay guidelines.
6. **No features that need legal judgment:** no user-uploaded content shown to others, no licensed-music catalogue, no AI-generated likenesses of real people, no marketplace.
Any future feature that cannot meet this rule is rejected or redesigned rather than sent to a lawyer.

## 8a. Canonical-owner rules
| Topic | Canonical doc |
|---|---|
| Endpoints, states, data model, storage layout, env vars | ARCHITECTURE.md |
| Metrics, thresholds, G0 checklist (§12), golden set | QUALITY.md |
| Security controls | SECURITY.md |
| Screens, copy, interactions | UX-SPEC.md / DESIGN.md |
| Tasks, phases, traceability | ROADMAP.md (references thresholds, never restates different numbers) |

## 9. Changelog
- **Rev 3.6 (2026-11-26):** §8g auto-detected concurrency/threads with overrides; Phase 0 trimmed (no golden set, labels, canary or speed run); FFmpeg pinned to BtbN 9.0.x GPL static by sha256.
- **Rev 3.5 (2026-11-26):** §8f local-only edition: runs on the owner's machine, no VPS/Tailscale, ports on 127.0.0.1 with Host/Origin checks, keyless keywords by default, ADR-0014. Same day: web editor + `saveclock` CLI for Claude Code, keyword order explicit → Haiku-if-key → offline table.
- **Rev 3.4 (2026-11-08):** §8e owner design choices: pulse on, sentence case, 540×960 preview, no report button.
- **Rev 3.3 (2026-11-08):** §8d single-user simplifications (streamed upload, no signed tokens, no op_id, exports folded into renders, one settings endpoint, simple eval script, T-0.16 non-gating, process listed once).
- **Rev 3.2 (2026-11-08):** §8c — service list incl. worker-maint, owner seeded by migration, mean-based beat gate, Tailscale serve test + Caddy fallback, Settings endpoints.
- **Rev 3.1 (2026-11-08):** §8b lawyer-free rule — Phase P must keep songs and outputs on the user's device, collect minimal data, use a merchant of record and standard templates; browser-feasibility check added to Phase 0.
- **Rev 3 (2026-11-08):** rescoped to a single-user personal edition on Tailscale, kept public-ready. Removed: auth UI/sessions/CSRF, billing, tiers, watermark, quotas, DMCA, fingerprinting, age gate, ToS/Privacy, analytics, email, Turnstile, worker VM, egress proxy, second Redis, R2 (local disk adapter), 72 h forced deletion (owner-controlled retention + 7-day intermediate housekeeping), Pixabay by default. Kept: all accuracy/render/quality rules, both export modes, the editor, FFmpeg basic hardening, user_id scoping. Rev 2.2 archived in `archive/public-edition-rev2.2/` as Phase P.
- Rev 2.2 / 2.1 / 2 / 1: see archive copy.
