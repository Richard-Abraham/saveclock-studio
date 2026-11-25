# SaveClock Studio — Canonical Decisions (source of truth)

Status: **Rev 2.2 — final verification fixes applied (Rev 2 reconciled after cross-check review)** · Date: 2026-11-08 · Owner: project owner
Every other doc in `docs/` MUST be consistent with this file. If a doc needs to deviate, it raises it in its "Open questions" section instead of silently changing a decision.

Background research: `../reports/SaveClock Studio feasibility.md`, `../research_notes/SaveClock Studio feasibility/`. Review inputs: `review/consistency-review.md` (C-xx, D-xx), `review/completeness-review.md` (G-xx), `review/fact-check.md` (F-xx).

Legend: **[spike]** = value to be confirmed by Phase 0 measurements; **[counsel]** = needs lawyer sign-off before public launch.

## 1. Product
- **What:** user uploads a song → app detects beats/downbeats/sections/energy → fetches matching stock clips → auto-generates a beat-synced vertical video draft. User can tweak, preview, render, and export.
- **Platform:** responsive **web app**, mobile-first. No native app, no PWA in MVP.
- **Audience:** public SaaS. **Sign-in required before upload**; no anonymous trial in MVP. Age **16+** self-declared at signup [counsel].
- **Upload limits:** ≤ **100 MB**, ≤ **10 min**, ≥ **15 s**; audio containers/codecs per SECURITY allowlist. Output length ≤ song length.
- **Output (MVP):** 9:16, 1080×1920 (Pro) / 720×1280 (Free, watermarked), 30 fps CFR, H.264 High, AAC-LC 48 kHz, MP4 `+faststart`. Durations 15 / 30 / 60 s or user-selected segment.
- **Non-goals for MVP:** AI-generated video, native mobile/PWA, public share links/feeds, team workspaces, premium stock libraries, structure/mood models with non-commercial or unclear licenses (madmom weights, essentia models, MERT, allin1, SongFormer until cleared). Beat This `dbn=True` is banned (requires madmom).

## 2. Song / audio policy (legal-risk driver)
- **Export flow:** every render produces a **silent master MP4 + cut list**. At export the user picks:
  - **Mode A — With song:** fast remux of the original song onto the silent master (seconds, no re-encode of video); private download via short-lived signed URL; repeat downloads allowed within retention.
  - **Mode B — Silent + beat map:** silent MP4 + cut list as **separate downloads** (MP4, JSON, CSV). ZIP may come later.
  - Switching modes never re-renders.
- **No public share links, no gallery, no third-party viewing.**
- **Fingerprinting** (AudD or ACRCloud) on every upload: a match **warns and nudges to Mode B**, shows only "this may be a released track" (never the matched title), and **does not block** in MVP [counsel decides at launch gate].
- Rights warranty checkbox before upload. ToS: warranty + indemnity + DMCA policy + repeat-infringer policy. DMCA designated agent registered before public launch [counsel].
- **Retention — one clock:** all project media (song, mezzanines, intermediates, silent master, mode-A export) is deleted **72 h after upload-complete**. No extension without counsel. Kept after expiry: project metadata, analysis/beat map (no audio), edit plan, and the song's SHA-256 so the user can **re-attach the same file** to the project (hash must match) — otherwise new project.
- Audit-log and DMCA-record retention periods [counsel] (proposal: 12 months audit, 3 years DMCA records).
- **Attribution** to Pexels/Pixabay shown **in-app** (export screen, credits sheet, "copy credits" for captions); not burned into the video, pending Pexels' reply (T-0.5).
- **Analytics:** first-party, cookie-free, aggregate event counts only in MVP → no consent banner [counsel confirms].

## 3. Stack & topology
| Layer | Choice |
|---|---|
| Frontend | Next.js 16.x (App Router), TypeScript strict, Tailwind + design tokens |
| API | Python 3.12, FastAPI (current 0.16x), Pydantic v2, SQLAlchemy 2.x + Alembic. Exact pins at lockfile time. |
| Workers | Dramatiq 2.x on Redis. Queues: **`analysis`, `fetch`, `render`, `maintenance`** (retention sweeper, Stripe/webhook follow-ups, cleanup). FFmpeg via subprocess with argument lists only. |
| Images | **One Python codebase, two build targets**: `api` (no torch, no ffmpeg) and `worker` (torch CPU, ffmpeg, models). |
| DB | PostgreSQL 16 |
| Redis | **Two instances**: broker (`noeviction`) and cache/rate-limit (`allkeys-lru`) |
| Object storage | Cloudflare R2, private buckets, presigned URLs only |
| FFmpeg | **≥ 8.1; exact build (8.1.x vs 9.0.x) pinned by the Phase 0 spike** [spike] |
| Beat/downbeat | Beat This! (MIT), octave clamp ~70–180 BPM, user half/double override |
| Sections/energy | DSP energy segmenter snapped to downbeats (librosa allowed for DSP features only) |
| Vibe → keywords | Claude Haiku (`claude-haiku-5-5`), strict JSON schema + validation + fallback keyword table + per-video cost cap |
| Clip ranking | SigLIP 2 (Apache-2.0) on low-res sampled frames |
| Shot-cut rejection | PySceneDetect 0.7.x in MVP; TransNetV2 (code MIT) adopted once weights terms are checked (T-0.6) |
| Stock | Pexels (primary, `orientation=portrait`), Pixabay (secondary), fetched per job |
| Auth | FastAPI-owned: email+password (argon2id) with email verification, Google OAuth, `__Host-` httpOnly Secure SameSite=Lax session cookie, CSRF token on state-changing requests. **Minimal real users + sessions from Phase 1**; verification, OAuth, tiers, quotas in Phase 4. |
| Email | Transactional email provider chosen in Phase 1 (candidates: Postmark, Resend, SES); dev uses a local mailbox (Mailpit) |
| Billing | Stripe (Checkout, Portal, webhooks), Phase 5 |
| **Origin** | **Single origin** `app.<domain>`: Traefik path routing, `/api/*` → FastAPI, rest → Next.js. No CORS. SSE on same origin. |
| **Hosting** | Web + API + Postgres + Redis on the existing Dokploy/Traefik VPS. **Analysis/fetch/render workers on a dedicated worker VM**: no inbound ports, outbound only via an allow-listed egress proxy (Pexels, Pixabay, R2, LLM, fingerprint vendor), non-root, read-only rootfs, cgroup CPU/mem/time limits. Serverless GPU only if profiling justifies. |
| Observability | Structured JSON logs, Sentry, metrics, per-stage job timing |

## 4. Rendering rules (non-negotiable)
- **Frame rule:** cut frame `f_i = floor((t_i − t0) × fps + 0.5)`, where `t_i` is the absolute beat time on the song timeline and `t0` is the selected segment start. The edit plan stores integer frame indices; shot lengths are differences of indices, never summed rounded durations. Schema includes `lead_frames` (default **0** in MVP; early-cut bias only after an A/B test). **Sign convention (Rev 2.2, V-05):** `f_i = floor((t_i − t0)·fps + 0.5) − lead_frames`, so a **positive `lead_frames` = the cut happens EARLIER than the beat** (applied for `i > 0`, after rounding). **Minimum shot length = 0.5 s (15 frames) everywhere; cut points are beat or downbeat only (no half-beats in MVP; no "Frantic" density stop).**
- **Clip pipeline:** rank candidates on cheap low-res frames; normalize only the top-K (~1.3× number of cuts) to the mezzanine (1080×1920 scale+crop, 30 fps CFR, yuv420p, SAR 1, common timescale, short GOP) [spike validates K]. **Mezzanines are per-project** (live in the project prefix, die with the 72 h clock); no shared cross-user cache unless Pexels/Pixabay terms permit.
- **Audio:** the song is never loudness-normalized or re-processed; trimmed once for the selected segment and muxed. Loudness is measured and a warning shown if far from platform targets.
- **Tolerances:** video duration ±1 frame; audio duration ±1 AAC frame (21.3 ms); A/V offset ≤ 1 frame.
- **No MoviePy** in production.
- **FFmpeg hardening:** `-protocol_whitelist file` only; input demuxer forced via an explicit format allowlist (`-f`); playlist/concat/HLS demuxers never applied to untrusted input; `ffprobe` validation with duration/size/stream limits; non-root, sandboxed worker VM.

## 5. Tiers
- **Free:** stock-only, 720p, watermark, daily render cap (value set in Phase 5; placeholder 3/day).
- **Pro:** 1080p, no watermark, monthly allowance, priority queue. Price $9.99–14.99/month, decided in Phase 5 (A/B). Pricing page shows "Coming soon" until then.
- **Credits:** reserved for AI hero shots; not in MVP.

## 6. Quality targets (initial — validated in Phase 0)
- **Beat accuracy (golden core set, untrimmed, `min_beat_time=0`, 70 ms window):** beat F1 ≥ 0.85 **and** AMLt ≥ 0.85 **and** CMLt ≥ 0.75 **and** downbeat F1 ≥ 0.75 **and** octave-error rate ≤ 5%. Report the hard set separately (no gate in MVP).
- **Render fidelity:** every rendered cut within ±1 frame of its planned frame index (automated, every render).
- **Musical alignment:** ≥ 90% of planned cuts within 70 ms of an annotated beat on the golden set.
- **Internal hard cuts:** 0 detected by the admission detectors, and ≤ 1% of used segments on a 100-segment human audit.
- **Speed (4-vCPU worker, exclusive use of the box) [spike]:** each metric has a **target (Should)** and a **hard NO-GO limit (Must)** at G0: analysis p95 target ≤ 20 s, **hard ≤ 40 s** (4-min song); **draft** (upload-complete → draft ready, incl. analysis, fetch, rank, normalize) target ≤ 120 s, **hard ≤ 180 s**; **render** (edit plan → silent master, 30 s 1080p) target ≤ 60 s, **hard ≤ 90 s**; Mode A remux target ≤ 5 s, **hard ≤ 10 s**. Numbers are for an exclusive 4 vCPU; contended-load p95 per stage and a worker-concurrency recommendation are measured in ROADMAP T-0.11 (QUALITY G0-27).
- **Low confidence:** fallback energy grid auto-applied only when beat confidence < 0.5, with visible banner and "use detected beats" toggle; 4-step fallback ladder per QUALITY.md. Beat This `small` ensemble is eval-only.
- No repeated clip within one video unless the candidate pool is exhausted.

## 7. Repo shape (proposed — created only when implementation is approved)
Monorepo: `apps/web` (Next.js), `services/api` (FastAPI + domain + worker entrypoints, two Docker targets), `packages/contracts` (OpenAPI → generated TS client), `infra/` (Dockerfiles, compose for local dev incl. Postgres, 2× Redis, MinIO or R2 dev bucket, Mailpit), `docs/`, `plans/`, `eval/` (golden-set manifests + scripts; no copyrighted audio committed).

## 8. Process
- Phases: 0 Spike → 1 Walking skeleton (incl. minimal auth) → 2 Core pipeline → 3 Editor UX → 4 Accounts/limits/compliance → 5 Paid launch → 6 Post-launch. Each phase: plan via `improve` skill → (UI) design approval → implement in small steps → gates green → `ponytail-review` (+ `web-interface-guidelines` for UI) → change summary → owner confirmation before commit. Never push without explicit instruction.
- Gates: format, lint, type-check, tests, build — green before commit. Malware config guard before any npm/next/vite/etc. command; pre-push malware scan.
- Any DB schema change announced as "DB CHANGE: … — run this SQL: …" before commit.

## 8a. Canonical-owner rules (Rev 2.1)
When docs disagree, this table decides which doc wins for that topic (after DECISIONS itself):
| Topic | Canonical doc |
|---|---|
| Endpoint paths, job/project state names, data model, R2 bucket layout (4 buckets), env vars | ARCHITECTURE.md (§7 endpoints, §4 states) |
| Metric definitions, numeric thresholds for G0/G2 gates, golden set | QUALITY.md (§12 is the G0 checklist) |
| Security controls, isolation model | SECURITY.md |
| Screens, copy, interactions | UX-SPEC.md / DESIGN.md |
| Tasks, phases, gates' task ownership, traceability | ROADMAP.md (gates *reference* QUALITY/SECURITY thresholds, never restate different numbers) |

Rev 2.1 clarifications:
- **Stock availability (G0):** ≥ 20 portrait clips ≥ 1080p per keyword for ≥ 80% of 50 vibe keywords (QUALITY §12 G0-17).
- **Editor ops:** the edit-plan PATCH ops MUST include clip **reorder (move earlier/later)** and **cut nudge (±1 beat / ±1 bar)** — they are the WCAG 2.5.7 non-drag alternatives in UX-SPEC.
- **Mode A audio:** source = the validated original upload, trimmed to the segment; stream-copied when it is AAC, otherwise transcoded to AAC-LC 48 kHz. No gain, loudness, EQ or other processing.
- **Re-attach** after expiry = a new upload-complete, so a new 72 h clock starts [counsel confirms].
- **"Notify me" on pricing page:** cut from MVP — static "Coming soon" text only, no email capture.
- **Benchmarks** run on a 4-vCPU worker with 4 threads unless a metric says otherwise.
- The golden **hard set stays ungated** in MVP (reported only).

## 9. Changelog
- **Rev 2.2 (2026-11-08):** final-verification fixes. (1) V-01: "Frantic" density stop removed everywhere (4 stops; `set_density` −2..+1); minimum shot length 0.5 s (15 frames) in every doc (QUALITY's 0.3 s changed); cuts on beat/downbeat only. (2) V-02: contended-load measurement (analysis + fetch + render concurrently on one 4-vCPU VM, p95 per stage, worker-concurrency recommendation) added to ROADMAP T-0.11 and QUALITY §12 (G0-27). (3) V-03: speed gates now have a hard limit and a target (analysis 40/20 s, draft 180/120 s, render 90/60 s, remux 10/5 s); §6 Speed line updated. (4) V-05: `lead_frames` sign — positive = cut EARLIER than the beat; ARCHITECTURE, QUALITY and §4 aligned. (5) V-06 and shortcuts: signed download URL TTL = 10 min everywhere (UX-SPEC fixed); `Alt+←/→` replaced by `Shift+[` / `Shift+]` for move clip (`[` / `]` = previous/next cut). Other MINOR doc-consistency fixes are listed in `review/final-fixes-log.md` (Rev 2.2).
- **Rev 2.1 (2026-11-08):** canonical-owner table; stock G0 threshold; reorder/nudge ops restored; Mode A audio source; re-attach clock; "Notify me" cut; benchmark threads.
- **Rev 2 (2026-11-08):** applied review recommendations D-01–D-11, D-14, D-17, D-18, D-20, D-23–D-25, D-31, D-36 and owner choices (dedicated worker VM; mode chosen after render; sign-in first, 16+). Fixed frame formula (C-01), split speed targets (C-02), added beat co-gates (QUAL D1), corrected versions (F-12, F-43/44), FFmpeg ≥ 8.1, single origin, 4th queue, two Redis, two images, per-project mezzanines, one retention clock, auth from Phase 1, email provider.
- Rev 1 (2026-11-08): initial.
